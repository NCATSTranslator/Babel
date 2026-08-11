# Tests for src/datahandlers/gtdb.py — GTDB taxonomy ingest for the taxon compendium.
#
# Offline unit tests over a verbatim GTDB bac120_metadata.tsv fixture (all 113 columns, 3 real genome
# rows; tests/data/gtdb_metadata_sample.tsv). The fixture rows are the genomes RS_GCF_027889305.1,
# GB_GCA_947493065.1, and GB_GCA_949388335.1 (re-derive by accession). The parser reads columns by name,
# so the full-width header is exercised. Sections:
#   TAXONOMY PARSING — parse_gtdb_taxonomy (rank splitting, spaces->underscores, label spacing)
#   LABELS           — write_gtdb_labels (one label per unique taxon, all ranks, dedup)
#   CONCORD          — build_gtdb_relationships (species-rank GTDB <-> NCBITaxon only)
import os

import pytest

from src.datahandlers.gtdb import (
    _taxonomy_and_taxid_indices,
    build_gtdb_relationships,
    parse_gtdb_taxonomy,
    write_gtdb_labels,
)

FIXTURE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "gtdb_metadata_sample.tsv")


# TAXONOMY PARSING


@pytest.mark.unit
def test_parse_gtdb_taxonomy_should_split_all_ranks_and_underscore_species_names():
    """A taxonomy string splits domain->species; the CURIE local part underscores spaces while the
    label keeps the original spacing with the rank prefix removed."""
    taxa = parse_gtdb_taxonomy(
        "d__Bacteria;p__Pseudomonadota;c__Gammaproteobacteria;o__Enterobacterales;"
        "f__Enterobacteriaceae;g__Enterobacter;s__Enterobacter hormaechei_C"
    )
    assert taxa[0] == ("d__Bacteria", "Bacteria")
    assert taxa[-1] == ("s__Enterobacter_hormaechei_C", "Enterobacter hormaechei_C")
    assert [ranked for ranked, _label in taxa] == [
        "d__Bacteria",
        "p__Pseudomonadota",
        "c__Gammaproteobacteria",
        "o__Enterobacterales",
        "f__Enterobacteriaceae",
        "g__Enterobacter",
        "s__Enterobacter_hormaechei_C",
    ]


@pytest.mark.unit
def test_parse_gtdb_taxonomy_should_skip_malformed_tokens():
    """Tokens without a '__' rank separator or with an empty name are dropped, not crashed on."""
    taxa = parse_gtdb_taxonomy("d__Bacteria;garbage;s__")
    assert taxa == [("d__Bacteria", "Bacteria")]


# LABELS


@pytest.mark.unit
def test_write_gtdb_labels_should_emit_one_label_per_unique_taxon_across_all_ranks(tmp_path):
    """The 3 fixture genomes share d__Bacteria but otherwise differ, yielding 19 unique taxa
    (1 domain + 3 each of phylum/class/order/family/genus/species), each labeled once."""
    outfile = tmp_path / "labels"
    write_gtdb_labels([FIXTURE], str(outfile))
    rows = [line.split("\t") for line in outfile.read_text().splitlines()]
    labels = dict(rows)
    assert len(labels) == 19
    assert labels["GTDB:d__Bacteria"] == "Bacteria"
    assert labels["GTDB:s__Enterobacter_hormaechei_C"] == "Enterobacter hormaechei_C"
    assert labels["GTDB:g__UBA7173"] == "UBA7173"
    # No CURIE is emitted twice.
    assert len(rows) == len(labels)


# CONCORD


@pytest.mark.unit
def test_build_gtdb_relationships_should_link_only_species_rank_to_ncbi(tmp_path):
    """Each fixture genome's species-rank GTDB taxon is linked eq to its ncbi_species_taxid; higher
    ranks (which have no NCBI taxid in the metadata) produce no edge."""
    outfile = tmp_path / "concord"
    metadata = tmp_path / "meta.yaml"
    build_gtdb_relationships([FIXTURE], str(outfile), str(metadata))

    from tests.conftest import assert_concordance_file_valid

    rows = assert_concordance_file_valid(str(outfile))
    edges = {(row[0], row[1], row[2]) for row in rows}
    assert edges == {
        ("GTDB:s__Enterobacter_hormaechei_C", "eq", "NCBITaxon:158836"),
        ("GTDB:s__BJHT01_sp945861535", "eq", "NCBITaxon:2026799"),
        ("GTDB:s__UBA7173_sp001689485", "eq", "NCBITaxon:2498093"),
    }
    # Every subject is a species-rank GTDB CURIE.
    assert all(subject.startswith("GTDB:s__") for subject, _rel, _obj in edges)


@pytest.mark.unit
def test_column_indices_should_be_resolved_by_name(tmp_path):
    """The parser locates gtdb_taxonomy/ncbi_species_taxid by column name (robust to the 113-column
    layout), not by a hard-coded position."""
    with open(FIXTURE) as inf:
        header = inf.readline()
    taxonomy_idx, taxid_idx = _taxonomy_and_taxid_indices(header)
    columns = header.rstrip("\n").split("\t")
    assert columns[taxonomy_idx] == "gtdb_taxonomy"
    assert columns[taxid_idx] == "ncbi_species_taxid"


