"""Characterize the malformed DOIs in a pubmed2db export, measure what repairing them would produce, and
write the table of repairs that Babel applies.

PubMed publishes ``ArticleId[@IdType='doi']`` as the publisher supplied it, so several hundred of the ~37M
DOIs in an export contain a space or other text. ``write_compendium()`` fails the build on a CURIE that
``curie_format_problem()`` rejects, so Babel has to either repair or skip each one
(https://github.com/NCATSTranslator/Babel/issues/1112). This script is the evidence for which: it streams
*every* record of the export through the production ``_read_shard_records()`` with no repairs applied, gives
each rejected ``doi:`` a shape, generates the candidate DOIs each plausible repair strategy would produce,
asks doi.org whether each candidate is a registered DOI, and asks Crossref whether each repair it would make
names the same article as the PubMed record.

Shapes (the first that fits; ``SHAPES`` has the exact tests):

- ``no_whitespace`` -- rejected for a ``|`` or a control character rather than whitespace.
- ``several_dois`` -- two or more complete DOIs separated by whitespace.
- ``leading_text`` -- text, then one complete DOI as the last token (``EDN: XVYYSN 10.7868/...``).
- ``soft_line_break`` -- an ``=`` followed by whitespace: a quoted-printable line break left in the value.
- ``punctuation_gap`` -- every run of whitespace touches ``.``, ``/``, ``-`` or ``_``, and nothing after the
  first whitespace looks like prose (``10.1126/science. 1134405``).
- ``trailing_text`` -- one complete DOI as the first token, ending in ``,``, ``;`` or ``.`` or followed by
  prose (``10.1101/gr.214102. Article published online before print in January 2002``).
- ``word_gap`` -- anything else starting ``10.``: whitespace between two letters or digits
  (``10.3305/nutr hosp.v28in06.7011``).
- ``other`` -- none of the above.

Strategies: ``join`` (delete the characters ``curie_format_problem()`` objects to), ``first_token``,
``last_token`` and ``each_token`` (keep whitespace-separated tokens that are complete DOIs, minus trailing
``,;.``), ``soft_line_break`` (delete ``=`` plus the whitespace after it), and, for a ``word_gap``,
``separators`` (turn each whitespace run between two letters or digits into one of ``GAP_SEPARATORS``:
``10.3129/can j ophthalmol.i07-089`` is ``10.3129/can.j.ophthalmol.i07-089``). A strategy only proposes a
candidate that ``DOI_RE`` accepts. So that the hit rates have something to be compared with, the script also
looks up a sample of well-formed DOIs from the same export (``baseline``).

**The repairs table.** ``REPAIR_STRATEGY`` names the one strategy trusted for each shape, and a malformed
DOI is repaired to that strategy's candidates when doi.org says a candidate is registered (for a strategy in
``ONE_OF_STRATEGIES``, exactly one of its candidates), Crossref doesn't say it belongs to another article
(``crossref_title_match()``; a DOI Crossref doesn't hold is registered with another agency, and passes), and
no PMID
in the export already carries it well-formed except ones that carry the malformed DOI too (repairing would
then take the DOI away from that PMID's clique, since a shared DOI stays on the lowest PMID). The table is
keyed by the malformed DOI alone, so the build repairs it on every PMID that carries it, and the check is
made once per malformed DOI, against all of them; when several PMIDs carry one, the repair is a DOI they
share, which the build keeps on the lowest of them like any other (two such in 2026nov08, e.g.
PMID:25476091 and PMID:25591444). ``first_token`` is trusted for no shape, although its
candidates are often registered: a DOI cut off at a space is frequently a *different* registered DOI
(``10.1126/science. 1134405`` gives ``10.1126/science``, the journal's own DOI). Crossref is only ever
asked about a DOI the malformed value spells, never searched by title for one: a title search finds
same-titled articles in other issues (``At the crossroads--neonatal detection of developmental dysplasia of
the hip``, PMID:10755418, comes back as two other JBJS articles).

Outputs:

- ``input_data/pubmed_doi_repairs.tsv`` -- the table the build reads (``PUBMED_DOI_REPAIRS`` in
  ``src/createcompendia/publications.py``). Only written when doi.org answered for every candidate and
  Crossref for every repair.
- ``counts.json`` (beside this script) -- per shape: how many, how many are repaired or vetoed by Crossref,
  and per strategy how many candidates it proposes and how many of those doi.org knows; Crossref's verdicts;
  and the baseline.
- ``malformed_dois.csv`` (beside this script) -- one row per malformed DOI and candidate: the strategy,
  whether doi.org knows the candidate, whether the same record already carries it, which PMIDs carry it
  without carrying the malformed DOI, for each repair Crossref's title and verdict, and whether it went into
  the repairs table.

Regenerate with (``--export-dir`` defaults to the download of the export pinned in config.yaml):

    uv run python docs/sources/PubMed/dois/characterize_dois.py [--export-dir DIR] [--workers N] [--offline]

It makes two parallel passes over the export (about a minute on 8 cores), then about 1,500 requests to
doi.org's handle API and 450 to Crossref's REST API, a second apart (about 40 minutes from cold). Answers are
cached in ``data/pubmed-dois/doi_org_cache.json`` and ``crossref_cache.json``, so a re-run only asks about
what it has no answer for; delete a cache to re-ask. ``--offline`` uses only the caches, so it writes the
repairs table only if they already answer for everything. See "Malformed DOIs" in
docs/sources/PubMed/README.md for what the counts mean for Babel.
"""

