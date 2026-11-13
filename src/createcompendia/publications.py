"""
Build the Publication compendium from a pubmed2db NDJSON export.

Babel used to download and parse the PubMed XML baseline and update files itself (~1,500 files, 20 hours
single-threaded in 2026jul22). That work now happens in pubmed2db (https://github.com/TranslatorSRI/pubmed2db),
which loads PubMed into DuckDB and exports one NDJSON record per PMID -- latest version only, deleted PMIDs
removed -- as gzipped ``pubmed_metadata_*.ndjson.gz`` shards, with a ``metadata.json`` that gives the
export's data model version and every shard's SHA-256, and a validation report that lists every shard and
how many records it holds. Babel downloads the export pinned by ``config.yaml: pubmed2db_version`` and reads
just three fields from each record: ``id`` (``PMID:...``), ``identifiers`` (the PMID plus its ``doi:`` and
PubMed Central CURIEs) and ``article_title``.

**Whenever you change this module, check https://stars.renci.org/var/babel_outputs/pubmed2db/ for a newer
export** and move the pubmed2db settings at the top of ``config.yaml`` to it. pubmed2db versions its outputs
with a "data model" version, and this module reads major version ``PUBMED2DB_DATA_MODEL_MAJOR``: an export
from another major version is refused, because only a major bump may rename, remove or change the meaning
of a field. The layout around the shards is not covered by that promise and has changed before (where the
validation report lives), so read a new export against docs/sources/PubMed/README.md, which describes the
contract this module relies on.

Because every record already carries its complete identifier set, the compendium is written straight from
the shards without glom(): a record *is* a clique. The one thing that needs a corpus-wide view is a DOI or
PMCID that appears in more than one record -- see ``parse_pubmed2db_into_tsvs()`` for how that is resolved.
"""

import functools
import gzip
import hashlib
import json
import os
import shutil
import tempfile
import zlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from src.babel_utils import TypedClique, pull_via_wget, write_compendium
from src.categories import JOURNAL_ARTICLE, PUBLICATION
from src.metadata.provenance import write_concord_metadata
from src.prefixes import DOI
from src.util import Text, curie_format_problem, ensure_parent_dir, get_logger, get_repo_root

logger = get_logger(__name__)

# The local name of the export's validation report, wherever the export keeps it (config.yaml:
# pubmed2db_validation_report) and whether or not it is gzipped there.
VALIDATION_REPORT = "validation_report.json"

# The export's own description of itself, at the top level of every export from data model 1.0 on: its data
# model version, record count, corpus cutoff, and each shard's size and SHA-256. Unlike the validation
# report, its path never changes.
EXPORT_METADATA = "metadata.json"

# The major version of pubmed2db's data model that this module reads. pubmed2db promises
# (https://github.com/TranslatorSRI/pubmed2db/blob/main/docs/data-model/README.md#versioning-and-stability)
# that a minor version only adds fields, while a major one may rename, remove or change the meaning of the
# three this module reads, so read_export_metadata() accepts any 1.x and refuses everything else. Before
# raising this, read pubmed2db's changelog entry for the new major version
# (https://github.com/TranslatorSRI/pubmed2db/blob/main/docs/data-model/Changelog.md), which says what an
# NDJSON consumer has to do, and make that change here.
#
# The change most likely to arrive that way is the prefix of PubMed Central ids. Data model 1 spells them
# PMC:PMC123, the spelling every Babel release has shipped and the one Biolink registers on
# biolink:Publication (PMCID only on biolink:JournalArticle). Which prefix Translator should use is still
# open (https://github.com/NCATSTranslator/Babel/issues/1044, and
# https://github.com/TranslatorSRI/pubmed2db/issues/33 for the export, which follows Babel in the meantime).
# If that settles on PMCID, the export changes with a major bump, and generate_compendium() must then pass
# extra_prefixes=["PMCID"] to write_compendium(), or create_node() will silently drop every one of them as
# unregistered for biolink:Publication.
PUBMED2DB_DATA_MODEL_MAJOR = 1

