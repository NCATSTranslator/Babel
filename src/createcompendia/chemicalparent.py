"""Build the ChemicalParent conflation: group chemical cliques that are one parent compound in different forms.

Two rules from issue #1173 decide the groups, both read off a clique's ``INCHIKEY:`` members.

**Charge states (rule 1).** An InChIKey has three blocks, ``XXXXXXXXXXXXXX-YYYYYYYYFV-P``: a 14-character hash of
the connectivity layer, a block hashing the remaining layers (stereo, isotopes) followed by a standard flag and a
version character, and a single protonation character. Two standard InChIKeys that differ *only* in that last
character describe the same molecule with protons added or removed -- valproic acid (``-N``) and valproate (``-M``),
folic acid and folate(2-). The key without its protonation block is the clique's *parent key*.

**Salts and hydrates (rule 3).** A salt or hydrate is a multi-component structure (fluoxetine hydrochloride is
``C17H18F3NO.ClH``), so its InChIKey hashes every component and shares nothing with its parent's. Such a record's
parent key is instead the parent key of the one component left after dropping the reviewed counterions and solvents
(``src/createcompendia/inchi_components.py``, ``input_data/chemical_parent_components.tsv``). The rule
``chemicalparent_salt_parents`` writes those mappings, keyed by the salt's own parent key so that every charge
state of a salt follows it -- PubChem often has a multi-component InChI for only one of them. A clique whose own
parent key has a mapping uses the mapped parent key instead.

Cliques sharing a parent key form a group. Within a group, a clique that reached the parent key directly leads one
that reached it through a salt, then a neutral (``-N``) form leads charged ones; see order_group().

The second InChIKey block stays in the parent key, so stereoisomers (dexamethasone/betamethasone) and
isotope-labelled forms never group. #1173's rule 2 (stereo-unspecified to specified) is not implemented.

A clique takes part only through its own ``INCHIKEY:`` members. ``glom()`` restricts INCHIKEY to one per clique,
but a few cliques still carry several; such a clique is grouped when all its keys share one parent key, and is
otherwise left out and counted, rather than guessing which of its structures it "is".
"""

import csv
import json
import re
from array import array
from collections import defaultdict

import numpy as np

from src.createcompendia.drugchemical import conflation_member_sort_key
from src.metadata.provenance import write_metadata
from src.prefixes import INCHIKEY
from src.util import ensure_parent_dir, get_logger

logger = get_logger(__name__)

# A standard InChIKey: 14-letter connectivity hash, 8-letter hash of the other layers, the standard/non-standard
# flag, the version character, and the protonation character. The parent key is everything before the final
# "-P", so the second block (stereo and isotope layers) stays in it -- see the module docstring for why.
INCHIKEY_PATTERN = re.compile(r"^([A-Z]{14}-[A-Z]{8}[SN][A-Z])-([A-Z])$")

# Any InChIKey-shaped string. A key of this shape that INCHIKEY_PATTERN rejects is well formed but not from InChI v1's
# standard or non-standard algorithm: UniChem's one InChI beta record (UCI 201259320, "InChI=1B/612Li.Na.613H")
# has key MNCFTHPAOBNIAB-UHFFFAOYBA-N. Its parent key isn't comparable with v1 keys, so it is skipped, not grouped.
INCHIKEY_SHAPE = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")

# The protonation character of a neutral structure. Within a group the neutral form leads the conflation, since it
# is the parent the other forms are charged versions of; "N" is the InChIKey spec's value for zero protons added.
NEUTRAL_PROTONATION_FLAG = "N"

# Header of the salt-parents file written by inchi_components.write_salt_parents().
SALT_PARENTS_TSV_HEADER = ["salt_parent_key", "parent_key"]


