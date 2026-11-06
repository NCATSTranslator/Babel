"""Unit tests for src/synonyms/synonymconflation.py.

conflate_synonyms() merges the synonym records of cliques that a conflation file says are the same
thing: the lead clique's record is kept and the others' names, types, taxa and identifier counts are
folded into it, in the order the conflation file lists them. It drives two of Babel's most expensive
rules -- `geneprotein_conflated_synonyms` (15,719 s) and `drugchemical_conflated_synonyms`
(9,949 s) in the babel-1.18 benchmarks -- and had no tests before these.

The synonym and compendium records below are copied verbatim from a local anatomy build
(`babel_outputs/synonyms/AnatomicalEntity.txt.gz` and
`babel_outputs/compendia/AnatomicalEntity.txt`); their CURIEs are named in each constant so they
can be re-derived. Only the conflation file is authored here, because a conflation pairing anatomy
cliques does not occur in a real build -- it stands in for GeneProtein.txt, which has the same
`["primary", "secondary", ...]` JSONL shape.
"""

import gzip
import json

import pytest

from src.synonyms.synonymconflation import conflate_synonyms, merge_conflated_group

# UMLS:C0733999 "Scapular line" -- the conflation primary. Clique also holds FMA:14613.
SCAPULAR_LINE_SYNONYM = {
    "curie": "UMLS:C0733999",
    "names": ["Scapular line", "Linea scapularis"],
    "types": ["AnatomicalEntity", "PhysicalEssence", "OntologyClass", "NamedThing", "Entity"],
    "preferred_name": "Scapular line",
    "shortest_name_length": 13,
    "clique_identifier_count": 2,
    "taxa": [],
    "taxon_specific": False,
}
SCAPULAR_LINE_CLIQUE = {
    "type": "biolink:AnatomicalEntity",
    "ic": None,
    "identifiers": [
        {"i": "UMLS:C0733999", "l": "Scapular line", "d": [], "t": []},
        {"i": "FMA:14613", "l": "", "d": [], "t": []},
    ],
    "preferred_name": "Scapular line",
    "taxa": [],
}
# SCAPULAR_LINE_CLIQUE's second member, for tests that put it in a second clique too. Such a clique is authored,
# like the conflation file: a CURIE in two cliques is a build fault, so no build has one to copy.
FMA_14613 = SCAPULAR_LINE_CLIQUE["identifiers"][1]

# UMLS:C1182464 "Right thyrocervical artery" -- the conflation secondary. Clique also holds FMA:70347.
THYROCERVICAL_SYNONYM = {
    "curie": "UMLS:C1182464",
    "names": ["Right thyrocervical artery"],
    "types": ["AnatomicalEntity", "PhysicalEssence", "OntologyClass", "NamedThing", "Entity"],
    "preferred_name": "Right thyrocervical artery",
    "shortest_name_length": 26,
    "clique_identifier_count": 2,
    "taxa": [],
    "taxon_specific": False,
}
THYROCERVICAL_CLIQUE = {
    "type": "biolink:AnatomicalEntity",
    "ic": None,
    "identifiers": [
        {"i": "UMLS:C1182464", "l": "Right thyrocervical artery", "d": [], "t": []},
        {"i": "FMA:70347", "l": "", "d": [], "t": []},
    ],
    "preferred_name": "Right thyrocervical artery",
    "taxa": [],
}

# UMLS:C0450491 "LI15" -- named in no conflation, so it must pass through untouched.
UNCONFLATED_SYNONYM = {
    "curie": "UMLS:C0450491",
    "names": ["LI15", "LI15 (body structure)"],
    "types": ["AnatomicalEntity", "PhysicalEssence", "OntologyClass", "NamedThing", "Entity"],
    "preferred_name": "LI15",
    "shortest_name_length": 4,
    "clique_identifier_count": 1,
    "taxa": [],
    "taxon_specific": False,
}
UNCONFLATED_CLIQUE = {
    "type": "biolink:AnatomicalEntity",
    "ic": None,
    "identifiers": [{"i": "UMLS:C0450491", "l": "LI15", "d": [], "t": []}],
    "preferred_name": "LI15",
    "taxa": [],
}


