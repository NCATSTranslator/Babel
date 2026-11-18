"""Tests for building the OrganismTaxon concords (src/createcompendia/taxon.py)."""

import io
import tarfile

import pytest
import yaml

from src.categories import ORGANISM_TAXON
from src.createcompendia.taxon import (
    build_taxon_umls_relationships,
    update_obsolete_ncbitaxon_ids,
    write_taxon_concords,
)
from src.datahandlers.ncbitaxon import read_obsolete_taxa, read_taxon_names
from src.predicates import HAS_EXACT_SYNONYM
from tests.conftest import assert_concordance_file_valid, read_tsv

# MRCONSO.RRF rows copied verbatim from the UMLS 2026AA release.
MRCONSO_ROWS = [
    # C1110641 Armoracia rusticana: UMLS calls NCBI Taxonomy "NCBI", and its CODE is the bare taxon ID.
    "C1110641|ENG|P|L0514063|PF|S0592368|N|A0647575||3704||NCBI|SCN|3704|Armoracia rusticana|0|N||",
    # C0003062 Animals: only the MeSH main heading (MH) is used; the entry term (ET) is skipped.
    "C0003062|ENG|P|L0003043|PF|S0014166|N|A2782515||M0001219|D000818|MSH|MH|D000818|Animals|0|N||",
    "C0003062|ENG|P|L0003043|VO|S0014083|Y|A26622215||M0001219|D000818|MSH|ET|D000818|Animal|0|N||",
    "C0003062|ENG|S|L0161925|PF|S0226340|N|A2687514||33208||NCBI|SY|33208|Animalia|0|N||",
    # C1704307 Fly (organism): a SNOMED CT atom, which isn't a source we map taxa from.
    "C1704307|ENG|S|L0016237|PF|S0004196|Y|A2876298|17694013|10147004||SNOMEDCT_US|PT|10147004|Fly|9|N||",
    # C0010395 Crustacea: NCBI 6657 has since been merged into 197562 (see MERGED_DMP_ROWS).
    "C0010395|ENG|S|L0010395|PF|S0028997|N|A0043885||6657||NCBI|SCN|6657|Crustacea|0|N||",
    # C0331518 Paspalum notatum: NCBI 147272 has since been deleted (see DELNODES_DMP_ROWS).
    "C0331518|ENG|P|L0599004|PF|S0711248|N|A2688028||147272||NCBI|SCN|147272|Paspalum notatum|0|N||",
]
TAXON_CUIS = ["C1110641", "C0003062", "C1704307", "C0010395", "C0331518"]

