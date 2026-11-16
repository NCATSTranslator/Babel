"""Split multi-component standard InChIs into components, and reduce a salt or hydrate to its parent component.

A salt or hydrate is one record whose standard InChI holds several disconnected components: fluoxetine hydrochloride
is ``InChI=1S/C17H18F3NO.ClH/...``, naproxen sodium ``InChI=1S/C14H14O3.Na/...;/q;+1/p-1``. The ChemicalParent
conflation maps such a record to its parent compound (issue #1173, rule 3) by dropping the components on a reviewed
list of counterions and solvents (``input_data/chemical_parent_components.tsv``) and taking the parent key of the one
component left.

Two decisions make this safe:

- **Only listed components are dropped.** "Keep the largest component" would map a two-drug co-crystal to whichever
  drug is bigger, and would strip the metal from a coordination compound: standard InChI disconnects metals, so
  cobalamin is ``C...O14P.Co`` and cisplatin ``2ClH.2H3N.Pt``, where the metal is part of the drug. The list says
  ``drop`` or ``keep`` for each component reviewed; anything unlisted is kept.
- **A record maps only when exactly one distinct component remains.** None left (sodium chloride, a bare
  counterion) or several (a combination, a co-crystal, a metal complex) and the record keeps its own key.

Components are compared by *parent key* -- the InChIKey without its protonation block, as in
``chemicalparent.split_inchikey()`` -- so hydrochloric acid and chloride are one list entry, and the remaining
component's parent key groups with every charge state of the parent compound.

Splitting needs RDKit: it parses the InChI, separates the fragments and computes each fragment's standard InChI
and InChIKey. That is the slow part (~0.5 ms per InChI), so ``write_inchi_components()`` does it once per build for
every multi-component InChI and the result is reused.
"""

import csv
import gzip
from itertools import chain, groupby

from more_itertools import chunked
from pebble import ProcessPool

from src.createcompendia.chemicalparent import INCHIKEY_PATTERN
from src.datahandlers.unichem import UNICHEM_STRUCT_TSV_HEADER
from src.util import ensure_parent_dir, get_logger

logger = get_logger(__name__)

# The prefix of a standard InChI; anything else (InChI beta "InChI=1B/", non-standard "InChI=1/") is skipped.
STANDARD_INCHI_PREFIX = "InChI=1S/"

# Header of the intermediate components file: one row per distinct component of each multi-component InChI.
COMPONENTS_TSV_HEADER = ["inchikey", "component_inchikey", "component_heavy_atoms", "component_inchi"]

# Columns of input_data/chemical_parent_components.tsv, the reviewed list of components.
DECISIONS_TSV_HEADER = ["component_parent_key", "decision", "kind", "name", "example_inchi", "note"]
DROP = "drop"
KEEP = "keep"

# Lines handed to each worker at a time when splitting InChIs in parallel: large enough that pickling overhead is
# small next to ~0.5 ms of RDKit work per multi-component line, small enough to keep every worker busy.
CHUNK_LINES = 2000

# Chunks queued per worker process at once. Two keeps every worker busy while the next batch is read, and bounds
# memory to a few thousand InChIs per process (see write_inchi_components()).
CHUNKS_IN_FLIGHT_PER_PROCESS = 2

# Seconds before a chunk of CHUNK_LINES InChIs is abandoned and its worker killed. A chunk normally takes 1-5 s
# (large peptides are the slow ones); a hanging InChI would otherwise hold a worker forever. Generous, because a
# timed-out chunk is re-run one InChI at a time.
CHUNK_TIMEOUT_SECONDS = 120

# Seconds allowed for a single InChI when a timed-out chunk is re-run. The slowest real InChIs seen take under 3 s.
ITEM_TIMEOUT_SECONDS = 30

# How many InChIKeys of InChIs RDKit couldn't split to log; the count goes in the metadata.
MAX_FAILURE_EXAMPLES = 20


def is_multi_component(inchi):
    """Whether a standard InChI's formula layer has more than one component (``C17H18F3NO.ClH``)."""
    parts = inchi.split("/", 2)
    return len(parts) > 1 and "." in parts[1]


def parent_key(inchikey):
    """The parent key of a bare InChIKey (no ``INCHIKEY:`` prefix): the key without its protonation block."""
    match = INCHIKEY_PATTERN.match(inchikey)
    if match is None:
        raise ValueError(f"Malformed InChIKey: {inchikey!r}")
    return match.group(1)