import argparse
import csv
import difflib
import html
import json
import os
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path
from urllib.parse import quote

import requests

from src.createcompendia.publications import (
    PUBMED_DOI_REPAIRS,
    _read_shard_records,
    expected_shard_counts,
    load_doi_repairs,
)
from src.prefixes import DOI
from src.util import MALFORMED_CURIE_CHARS_RE, curie_format_problem, get_config, get_repo_root

OUTPUT_DIR = Path(__file__).parent
CACHE_FILE = get_repo_root() / "data/pubmed-dois/doi_org_cache.json"
CROSSREF_CACHE_FILE = get_repo_root() / "data/pubmed-dois/crossref_cache.json"
# https://www.doi.org/the-identifier/resources/factsheets/doi-resolution-documentation#5-proxy-server-rest-api
DOI_ORG_HANDLE_API = "https://doi.org/api/handles/"
# https://api.crossref.org/swagger-ui/index.html#/Works/get_works__doi_ -- 404 for a DOI Crossref doesn't hold.
CROSSREF_WORKS_API = "https://api.crossref.org/works/"
SECONDS_BETWEEN_LOOKUPS = 1.0
# One well-formed DOI is sampled from each record whose PMID is a multiple of this (~200 records).
BASELINE_PMID_MODULUS = 200003
EXAMPLES_PER_SHAPE = 8

# A complete DOI: the directory indicator 10, a 4-9 digit registrant code, and a non-empty suffix with no
# whitespace. Crossref's recommended pattern for modern DOIs, minus its restriction on suffix characters.
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
# Words that mark the text around a DOI as prose rather than a piece of the DOI.
PROSE_RE = re.compile(r"\s[^\W\d_]{3,}(\s|$)")
TRAILING_PUNCTUATION = ",;."
# The one strategy whose registered candidates go into the repairs table, per shape. A candidate made by
# deleting characters from the whole value can only be registered if the value really was that DOI with
# stray characters in it, so ``join`` is trusted wherever a shape has nothing more specific. ``first_token``
# is trusted nowhere (see the module docstring), and ``other`` has no candidates at all.
REPAIR_STRATEGY = {
    "no_whitespace": "join",
    "punctuation_gap": "join",
    "word_gap": "separators",
    "trailing_text": "join",
    "soft_line_break": "join",
    "several_dois": "each_token",
    "leading_text": "last_token",
}
# Strategies whose candidates are alternative spellings of one DOI rather than several DOIs: a repair is made
# only when exactly one of them is registered (case-insensitively), since two registered spellings are two
# different DOIs and nothing here says which one the publisher meant.
ONE_OF_STRATEGIES = {"separators"}
# What a whitespace run between two letters or digits may have stood for. Canadian Journal of Ophthalmology
# DOIs lost dots (``10.3129/can j ophthalmol.i07-089`` is ``can.j.ophthalmol.i07-089``), Journal of
# Neurosurgery's underscores (``supplement 3.0334`` is ``supplement_3.0334``).
GAP_SEPARATORS = ("", ".", "_", "-")
# A whitespace run with a letter or digit on both sides.
WORD_GAP_RE = re.compile(r"(?<=[^\W_])\s+(?=[^\W_])")
# When Crossref's title for a repaired DOI agrees with the PubMed record's, after both are casefolded and
# stripped to letters and digits: when one contains the other, or their difflib ratio (0-1) is at least this.
# Containment is the common case: PubMed prefixes a Science article with its section ("Neuroscience. The
# brain's dark energy.", PMID:17124311), appends a quiz's diagnosis ("Radiology quiz case 2. Acute calcific
# tendinitis...", PMID:22710516) and drops subtitles ("Panic Disorder in Primary Care.", PMID:30995952). Over
# 2026nov08 those were the only five repairs a ratio alone would have vetoed, and all five are the right
# article. A disagreeing title vetoes the repair; see crossref_title_match().
TITLE_MATCH_MIN_RATIO = 0.8
# The shortest normalized title that counts as contained in another: shorter ones ("Editorial", "Reply")
# could be contained in almost anything.
MIN_CONTAINED_TITLE_CHARS = 15