# merged.dmp, delnodes.dmp and names.dmp rows copied verbatim from the NCBI Taxonomy taxdump: the first three
# merged.dmp rows and the delnodes.dmp row from that of 2026-10-09, everything else from that of 2026-11-17.
MERGED_DMP_ROWS = [
    "6657\t|\t197562\t|",  # Crustacea -> Pancrustacea
    "650420\t|\t2761485\t|",  # Marasmius distantifolius
    "71877\t|\t206318\t|",  # Collybia dryophila -> Gymnopus dryophilus
    "1560619\t|\t30592\t|",  # Cheracebus purinus -> Cheracebus torquatus
    "186125\t|\t2870670\t|",  # -> Fomitopsis palustris
    "103857\t|\t2870670\t|",  # -> Fomitopsis palustris
    "181964\t|\t2726193\t|",  # -> Callistosporium brunnescens
    "2108235\t|\t2726193\t|",  # -> Callistosporium brunnescens
    "137676\t|\t3618\t|",  # Emex -> Rumex
]
DELNODES_DMP_ROWS = [
    "147272\t|",  # Paspalum notatum
]
NAMES_DMP_ROWS = [
    "197562\t|\tCrustacea\t|\t\t|\tincludes\t|",
    "197562\t|\tcrustaceans and hexapods\t|\t\t|\tgenbank common name\t|",
    "197562\t|\tcrustaceans\t|\t\t|\tblast name\t|",
    "197562\t|\tPancrustacea\t|\t\t|\tscientific name\t|",
    "206318\t|\tAgaricus dryophilus\t|\t\t|\tsynonym\t|",
    "206318\t|\tCollybia dryophila\t|\t\t|\tsynonym\t|",
    "206318\t|\tGymnopus dryophilus\t|\t\t|\tscientific name\t|",
    "30592\t|\tCallicebus purinus\t|\t\t|\tsynonym\t|",
    "30592\t|\tCallicebus torquatus purinus\t|\t\t|\tsynonym\t|",
    "30592\t|\tCallicebus torquatus\t|\t\t|\tsynonym\t|",
    "30592\t|\tCallitrix torquata Hoffmannsegg, 1807\t|\t\t|\tsynonym\t|",
    "30592\t|\tCheracebus purinus\t|\t\t|\tsynonym\t|",
    "30592\t|\tCheracebus torquatus\t|\t\t|\tscientific name\t|",
    "2870670\t|\tFomitopsis palustris (Berk. & M.A. Curtis) Gilb. & Ryvarden, 1985\t|\t\t|\tsynonym\t|",
    "2870670\t|\tFomitopsis palustris\t|\t\t|\tscientific name\t|",
    "2870670\t|\tPilatoporus palustris\t|\t\t|\tsynonym\t|",
    "2870670\t|\tPolyporus palustris\t|\t\t|\tsynonym\t|",
    "2726193\t|\tCallistosporium brunnescens\t|\t\t|\tscientific name\t|",
    "2726193\t|\tGeopetalum brunescens\t|\t\t|\tsynonym\t|",
    "2726193\t|\tPleurocollybia brunescens (Earle) Singer, 1973\t|\t\t|\tsynonym\t|",
    "3618\t|\tEmex Neck. ex Campd., 1819\t|\t\t|\tauthority\t|",
    "3618\t|\tEmex\t|\t\t|\tsynonym\t|",
    "3618\t|\tRumex\t|\t\t|\tscientific name\t|",
    "3618\t|\tRumex subgen. Emex\t|\t\t|\tincludes\t|",
]

# MeSH labels (MESH/labels) for the MeSH records used below, as in the MeSH 2026 supplementary records.
MESH_LABELS = {
    "MESH:D003445": "Crustacea",
    "MESH:C000630305": "Cheracebus torquatus",
    "MESH:C000630328": "Cheracebus purinus",
    "MESH:C000668355": "Collybia dryophila",
    "MESH:C000672803": "Gymnopus dryophilus",
    "MESH:C000675279": "Pleurocollybia brunnescens",
    "MESH:C000679014": "Fomitopsis palustris",
    "MESH:C000699486": "Pilatoporus palustris",
    "MESH:C000699630": "Pleurocollybia brunescens",
}
# UMLS synonyms (UMLS/synonyms) for the UMLS records used below: the distinct MRCONSO strings in UMLS 2026AA.
UMLS_SYNONYMS = {
    "UMLS:C0010395": [
        "Subphylum Crustacea",
        "Crustacea",
        "crustacea",
        "Crustaceans",
        "crustaceans",
        "Crustacean",
        "crustacean",
        "Crustaceas",
        "Subphylum Crustacea (organism)",
    ],
    "UMLS:C1003295": ["Cheracebus torquatus", "Callicebus torquatus", "Callitrix torquata", "Collared titi"],
    "UMLS:C3672314": ["Cheracebus purinus", "Callicebus purinus", "Callicebus torquatus purinus"],
    "UMLS:C1683638": ["Fomitopsis palustris"],
    "UMLS:C1066610": ["Emex", "Rumex subgen. Emex"],
}


def write_taxdump(path, merged_rows, delnodes_rows, names_rows=()):
    """Write a taxdump.tar containing only merged.dmp, delnodes.dmp and names.dmp."""
    with tarfile.open(path, "w") as tar:
        for name, rows in [("merged.dmp", merged_rows), ("delnodes.dmp", delnodes_rows), ("names.dmp", names_rows)]:
            data = "".join(row + "\n" for row in rows).encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return str(path)


@pytest.fixture
def taxdump(tmp_path):
    return write_taxdump(tmp_path / "taxdump.tar", MERGED_DMP_ROWS, DELNODES_DMP_ROWS, NAMES_DMP_ROWS)