def split_inchi(inchi):
    """Split a standard InChI into its distinct components.

    :return: a list of (component InChIKey, heavy-atom count, component InChI), one per distinct component, in
        decreasing heavy-atom order; or None if RDKit can't parse the InChI, sanitize a fragment, or produce a key.
    """
    from rdkit import Chem, RDLogger

    RDLogger.DisableLog("rdApp.*")
    mol = Chem.MolFromInchi(inchi)
    if mol is None:
        return None
    # Fragments are re-sanitized: an unsanitized fragment keeps aromatic flags that can't be kekulized on their
    # own. Some fragments (large fused polyaromatics, e.g. CID 11194182) sanitize but still fail to kekulize when
    # their InChI is generated. Either makes the InChI unsplittable; only RDKit's sanitization error (which
    # KekulizeException subclasses) is caught, so anything else still fails the build.
    components = {}
    try:
        for fragment in Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=True):
            key = Chem.MolToInchiKey(fragment)
            if not key:
                return None
            if key not in components:
                components[key] = (fragment.GetNumHeavyAtoms(), Chem.MolToInchi(fragment))
    except Chem.rdchem.MolSanitizeException:
        return None
    return sorted(
        ((key, heavy, component_inchi) for key, (heavy, component_inchi) in components.items()),
        key=lambda c: (-c[1], c[0]),
    )


def _split_lines(lines):
    """Worker for write_inchi_components(): split each (InChIKey, InChI) line, returning rows and a failure count."""
    rows = []
    failures = []
    for inchikey, inchi in lines:
        components = split_inchi(inchi)
        if components is None:
            failures.append(inchikey)
            continue
        rows.extend((inchikey, key, heavy, component_inchi) for key, heavy, component_inchi in components)
    return rows, failures


def read_unichem_inchis(structure_gz):
    """Yield (InChIKey, InChI) for every row of UniChem's ``structure.tsv.gz``.

    This is the file write_unichem_concords() takes nearly every clique's ``INCHIKEY:`` from, so each such key's
    InChI is here, from the same release. The header is checked as read_inchikeys() checks it.
    """
    with gzip.open(structure_gz, "rt") as inf:
        header = inf.readline()
        if header != UNICHEM_STRUCT_TSV_HEADER:
            raise ValueError(f"{structure_gz}: unexpected header {header!r}, expected {UNICHEM_STRUCT_TSV_HEADER!r}")
        for line in inf:
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 3:
                raise ValueError(f"{structure_gz}: expected UCI, InChI, InChIKey; got {line!r}")
            _, inchi, inchikey = fields
            yield inchikey, inchi


def read_gtopdb_inchis(ligands_tsv):
    """Yield (InChIKey, InChI) for every ligand in GtoPdb's ``ligands.tsv`` that has both.

    make_gtopdb_relations() adds GtoPdb's InChIKeys to cliques directly (some aren't in UniChem), so their InChIs
    come from the same file. Values are double-quoted; an optional ``# GtoPdb Version`` line precedes the header.
    """
    with open(ligands_tsv) as inf:
        header = inf.readline()
        if header.startswith('"# GtoPdb Version'):
            header = inf.readline()
        columns = header.rstrip("\n").split("\t")
        key_index = columns.index('"InChIKey"')
        inchi_index = columns.index('"InChI"')
        for line in inf:
            fields = line.rstrip("\n").split("\t")
            inchikey = fields[key_index].strip('"')
            inchi = fields[inchi_index].strip('"')
            if inchikey and inchi:
                yield inchikey, inchi


def _standard_only(inchi_pairs, counts):
    """Pass on only standard InChIs (``InChI=1S/``), counting the rest in ``counts["non_standard_inchis_skipped"]``.

    Parent keys are only comparable between standard keys. UniChem's STANDARDINCHI column holds one InChI beta record
    (UCI 201259320, ``InChI=1B/612Li.Na.613H``); its key isn't one chemicalparent.split_inchikey() groups.
    """
    for inchikey, inchi in inchi_pairs:
        if not inchi.startswith(STANDARD_INCHI_PREFIX):
            counts["non_standard_inchis_skipped"] += 1
            continue
        yield inchikey, inchi