# The malformed DOIs Babel repairs, and what each is repaired to: `malformed doi CURIE<TAB>repaired doi CURIE`,
# one row per repaired DOI (a value holding two DOIs has two rows), with `#` comments.
#
# PubMed publishes ArticleId[@IdType='doi'] as the publisher supplied it, so several hundred DOIs in an export
# contain a space or stray text (`doi:10.1126/science. 1134405`), and write_compendium() fails the build on
# any CURIE with whitespace. They are repaired from this table rather than by a rule because no rule is
# reliable: deleting the whitespace gives a DOI registered at doi.org for only about three quarters of even
# the most regular shape, against 163 of 163 well-formed DOIs sampled from the same export (see "Malformed
# DOIs" in docs/sources/PubMed/README.md for the numbers and the rules that were tried). So the table holds
# only repairs that doi.org confirms and that no PMID already carries unless it carries the malformed DOI too
# (a row applies to every PMID with that malformed DOI); a malformed DOI not in it is skipped, as all of them
# were before, and counted in the concord metadata.
#
# Never edit it by hand: docs/sources/PubMed/dois/characterize_dois.py regenerates it from a whole export.
# Re-run that when pubmed2db_version moves, to pick up the new export's malformed DOIs; a stale table is
# harmless (rows for DOIs PubMed has since corrected simply never match).
#
# Two consumers resolve this file: the build, where the PubMed rules declare it as an input (so regenerating
# it re-runs them) and pass the path in, and the scripts under docs/sources/PubMed/, which take this default.
# Absolute, because those scripts can be run from any directory.
PUBMED_DOI_REPAIRS = str(get_repo_root() / "input_data/pubmed_doi_repairs.tsv")

# How much of a shard to hash at a time (shards are ~2 GB, so they are never read whole).
HASH_CHUNK_BYTES = 8 * 1024 * 1024


def shared_identifier_key(curie):
    """
    The form in which two records' DOIs and PMCIDs are compared to decide whether they are the same identifier.

    DOIs are case-insensitive, and PubMed publishes them as supplied, so the same DOI can arrive in different
    cases on different PMIDs (``doi:10.1039/C4BM00222A`` on PMID:26146547, ``doi:10.1039/c4bm00222a`` on
    PMID:26214188 in 2026sep26). Compared exactly, both would be kept, in two cliques -- and Node
    Normalization, which looks CURIEs up case-insensitively, would resolve both spellings to only one of them.
    So a DOI is compared lower-cased. A PubMed Central id is ``PMC`` plus digits and is compared as-is.
    """
    if Text.get_prefix_or_none(curie) == DOI.upper():
        return curie.lower()
    return curie


def download_pubmed2db(export_url, report_path, download_dir, done_file):
    """
    Download a pubmed2db export: its ``metadata.json`` and validation report, then exactly the shards they
    list, and check every shard against its SHA-256.

    The report doubles as the export's manifest, so we never crawl the export directory -- since 2026sep26
    it also holds pubmed2db's own ~76 GB DuckDB database and a ``manifests/`` subdirectory, which a recursive
    wget would fetch. ``metadata.json`` is read first, so an export in a data model this module wasn't
    written for is refused before 17 GB of it is downloaded.

    ``download_dir`` belongs to a single export version, and a published export is never modified, so a
    shard left half-downloaded by an interrupted run is safely resumed (``wget --continue``) and a complete
    one is left alone. That is also what makes carrying ``download_dir`` forward into a new run safe -- and
    the checksums are what catch a carried-forward directory holding another export's shards, which would
    otherwise be left alone as "complete". The marker is only written once every shard matches.

    :param export_url: The export directory URL, ending in ``/``.
    :param report_path: The validation report's path relative to ``export_url``
        (``config.yaml: pubmed2db_validation_report``); gzipped if it ends in ``.gz``.
    :param download_dir: The local directory to download into.
    :param done_file: Marker file to touch once every shard is downloaded.
    """
    report_file = os.path.join(download_dir, VALIDATION_REPORT)
    metadata_file = os.path.join(download_dir, EXPORT_METADATA)
    report_gzipped = report_path.endswith(".gz")
    # Both are small and always re-fetched; clear any old copy so that a stale one is never read, and so
    # gunzip doesn't refuse to overwrite the report.
    for stale in (metadata_file, report_file, report_file + ".gz"):
        if os.path.exists(stale):
            os.remove(stale)
    pull_via_wget(export_url, EXPORT_METADATA, decompress=False, outpath=metadata_file, continue_incomplete=False)
    # Refuse another data model before fetching anything else. The report isn't here yet, so the comparison
    # of the two shard lists waits for the call below.
    read_export_metadata(download_dir, check_against_report=False)
    pull_via_wget(
        export_url,
        report_path,
        decompress=report_gzipped,
        outpath=report_file + (".gz" if report_gzipped else ""),
        continue_incomplete=False,
    )

    shard_counts = expected_shard_counts(download_dir)
    metadata = read_export_metadata(download_dir, shard_counts)
    for shard in shard_counts:
        pull_via_wget(
            export_url, shard, decompress=False, outpath=os.path.join(download_dir, shard), continue_incomplete=True
        )
    verify_shard_checksums(download_dir, metadata)
    logger.info(
        f"Downloaded {len(shard_counts)} pubmed2db shards ({sum(shard_counts.values()):,} records, data model "
        f"{metadata['data_model_version']}) from {export_url} into {download_dir}; every SHA-256 matches."
    )
    ensure_parent_dir(done_file)
    Path(done_file).touch()


