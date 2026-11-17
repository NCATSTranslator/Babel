"""Unit tests for chemicals.write_unii_records_concords(), which turns the PUBCHEM and RN columns of FDA's UNII records
into the UNII_PUBCHEM and UNII_CAS concords (#1225).

Every record below is copied verbatim from Latest_UNII_Records.txt as downloaded on 2026-11-17 (the UNII_Records_4Aug2026
release), CRLF line endings included; each is named by its UNII in a comment.
"""

import pytest
import yaml

import src.createcompendia.chemicals as chemicals
from src.createcompendia.chemicals import is_cas, write_unii_ids, write_unii_records_concords
from src.model.intermediates import read_concords

HEADER = "UNII\tDISPLAY_NAME\tRN\tEC\tNCIT\tRXCUI\tPUBCHEM\tSMSID\tEPA_CompTox\tCATALOGUE_OF_LIFE\tITIS\tNCBI\tPLANTS\tPOWO\tGRIN\tMPNS\tINN_ID\tUSAN_ID\tDAILYMED\tMF\tINCHIKEY\tSMILES\tINGREDIENT_TYPE\tUTF8_DISPLAY_NAME\tSUBSTANCE_TYPE"

# UNII:LWB6BD8SN9 "INSULIN RABBIT" -- the #1171 case: the record names rabbit insulin's CID and CAS number.
RABBIT = "LWB6BD8SN9\tINSULIN RABBIT\t11061-69-1\t\t\t\t118984376\t300000017514\t\t\t\t\t\t\t\t\t\t\t\t\t\t\tINGREDIENT SUBSTANCE\tINSULIN RABBIT\tprotein"
# UNII:576O9IZ534 "INSULIN BEEF" -- a CAS number and no CID.
BEEF = "576O9IZ534\tINSULIN BEEF\t11070-73-8\t\tC90960\t314686\t\t100000089133\tDTXSID8040430\t\t\t\t\t\t\t\t\t\t\t\t\t\tINGREDIENT SUBSTANCE\tINSULIN BEEF\tprotein"
# UNII:16902YVY2B "PODOPHYLLUM RESIN" -- populated NCBI/PLANTS/GRIN/MPNS columns: an organism, which write_unii_ids()
# drops, so neither of its xrefs may be written.
ORGANISM = "16902YVY2B\tPODOPHYLLUM RESIN\t9000-55-9\t\tC2362\t8462\t11979494\t100000086333\tDTXSID101026250\t4KR3V\t18850\t35933\tPOPE\t107599-1\t29138\tWCSCMP-2412818\t\t\t16902YVY2B\t\t\t\tINGREDIENT SUBSTANCE\tPODOPHYLLUM RESIN\tstructurallyDiverse"
# UNII:58QVG85GW3 "POLYVINYL ACETATE PHTHALATE" -- a polymer, whose CID (PUBCHEM.COMPOUND:161821) is its monomers.
POLYMER = "58QVG85GW3\tPOLYVINYL ACETATE PHTHALATE\t34481-48-6\t\t\t1367129\t161821\t100000076476\tDTXSID40956012\t\t\t\t\t\t\t\t\t\t58QVG85GW3\t\t\t\tINGREDIENT SUBSTANCE\tPOLYVINYL ACETATE PHTHALATE\tpolymer"
# UNII:7C236S3MKV -- its PUBCHEM column holds a CAS number.
CAS_IN_PUBCHEM = "7C236S3MKV\t4-((2S,4R)-4-ETHOXY-1-((5-METHOXY-7-METHYL-1H-INDOL-4-YL)METHYL)PIPERIDIN-2-YL)BENZOIC ACID\t\t\t\t\t3057514-75-4\t\t\t\t\t\t\t\t\t\t\t\t\tC25H30N2O4\tRENRQMCACQEWFC-KNQAVFIVSA-N\tC(c1ccc(cc1)[C@H]2N(CC[C@H](C2)OCC)Cc3c4cc[nH]c4c(cc3OC)C)(=O)O\tINGREDIENT SUBSTANCE\t4-[(2S,4R)-4-Ethoxy-1-[(5-methoxy-7-methyl-1H-indol-4-yl)methyl]piperidin-2-yl]benzoic acid\tchemical"
# UNII:8MJD3NPN7Z -- its RN column repeats its CID.
CID_IN_RN = "8MJD3NPN7Z\t6-CHLORO-.ALPHA.-(2,4-DIFLUOROPHENYL)-5-FLUORO-.BETA.-METHYL-.ALPHA.-(1H-1,2,4-TRIAZOL-1-YLMETHYL)-4-PYRIMIDINEETHANOL, (.ALPHA.S,.BETA.S)-\t29414406\t\t\t\t29414406\t\t\t\t\t\t\t\t\t\t\t\t\tC16H13ClF3N5O\tBQDLXFABVRRDFU-FVMDXXJSSA-N\t[C@]([C@@H](C)c1c(F)c(Cl)ncn1)(Cn2cncn2)(O)c3c(F)cc(F)cc3\tINGREDIENT SUBSTANCE\t6-Chloro-?-(2,4-difluorophenyl)-5-fluoro-?-methyl-?-(1H-1,2,4-triazol-1-ylmethyl)-4-pyrimidineethanol, (?S,?S)-\tchemical"