def _multi_component_chunks(inchi_pairs):
    """Batch the multi-component (InChIKey, InChI) pairs into lists of CHUNK_LINES.

    A key both sources give appears twice; readers of the components file deduplicate, which is cheaper than holding
    a set of every key here.
    """
    chunk = []
    for inchikey, inchi in inchi_pairs:
        if not is_multi_component(inchi):
            continue
        chunk.append((inchikey, inchi))
        if len(chunk) >= CHUNK_LINES:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def _split_one_at_a_time(pool, lines, item_timeout):
    """Split a chunk that timed out one InChI per task, so a single hanging InChI costs only itself.

    Returns (rows, failures, timed-out InChIKeys).
    """
    futures = [
        (inchikey, pool.schedule(_split_lines, args=[[(inchikey, inchi)]], timeout=item_timeout))
        for inchikey, inchi in lines
    ]
    rows, failures, timed_out = [], [], []
    for inchikey, future in futures:
        try:
            item_rows, item_failures = future.result()
        except TimeoutError:
            timed_out.append(inchikey)
            continue
        rows.extend(item_rows)
        failures.extend(item_failures)
    return rows, failures, timed_out


def write_inchi_components(
    unichem_structure_gz,
    gtopdb_ligands_tsv,
    outfile,
    processes,
    chunk_timeout=CHUNK_TIMEOUT_SECONDS,
    item_timeout=ITEM_TIMEOUT_SECONDS,
):
    """Write the components of every multi-component InChI in UniChem's ``structure.tsv.gz`` and GtoPdb's
    ``ligands.tsv`` to a TSV.

    Those are the two files clique InChIKeys come from (write_unichem_concords(), make_gtopdb_relations()), so
    every clique key has its InChI here, from the same release. PubChem's ``CID-InChI-Key.gz`` was tried first and
    lacked 1.6% of 2025dec11's clique keys, including 71,288 ChEMBL cliques. SMILES aren't used: the InChI is the
    exact string a clique's key hashes, while a source's SMILES may describe a different tautomer or charge.

    Columns are COMPONENTS_TSV_HEADER. An InChI RDKit can't split, or that takes longer than ``item_timeout`` seconds,
    is counted and left out, and a sample is logged; its record keeps its own key. Returns counts for the rule's
    metadata.

    Two guards keep this from taking the machine down, and both have done so without them:

    - **Bounded queue.** The pool gets processes * CHUNKS_IN_FLIGHT_PER_PROCESS chunks at a time. Feeding it the
      reader directly (``Pool.imap()``) queued the whole file -- reading is far faster than RDKit -- and on
      2026-11-10 that exhausted a 36 GB laptop.
    - **Timeouts that kill the worker.** RDKit's InChI parser never returns on some structures (the pentafoil knot,
      CID 53389302) and grows ~150 MB a minute while it runs; being C++, it can't be interrupted from Python. pebble
      kills a worker whose chunk passes ``chunk_timeout``; that chunk is then re-run one InChI per task with
      ``item_timeout`` each, so only the hanging InChI is lost.
    """
    ensure_parent_dir(outfile)
    counts = {
        "multi_component_inchis": 0,
        "component_rows": 0,
        "unparseable_inchis": 0,
        "timed_out_inchis": 0,
        "non_standard_inchis_skipped": 0,
    }
    failure_examples = []
    timeout_examples = []
    with open(outfile, "w", newline="") as outf, ProcessPool(max_workers=processes) as pool:
        writer = csv.writer(outf, delimiter="\t", lineterminator="\n")
        writer.writerow(COMPONENTS_TSV_HEADER)
        inchis = chain(read_unichem_inchis(unichem_structure_gz), read_gtopdb_inchis(gtopdb_ligands_tsv))
        inchis = _standard_only(inchis, counts)
        for batch in chunked(_multi_component_chunks(inchis), processes * CHUNKS_IN_FLIGHT_PER_PROCESS):
            futures = [(lines, pool.schedule(_split_lines, args=[lines], timeout=chunk_timeout)) for lines in batch]
            for lines, future in futures:
                try:
                    rows, failures = future.result()
                    timed_out = []
                except TimeoutError:
                    logger.warning(f"A chunk of {len(lines):,} InChIs timed out; re-running it one InChI at a time")
                    rows, failures, timed_out = _split_one_at_a_time(pool, lines, item_timeout)
                writer.writerows(rows)
                counts["component_rows"] += len(rows)
                counts["multi_component_inchis"] += len({row[0] for row in rows}) + len(failures) + len(timed_out)
                counts["unparseable_inchis"] += len(failures)
                counts["timed_out_inchis"] += len(timed_out)
                failure_examples.extend(failures[: max(0, MAX_FAILURE_EXAMPLES - len(failure_examples))])
                timeout_examples.extend(timed_out[: max(0, MAX_FAILURE_EXAMPLES - len(timeout_examples))])
    if failure_examples:
        logger.warning(
            f"RDKit could not split {counts['unparseable_inchis']:,} InChIs; those records keep their own keys. "
            f"Examples: {failure_examples}"
        )
    if timeout_examples:
        logger.warning(
            f"{counts['timed_out_inchis']:,} InChIs took over {item_timeout}s to split and were left out; those "
            f"records keep their own keys. Examples: {timeout_examples}"
        )
    logger.info(f"InChI components: {counts}")
    return counts


