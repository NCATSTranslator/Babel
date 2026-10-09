# Tests for datahandlers/umls.py
import pytest

from src.datahandlers.umls import build_snomed_entire_structure_pairs


def mrrel_row(cui1, rel, cui2, rela, sab="SNOMEDCT_US", suppress="N"):
    """Build an MRREL.RRF line in the real 16-column pipe-delimited format."""
    return f"{cui1}|A1|SCUI|{rel}|{cui2}|A2|SCUI|{rela}|R1|S1|{sab}|{sab}|0|Y|{suppress}||\n"


@pytest.mark.unit
def test_build_snomed_entire_structure_pairs(tmp_path):
    ids = ["C1289388", "C0037959", "C0000001", "C0000002", "C0000003", "C0000004", "C0000005", "C0000006", "C0000007", "C0000008"]
    idfile = tmp_path / "UMLS"
    idfile.write_text("".join(f"UMLS:{c}\tbiolink:AnatomicalEntity\n" for c in ids))
    mrrel = tmp_path / "MRREL.RRF"
    mrrel.write_text(
        "".join(
            [
                # Entire spiral ganglion (C1289388) / spiral ganglion structure (C0037959), in both directions as in MRREL.
                mrrel_row("C1289388", "RO", "C0037959", "has_entire_anatomy_structure"),
                mrrel_row("C0037959", "RO", "C1289388", "entire_anatomy_structure_of"),
                # Other relationships between the same concepts are not used.
                mrrel_row("C1289388", "PAR", "C0037959", "inverse_isa"),
                # Suppressed relationships are not used.
                mrrel_row("C0000001", "RO", "C0000002", "has_entire_anatomy_structure", suppress="O"),
                # Other sources are not used.
                mrrel_row("C0000003", "RO", "C0000004", "has_entire_anatomy_structure", sab="SNOMEDCT_VET"),
                # A structure with two entire concepts is ambiguous, so neither pair is used.
                mrrel_row("C0000005", "RO", "C0000007", "has_entire_anatomy_structure"),
                mrrel_row("C0000006", "RO", "C0000007", "has_entire_anatomy_structure"),
                # CUIs outside the anatomy UMLS ids are not used.
                mrrel_row("C0000008", "RO", "C9999999", "has_entire_anatomy_structure"),
            ]
        )
    )
    outfile = tmp_path / "UMLS_SNOMED_ENTIRE"
    build_snomed_entire_structure_pairs(str(mrrel), str(idfile), str(outfile), str(tmp_path / "metadata.yaml"))
    assert outfile.read_text() == "UMLS:C0037959\teq\tUMLS:C1289388\n"
    assert (tmp_path / "metadata.yaml").exists()