def split_inchikey(curie):
    """Split an ``INCHIKEY:`` CURIE into (parent key, protonation character), or None for a non-v1 key.

    The parent key is the InChIKey without its final ``-P`` block. A well-formed key that isn't from InChI v1
    (see INCHIKEY_SHAPE) returns None, and its clique is grouped by its other keys or not at all. Raises ValueError
    for anything that is not a well-formed InChIKey CURIE: a malformed key in a compendium is a source bug to fix,
    not a clique to skip.
    """
    prefix, _, local_id = curie.partition(":")
    if prefix != INCHIKEY:
        raise ValueError(f"Not an {INCHIKEY} CURIE: {curie!r}")
    match = INCHIKEY_PATTERN.match(local_id)
    if match is None:
        if INCHIKEY_SHAPE.match(local_id):
            return None
        raise ValueError(f"Malformed InChIKey CURIE: {curie!r}")
    return match.group(1), match.group(2)


def grouping_key(curie, salt_parents):
    """Return (parent key, protonation character, reached through a salt) for one ``INCHIKEY:`` CURIE, or None.

    A key whose parent key is in ``salt_parents`` (salt parent key -> parent key) groups under the mapped parent
    key; any other under its own. The protonation character is the key's own either way. None for a non-v1 key.
    """
    split = split_inchikey(curie)
    if split is None:
        return None
    parent, flag = split
    salt_parent = salt_parents.get(parent)
    if salt_parent is not None:
        return salt_parent, flag, True
    return parent, flag, False


def parent_key_for_clique(inchikey_curies, salt_parents=None):
    """Return (parent key, protonation flags, via salt) for one clique's INCHIKEY members, or None.

    A clique with no v1 InChIKey has no structure to group on. A clique whose InChIKeys have more than one parent key
    contains several structures, and we don't pick one. ``via salt`` is True when every key reached the parent key
    through ``salt_parents``: a clique holding the parent compound's own key is a direct member even if it also
    holds a salt's.
    """
    if not inchikey_curies:
        return None
    salt_parents = salt_parents or {}
    parents = set()
    flags = set()
    via_salt = True
    for curie in inchikey_curies:
        key = grouping_key(curie, salt_parents)
        if key is None:
            continue
        parent, flag, through_salt = key
        parents.add(parent)
        flags.add(flag)
        via_salt = via_salt and through_salt
    if len(parents) != 1:
        return None
    return parents.pop(), frozenset(flags), via_salt


def grouping_parents(inchikey_curies, salt_parents):
    """The set of grouping parent keys of a clique's v1 InChIKeys (non-v1 keys are skipped)."""
    keys = (grouping_key(curie, salt_parents) for curie in inchikey_curies)
    return {key[0] for key in keys if key is not None}


def group_cliques_by_parent_key(clique_inchikeys, salt_parents=None):
    """Group clique leaders that share a parent key.

    :param clique_inchikeys: an iterable of (clique leader, list of the clique's INCHIKEY CURIEs). It may be every
        InChIKey clique or any superset of the cliques that can group (see find_shared_parent_key_hashes()).
    :param salt_parents: salt parent key -> parent key for resolved salts and hydrates (see load_salt_parents()).
    :return: (groups, counts). ``groups`` maps a parent key to the list of (leader, protonation flags, via salt)
        sharing it, for parent keys shared by two or more cliques, in input order. ``counts`` records how many
        cliques were considered and how many were left out for carrying several structures.
    """
    by_parent = defaultdict(list)
    counts = defaultdict(int)
    for leader, inchikey_curies in clique_inchikeys:
        counts["candidate_cliques"] += 1
        if all(split_inchikey(curie) is None for curie in inchikey_curies):
            counts["cliques_without_v1_inchikey"] += 1
            continue
        result = parent_key_for_clique(inchikey_curies, salt_parents)
        if result is None:
            counts["cliques_skipped_multiple_parent_keys"] += 1
            logger.debug("Skipping %s: its InChIKeys have several parent keys: %s", leader, inchikey_curies)
            continue
        if len(inchikey_curies) > 1:
            counts["cliques_with_several_keys_one_parent"] += 1
        parent, flags, via_salt = result
        by_parent[parent].append((leader, flags, via_salt))

    groups = {parent: members for parent, members in by_parent.items() if len(members) > 1}
    counts["groups"] = len(groups)
    counts["cliques_in_groups"] = sum(len(members) for members in groups.values())
    counts["cliques_in_groups_via_salt"] = sum(
        1 for members in groups.values() for _, _, via_salt in members if via_salt
    )
    counts["groups_with_neutral_member"] = sum(
        1
        for members in groups.values()
        if any(NEUTRAL_PROTONATION_FLAG in flags and not via_salt for _, flags, via_salt in members)
    )
    return groups, dict(counts)