def is_doi(token):
    return bool(DOI_RE.match(token))


def _gaps_touch_punctuation(value):
    return all(
        value[m.start() - 1] in "./-_" or value[m.end()] in "./-_"
        for m in re.finditer(r"\s+", value)
        if m.start() > 0 and m.end() < len(value)
    )


# (shape, test on the DOI without its ``doi:`` prefix and on its whitespace-separated tokens), in order.
SHAPES = [
    ("no_whitespace", lambda value, tokens: len(tokens) == 1 and value == tokens[0]),
    ("several_dois", lambda value, tokens: sum(is_doi(t.rstrip(TRAILING_PUNCTUATION)) for t in tokens) >= 2),
    ("leading_text", lambda value, tokens: not tokens[0].startswith("10.") and is_doi(tokens[-1])),
    ("soft_line_break", lambda value, tokens: re.search(r"=\s", value) is not None),
    ("punctuation_gap", lambda value, tokens: _gaps_touch_punctuation(value) and not PROSE_RE.search(value)),
    (
        "trailing_text",
        lambda value, tokens: (
            is_doi(tokens[0].rstrip(TRAILING_PUNCTUATION))
            and (tokens[0][-1] in TRAILING_PUNCTUATION or PROSE_RE.search(value) is not None)
        ),
    ),
    ("word_gap", lambda value, tokens: value.startswith("10.")),
]


# Every shape shape_of() can return, in the order it tests them; "other" is what's left.
SHAPE_ORDER = [shape for shape, _ in SHAPES] + ["other"]


def shape_of(value):
    """The shape (see the module docstring) of one malformed DOI, given without its ``doi:`` prefix."""
    tokens = value.split()
    if not tokens:
        return "other"
    for shape, test in SHAPES:
        if test(value, tokens):
            return shape
    return "other"


def candidates(value):
    """``{strategy: [candidate DOIs]}`` for one malformed DOI: what each repair strategy would make of it."""
    tokens = [t.rstrip(TRAILING_PUNCTUATION) for t in value.split()]
    proposals = {
        "join": [MALFORMED_CURIE_CHARS_RE.sub("", value)],
        "first_token": tokens[:1],
        "last_token": tokens[-1:] if len(tokens) > 1 else [],
        "each_token": [t for t in tokens if is_doi(t)] if sum(map(is_doi, tokens)) >= 2 else [],
        "soft_line_break": [re.sub(r"=\s+", "", value)] if re.search(r"=\s", value) else [],
        # Only for word gaps: elsewhere a gap touches punctuation, and deleting it is all there is to try.
        "separators": (
            list(dict.fromkeys(MALFORMED_CURIE_CHARS_RE.sub("", WORD_GAP_RE.sub(sep, value)) for sep in GAP_SEPARATORS))
            if shape_of(value) == "word_gap" and WORD_GAP_RE.search(value)
            else []
        ),
    }
    return {strategy: [c for c in found if is_doi(c)] for strategy, found in proposals.items()}