@pytest.fixture
def name_files(tmp_path):
    """Write MeSH labels and UMLS synonyms files, returning (label_files, synonym_files)."""
    labels = tmp_path / "MESH_labels"
    labels.write_text("".join(f"{curie}\t{label}\n" for curie, label in MESH_LABELS.items()))
    synonyms = tmp_path / "UMLS_synonyms"
    synonyms.write_text(
        "".join(f"{curie}\t{HAS_EXACT_SYNONYM}\t{s}\n" for curie, names in UMLS_SYNONYMS.items() for s in names)
    )
    return [str(labels)], [str(synonyms)]


def update_concords(tmp_path, taxdump, name_files, **concord_texts):
    """Run update_obsolete_ncbitaxon_ids() over the given concords; return (rows by concord, counts, decisions)."""
    concords = {}
    for name, text in concord_texts.items():
        infile = tmp_path / f"{name}.raw"
        infile.write_text(text)
        concords[name] = (str(infile), str(tmp_path / name))
    counts, decisions = update_obsolete_ncbitaxon_ids(concords, taxdump, *name_files)
    # read_tsv() rather than assert_concordance_file_valid(), which rejects the empty concords some tests expect.
    rows = {name: read_tsv(outfile) for name, (_, outfile) in concords.items()}
    return rows, {name: c["obsolete_ncbitaxon"] for name, c in counts.items()}, decisions


def decision_for(decisions, identifier):
    (decision,) = [d["decision"] for d in decisions if d["identifier"] == identifier]
    return decision


# OBSOLETE NCBITAXON IDS


@pytest.mark.unit
def test_read_obsolete_taxa(taxdump):
    """merged.dmp should be read as old CURIE -> new CURIE, and delnodes.dmp as a set of CURIEs."""
    merged, deleted = read_obsolete_taxa(taxdump)
    assert merged == {f"NCBITaxon:{row.split()[0]}": f"NCBITaxon:{row.split()[2]}" for row in MERGED_DMP_ROWS}
    assert merged["NCBITaxon:6657"] == "NCBITaxon:197562"
    assert deleted == {"NCBITaxon:147272"}


@pytest.mark.unit
def test_read_obsolete_taxa_rejects_merge_chains(tmp_path):
    """A merge target that is itself merged should raise, since we only follow one step.

    NCBI flattens merge chains, so this taxdump is constructed rather than copied: it chains the two real
    merges above so that 650420 -> 2761485 -> 6657.
    """
    path = write_taxdump(tmp_path / "taxdump.tar", ["2761485\t|\t6657\t|", "650420\t|\t2761485\t|"], [])
    with pytest.raises(ValueError, match="merge targets are themselves obsolete"):
        read_obsolete_taxa(path)


@pytest.mark.unit
def test_read_taxon_names(taxdump):
    """names.dmp should be read as {name: name classes} for the requested taxa only."""
    names = read_taxon_names(taxdump, {"NCBITaxon:197562", "NCBITaxon:99999"})
    assert names == {
        "NCBITaxon:197562": {
            "Crustacea": {"includes"},
            "crustaceans and hexapods": {"genbank common name"},
            "crustaceans": {"blast name"},
            "Pancrustacea": {"scientific name"},
        }
    }


@pytest.mark.unit
def test_update_obsolete_ncbitaxon_ids(tmp_path, taxdump, name_files):
    """Merged IDs should be replaced, rows with deleted IDs dropped, and rows that become duplicates removed."""
    rows, counts, _ = update_concords(
        tmp_path,
        taxdump,
        name_files,
        UMLS="UMLS:C2783570\teq\tNCBITaxon:650420\n"
        "UMLS:C2783570\teq\tNCBITaxon:650420\n"
        "UMLS:C0003062\teq\tNCBITaxon:33208\n"
        "UMLS:C0331518\teq\tNCBITaxon:147272\n"
        "UMLS:C0331518\teq\tMESH:C000695935\n",
    )

    assert rows["UMLS"] == [
        ["UMLS:C2783570", "eq", "NCBITaxon:2761485"],
        ["UMLS:C0003062", "eq", "NCBITaxon:33208"],
        ["UMLS:C0331518", "eq", "MESH:C000695935"],
    ]
    assert counts["UMLS"] == {
        "remapped_merged": 2,
        "dropped_merged_already_linked": 0,
        "dropped_merged_into_broader_taxon": 0,
        "dropped_merged_superseded_by_direct": 0,
        "dropped_merged_ambiguous": 0,
        "dropped_deleted": 1,
    }