# MANY-TO-ONE / EXTRA_PREFIXES (the two load-bearing taxon-build decisions)


@pytest.mark.unit
def test_taxon_uniques_should_merge_a_species_with_ncbi_but_keep_two_gtdb_species_apart():
    """With the taxon unique_prefixes (incl. GTDB), a GTDB species merges with its NCBITaxon, but two
    GTDB species sharing one NCBITaxon stay two cliques — the many-to-one guard. Removing GTDB from
    unique_prefixes would wrongly merge the two species, failing this test."""
    from src.babel_utils import glom
    from src.prefixes import GTDB, MESH, NCBITAXON, UMLS

    uniques = [NCBITAXON, MESH, UMLS, GTDB]
    species_a = f"{GTDB}:s__A"
    species_b = f"{GTDB}:s__B"
    ncbi_x = f"{NCBITAXON}:1"
    dicts = {}
    # Ids load first (as in glom_from_files): every taxon starts as a singleton.
    glom(dicts, [(species_a,), (species_b,), (ncbi_x,)], unique_prefixes=uniques)
    # A<->X merges; B<->X is rejected (it would put two GTDB ids in one clique), so B stays the
    # singleton it was loaded as.
    glom(dicts, [{species_a, ncbi_x}], unique_prefixes=uniques)
    glom(dicts, [{species_b, ncbi_x}], unique_prefixes=uniques)

    cliques = set(frozenset(members) for members in dicts.values())
    assert frozenset({species_a, ncbi_x}) in cliques  # A merged with its NCBI taxon
    assert frozenset({species_b}) in cliques  # B stayed a singleton
    assert not any(species_a in c and species_b in c for c in cliques)


@pytest.mark.network
def test_create_node_should_keep_gtdb_only_with_extra_prefixes():
    """GTDB is not in organism-taxon id_prefixes, so a GTDB-only clique is dropped by create_node unless
    extra_prefixes=[GTDB] is passed (the taxon build does this). Removing extra_prefixes from
    taxon.build_compendia would make the 'kept' case drop, failing this test. Needs the Biolink toolkit
    (network on first use)."""
    from src.babel_utils import make_local_name
    from src.categories import ORGANISM_TAXON
    from src.node import NodeFactory
    from src.prefixes import GTDB
    from src.util import get_config

    factory = NodeFactory(make_local_name(""), get_config()["biolink_version"])
    factory.common_labels = {}  # bypass the on-disk common-labels load (absent on a dev laptop)
    gtdb_id = f"{GTDB}:s__Escherichia_coli"
    labels = {gtdb_id: "Escherichia coli"}

    kept = factory.create_node([gtdb_id], ORGANISM_TAXON, labels=labels, extra_prefixes=[GTDB])
    assert kept is not None
    assert any(entry["identifier"] == gtdb_id for entry in kept["identifiers"])

    dropped = factory.create_node([gtdb_id], ORGANISM_TAXON, labels=labels, extra_prefixes=[])
    assert dropped is None


# PARSER ROBUSTNESS


@pytest.mark.unit
def test_write_gtdb_labels_should_read_gzipped_metadata(tmp_path):
    """_open_metadata transparently reads a gzipped metadata file (.gz) as well as plain TSV."""
    import gzip

    gz_fixture = tmp_path / "gtdb.tsv.gz"
    with open(FIXTURE, "rb") as src:
        data = src.read()
    with open(gz_fixture, "wb") as dst:
        dst.write(gzip.compress(data))

    outfile = tmp_path / "labels"
    write_gtdb_labels([str(gz_fixture)], str(outfile))
    assert len(outfile.read_text().splitlines()) == 19


@pytest.mark.unit
def test_build_gtdb_relationships_should_skip_rows_with_missing_values(tmp_path):
    """MECHANISM TEST (synthetic 2-column input — exercises the skip guards, not a claim about GTDB
    data): rows with an empty/'-' gtdb_taxonomy or ncbi_species_taxid, and short rows, produce no edge."""
    metadata = tmp_path / "mini.tsv"
    metadata.write_text(
        "gtdb_taxonomy\tncbi_species_taxid\n"
        "d__Bacteria;s__Foo bar\t123\n"  # good -> one edge
        "d__Bacteria;s__No taxid\t-\n"  # '-' taxid -> skipped
        "-\t456\n"  # '-' taxonomy -> skipped
        "d__Bacteria;s__Empty taxid\t\n"  # empty taxid -> skipped
        "d__Bacteria;s__OnlyOneField\n"  # short row -> skipped
    )
    outfile = tmp_path / "concord"
    yaml = tmp_path / "meta.yaml"
    build_gtdb_relationships([str(metadata)], str(outfile), str(yaml))
    assert outfile.read_text().splitlines() == ["GTDB:s__Foo_bar\teq\tNCBITaxon:123"]