def expected_shard_counts(download_dir):
    """
    The shards of the export downloaded into ``download_dir``, mapped to the record count pubmed2db's validator
    saw in each, in a fixed (sorted) order.

    The validation report is pubmed2db's statement of what the export contains: it is our manifest of which
    shards to download and read, and the per-shard counts catch an intact shard from a different export (a
    truncated or corrupted one already fails decompression in ``_read_shard()``). ``verify_shard_checksums()``
    catches that too, even when the counts happen to match, but only runs when the shards are downloaded;
    the counts are checked on every parse. Reads ``checks.structure.records_by_shard`` and
    ``records_total`` rather than the human-readable ``checks_run[].observed`` strings. Raises if the report's
    overall status is ``fail`` or those fields are missing or inconsistent.
    """
    report_file = os.path.join(download_dir, VALIDATION_REPORT)
    with open(report_file) as f:
        report = json.load(f)
    if report.get("status") == "fail":
        raise RuntimeError(
            f"pubmed2db validation report {report_file} has status 'fail': {report.get('errors')}. "
            "Refusing to build a compendium from an export its own validator rejected."
        )
    try:
        structure = report["checks"]["structure"]
        records_by_shard = structure["records_by_shard"]
        records_total = structure["records_total"]
    except KeyError as e:
        raise RuntimeError(
            f"pubmed2db validation report {report_file} has no checks.structure.records_by_shard and "
            f"records_total (missing {e}): the report format has changed; see docs/sources/PubMed/README.md."
        ) from e
    if not records_by_shard:
        raise RuntimeError(f"pubmed2db validation report {report_file} lists no shards.")
    for shard in records_by_shard:
        # Shard names become both a download URL and a local path, so they must be bare filenames.
        if os.path.basename(shard) != shard or not shard.endswith(".ndjson.gz"):
            raise RuntimeError(f"pubmed2db validation report {report_file} lists an unexpected shard name {shard!r}.")
    if sum(records_by_shard.values()) != records_total:
        raise RuntimeError(
            f"pubmed2db validation report {report_file}: records_by_shard sums to "
            f"{sum(records_by_shard.values()):,} but records_total is {records_total:,}."
        )
    return dict(sorted(records_by_shard.items()))