def choose_repairs(malformed, proposals, registered, carriers):
    """
    The repairs table, ``{malformed doi CURIE: [repaired doi CURIEs]}``, by the rule in the module docstring.

    :param malformed: ``[(pmid, malformed doi CURIE, ...)]``, every malformed DOI on every record.
    :param proposals: ``{malformed doi CURIE: candidates()}``.
    :param registered: ``{candidate DOI: "yes" | "no" | ""}``, from doi.org.
    :param carriers: ``{lower-cased doi CURIE: {PMIDs carrying it well-formed}}``.
    """
    pmids_with = malformed_carriers(malformed)
    repairs = {}
    for curie in sorted(pmids_with):
        strategy = REPAIR_STRATEGY.get(shape_of(curie.split(":", 1)[1]))
        found = [candidate for candidate in proposals[curie].get(strategy, []) if registered[candidate] == "yes"]
        if strategy in ONE_OF_STRATEGIES and len({candidate.lower() for candidate in found}) != 1:
            continue
        verified = [
            f"{DOI}:{candidate}" for candidate in found if not others_carrying(candidate, pmids_with[curie], carriers)
        ]
        if verified:
            repairs[curie] = list(dict.fromkeys(verified))
    return repairs


def normalized_title(title):
    """A title casefolded and stripped to letters and digits, with Crossref's HTML markup and entities removed."""
    return re.sub(r"[\W_]+", "", html.unescape(re.sub(r"<[^>]+>", "", title)).casefold())


def crossref_title_match(pubmed_titles, crossref_record):
    """
    Whether Crossref's record for a repaired DOI describes the article the PubMed records name (one title
    contains the other, or they are at least ``TITLE_MATCH_MIN_RATIO`` alike):
    ``(verdict, best ratio)``, where the verdict is ``match``, ``mismatch``, ``translated`` (no PubMed
    title matches, but one is ``[bracketed]``: PubMed's English translation of a title Crossref may hold in
    the original language, so no evidence either way), ``no_title`` or ``not_in_crossref``.
    """
    if not crossref_record["found"]:
        return "not_in_crossref", None
    crossref_titles = [normalized_title(t) for t in crossref_record["titles"] if normalized_title(t)]
    if not crossref_titles:
        return "no_title", None
    pairs = [(normalized_title(p), c) for p in pubmed_titles for c in crossref_titles]
    ratio = max(difflib.SequenceMatcher(None, p, c).ratio() for p, c in pairs)
    contained = any(
        min(len(p), len(c)) >= MIN_CONTAINED_TITLE_CHARS and (p in c or c in p) for p, c in pairs if p and c
    )
    if contained or ratio >= TITLE_MATCH_MIN_RATIO:
        return "match", ratio
    if any(p.strip().startswith("[") for p in pubmed_titles):
        return "translated", ratio
    return "mismatch", ratio


def apply_crossref_veto(repairs, pmids_with, titles, crossref):
    """
    ``repairs`` without the repaired DOIs Crossref says belong to another article, and
    ``{(malformed, repaired): (verdict, ratio)}`` for every repaired DOI checked.

    :param pmids_with: ``malformed_carriers()``.
    :param titles: ``{pmid: article_title}`` for every PMID carrying a malformed DOI.
    :param crossref: ``{repaired doi (no prefix): Crossref.lookup()}``.
    """
    kept = {}
    verdicts = {}
    for curie, repaired in repairs.items():
        carrier_titles = [titles[pmid] for pmid in sorted(pmids_with[curie]) if titles[pmid]]
        for doi in repaired:
            record = crossref[doi.split(":", 1)[1]]
            verdicts[(curie, doi)] = crossref_title_match(carrier_titles, record) if carrier_titles else ("", None)
        survivors = [doi for doi in repaired if verdicts[(curie, doi)][0] != "mismatch"]
        if survivors:
            kept[curie] = survivors
    return kept, verdicts


def malformed_carriers(malformed):
    """``{malformed doi CURIE: {PMIDs carrying it}}``."""
    pmids_with = defaultdict(set)
    for pmid, curie, *_ in malformed:
        pmids_with[curie].add(pmid)
    return pmids_with


def others_carrying(candidate, pmids_with_malformed, carriers):
    """The PMIDs carrying ``candidate`` well-formed, other than the ones carrying the malformed DOI it repairs:
    a repair would take the DOI away from them, since the build applies it to every carrier of the malformed
    DOI and keeps a shared DOI only on the lowest PMID."""
    return sorted(carriers.get(f"{DOI}:{candidate}".lower(), set()) - pmids_with_malformed)