@pytest.mark.unit
@pytest.mark.parametrize("direct_first", [True, False])
def test_update_obsolete_ncbitaxon_ids_prefers_direct_links(tmp_path, taxdump, name_files, direct_first):
    """A remapped row should be dropped when another ID of the same prefix links to that taxon directly.

    These are the MeSH registry rows for Collybia dryophila (pointing at merged NCBITaxon:71877) and
    Gymnopus dryophilus (pointing at its replacement, NCBITaxon:206318). The remapped Collybia row must not
    compete with the direct Gymnopus row, whichever comes first in the file.
    """
    collybia = "MESH:C000668355\txref\tNCBITaxon:71877\n"
    gymnopus = "MESH:C000672803\txref\tNCBITaxon:206318\n"
    rows, counts, _ = update_concords(
        tmp_path, taxdump, name_files, NCBI_MESH=gymnopus + collybia if direct_first else collybia + gymnopus
    )

    assert rows["NCBI_MESH"] == [["MESH:C000672803", "xref", "NCBITaxon:206318"]]
    assert counts["NCBI_MESH"]["dropped_merged_superseded_by_direct"] == 1


@pytest.mark.unit
def test_update_obsolete_ncbitaxon_ids_checks_direct_links_across_concords(tmp_path, taxdump, name_files):
    """A direct link reached through the other concord should still supersede a remapped row.

    MeSH "Cheracebus purinus" cites NCBITaxon:1560619, since merged into NCBITaxon:30592 "Cheracebus
    torquatus". MeSH's own "Cheracebus torquatus" has no txid, but reaches 30592 through its UMLS CUI
    (C1003295), which cites it directly. Looking at the MeSH concord alone, nothing links to 30592, so
    the remapped row would be kept and compete with C000630305 for the clique's one MeSH slot.
    """
    rows, counts, decisions = update_concords(
        tmp_path,
        taxdump,
        name_files,
        NCBI_MESH="MESH:C000630328\txref\tNCBITaxon:1560619\n",
        UMLS="UMLS:C1003295\teq\tNCBITaxon:30592\n"
        "UMLS:C1003295\teq\tMESH:C000630305\n"
        "UMLS:C3672314\teq\tNCBITaxon:1560619\n"
        "UMLS:C3672314\teq\tMESH:C000630328\n",
    )

    assert rows["NCBI_MESH"] == []
    assert rows["UMLS"] == [
        ["UMLS:C1003295", "eq", "NCBITaxon:30592"],
        ["UMLS:C1003295", "eq", "MESH:C000630305"],
        ["UMLS:C3672314", "eq", "MESH:C000630328"],
    ]
    assert decision_for(decisions, "MESH:C000630328") == "dropped_merged_superseded_by_direct"
    assert decision_for(decisions, "UMLS:C3672314") == "dropped_merged_superseded_by_direct"


@pytest.mark.unit
def test_update_obsolete_ncbitaxon_ids_does_not_follow_merges_into_broader_taxa(tmp_path, taxdump, name_files):
    """A record should not be linked to a merge target that NCBI says only includes it.

    NCBI merged Crustacea (6657) into Pancrustacea (197562), which also contains the insects, and lists
    "Crustacea" under it as a name it "includes". (UMLS also calls Crustacea "crustaceans", which NCBI uses
    as a blast name for Pancrustacea; that vernacular match should not make it the same taxon.)
    """
    rows, counts, _ = update_concords(
        tmp_path,
        taxdump,
        name_files,
        NCBI_MESH="MESH:D003445\txref\tNCBITaxon:6657\n",
        UMLS="UMLS:C0010395\teq\tNCBITaxon:6657\nUMLS:C0010395\teq\tMESH:D003445\n",
    )

    assert rows == {"NCBI_MESH": [], "UMLS": [["UMLS:C0010395", "eq", "MESH:D003445"]]}
    assert counts["NCBI_MESH"]["dropped_merged_into_broader_taxon"] == 1
    assert counts["UMLS"]["dropped_merged_into_broader_taxon"] == 1