def read_export_metadata(download_dir, shard_counts=None, check_against_report=True):
    """
    The ``metadata.json`` of the export downloaded into ``download_dir``, once it is known to describe an
    export this module can read.

    Raises unless its ``data_model_version`` has major version ``PUBMED2DB_DATA_MODEL_MAJOR`` (see that
    constant for why any minor version is accepted), and unless every entry of ``files`` has a ``name`` and
    a ``sha256``. With ``check_against_report``, also raises unless it lists exactly the shards the
    validation report does and gives the same total record count: the two are written by different pubmed2db
    steps (``export`` and ``validate``), so a disagreement means they describe different exports. A caller
    that has already read the report passes its ``expected_shard_counts()`` as ``shard_counts``, so it isn't
    read twice.

    A missing file raises too, with what to do about it: exports before data model 1.0 (2026sep26 and
    earlier) have none, and neither does a directory preloaded from a build that predates this check.
    """
    metadata_file = os.path.join(download_dir, EXPORT_METADATA)
    try:
        with open(metadata_file) as f:
            metadata = json.load(f)
    except FileNotFoundError as e:
        raise RuntimeError(
            f"{metadata_file} is missing. Every pubmed2db export from data model 1.0 on has one, so either this "
            f"export predates it (2026sep26 and earlier, which this code no longer reads) or the directory was "
            f"preloaded without it: delete {os.path.join(download_dir, 'downloaded')} and re-run "
            f"download_pubmed2db, which fetches it and leaves complete shards alone."
        ) from e

    version = str(metadata.get("data_model_version", ""))
    if version.split(".")[0] != str(PUBMED2DB_DATA_MODEL_MAJOR):
        raise RuntimeError(
            f"{metadata_file} says this export follows pubmed2db data model {version or '(none)'}, but Babel "
            f"reads major version {PUBMED2DB_DATA_MODEL_MAJOR}. A major version may rename, remove or change "
            f"the meaning of the fields Babel reads: see PUBMED2DB_DATA_MODEL_MAJOR in "
            f"src/createcompendia/publications.py and pubmed2db's data model changelog before changing it."
        )
    try:
        shard_hashes = {entry["name"]: entry["sha256"] for entry in metadata["files"]}
        records = metadata["records"]
        # bool is an int, and anything else would turn the comparison below into a confusing error.
        if not isinstance(records, int) or isinstance(records, bool):
            raise TypeError(f"records is {records!r}, not an integer")
    except (KeyError, TypeError) as e:
        raise RuntimeError(
            f"{metadata_file} has no usable files[].name, files[].sha256 and records ({type(e).__name__}: {e}); "
            f"see docs/sources/PubMed/README.md."
        ) from e

    if check_against_report:
        if shard_counts is None:
            shard_counts = expected_shard_counts(download_dir)
        if set(shard_hashes) != set(shard_counts) or records != sum(shard_counts.values()):
            raise RuntimeError(
                f"{metadata_file} and the validation report beside it describe different exports: metadata.json "
                f"lists {sorted(shard_hashes)} with {records:,} records, the report lists {sorted(shard_counts)} "
                f"with {sum(shard_counts.values()):,}. Check config.yaml: pubmed2db_validation_report names the "
                f"report of the export that pubmed2db_version names."
            )
    return metadata


def verify_shard_checksums(download_dir, metadata):
    """
    Raise unless every shard ``metadata`` (from ``read_export_metadata()``) lists is in ``download_dir`` with
    the SHA-256 it gives, naming all the ones that aren't.

    This is step 2 of pubmed2db's recipe for checking a download (``sha256sum -c SHA256SUMS``; the hashes in
    ``metadata.json`` are the same ones). It is the only check that catches an intact shard from a different
    export whose record count happens to match -- most likely one already in a carried-forward
    ``download_dir``, which ``wget --continue`` leaves alone as complete. Hashing the ~17 GB took 6 s
    on an Apple M-series laptop.
    """
    problems = []
    for entry in metadata["files"]:
        shard_path = os.path.join(download_dir, entry["name"])
        if not os.path.exists(shard_path):
            problems.append(f"{entry['name']} is missing")
            continue
        digest = hashlib.sha256()
        with open(shard_path, "rb") as f:
            while chunk := f.read(HASH_CHUNK_BYTES):
                digest.update(chunk)
        if digest.hexdigest() != entry["sha256"]:
            problems.append(f"{entry['name']} has SHA-256 {digest.hexdigest()}, expected {entry['sha256']}")
    if problems:
        raise RuntimeError(
            f"Shards in {download_dir} don't match the export's {EXPORT_METADATA}, so they are damaged or come "
            f"from a different export: {'; '.join(problems)}. Delete those shards and re-run download_pubmed2db."
        )