def load_salt_parents(filename):
    """Read the salt-parents file into ({salt parent key: parent key}, set of conflicting salt parent keys).

    A salt parent key appears once per source record (each charge state) that resolved, and normally every one
    gives the same parent. Rarely they disagree: for nitrobenzene with ammonia, UniChem's ``-N`` record (UCI
    50179722) resolves to nitrobenzene, but in the ``-O`` record (UCI 60606567) RDKit puts the extra proton on the
    nitrobenzene, a cation with a different parent key (25 of 4.66M salt parent keys from UniChem, 2026-11-18). The parent is then ambiguous, so
    such a salt is left out -- it keeps its own key -- and returned in the conflict set for the metadata. A
    conflict can only remove a mapping, never produce a wrong one.
    """
    salt_parents = {}
    conflicting = set()
    with open(filename, newline="") as inf:
        reader = csv.reader(inf, delimiter="\t")
        header = next(reader)
        if header != SALT_PARENTS_TSV_HEADER:
            raise ValueError(f"{filename}: expected header {SALT_PARENTS_TSV_HEADER}, got {header}")
        for salt_parent_key, parent in reader:
            if salt_parents.setdefault(salt_parent_key, parent) != parent:
                conflicting.add(salt_parent_key)
    for salt_parent_key in conflicting:
        del salt_parents[salt_parent_key]
    if conflicting:
        logger.warning(
            f"{len(conflicting):,} salt parent keys resolve to different parents in different source records and "
            f"were left out. Examples: {sorted(conflicting)[:10]}"
        )
    logger.info(f"Loaded {len(salt_parents):,} salt and hydrate parent keys from {filename}")
    return salt_parents, conflicting


# Finds each INCHIKEY identifier in a compendium line without parsing the JSON. Compendium lines are written by
# jsonlines, so a quote inside a label or description is escaped and can't produce a false ``"i": "`` match.
# Pass 2 parses every candidate line properly and checks this regex found the same keys.
INCHIKEY_IDENTIFIER_PATTERN = re.compile(r'"i":\s*"(INCHIKEY:[^"]*)"')


def parent_key_hash(parent_key):
    """A 64-bit hash of a parent key. Only compared within one process, so Python's salted str hash is fine."""
    return hash(parent_key)


def find_shared_parent_key_hashes(compendium_filenames, salt_parents):
    """Pass 1: return (hashes of parent keys that two or more cliques share, number of InChIKey cliques).

    The chemical compendia hold about 116 million InChIKey cliques (2025dec11) and only a few million of them
    group, so holding every clique's key and leader in a dict would take tens of GB. Instead this keeps one 8-byte
    hash per clique in an array and finds the repeated ones with a sort. A hash collision only makes a clique a
    candidate; group_cliques_by_parent_key() compares the actual keys.
    """
    hashes = array("q")
    clique_count = 0
    for filename in compendium_filenames:
        logger.info(f"Pass 1: hashing InChIKey parent keys in {filename}")
        with open(filename) as compendiumf:
            for line in compendiumf:
                inchikeys = INCHIKEY_IDENTIFIER_PATTERN.findall(line)
                if not inchikeys:
                    continue
                clique_count += 1
                for parent in grouping_parents(inchikeys, salt_parents):
                    hashes.append(parent_key_hash(parent))
    ordered = np.sort(np.frombuffer(hashes, dtype=np.int64))
    repeated = np.unique(ordered[1:][ordered[1:] == ordered[:-1]])
    logger.info(f"Pass 1: {clique_count:,} InChIKey cliques, {len(repeated):,} shared parent-key hashes")
    return set(repeated.tolist()), clique_count