@pytest.mark.unit
def test_update_obsolete_ncbitaxon_ids_drops_partial_matches_even_with_a_synonym_match(tmp_path, taxdump, name_files):
    """A record with any name NCBI says the merge target only includes should not be linked to it.

    UMLS "Emex" cites NCBITaxon:137676, merged into NCBITaxon:3618 "Rumex". NCBI lists "Emex" as a synonym
    of Rumex, but also "Rumex subgen. Emex" -- UMLS's other name for the record -- as a name Rumex includes:
    the genus was sunk into Rumex as a subgenus, so the record is narrower than Rumex.
    """
    rows, counts, _ = update_concords(tmp_path, taxdump, name_files, UMLS="UMLS:C1066610\teq\tNCBITaxon:137676\n")

    assert rows["UMLS"] == []
    assert counts["UMLS"]["dropped_merged_into_broader_taxon"] == 1


@pytest.mark.unit
def test_update_obsolete_ncbitaxon_ids_prefers_the_scientific_name_among_remapped_rows(tmp_path, taxdump, name_files):
    """When several records reach a taxon only through merged IDs, the one with its scientific name should win.

    MeSH has "Fomitopsis palustris" and "Pilatoporus palustris", citing two IDs NCBI merged into
    NCBITaxon:2870670 "Fomitopsis palustris". Their UMLS CUIs are left out so that only the MeSH registry
    rows decide.
    """
    rows, counts, _ = update_concords(
        tmp_path,
        taxdump,
        name_files,
        NCBI_MESH="MESH:C000699486\txref\tNCBITaxon:103857\nMESH:C000679014\txref\tNCBITaxon:186125\n",
    )

    assert rows["NCBI_MESH"] == [["MESH:C000679014", "xref", "NCBITaxon:2870670"]]
    assert counts["NCBI_MESH"]["dropped_merged_ambiguous"] == 1


@pytest.mark.unit
@pytest.mark.parametrize("brunnescens_first", [True, False])
def test_update_obsolete_ncbitaxon_ids_drops_ambiguous_remapped_rows(tmp_path, taxdump, name_files, brunnescens_first):
    """When several records reach a taxon only through merged IDs and none has its name, none should link to it.

    MeSH has "Pleurocollybia brunnescens" and "Pleurocollybia brunescens", citing two IDs NCBI merged into
    NCBITaxon:2726193 "Callistosporium brunnescens". Neither name is one NCBI lists for it, so whichever came
    first would otherwise win.
    """
    brunnescens = "MESH:C000675279\txref\tNCBITaxon:181964\n"
    brunescens = "MESH:C000699630\txref\tNCBITaxon:2108235\n"
    rows, counts, _ = update_concords(
        tmp_path,
        taxdump,
        name_files,
        NCBI_MESH=brunnescens + brunescens if brunnescens_first else brunescens + brunnescens,
    )

    assert rows["NCBI_MESH"] == []
    assert counts["NCBI_MESH"]["dropped_merged_ambiguous"] == 2


@pytest.mark.unit
def test_update_obsolete_ncbitaxon_ids_counts_already_linked_rows(tmp_path, taxdump, name_files):
    """A remapped row for a record that already reaches the taxon directly should be counted as already linked.

    MeSH "Fomitopsis palustris" cites merged NCBITaxon:186125, while its UMLS CUI cites the current
    NCBITaxon:2870670, so the remapped MeSH row adds nothing. The second concord's UMLS:C0010395 row is
    constructed (no real record cites both IDs): a record citing both a merged ID and its replacement
    shouldn't be counted as superseded by itself.
    """
    rows, counts, _ = update_concords(
        tmp_path,
        taxdump,
        name_files,
        NCBI_MESH="MESH:C000679014\txref\tNCBITaxon:186125\n",
        UMLS="UMLS:C1683638\teq\tMESH:C000679014\n"
        "UMLS:C1683638\teq\tNCBITaxon:2870670\n"
        "UMLS:C0010395\teq\tNCBITaxon:197562\n"
        "UMLS:C0010395\teq\tNCBITaxon:6657\n",
    )

    assert rows["NCBI_MESH"] == []
    assert counts["NCBI_MESH"]["dropped_merged_already_linked"] == 1
    assert counts["UMLS"]["dropped_merged_already_linked"] == 1
    assert counts["UMLS"]["dropped_merged_superseded_by_direct"] == 0