def read_component_decisions(filename):
    """Read the reviewed component list into {component parent key: "drop" or "keep"}.

    Raises on an unknown decision, a malformed key or a key listed twice, so a bad edit to the list fails loudly.
    """
    decisions = {}
    with open(filename, newline="") as inf:
        reader = csv.DictReader(inf, delimiter="\t")
        if reader.fieldnames != DECISIONS_TSV_HEADER:
            raise ValueError(f"{filename}: expected columns {DECISIONS_TSV_HEADER}, got {reader.fieldnames}")
        for row in reader:
            key = row["component_parent_key"]
            if INCHIKEY_PATTERN.match(key + "-N") is None:
                raise ValueError(f"{filename}: malformed component parent key {key!r}")
            if row["decision"] not in (DROP, KEEP):
                raise ValueError(f"{filename}: decision for {key} must be {DROP!r} or {KEEP!r}: {row['decision']!r}")
            if key in decisions:
                raise ValueError(f"{filename}: component {key} is listed twice")
            decisions[key] = row["decision"]
    return decisions


def resolve_parent(component_keys, decisions):
    """Return the parent key a multi-component record maps to, or None if it keeps its own key.

    :param component_keys: the record's component InChIKeys (bare, with protonation blocks).
    :param decisions: from read_component_decisions().
    """
    remaining = {parent_key(key) for key in component_keys}
    remaining = {key for key in remaining if decisions.get(key) != DROP}
    if len(remaining) != 1:
        return None
    return remaining.pop()


def write_salt_parents(components_tsv, decisions_tsv, outfile):
    """Write ``salt parent key -> parent key`` for every multi-component record the reviewed list resolves.

    The salt is keyed by its own parent key (its InChIKey without the protonation block), so every charge state of
    the salt follows the mapping even when only one of them has a multi-component InChI in the sources; a component's
    parent key doesn't depend on which component carries the protons, so all of them resolve alike.

    Streams the components file one record at a time (write_inchi_components() writes a record's components on
    consecutive rows), so memory stays flat. Records are counted, and written, once per source record (charge
    state and CID); chemicalparent.load_salt_parents() checks repeats agree. Returns counts for the rule's metadata.
    """
    from src.createcompendia.chemicalparent import SALT_PARENTS_TSV_HEADER

    decisions = read_component_decisions(decisions_tsv)
    counts = {"records": 0, "resolved": 0, "every_component_dropped": 0, "blocked": 0}
    drops = {key for key, decision in decisions.items() if decision == DROP}
    ensure_parent_dir(outfile)
    with open(components_tsv, newline="") as inf, open(outfile, "w", newline="") as outf:
        reader = csv.reader(inf, delimiter="\t")
        header = next(reader)
        if header != COMPONENTS_TSV_HEADER:
            raise ValueError(f"{components_tsv}: expected header {COMPONENTS_TSV_HEADER}, got {header}")
        writer = csv.writer(outf, delimiter="\t", lineterminator="\n")
        writer.writerow(SALT_PARENTS_TSV_HEADER)
        for inchikey, rows in groupby(reader, key=lambda row: row[0]):
            component_keys = [row[1] for row in rows]
            counts["records"] += 1
            parent = resolve_parent(component_keys, decisions)
            if parent is not None:
                writer.writerow([parent_key(inchikey), parent])
                counts["resolved"] += 1
            elif {parent_key(key) for key in component_keys} <= drops:
                counts["every_component_dropped"] += 1
            else:
                counts["blocked"] += 1
    logger.info(f"Salt parents: {counts}")
    return counts