def _write(tmp_path, *records, **kwargs):
    records_file = tmp_path / "Latest_UNII_Records.txt"
    records_file.write_bytes("\r\n".join([HEADER, *records, ""]).encode("windows-1252"))
    paths = [tmp_path / name for name in ["UNII_PUBCHEM", "UNII_CAS", "pubchem.yaml", "cas.yaml"]]
    write_unii_records_concords(records_file, *paths, **kwargs)
    return list(read_concords(paths[0])), list(read_concords(paths[1]))


# THE #1171 RECORDS


@pytest.mark.unit
def test_writes_a_records_cid_and_cas_number(tmp_path):
    """Rabbit insulin's UNII should be linked to both the CID and the CAS number its record gives."""
    pubchem, cas = _write(tmp_path, RABBIT)
    assert pubchem == [("UNII:LWB6BD8SN9", "xref", "PUBCHEM.COMPOUND:118984376")]
    assert cas == [("UNII:LWB6BD8SN9", "xref", "CAS:11061-69-1")]


@pytest.mark.unit
def test_a_record_without_a_cid_writes_only_its_cas_number(tmp_path):
    """Beef insulin's record has no CID, so it should appear only in the CAS concord."""
    pubchem, cas = _write(tmp_path, BEEF)
    assert pubchem == []
    assert cas == [("UNII:576O9IZ534", "xref", "CAS:11070-73-8")]


# ROWS THAT MUST BE SKIPPED


@pytest.mark.unit
def test_an_organism_record_writes_nothing(tmp_path):
    """A record write_unii_ids() leaves out as an organism should have no xrefs written either."""
    assert _write(tmp_path, ORGANISM) == ([], [])


@pytest.mark.unit
def test_a_polymer_record_writes_nothing(tmp_path):
    """A polymer's CID and CAS number name its monomers, so neither should be written."""
    assert _write(tmp_path, POLYMER) == ([], [])


@pytest.mark.unit
def test_a_cas_number_in_the_pubchem_column_is_skipped(tmp_path):
    """A PUBCHEM value that is not all digits should be skipped rather than written as a PUBCHEM.COMPOUND CURIE."""
    assert _write(tmp_path, CAS_IN_PUBCHEM) == ([], [])