def read_candidate_cliques(compendium_filenames, shared_hashes, salt_parents):
    """Pass 2: yield (leader, INCHIKEY CURIEs, information content, clique size) for each clique that may group.

    A clique is a candidate when any of its InChIKeys has a grouping key whose hash is in ``shared_hashes``.
    """
    for filename in compendium_filenames:
        logger.info(f"Pass 2: reading candidate cliques from {filename}")
        with open(filename) as compendiumf:
            for line in compendiumf:
                inchikeys = INCHIKEY_IDENTIFIER_PATTERN.findall(line)
                if not any(
                    parent_key_hash(parent) in shared_hashes for parent in grouping_parents(inchikeys, salt_parents)
                ):
                    continue
                clique = json.loads(line)
                identifiers = clique["identifiers"]
                parsed = [ident["i"] for ident in identifiers if ident["i"].startswith(INCHIKEY + ":")]
                if sorted(parsed) != sorted(inchikeys):
                    raise RuntimeError(
                        f"INCHIKEY_IDENTIFIER_PATTERN found {inchikeys} in a line of {filename} whose JSON has "
                        f"{parsed}; pass 1 may have missed cliques. Line starts: {line[:200]!r}"
                    )
                yield identifiers[0]["i"], parsed, clique.get("ic"), len(identifiers)


def order_group(members, clique_info, prefix_sort_order):
    """Order one group's (leader, flags, via salt) members; the first leads the conflation.

    Members reached directly come before those reached through a salt, so fluoxetine leads fluoxetine
    hydrochloride even though both InChIKeys end ``-N``. Then the neutral form leads the charged ones, and the rest
    follow ``drugchemical.conflation_member_sort_key()``. ``clique_info`` maps a leader to (information content,
    clique size).
    """

    def sort_key(member):
        leader, flags, via_salt = member
        ic, size = clique_info[leader]
        return (via_salt, NEUTRAL_PROTONATION_FLAG not in flags) + conflation_member_sort_key(
            leader, prefix_sort_order, ic, size
        )

    return [leader for leader, _, _ in sorted(members, key=sort_key)]


def build_conflation(chemical_compendia, salt_parents_filename, prefix_sort_order, outfilename, metadata_yaml):
    """Write the ChemicalParent conflation file: one JSON list of clique leaders per group.

    Reads the chemical compendia twice (see find_shared_parent_key_hashes() for why). Groups are written in
    parent-key order so the file is reproducible.
    """
    salt_parents, conflicting_salt_parents = load_salt_parents(salt_parents_filename)
    shared_hashes, inchikey_clique_count = find_shared_parent_key_hashes(chemical_compendia, salt_parents)

    clique_info = {}

    def candidates():
        for leader, inchikeys, ic, size in read_candidate_cliques(chemical_compendia, shared_hashes, salt_parents):
            clique_info[leader] = (ic, size)
            yield leader, inchikeys

    groups, counts = group_cliques_by_parent_key(candidates(), salt_parents)
    counts = {
        "cliques_with_inchikey": inchikey_clique_count,
        "salt_parent_keys": len(salt_parents),
        "salt_parent_keys_conflicting": len(conflicting_salt_parents),
        **counts,
    }
    logger.info(f"ChemicalParent counts: {counts}")

    ensure_parent_dir(outfilename)
    with open(outfilename, "w") as outf:
        for parent in sorted(groups):
            outf.write(json.dumps(order_group(groups[parent], clique_info, prefix_sort_order)) + "\n")

    write_metadata(
        metadata_yaml,
        typ="conflation",
        name="chemicalparent.build_conflation()",
        description="Build the ChemicalParent conflation: chemical cliques whose InChIKeys share a parent key, "
        "differing only in protonation (charge state) or reaching it through a salt or hydrate.",
        sources=[
            {"type": "Babel", "name": "Chemical compendia", "filenames": list(chemical_compendia)},
            {"type": "Babel", "name": "Salt and hydrate parent keys", "filenames": [salt_parents_filename]},
        ],
        counts=counts,
    )