@pytest.mark.unit
def test_update_obsolete_ncbitaxon_ids_rejects_malformed_rows(tmp_path, taxdump, name_files):
    """A concord line without exactly three tab-separated fields should raise, naming the file and line."""
    with pytest.raises(ValueError, match=r"NCBI_MESH\.raw:2: expected 3 tab-separated fields"):
        update_concords(tmp_path, taxdump, name_files, NCBI_MESH="MESH:D003445\txref\tNCBITaxon:6657\n\n")


@pytest.mark.unit
def test_write_taxon_concords_records_counts_in_metadata(tmp_path, taxdump, name_files):
    """write_taxon_concords() should write each concord's obsolete-ID counts into its metadata YAML."""
    raw = tmp_path / "NCBI_MESH.raw"
    raw.write_text("MESH:C000668355\txref\tNCBITaxon:71877\nMESH:D003445\txref\tNCBITaxon:6657\n")
    outfile, metadata = tmp_path / "NCBI_MESH", tmp_path / "metadata-NCBI_MESH.yaml"

    write_taxon_concords({"NCBI_MESH": (str(raw), str(outfile), str(metadata))}, taxdump, *name_files)

    assert assert_concordance_file_valid(str(outfile)) == [["MESH:C000668355", "xref", "NCBITaxon:206318"]]
    counts = yaml.safe_load(metadata.read_text())["counts"]
    assert counts["obsolete_ncbitaxon"]["remapped_merged"] == 1
    assert counts["obsolete_ncbitaxon"]["dropped_merged_into_broader_taxon"] == 1
    assert counts["concords"]["count_concords"] == 1


# UMLS CONCORD


def run_build_taxon_umls_relationships(tmp_path, cuis):
    mrconso = tmp_path / "MRCONSO.RRF"
    mrconso.write_text("".join(row + "\n" for row in MRCONSO_ROWS))
    idfile = tmp_path / "ids"
    idfile.write_text("".join(f"UMLS:{cui}\t{ORGANISM_TAXON}\n" for cui in cuis))
    outfile = tmp_path / "concord"
    build_taxon_umls_relationships(str(mrconso), str(idfile), str(outfile))
    return outfile


@pytest.mark.unit
def test_build_taxon_umls_relationships(tmp_path):
    """UMLS taxon CUIs should be mapped to MeSH and to NCBITaxon as UMLS cites it, and other sources ignored."""
    outfile = run_build_taxon_umls_relationships(tmp_path, TAXON_CUIS)

    assert {tuple(row) for row in assert_concordance_file_valid(str(outfile))} == {
        ("UMLS:C1110641", "eq", "NCBITaxon:3704"),
        ("UMLS:C0003062", "eq", "MESH:D000818"),
        ("UMLS:C0003062", "eq", "NCBITaxon:33208"),
        # Obsolete IDs are left for update_obsolete_ncbitaxon_ids().
        ("UMLS:C0010395", "eq", "NCBITaxon:6657"),
        ("UMLS:C0331518", "eq", "NCBITaxon:147272"),
    }


@pytest.mark.unit
def test_build_taxon_umls_relationships_skips_cuis_not_in_id_list(tmp_path):
    """A CUI with an NCBI atom should not be mapped if it isn't one of the taxon UMLS IDs."""
    outfile = run_build_taxon_umls_relationships(tmp_path, ["C0003062"])

    assert "UMLS:C1110641" not in outfile.read_text()
