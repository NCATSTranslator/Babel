# Tests for src/createcompendia/transcript.py — the biolink:Transcript compendium.
#
# Offline unit tests over a real gene2ensembl.gz fixture (tests/data/gene2ensembl_sample.gz, verbatim
# rows for tax_id 3486 / Lupinus albus; the parser is species-agnostic). Sections:
#   IDS EXTRACTION — write_transcript_ids (unversioned ENST, '-' skip, dedup)
#   CONCORD        — build_transcript_ensembl_relationships (versioned<->unversioned)
#   CLIQUE BUILD   — compute_cliques_for_impact_report (the versioned form gloms into the unversioned)
import gzip
import os

import pytest

from src.createcompendia.transcript import (
    build_transcript_ensembl_relationships,
    compute_cliques_for_impact_report,
    write_transcript_ids,
)

FIXTURE = os.path.join(os.path.dirname(__file__), "data", "gene2ensembl_sample.gz")


# COLUMN LAYOUT


@pytest.mark.unit
def test_gene2ensembl_fixture_should_have_the_transcript_column_where_expected():
    """Pin the gene2ensembl.gz column layout the parser relies on: column 4 is Ensembl_rna_identifier.
    Guards against NCBI silently reordering columns (cf. the complexportal header-column guard)."""
    with gzip.open(FIXTURE, "rt") as inf:
        header = inf.readline().rstrip("\n").split("\t")
    assert header[4] == "Ensembl_rna_identifier"


# IDS EXTRACTION


@pytest.mark.unit
def test_write_transcript_ids_should_extract_unversioned_ensembl_transcripts(tmp_path):
    """write_transcript_ids emits the unversioned ENST (version stripped) typed biolink:Transcript;
    the versioned form is left to the concord, not the ids file."""
    outfile = tmp_path / "ids"
    write_transcript_ids(FIXTURE, str(outfile))
    rows = [line.split("\t") for line in outfile.read_text().splitlines()]
    ids = {curie for curie, _type in rows}
    assert ids == {"ENSEMBL:ENSLUPT00005032457", "ENSEMBL:ENSLUPT00005035054"}
    assert all(biolink_type == "biolink:Transcript" for _curie, biolink_type in rows)
    # No versioned id leaks into the ids file (the '.N' suffix is stripped).
    assert not any("." in curie.split(":")[1] for curie in ids)


@pytest.mark.unit
def test_write_transcript_ids_should_skip_rows_lacking_a_transcript(tmp_path):
    """Rows whose Ensembl_rna_identifier is '-' (the gene has no Ensembl transcript) yield no id:
    the fixture's 4 data rows include 2 '-' rows, so exactly 2 transcript ids are written."""
    outfile = tmp_path / "ids"
    write_transcript_ids(FIXTURE, str(outfile))
    assert len(outfile.read_text().splitlines()) == 2


@pytest.mark.unit
def test_write_transcript_ids_should_dedup_a_repeated_transcript(tmp_path):
    """A transcript appearing in more than one row is written once. gene2ensembl normally lists one
    current version per transcript, so this is defensive; the input is a real fixture row duplicated
    (not a fabricated row shape)."""
    with gzip.open(FIXTURE, "rt") as inf:
        lines = inf.read().splitlines()
    header, first_row = lines[0], lines[1]  # first data row is a real versioned transcript
    dup_gz = tmp_path / "dup.gz"
    with gzip.open(dup_gz, "wt", encoding="utf-8") as outf:
        outf.write("\n".join([header, first_row, first_row]) + "\n")

    outfile = tmp_path / "ids"
    write_transcript_ids(str(dup_gz), str(outfile))
    assert outfile.read_text().splitlines() == ["ENSEMBL:ENSLUPT00005032457\tbiolink:Transcript"]


# CONCORD


@pytest.mark.unit
def test_build_transcript_ensembl_relationships_should_link_versioned_to_unversioned(tmp_path):
    """Each versioned ENST gets an 'eq' edge to its unversioned form (issue #72 pattern); the '-'
    rows produce no edge."""
    outfile = tmp_path / "concord"
    metadata = tmp_path / "meta.yaml"
    build_transcript_ensembl_relationships(FIXTURE, str(outfile), str(metadata))

    from tests.conftest import assert_concordance_file_valid

    rows = assert_concordance_file_valid(str(outfile))
    edges = {(row[0], row[1], row[2]) for row in rows}
    assert edges == {
        ("ENSEMBL:ENSLUPT00005032457.1", "eq", "ENSEMBL:ENSLUPT00005032457"),
        ("ENSEMBL:ENSLUPT00005035054.1", "eq", "ENSEMBL:ENSLUPT00005035054"),
    }


@pytest.mark.unit
def test_build_transcript_ensembl_relationships_should_write_provenance_metadata(tmp_path):
    """The concord provenance YAML is written alongside the concord file."""
    outfile = tmp_path / "concord"
    metadata = tmp_path / "meta.yaml"
    build_transcript_ensembl_relationships(FIXTURE, str(outfile), str(metadata))
    assert metadata.exists()
    assert "gene2ensembl" in metadata.read_text()


# CLIQUE BUILD


@pytest.mark.unit
def test_compute_cliques_should_merge_versioned_into_unversioned_transcript(tmp_path):
    """The versioned<->unversioned concord gloms the versioned ENST into the unversioned id's clique,
    so a versioned query normalizes into the same (biolink:Transcript) clique."""
    ids_file = tmp_path / "ids"
    concord_file = tmp_path / "concord"
    metadata = tmp_path / "meta.yaml"
    write_transcript_ids(FIXTURE, str(ids_file))
    build_transcript_ensembl_relationships(FIXTURE, str(concord_file), str(metadata))

    dicts, types = compute_cliques_for_impact_report([str(concord_file)], [str(ids_file)])

    target = "ENSEMBL:ENSLUPT00005032457"
    clique = next(members for members in dicts.values() if target in members)
    assert "ENSEMBL:ENSLUPT00005032457.1" in clique  # the versioned form merged in
    assert types[target] == "biolink:Transcript"


@pytest.mark.unit
def test_compute_cliques_should_keep_distinct_transcripts_in_separate_cliques(tmp_path):
    """Two unrelated transcripts stay in separate cliques (no spurious merge)."""
    ids_file = tmp_path / "ids"
    concord_file = tmp_path / "concord"
    metadata = tmp_path / "meta.yaml"
    write_transcript_ids(FIXTURE, str(ids_file))
    build_transcript_ensembl_relationships(FIXTURE, str(concord_file), str(metadata))

    dicts, _types = compute_cliques_for_impact_report([str(concord_file)], [str(ids_file)])
    # dicts is a union-find: deduplicate aliased clique sets the same way build_compendia does.
    cliques = set(frozenset(members) for members in dicts.values())
    # Each transcript (unversioned + its versioned form) is its own 2-member clique.
    assert sorted(len(clique) for clique in cliques) == [2, 2]