@pytest.mark.unit
def test_a_cid_in_the_rn_column_is_skipped_but_the_cid_is_kept(tmp_path):
    """An RN value that is not a CAS number should be skipped, without losing the record's CID."""
    pubchem, cas = _write(tmp_path, CID_IN_RN)
    assert pubchem == [("UNII:8MJD3NPN7Z", "xref", "PUBCHEM.COMPOUND:29414406")]
    assert cas == []


# VALUES THAT ARE NOT CIDS
#
# Neither row below is in the records file: each is RABBIT with one value altered, to pin what PUBCHEM_CID_RE rejects.


@pytest.mark.unit
@pytest.mark.parametrize(
    "bad_cid",
    [
        pytest.param("0118984376", id="leading-zero"),
        # windows-1252 byte 0xB2, which the reader decodes to a superscript two that str.isdigit() accepts.
        pytest.param("118984376²", id="superscript-digit"),
    ],
)
def test_a_pubchem_value_that_is_not_a_canonical_cid_is_skipped(tmp_path, bad_cid):
    """A zero-padded CID or one with a non-ASCII digit should be skipped, not written as a PUBCHEM.COMPOUND CURIE."""
    pubchem, cas = _write(tmp_path, RABBIT.replace("\t118984376\t", f"\t{bad_cid}\t"))
    assert pubchem == []
    assert cas == [("UNII:LWB6BD8SN9", "xref", "CAS:11061-69-1")]


@pytest.mark.unit
def test_a_superscript_digit_is_not_a_cas_number():
    """is_cas() should accept only ASCII digits, as str.isnumeric() did not."""
    assert is_cas("11061-69-1")
    assert not is_cas("11061-69-¹")


# MALFORMED-VALUE ACCOUNTING


@pytest.mark.unit
def test_malformed_values_are_counted_in_the_concord_metadata(tmp_path):
    """Each concord's metadata should record how many of its column's values were skipped as malformed."""
    _write(tmp_path, CAS_IN_PUBCHEM, CID_IN_RN)
    for name in ["pubchem.yaml", "cas.yaml"]:
        counts = yaml.safe_load((tmp_path / name).read_text())["counts"]
        assert counts["malformed values skipped"] == 1


@pytest.mark.unit
def test_too_many_malformed_values_fail_the_rule(tmp_path, monkeypatch):
    """More malformed values in a column than UNII_RECORDS_MAX_MALFORMED_VALUES should raise, not just log."""
    monkeypatch.setattr(chemicals, "UNII_RECORDS_MAX_MALFORMED_VALUES", 0)
    with pytest.raises(ValueError, match="malformed PUBCHEM values"):
        _write(tmp_path, CAS_IN_PUBCHEM)


# OPTIONS AND NORMALISATION


@pytest.mark.unit
def test_skip_substance_types_can_be_overridden(tmp_path):
    """With no SUBSTANCE_TYPE skipped, the polymer's CID and CAS number should both be written."""
    pubchem, cas = _write(tmp_path, POLYMER, skip_substance_types=frozenset())
    assert pubchem == [("UNII:58QVG85GW3", "xref", "PUBCHEM.COMPOUND:161821")]
    assert cas == [("UNII:58QVG85GW3", "xref", "CAS:34481-48-6")]


@pytest.mark.unit
def test_the_ids_file_and_the_concord_name_a_padded_unii_the_same_way(tmp_path):
    """A UNII with whitespace around it (not in the 4 Aug 2026 file; RABBIT padded by hand) should give the same
    CURIE in the ids file and the concord, because read_unii_records() strips every value."""
    pubchem, _ = _write(tmp_path, RABBIT.replace("LWB6BD8SN9\t", " LWB6BD8SN9 \t", 1))
    write_unii_ids(tmp_path / "Latest_UNII_Records.txt", tmp_path / "ids")
    assert pubchem == [("UNII:LWB6BD8SN9", "xref", "PUBCHEM.COMPOUND:118984376")]
    assert (tmp_path / "ids").read_text() == "UNII:LWB6BD8SN9\tbiolink:ChemicalEntity\n"