def find_malformed(shard_path):
    """Pass 1 over one shard: ``(record count, [(pmid, malformed doi CURIE, the record's other identifiers,
    its title)])``."""
    count = 0
    rows = []
    for _, pmid, title, others, malformed in _read_shard_records(shard_path):
        count += 1
        for curie in malformed:
            rows.append((pmid, curie, others, title))
    return count, rows


def find_carriers(args):
    """Pass 2 over one shard: which PMIDs carry, well-formed, a DOI in ``wanted`` (lower-cased CURIEs), and a
    sample of well-formed DOIs for the baseline. Returns ``([(lower-cased doi, pmid)], [baseline DOIs])``."""
    shard_path, wanted = args
    carriers = []
    baseline = []
    for _, pmid, _, others, _ in _read_shard_records(shard_path):
        dois = [o for o in others if o.startswith(DOI + ":")]
        for doi in dois:
            if doi.lower() in wanted:
                carriers.append((doi.lower(), pmid))
        if dois and int(pmid.split(":")[1]) % BASELINE_PMID_MODULUS == 0:
            baseline.append(dois[0].split(":", 1)[1])
    return carriers, baseline


class DoiOrg:
    """Asks doi.org's handle API whether a DOI is registered, politely and with an on-disk cache."""

    def __init__(self, offline):
        self.offline = offline
        self.cache = json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "babel-doi-characterization"

    def registered(self, doi):
        """``"yes"``, ``"no"``, or ``""`` when offline or doi.org gave neither answer."""
        if doi not in self.cache:
            if self.offline:
                return ""
            time.sleep(SECONDS_BETWEEN_LOOKUPS)
            try:
                response = self.session.get(DOI_ORG_HANDLE_API + quote(doi, safe="/"), timeout=60)
                # responseCode 1 is "success", 100 "handle not found" (served with HTTP 404).
                code = response.json().get("responseCode")
            except (requests.RequestException, ValueError):
                code = None
            if code not in (1, 100):
                return ""
            self.cache[doi] = "yes" if code == 1 else "no"
            if len(self.cache) % 50 == 0:
                self.save()
        return self.cache[doi]

    def save(self):
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(self.cache, indent=1, sort_keys=True))


class Crossref:
    """Asks Crossref's REST API for the titles of a DOI's work, politely and with an on-disk cache."""

    def __init__(self, offline):
        self.offline = offline
        self.cache = json.loads(CROSSREF_CACHE_FILE.read_text()) if CROSSREF_CACHE_FILE.exists() else {}
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "babel-doi-characterization"

    def lookup(self, doi):
        """``{"found": bool, "titles": [...]}``, or None when offline or Crossref gave neither answer. Not found
        means Crossref doesn't hold the DOI: it may be registered with another agency (DataCite, mEDRA, ...)."""
        if doi not in self.cache:
            if self.offline:
                return None
            time.sleep(SECONDS_BETWEEN_LOOKUPS)
            try:
                response = self.session.get(CROSSREF_WORKS_API + quote(doi, safe="/"), timeout=60)
                if response.status_code == 404:
                    self.cache[doi] = {"found": False, "titles": []}
                elif response.status_code == 200:
                    message = response.json()["message"]
                    titles = list(message.get("title") or []) + list(message.get("original-title") or [])
                    self.cache[doi] = {"found": True, "titles": titles}
                else:
                    return None
            except (requests.RequestException, ValueError, KeyError):
                return None
            if len(self.cache) % 50 == 0:
                self.save()
        return self.cache[doi]

    def save(self):
        CROSSREF_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CROSSREF_CACHE_FILE.write_text(json.dumps(self.cache, indent=1, sort_keys=True))


