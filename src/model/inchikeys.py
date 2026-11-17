"""How two InChIKeys relate: the same structure, a different charge, a different stereo layer, or a different skeleton.

Chemical cliques form on an exact InChIKey, so two records of "the same drug" that differ in any block of
their keys end up in different cliques. Which block differs says why, and decides what can be done about it:

- the **first block** (14 characters) hashes the connectivity, the molecular skeleton;
- the **second block** (10 characters) hashes the stereochemistry and isotope layers, then a standard flag and
  a version letter. ``UHFFFAOYSA`` is the hash of an empty layer, i.e. a structure with no stereo specified;
- the **third block** (one character) is the protonation flag (``N`` neutral, ``M``/``O``/… charged).

A different second block is usually a different stereoisomer, but can also be an isotope-labelled form
(ethanol-d6 shares ethanol's skeleton), which the key alone cannot tell apart; #1173 notes this. Reading
the InChI's ``/i`` layer would.

The relations map onto where such pairs are tracked: a stereo-less record beside the drug is #1232's
conflation rule, a charge state is #1214's ChemicalParent conflation, two different specified structures
for one drug are #1208.
"""

import enum

from src.util import Text

# The second InChIKey block of a structure with no stereo (and no isotope) layer: the hash of an empty layer,
# plus the standard flag S and version A. It is the same for every such structure.
STEREO_UNSPECIFIED_BLOCK = "UHFFFAOYSA"


class InchikeyRelation(enum.StrEnum):
    """How two InChIKeys relate, from most to least alike. The value is a short description for reports."""

    IDENTICAL = "identical InChIKey"
    CHARGE_ONLY = "same structure, different protonation"
    ONE_STEREO_UNSPECIFIED = "same skeleton; one has no stereo layer"
    DIFFERENT_STEREO = "same skeleton; different stereo layers"
    DIFFERENT_SKELETON = "different skeleton"
    MISSING = "at least one has no InChIKey"


def split_inchikey(key: str) -> tuple[str, str, str]:
    """Split an InChIKey, with or without an ``INCHIKEY:`` prefix, into its three blocks.

    Raises ``ValueError`` for anything that isn't three dash-separated blocks of 14, 10 and 1 characters.
    """
    local_id = Text.un_curie(key) if ":" in key else key
    blocks = local_id.split("-")
    if len(blocks) != 3 or [len(b) for b in blocks] != [14, 10, 1]:
        raise ValueError(f"Not an InChIKey: {key!r}")
    return blocks[0], blocks[1], blocks[2]


def classify_inchikey_pair(a: str | None, b: str | None) -> InchikeyRelation:
    """How InChIKey ``a`` relates to ``b``; either may be ``None`` (a clique with no structure)."""
    if not a or not b:
        return InchikeyRelation.MISSING
    skeleton_a, stereo_a, charge_a = split_inchikey(a)
    skeleton_b, stereo_b, charge_b = split_inchikey(b)
    if skeleton_a != skeleton_b:
        return InchikeyRelation.DIFFERENT_SKELETON
    if stereo_a != stereo_b:
        if STEREO_UNSPECIFIED_BLOCK in (stereo_a, stereo_b):
            return InchikeyRelation.ONE_STEREO_UNSPECIFIED
        return InchikeyRelation.DIFFERENT_STEREO
    if charge_a != charge_b:
        return InchikeyRelation.CHARGE_ONLY
    return InchikeyRelation.IDENTICAL