@functools.cache
def load_doi_repairs(doi_repairs_file):
    """
    The DOI repairs table (see ``PUBMED_DOI_REPAIRS``) as ``{malformed doi CURIE: (repaired doi CURIE, ...)}``.

    Cached per path, so each of ``parse_pubmed2db_into_tsvs()``'s worker processes reads it once. Raises on a
    row that isn't two tab-separated fields, a repair that is itself malformed, or a "malformed" DOI that
    isn't well-formed or isn't a DOI (a PMCID turned into a DOI would be a different identifier, not a
    repair): any of those means the table was edited by hand, and a repair that silently does nothing (or
    writes a CURIE that fails the build an hour later) is worse than stopping here.
    """
    repairs = {}
    with open(doi_repairs_file) as f:
        for line_number, line in enumerate(f, start=1):
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            fields = line.split("\t")
            where = f"{doi_repairs_file}:{line_number}"
            if len(fields) != 2:
                raise ValueError(f"{where} has {len(fields)} tab-separated fields, not 2: {line!r}")
            malformed, repaired = fields
            if not curie_format_problem(malformed):
                raise ValueError(f"{where}: {malformed!r} is not malformed, so it would never be looked up.")
            if Text.get_prefix_or_none(malformed) != DOI.upper():
                raise ValueError(f"{where}: {malformed!r} is not a {DOI}: CURIE, and only DOIs are repaired.")
            if curie_format_problem(repaired) or Text.get_prefix_or_none(repaired) != DOI.upper():
                raise ValueError(f"{where}: the repair {repaired!r} is not a well-formed {DOI}: CURIE.")
            repairs.setdefault(malformed, [])
            if repaired not in repairs[malformed]:
                repairs[malformed].append(repaired)
    return {malformed: tuple(repaired) for malformed, repaired in repairs.items()}


def _read_shard(shard_path, doi_repairs=None, repairs_made=None):
    """
    Yield ``(pmid, title, other_identifiers, malformed_identifiers)`` for every record in one shard; see
    ``_read_shard_records()``, which also yields the raw record and explains the other two arguments.
    """
    for _, pmid, title, others, malformed in _read_shard_records(shard_path, doi_repairs, repairs_made):
        yield pmid, title, others, malformed