def main():
    config = get_config()
    default_export_dir = os.path.join(config["download_directory"], "PubMed2DB", config["pubmed2db_version"])
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--export-dir", default=default_export_dir, help="A downloaded pubmed2db export.")
    parser.add_argument("--workers", type=int, default=os.cpu_count())
    parser.add_argument("--offline", action="store_true", help="Don't ask doi.org; use only cached answers.")
    args = parser.parse_args()

    shards = list(expected_shard_counts(args.export_dir))
    shard_paths = [os.path.join(args.export_dir, shard) for shard in shards]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        found = list(pool.map(find_malformed, shard_paths))
    records = sum(count for count, _ in found)
    malformed = sorted((row for _, rows in found for row in rows), key=lambda row: (int(row[0].split(":")[1]), row[1]))
    non_dois = [(pmid, curie) for pmid, curie, *_ in malformed if not curie.startswith(DOI + ":")]
    malformed = [row for row in malformed if row[1].startswith(DOI + ":")]

    proposals = {curie: candidates(curie.split(":", 1)[1]) for _, curie, *_ in malformed}
    wanted = frozenset(
        f"{DOI}:{candidate}".lower() for found in proposals.values() for cs in found.values() for candidate in cs
    )
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        second = list(pool.map(find_carriers, [(path, wanted) for path in shard_paths]))
    carriers = defaultdict(set)
    for shard_carriers, _ in second:
        for doi, pmid in shard_carriers:
            carriers[doi].add(pmid)
    baseline = sorted(doi for _, shard_baseline in second for doi in shard_baseline)

    doi_org = DoiOrg(args.offline)
    registered = {
        candidate: doi_org.registered(candidate)
        for found in proposals.values()
        for cs in found.values()
        for candidate in cs
    }
    baseline_answers = Counter(doi_org.registered(doi) or "unknown" for doi in baseline)
    doi_org.save()

    pmids_with = malformed_carriers(malformed)
    titles = {pmid: title for pmid, _, _, title in malformed}
    unvetoed = choose_repairs(malformed, proposals, registered, carriers)
    crossref_client = Crossref(args.offline)
    crossref = {
        doi.split(":", 1)[1]: crossref_client.lookup(doi.split(":", 1)[1])
        for repaired in unvetoed.values()
        for doi in repaired
    }
    crossref_client.save()
    crossref_unanswered = sorted(doi for doi, record in crossref.items() if record is None)
    if crossref_unanswered:
        repairs, verdicts = {}, {}
    else:
        repairs, verdicts = apply_crossref_veto(unvetoed, pmids_with, titles, crossref)
    vetoed = {key: verdict for key, verdict in verdicts.items() if verdict[0] == "mismatch"}
    for (curie, doi), (_, ratio) in sorted(vetoed.items()):
        print(f"Crossref veto: {curie} -> {doi} (title ratio {ratio:.2f}): {crossref[doi.split(':', 1)[1]]['titles']}")

    unanswered = sorted(candidate for candidate, answer in registered.items() if not answer)
    if unanswered or crossref_unanswered:
        print(f"doi.org gave no answer for {len(unanswered)} candidates, e.g. {unanswered[:5]}; re-run to ask again.")
        print(f"Crossref gave no answer for {len(crossref_unanswered)} repairs, e.g. {crossref_unanswered[:5]}.")
        print(f"NOT writing {PUBMED_DOI_REPAIRS}: it would be missing their repairs.")
    else:
        with open(PUBMED_DOI_REPAIRS, "w") as f:
            f.write(
                "# Malformed PubMed DOIs and the registered DOI each is repaired to. GENERATED: do not edit.\n"
                "# Regenerate with docs/sources/PubMed/dois/characterize_dois.py; see PUBMED_DOI_REPAIRS in\n"
                "# src/createcompendia/publications.py for what belongs here and why it is a table.\n"
                f"# From pubmed2db export {config['pubmed2db_version']}; checked against doi.org and Crossref on "
                f"{date.today().isoformat()}.\n"
                "# malformed doi CURIE<TAB>repaired doi CURIE\n"
            )
            for curie in sorted(repairs):
                for repaired in repairs[curie]:
                    f.write(f"{curie}\t{repaired}\n")
        # The build must do exactly what this script decided, so read the table back the way the build does.
        load_doi_repairs.cache_clear()
        written = load_doi_repairs(PUBMED_DOI_REPAIRS)
        if written != {curie: tuple(repaired) for curie, repaired in repairs.items()}:
            raise RuntimeError(f"{PUBMED_DOI_REPAIRS} does not read back as the repairs just written to it.")

    shapes = defaultdict(
        lambda: {
            "count": 0,
            "repaired": 0,
            "crossref_vetoed": 0,
            "strategies": defaultdict(Counter),
            "registrants": Counter(),
            "rows": [],
        }
    )
    csv_rows = []
    for pmid, curie, others, _ in malformed:
        value = curie.split(":", 1)[1]
        shape = shape_of(value)
        repaired = repairs.get(curie, [])
        info = shapes[shape]
        info["count"] += 1
        info["repaired"] += bool(repaired)
        info["crossref_vetoed"] += any(key[0] == curie for key in vetoed)
        info["registrants"][value.split("/")[0] if value.startswith("10.") else "(none)"] += 1
        info["rows"].append({"pmid": pmid, "identifier": curie, "repaired_to": repaired})
        proposed = [(strategy, c) for strategy, cs in proposals[curie].items() for c in cs]
        for strategy, candidate in proposed or [("", "")]:
            candidate_curie = f"{DOI}:{candidate}"
            checked = strategy == REPAIR_STRATEGY.get(shape) and (curie, candidate_curie) in verdicts
            verdict, ratio = verdicts[(curie, candidate_curie)] if checked else ("", None)
            if strategy:
                info["strategies"][strategy]["candidates"] += 1
                info["strategies"][strategy]["registered"] += registered[candidate] == "yes"
                info["strategies"][strategy]["not_registered"] += registered[candidate] == "no"
            csv_rows.append(
                {
                    "pmid": pmid,
                    "identifier": curie,
                    "problem": curie_format_problem(curie),
                    "shape": shape,
                    "strategy": strategy,
                    "candidate": candidate_curie if candidate else "",
                    "registered_at_doi_org": registered[candidate] if candidate else "",
                    "already_on_this_record": (
                        "yes" if candidate and candidate_curie.lower() in {o.lower() for o in others} else ""
                    ),
                    "other_pmids_with_candidate": " ".join(
                        others_carrying(candidate, pmids_with[curie], carriers) if candidate else []
                    ),
                    "crossref_title": " | ".join(crossref[candidate]["titles"]) if checked else "",
                    "crossref_title_match": verdict,
                    "crossref_title_ratio": f"{ratio:.2f}" if ratio is not None else "",
                    "in_repairs_table": (
                        "yes" if candidate_curie in repaired and strategy == REPAIR_STRATEGY.get(shape) else ""
                    ),
                }
            )

    with open(OUTPUT_DIR / "malformed_dois.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(csv_rows[0]))
        writer.writeheader()
        writer.writerows(csv_rows)

    report = {
        "export": config["pubmed2db_version"] if args.export_dir == default_export_dir else args.export_dir,
        # Shard names, not the local path: this output is committed, and may cover only part of an export.
        "shards": shards,
        "records": records,
        "doi_org_checked": "" if args.offline else date.today().isoformat(),
        "doi_org_unanswered": len(unanswered),
        "crossref_checked": "" if args.offline else date.today().isoformat(),
        "crossref_unanswered": len(crossref_unanswered),
        "crossref_vetoed": len(vetoed),
        "title_match_min_ratio": TITLE_MATCH_MIN_RATIO,
        "crossref_verdicts": dict(Counter(verdict for verdict, _ in verdicts.values())),
        "malformed_dois": len(malformed),
        "repaired": sum(info["repaired"] for info in shapes.values()),
        "skipped": sum(info["count"] - info["repaired"] for info in shapes.values()),
        "malformed_identifiers_that_are_not_dois": [list(row) for row in non_dois],
        "baseline_well_formed_dois": {"sampled": len(baseline), **baseline_answers},
        "shapes": {
            shape: {
                "count": info["count"],
                "repaired": info["repaired"],
                "crossref_vetoed": info["crossref_vetoed"],
                "repair_strategy": REPAIR_STRATEGY.get(shape, ""),
                "strategies": {strategy: dict(counts) for strategy, counts in sorted(info["strategies"].items())},
                "top_registrants": dict(info["registrants"].most_common(5)),
                # Spread across the PMID-sorted list rather than the first few, which are one journal issue.
                "examples": info["rows"][:: max(1, len(info["rows"]) // EXAMPLES_PER_SHAPE)][:EXAMPLES_PER_SHAPE],
            }
            # In SHAPES order, not by count, so that a shape overtaking another between exports doesn't move
            # its whole block in the diff of this committed file.
            for shape, info in sorted(shapes.items(), key=lambda item: SHAPE_ORDER.index(item[0]))
        },
    }
    with open(OUTPUT_DIR / "counts.json", "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")
    for shape, info in report["shapes"].items():
        print(f"{shape}: {info['count']} malformed, {info['repaired']} repaired; {json.dumps(info['strategies'])}")
    print(f"{report['malformed_dois']} malformed DOIs: {report['repaired']} repaired, {report['skipped']} skipped.")


if __name__ == "__main__":
    main()
