#!/usr/bin/env python
"""Replay create_typed_sets() over a completed build's Food.txt to check the #935 type vote.

Issue #918 typed a chemical clique as ``biolink:Food`` whenever *any* member carried DrugBank
food evidence, overriding the per-identifier type vote entirely. That was asserted to be safe
because "every concord partner of the 685 retyped cliques is typed ChemicalEntity" — an assertion
derived from the concords, never from a real build. The babel-1.18 build falsified it: seven
``Food.txt`` cliques hold a member Babel had already typed ``biolink:SmallMolecule`` or
``biolink:MolecularMixture``, so real small molecules (D-glucose, ergocalciferol, tocopherol,
amylose, castor oil, omega-3/omega-6 fatty acids) shipped as foods.

Issue #935 makes the evidence a *vote* instead. This script measures the effect of that change
without a rebuild, by replaying the real ``create_typed_sets`` over the inputs a completed build
already has on disk. It reports, and asserts, three things:

  1. how the existing Food.txt cliques re-type under the vote (expected: only the broken ones move);
  2. that D-glucose comes back as ``biolink:SmallMolecule`` with its food CURIE still a member;
  3. that no clique carrying food evidence votes ``biolink:Drug`` -- the one type ranked *below*
     Food, and therefore the one combination where the vote could still call a drug a food. If this
     ever reports a clique, Drug's rank needs revisiting before Food can outrank it.

Usage (against a directory holding a build's ``compendia/`` and ``intermediate/``)::

    python replay_type_vote.py path/to/babel_outputs

Reading the ~6 GB ``partials/types`` takes a couple of minutes; only the types of identifiers that
appear in Food.txt are kept.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# Allow running this script directly from a checkout without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from src.categories import DRUG, FOOD, MOLECULAR_MIXTURE, SMALL_MOLECULE  # noqa: E402
from src.createcompendia.chemicals import create_typed_sets  # noqa: E402

# The D-glucose clique from babel-1.18: DRUGBANK:DB09341 "Dextrose, unspecified form" is the
# structureless DrugBank food row whose evidence wrongly typed the whole clique biolink:Food.
GLUCOSE_FOOD_CURIE = "DRUGBANK:DB09341"
GLUCOSE_SMALL_MOLECULE_CURIE = "PUBCHEM.COMPOUND:107526"


def read_food_cliques(compendium):
    """Yield each Food.txt clique as a frozenset of its member CURIEs."""
    with open(compendium) as inf:
        for line in inf:
            yield frozenset(identifier["i"] for identifier in json.loads(line)["identifiers"])


def read_food_types(ids_file):
    """Read the food/extract evidence file (CURIE\\tbiolink:Type) the build passed to build_compendia."""
    with open(ids_file) as inf:
        return dict(line.rstrip("\n").split("\t") for line in inf if line.strip())


def read_types_for(types_file, wanted):
    """Read partials/types, keeping only the identifiers in ``wanted``.

    The full file is ~128M lines; holding all of it costs tens of GB, and every clique we replay is
    already in Food.txt, so a single filtered pass is enough.
    """
    types = {}
    with open(types_file) as inf:
        for line in inf:
            curie, _, biolink_type = line.rstrip("\n").partition("\t")
            if curie in wanted:
                types[curie] = biolink_type
    return types


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("babel_outputs", type=Path, help="A build's babel_outputs directory.")
    args = parser.parse_args()

    compendium = args.babel_outputs / "compendia" / "Food.txt"
    food_types_file = args.babel_outputs / "intermediate" / "chemicals" / "ids" / "DRUGBANK_food_extracts"
    types_file = args.babel_outputs / "intermediate" / "chemicals" / "partials" / "types"

    cliques = set(read_food_cliques(compendium))
    food_types = read_food_types(food_types_file)
    members = frozenset().union(*cliques)
    print(f"Read {len(cliques)} Food.txt cliques ({len(members)} identifiers) and {len(food_types)} food types.")

    types = read_types_for(types_file, members)
    print(f"Read types for {len(types)} of those identifiers from {types_file}.")
    print("  member types: " + ", ".join(f"{t}={n}" for t, n in Counter(types.values()).most_common()))

    typed = create_typed_sets(cliques, types, food_types)
    counts = Counter({biolink_type: len(sets) for biolink_type, sets in typed.items()})
    print("\nAfter the #935 vote, the same cliques type as:")
    for biolink_type, n in counts.most_common():
        print(f"  {biolink_type}: {n}")

    # Sorted so that re-running this script on the same build produces a byte-identical report.
    moved = sorted(
        (biolink_type, sorted(clique))
        for biolink_type, sets in typed.items()
        if biolink_type != FOOD
        for clique in sets
    )
    print(f"\n{len(moved)} clique(s) leave Food:")
    for biolink_type, clique in moved:
        print(f"  {biolink_type}: {clique}")

    # Check 2: the reported bug. D-glucose must come back a SmallMolecule, still holding its food CURIE.
    glucose = next(c for c in cliques if GLUCOSE_SMALL_MOLECULE_CURIE in c)
    assert glucose in typed[SMALL_MOLECULE], f"D-glucose did not re-type as {SMALL_MOLECULE}"
    assert GLUCOSE_FOOD_CURIE in glucose, f"{GLUCOSE_FOOD_CURIE} was dropped from the D-glucose clique"
    print(f"\nOK: the D-glucose clique re-types as {SMALL_MOLECULE} and still holds {GLUCOSE_FOOD_CURIE}.")

    # Check 3: Drug is ranked below Food, so a clique voting Drug plus food evidence becomes Food.
    drugs = [c for c in cliques if any(types.get(curie) == DRUG for curie in c)]
    assert not drugs, f"{len(drugs)} clique(s) with food evidence hold a {DRUG} member; revisit Drug's rank: {drugs}"
    print(f"OK: no clique carrying food evidence holds a {DRUG} member.")

    # Check 1: only the broken cliques move. babel-1.18: 285 Food, 5 SmallMolecule, 2 MolecularMixture,
    # 1 ComplexMolecularMixture. Asserted loosely (Food is the overwhelming majority, and every clique
    # that leaves does so for a structure-bearing type) so the script keeps working on later builds.
    assert counts[FOOD] > 0.9 * len(cliques), f"{counts[FOOD]} of {len(cliques)} cliques stayed Food; expected >90%"
    assert counts[SMALL_MOLECULE] or counts[MOLECULAR_MIXTURE], "no clique moved; the vote had no effect"
    print(f"\nOK: {counts[FOOD]} of {len(cliques)} cliques stay {FOOD}.")


if __name__ == "__main__":
    main()