def write_jsonl(path, records, compress=False):
    """Write `records` as JSONL, gzipped if `compress`, and return the path."""
    text = "".join(json.dumps(record) + "\n" for record in records)
    if compress:
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            handle.write(text)
    else:
        path.write_text(text)
    return path


def run_conflation(tmp_path, synonyms, cliques, conflations):
    """Run conflate_synonyms over the given records and return the output records."""
    synonyms_gz = write_jsonl(tmp_path / "synonyms.txt.gz", synonyms, compress=True)
    compendium = write_jsonl(tmp_path / "compendium.txt", cliques)
    conflation = write_jsonl(tmp_path / "conflation.txt", conflations)
    output = tmp_path / "conflated.txt.gz"

    conflate_synonyms([str(synonyms_gz)], [str(compendium)], [str(conflation)], str(output))

    with gzip.open(output, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


# CONFLATING SYNONYM RECORDS


@pytest.mark.unit
def test_synonyms_of_conflated_cliques_are_merged_into_the_lead_record(tmp_path):
    """Two conflated cliques should produce one record under the primary's CURIE, with the
    secondary's names appended after the primary's and the identifier counts summed."""
    records = run_conflation(
        tmp_path,
        [SCAPULAR_LINE_SYNONYM, THYROCERVICAL_SYNONYM],
        [SCAPULAR_LINE_CLIQUE, THYROCERVICAL_CLIQUE],
        [["UMLS:C0733999", "UMLS:C1182464"]],
    )

    assert len(records) == 1
    conflated = records[0]
    assert conflated["curie"] == "UMLS:C0733999"
    assert conflated["preferred_name"] == "Scapular line"
    # Primary's names first, in conflation order, then the secondary's.
    assert conflated["names"] == ["Scapular line", "Linea scapularis", "Right thyrocervical artery"]
    assert conflated["shortest_name_length"] == 13
    assert conflated["clique_identifier_count"] == 4
    assert conflated["taxon_specific"] is False
    # Types are the union in order of first appearance, minus OntologyClass.
    assert conflated["types"] == ["AnatomicalEntity", "PhysicalEssence", "NamedThing", "Entity"]


@pytest.mark.unit
def test_a_synonym_named_in_no_conflation_passes_through_unchanged(tmp_path):
    """A record whose CURIE appears in no conflation should be written out with the same content
    (re-serialised, not merged with anything) -- that is the path the overwhelming majority of records take."""
    records = run_conflation(
        tmp_path,
        [UNCONFLATED_SYNONYM, SCAPULAR_LINE_SYNONYM, THYROCERVICAL_SYNONYM],
        [UNCONFLATED_CLIQUE, SCAPULAR_LINE_CLIQUE, THYROCERVICAL_CLIQUE],
        [["UMLS:C0733999", "UMLS:C1182464"]],
    )

    passed_through = [record for record in records if record["curie"] == "UMLS:C0450491"]
    assert passed_through == [UNCONFLATED_SYNONYM]


@pytest.mark.unit
def test_a_synonym_keyed_on_a_non_leader_identifier_is_merged(tmp_path):
    """A synonym keyed on a clique member the conflation file does not name should still be folded
    into the conflated record, via the compendium that puts it in a conflated clique (#989).

    This used to be silently dropped: step 1.1 iterated a one-shot `map` twice, so the identifier the
    conflation file names was never registered against its clique and step 3 never expanded it.
    """
    fma_keyed = dict(THYROCERVICAL_SYNONYM, curie="FMA:70347", names=["Thyrocervical trunk"])
    records = run_conflation(
        tmp_path,
        [SCAPULAR_LINE_SYNONYM, fma_keyed],
        [SCAPULAR_LINE_CLIQUE, THYROCERVICAL_CLIQUE],
        [["UMLS:C0733999", "UMLS:C1182464"]],
    )

    assert len(records) == 1
    assert records[0]["curie"] == "UMLS:C0733999"
    assert records[0]["names"] == ["Scapular line", "Linea scapularis", "Thyrocervical trunk"]
    assert records[0]["clique_identifier_count"] == 4


@pytest.mark.unit
def test_two_conflation_ids_in_one_clique_merge_its_record_once(tmp_path):
    """When the conflation file names two members of the same clique, expanding each reaches the
    same synonym record; it should be merged once, not have its identifier count summed twice."""
    records = run_conflation(
        tmp_path,
        [SCAPULAR_LINE_SYNONYM],
        [SCAPULAR_LINE_CLIQUE],
        [["UMLS:C0733999", "FMA:14613"]],
    )

    assert len(records) == 1
    assert records[0]["clique_identifier_count"] == 2


@pytest.mark.unit
def test_two_conflation_lines_with_one_primary_are_both_merged_in_file_order(tmp_path):
    """Two conflation lines with the same primary ID map both secondaries to it. Both lines' records
    should be merged, in file order; `conflations` used to keep only the last line, so the earlier
    line's record was dropped."""
    records = run_conflation(
        tmp_path,
        [SCAPULAR_LINE_SYNONYM, THYROCERVICAL_SYNONYM, UNCONFLATED_SYNONYM],
        [SCAPULAR_LINE_CLIQUE, THYROCERVICAL_CLIQUE, UNCONFLATED_CLIQUE],
        [["UMLS:C0733999", "UMLS:C1182464"], ["UMLS:C0733999", "UMLS:C0450491"]],
    )

    assert len(records) == 1
    assert records[0]["names"] == [
        "Scapular line",
        "Linea scapularis",
        "Right thyrocervical artery",
        "LI15",
        "LI15 (body structure)",
    ]
    assert records[0]["clique_identifier_count"] == 5


@pytest.mark.unit
def test_a_clique_in_two_conflations_fails_the_rule(tmp_path):
    """A clique whose members are named by two different conflation lines can't be merged into one
    record: its synonym records would be split between two conflated records. That is a fault in the
    conflation file, so the rule fails and names the clique, rather than writing the split."""
    with pytest.raises(RuntimeError, match=r"UMLS:C0733999 in \['UMLS:C0450491', 'UMLS:C0733999'\]"):
        run_conflation(
            tmp_path,
            [SCAPULAR_LINE_SYNONYM, THYROCERVICAL_SYNONYM, UNCONFLATED_SYNONYM],
            [SCAPULAR_LINE_CLIQUE, THYROCERVICAL_CLIQUE, UNCONFLATED_CLIQUE],
            # UMLS:C0733999 and FMA:14613 are both members of SCAPULAR_LINE_CLIQUE.
            [["UMLS:C0733999", "UMLS:C1182464"], ["UMLS:C0450491", "FMA:14613"]],
        )


@pytest.mark.unit
def test_a_curie_in_two_conflated_cliques_of_different_groups_fails_the_rule(tmp_path):
    """Two conflated cliques of different groups that share a CURIE (a CURIE in two compendia) would
    both claim that CURIE's records, so this fails the rule too."""
    lone_with_fma = dict(UNCONFLATED_CLIQUE, identifiers=UNCONFLATED_CLIQUE["identifiers"] + [FMA_14613])
    with pytest.raises(RuntimeError, match="UMLS:C0450491 in"):
        run_conflation(
            tmp_path,
            [SCAPULAR_LINE_SYNONYM, THYROCERVICAL_SYNONYM, UNCONFLATED_SYNONYM],
            [SCAPULAR_LINE_CLIQUE, THYROCERVICAL_CLIQUE, lone_with_fma],
            [["UMLS:C0733999", "UMLS:C1182464"], ["UMLS:C0450491"]],
        )


@pytest.mark.unit
@pytest.mark.parametrize("sharer_first", [True, False], ids=["sharer-read-first", "sharer-read-last"])
def test_a_clique_sharing_a_curie_with_a_conflated_clique_is_not_pulled_in(tmp_path, sharer_first):
    """A clique the conflation file never names stays out of the group even if it shares a CURIE with
    a conflated clique, whichever of the two the compendia list first. Step 1.1 used to add a conflated
    clique's members to the index it was still matching against, so a clique read *after* it was pulled
    into the group through the shared CURIE, and one read before it was not."""
    lone_with_fma = dict(UNCONFLATED_CLIQUE, identifiers=UNCONFLATED_CLIQUE["identifiers"] + [FMA_14613])
    cliques = [SCAPULAR_LINE_CLIQUE, THYROCERVICAL_CLIQUE]
    cliques = [lone_with_fma, *cliques] if sharer_first else [*cliques, lone_with_fma]
    records = run_conflation(
        tmp_path,
        [SCAPULAR_LINE_SYNONYM, THYROCERVICAL_SYNONYM, UNCONFLATED_SYNONYM],
        cliques,
        [["UMLS:C0733999", "UMLS:C1182464"]],
    )

    assert [record["curie"] for record in records] == ["UMLS:C0450491", "UMLS:C0733999"]
    assert records[0] == UNCONFLATED_SYNONYM
    assert records[1]["clique_identifier_count"] == 4


@pytest.mark.unit
def test_two_records_for_one_clique_count_its_identifiers_once(tmp_path):
    """A synonym file should hold one record per clique. If a clique has records under both its leader
    and one of its members, both records' names should be merged, but the clique's identifiers should
    be counted once, not once per record."""
    fma_keyed = dict(THYROCERVICAL_SYNONYM, curie="FMA:70347", names=["Thyrocervical trunk"])
    records = run_conflation(
        tmp_path,
        [SCAPULAR_LINE_SYNONYM, THYROCERVICAL_SYNONYM, fma_keyed],
        [SCAPULAR_LINE_CLIQUE, THYROCERVICAL_CLIQUE],
        [["UMLS:C0733999", "UMLS:C1182464"]],
    )

    assert len(records) == 1
    assert records[0]["names"] == [
        "Scapular line",
        "Linea scapularis",
        "Right thyrocervical artery",
        "Thyrocervical trunk",
    ]
    # 2 (scapular line) + 2 (thyrocervical), not + 2 again for its second record.
    assert records[0]["clique_identifier_count"] == 4


@pytest.mark.unit
def test_a_curie_in_two_synonym_files_counts_its_identifiers_once(tmp_path):
    """The same synonym record read twice (a CURIE in two synonym files) should be merged once in
    effect: its identifiers counted once."""
    records = run_conflation(
        tmp_path,
        [SCAPULAR_LINE_SYNONYM, THYROCERVICAL_SYNONYM, THYROCERVICAL_SYNONYM],
        [SCAPULAR_LINE_CLIQUE, THYROCERVICAL_CLIQUE],
        [["UMLS:C0733999", "UMLS:C1182464"]],
    )

    assert len(records) == 1
    assert records[0]["clique_identifier_count"] == 4


@pytest.mark.unit
def test_a_group_whose_records_have_no_taxa_is_written(tmp_path):
    """A conflated group none of whose records carries `taxa` should be written with empty taxa, not
    crash the rule with a KeyError."""
    no_taxa = [
        {k: v for k, v in synonym.items() if k != "taxa"} for synonym in (SCAPULAR_LINE_SYNONYM, THYROCERVICAL_SYNONYM)
    ]
    records = run_conflation(
        tmp_path,
        no_taxa,
        [SCAPULAR_LINE_CLIQUE, THYROCERVICAL_CLIQUE],
        [["UMLS:C0733999", "UMLS:C1182464"]],
    )

    assert len(records) == 1
    assert records[0]["taxa"] == []
    assert records[0]["taxon_specific"] is False


@pytest.mark.unit
def test_a_record_the_conflation_order_does_not_reach_fails(tmp_path):
    """Step 1.1 gives a group only the members of cliques its listed IDs belong to, so expanding those
    IDs reaches every record step 2 gives the group. If the two ever disagree, merging should fail
    rather than drop the record or merge it out of order."""
    with pytest.raises(RuntimeError, match=r"does not reach its synonym records under \['UMLS:C0450491'\]"):
        merge_conflated_group(
            "UMLS:C0733999",
            ["UMLS:C0733999"],
            {"UMLS:C0733999": [SCAPULAR_LINE_SYNONYM], "UMLS:C0450491": [UNCONFLATED_SYNONYM]},
            {},
        )