def _read_shard_records(shard_path, doi_repairs=None, repairs_made=None):
    """
    Yield ``(record, pmid, title, other_identifiers, malformed_identifiers)`` for every record in one shard.

    :param doi_repairs: ``load_doi_repairs()``'s table. The build always passes it; the default of no
        repairs is for the analysis scripts, which want to see the export as it is.
    :param repairs_made: If given, a list to which each repair made is appended, as
        ``(pmid, malformed CURIE, repaired CURIEs)``.

    ``record`` is the parsed JSON line, for analysis scripts that read fields the build doesn't
    (docs/sources/PubMed/shared_identifiers/); the build itself uses ``_read_shard()``.

    This is the only place in the build that knows the export's record format. ``identifiers`` always starts
    with the record's own PMID, so ``identifiers[1:]`` is its DOI and PubMed Central CURIEs (``doi:`` and
    ``PMC:PMC123``; sorted and de-duplicated by pubmed2db). They are de-duplicated again by
    ``shared_identifier_key()``, since pubmed2db compares DOIs exactly -- before anything else, so a malformed
    DOI carried twice is counted, and repaired or skipped, once, in the spelling that comes first. ``title`` is ``article_title`` exactly
    as exported, and is ``""`` when the record has none.

    PubMed publishes DOIs as supplied, including some with embedded spaces or appended text
    (``doi:10.1126/science. 1134405``, PMID:17124311; 655 in 2026nov08), which ``curie_format_problem()``
    rejects and ``write_compendium()`` would fail the build on. One that ``doi_repairs`` lists is replaced by
    its repair, in ``other_identifiers``; any other goes in ``malformed_identifiers`` instead and is skipped.
    Both passes over the shards read through here with the same table, so they repair and skip the same ones.

    A damaged shard raises a RuntimeError naming it, with no checksum needed. pubmed2db writes each shard as a
    single gzip stream, which ends with a CRC32 and the length: a corrupted download fails the CRC if it hasn't
    already produced unparseable JSON, and a truncated one raises EOFError, even when it is cut off only in
    that trailer. The record counts in the validation report (see ``parse_pubmed2db_into_tsvs()``) are for an
    intact shard from a different export.
    """
    count_records = 0
    try:
        with gzip.open(shard_path, "rt") as f:
            for line in f:
                record = json.loads(line)
                pmid = record["id"]
                identifiers = record["identifiers"]
                title = record["article_title"]
                if not identifiers or identifiers[0] != pmid:
                    raise ValueError(
                        f"{shard_path}: record {pmid} has identifiers {identifiers} not starting with its PMID."
                    )
                others = []
                malformed = []
                keys = set()
                for exported in identifiers[1:]:
                    # A DOI in two cases is one identifier; keep the first spelling.
                    key = shared_identifier_key(exported)
                    if key in keys:
                        continue
                    keys.add(key)
                    if not curie_format_problem(exported):
                        others.append(exported)
                        continue
                    repaired = doi_repairs.get(exported) if doi_repairs else None
                    if not repaired:
                        malformed.append(exported)
                        continue
                    if repairs_made is not None:
                        repairs_made.append((pmid, exported, repaired))
                    for other in repaired:
                        # A repair can produce a DOI the record already carries; keep the first.
                        key = shared_identifier_key(other)
                        if key not in keys:
                            keys.add(key)
                            others.append(other)
                count_records += 1
                yield record, pmid, title, others, malformed
    # OSError covers gzip.BadGzipFile (a failed CRC), EOFError a truncated gzip stream, and the rest a record
    # mangled into something that still decompresses.
    except (OSError, EOFError, zlib.error, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as e:
        raise RuntimeError(
            f"{shard_path} is corrupt or truncated: reading it failed after {count_records:,} records "
            f"({type(e).__name__}: {e}). Delete it and re-run download_pubmed2db."
        ) from e


def escape_tsv_field(value):
    """
    Escape a value for one field of a TSV row, losslessly: backslash, tab, newline and carriage return become
    ``\\\\``, ``\\t``, ``\\n`` and ``\\r``, so the row always has the expected number of fields and the
    original can be recovered.
    """
    return value.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def _write_shard_tsvs(shard_path, part_prefix, doi_repairs_file):
    """
    Write one shard's ids, titles and concords rows to ``<part_prefix>.{ids,titles,concords}``.

    Run in a worker process, so it returns only ``(records, concords, malformed identifiers skipped, repairs
    made)`` -- the last two short lists -- and holds one record at a time; ``parse_pubmed2db_into_tsvs()``
    concatenates the parts in shard order. Module-level so ProcessPoolExecutor can pickle it.
    """
    count_records = 0
    count_concords = 0
    skipped = []
    repaired = []
    doi_repairs = load_doi_repairs(doi_repairs_file)
    with (
        open(part_prefix + ".ids", "w") as pmidf,
        open(part_prefix + ".titles", "w") as titlesf,
        open(part_prefix + ".concords", "w") as concordf,
    ):
        for pmid, title, others, malformed in _read_shard(shard_path, doi_repairs, repaired):
            count_records += 1
            skipped.extend(malformed)
            pmidf.write(f"{pmid}\t{JOURNAL_ARTICLE}\n")
            if title:
                titlesf.write(f"{pmid}\t{escape_tsv_field(title)}\n")
            for other in others:
                count_concords += 1
                concordf.write(f"{pmid}\teq\t{other}\n")
    logger.info(
        f"Parsed {count_records:,} records and {count_concords:,} concords from {shard_path}, repairing "
        f"{len(repaired):,} malformed DOIs and skipping {len(skipped):,} malformed DOIs/PMCIDs."
    )
    return count_records, count_concords, skipped, repaired


def parse_pubmed2db_into_tsvs(
    download_dir,
    titles_file,
    pmid_id_file,
    concord_file,
    shared_ids_file,
    metadata_yaml,
    url,
    workers,
    doi_repairs_file=PUBMED_DOI_REPAIRS,
):
    """
    Write the ids, titles and concords TSVs from a pubmed2db export, and resolve shared identifiers.

    - ``pmid_id_file``: ``PMID:x\\tbiolink:JournalArticle``
    - ``titles_file``: ``PMID:x\\t<title>``, escaped with ``escape_tsv_field()``; empty titles skipped. Nothing
      in the build reads it -- the compendium takes titles from the shards -- but it is the easiest place to
      diff titles between builds.
    - ``concord_file``: ``PMID:x\\teq\\t<doi: or PMC: CURIE>``

    Shards are parsed in parallel, each worker writing its own part files, so no worker or the parent ever
    holds more than one record of a shard; the parts are then concatenated in shard order.

    A DOI or PMCID can appear in more than one record (PubMed publishes them as-is). Two cliques must never
    share an identifier, so ``shared_ids_file`` records each such identifier -- as its
    ``shared_identifier_key()``, so a DOI is lower-cased -- with the *lowest* PMID that carries it, and
    ``generate_compendium()`` keeps it only there, in that PMID's own spelling. Lowest rather than highest:
    the PMIDs sharing a DOI are separate citations, not versions of one (pubmed2db already keeps only each
    PMID's latest version), and the lowest is almost always the first published, while the highest is often
    the author's reply in a block of letters published under one DOI -- see "Identifiers shared by more than
    one PMID" in docs/sources/PubMed/README.md for the measurements. It also matches what the old
    ``glom(unique_prefixes=[PMID])`` did (the first-seen PMID kept the identifier, and the XML was read in
    roughly PMID order), made independent of shard order. The file doubles as a data-quality report of
    ambiguous identifiers.

    A malformed DOI listed in ``doi_repairs_file`` is replaced by its repair (see ``PUBMED_DOI_REPAIRS``) and
    counted in the metadata YAML as ``repaired_malformed_article_ids``. Any other DOI or PMCID that
    ``write_compendium()`` would reject is skipped (see ``_read_shard_records()``) and counted as
    ``skipped_malformed_article_ids``; all of them are logged.

    Raises if the export follows a data model this module doesn't read (``read_export_metadata()``), or if
    any shard holds a different number of records than pubmed2db's validation report says.

    :param url: The export URL, recorded in the metadata YAML as the source of this build's PubMed data.
    :param workers: How many shards to parse at once.
    :param doi_repairs_file: The DOI repairs table; ``generate_compendium()`` must be given the same one.
    """
    for path in (titles_file, pmid_id_file, concord_file, shared_ids_file):
        ensure_parent_dir(path)

    shard_counts = expected_shard_counts(download_dir)
    # Checked here as well as on download, because a preloaded download_dir skips the download rule.
    export_metadata = read_export_metadata(download_dir, shard_counts)
    shards = list(shard_counts)
    shard_files = [os.path.join(download_dir, shard) for shard in shards]

    with tempfile.TemporaryDirectory(dir=os.path.dirname(concord_file), prefix="pubmed2db-parts-") as parts_dir:
        part_prefixes = [os.path.join(parts_dir, f"{i:05d}") for i in range(len(shards))]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_write_shard_tsvs, shard_files, part_prefixes, [doi_repairs_file] * len(shards)))

        mismatches = [
            f"{shard}: parsed {records:,}, report says {shard_counts[shard]:,}"
            for shard, (records, _, _, _) in zip(shards, results)
            if records != shard_counts[shard]
        ]
        if mismatches:
            raise RuntimeError(
                f"Shards in {download_dir} disagree with their validation report, so they probably come from a "
                f"different export: "
                f"{'; '.join(mismatches)}. Delete those shards and re-run download_pubmed2db."
            )

        for final_file, suffix in ((pmid_id_file, ".ids"), (titles_file, ".titles"), (concord_file, ".concords")):
            with open(final_file, "wb") as outf:
                for part_prefix in part_prefixes:
                    with open(part_prefix + suffix, "rb") as inf:
                        shutil.copyfileobj(inf, outf)

    count_records = sum(records for records, _, _, _ in results)
    count_concords = sum(concords for _, concords, _, _ in results)
    skipped = [curie for _, _, shard_skipped, _ in results for curie in shard_skipped]
    repaired = [repair for _, _, _, shard_repaired in results for repair in shard_repaired]
    logger.info(f"Repaired {len(repaired):,} malformed DOIs from {doi_repairs_file}, e.g. {repaired[:5]}")
    # All of them, not a sample: there are a few hundred, and this list is the input to regenerating the
    # repairs table (docs/sources/PubMed/dois/characterize_dois.py finds them itself, but a reader of the
    # log shouldn't have to run it to see what was dropped).
    logger.info(f"Skipped {len(skipped):,} malformed DOIs/PMCIDs with no repair: {skipped}")

    # Find the identifiers carried by more than one record, compared by shared_identifier_key()...
    seen = set()
    duplicated = set()
    with open(concord_file) as concordf:
        for line in concordf:
            key = shared_identifier_key(line.rstrip("\n").split("\t")[2])
            if key in seen:
                duplicated.add(key)
            else:
                seen.add(key)
    del seen

    # ...and resolve each to its lowest PMID with a second pass, rather than holding a PMID for all ~46M
    # identifiers in the first. identifier -> (lowest PMID carrying it, number of records carrying it).
    shared = {}
    if duplicated:
        with open(concord_file) as concordf:
            for line in concordf:
                pmid, _, other = line.rstrip("\n").split("\t")
                key = shared_identifier_key(other)
                if key in duplicated:
                    winner, n = shared.get(key, (None, 0))
                    shared[key] = (_lower_pmid(winner, pmid), n + 1)

    with open(shared_ids_file, "w") as sharedf:
        for other in sorted(shared):
            winner, n = shared[other]
            sharedf.write(f"{other}\t{winner}\t{n}\n")
    logger.info(
        f"Parsed {count_records:,} records and {count_concords:,} concords; {len(shared):,} identifiers are "
        f"shared by more than one PMID (see {shared_ids_file})."
    )

    write_concord_metadata(
        metadata_yaml,
        name="parse_pubmed2db_into_tsvs()",
        description=(
            f"Parse a pubmed2db NDJSON export into id, title and concord TSVs. Export "
            f"{export_metadata.get('corpus', {}).get('build_name', '(unnamed)')}, pubmed2db data model "
            f"{export_metadata['data_model_version']}, generated by pubmed2db "
            f"{export_metadata.get('generated_by', '(unknown)')}."
        ),
        url=url,
        sources=[{"type": "download", "name": "pubmed2db NDJSON export", "url": url}],
        counts={
            "pmid_count": count_records,
            "shard_count": len(shards),
            "shared_identifier_count": len(shared),
            "repaired_malformed_article_ids": len(repaired),
            "skipped_malformed_article_ids": len(skipped),
        },
        concord_filename=concord_file,
    )


def _lower_pmid(a, b):
    """The numerically lower of two ``PMID:n`` CURIEs (``None`` loses)."""
    if a is None:
        return b
    return a if int(a.split(":")[1]) <= int(b.split(":")[1]) else b


class _PublicationCliques:
    """
    A sized iterable of TypedCliques streamed from the export, so write_compendium() can log progress.

    Shards are read one record at a time in this process. write_compendium() is the bottleneck here, so
    parsing ahead in worker processes would buy little time and cost a parsed shard's worth of memory per
    worker.
    """

    def __init__(self, download_dir, winners, doi_repairs):
        self.download_dir = download_dir
        self.winners = winners
        self.doi_repairs = doi_repairs
        self.shard_counts = expected_shard_counts(download_dir)

    def __len__(self):
        return sum(self.shard_counts.values())

    def __iter__(self):
        for shard in self.shard_counts:
            for pmid, title, others, _ in _read_shard(os.path.join(self.download_dir, shard), self.doi_repairs):
                identifiers = [pmid] + [o for o in others if self.winners.get(shared_identifier_key(o), pmid) == pmid]
                yield TypedClique(PUBLICATION, identifiers, {pmid: title} if title else None)


def generate_compendium(
    download_dir,
    shared_ids_file,
    metadata_yamls,
    publication_compendium,
    icrdf_filename,
    doi_repairs_file=PUBMED_DOI_REPAIRS,
):
    """
    Write the Publication compendium straight from the pubmed2db shards: one record, one clique.

    Each PMID's label is its ``article_title`` exactly as exported, so a title with an embedded newline or
    surrounding whitespace keeps it (see docs/sources/PubMed/README.md, "Titles").

    :param shared_ids_file: Output of parse_pubmed2db_into_tsvs(); a shared identifier stays only in the
        PMID named there.
    :param doi_repairs_file: The DOI repairs table parse_pubmed2db_into_tsvs() was given. It has to be the
        same one: shared_ids_file was computed from the repaired identifiers.
    """
    winners = {}
    with open(shared_ids_file) as sharedf:
        for line in sharedf:
            other, winner, _ = line.rstrip("\n").split("\t")
            winners[other] = winner
    logger.info(f"Loaded {len(winners):,} shared identifiers from {shared_ids_file}.")

    write_compendium(
        metadata_yamls,
        _PublicationCliques(download_dir, winners, load_doi_repairs(doi_repairs_file)),
        os.path.basename(publication_compendium),
        None,
        # No extra_prefixes: the export spells PubMed Central ids PMC:, which Biolink registers on
        # biolink:Publication. A PMCID: would need extra_prefixes (see PUBMED2DB_DATA_MODEL_MAJOR).
        icrdf_filename=icrdf_filename,
    )
