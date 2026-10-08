# Tests for datahandlers/umls.py
import pytest

from src.datahandlers.umls import build_sets


def mrconso_row(cui, sab, tty, code, label, lat="ENG", suppress="N"):
    """Build a synthetic MRCONSO.RRF row with the columns that build_sets() reads filled in."""
    cols = [""] * 18
    cols[0] = cui
    cols[1] = lat
    cols[11] = sab
    cols[12] = tty
    cols[13] = code
    cols[14] = label
    cols[16] = suppress
    return "|".join(cols) + "|\n"


@pytest.mark.unit
def test_build_sets_go_uses_preferred_terms_only(tmp_path):
    # Modeled on GO:0045943: the GO preferred term is in one CUI, but UMLS places the GO narrow synonyms
    # ("activation of ...", "stimulation of ...") in other CUIs that still carry the GO code.
    rows = [
        mrconso_row("C1158785", "GO", "PT", "GO:0045943", "positive regulation of transcription by RNA polymerase I"),
        mrconso_row("C1158785", "GO", "SY", "GO:0045943", "up regulation of transcription by RNA polymerase I"),
        mrconso_row("C2249862", "GO", "ET", "GO:0045943", "activation of transcription from RNA polymerase I promoter"),
        mrconso_row("C2249863", "GO", "SY", "GO:0045943", "stimulation of transcription from RNA polymerase I promoter"),
        # MTH_PT is NLM's adjusted preferred name and is kept.
        mrconso_row("C0000002", "GO", "MTH_PT", "GO:0000002", "some activity"),
        # Non-GO sources are unaffected by the GO term type filter.
        mrconso_row("C0000002", "MSH", "MH", "D000002", "Some Activity"),
        # Obsolete GO preferred terms are still dropped by the SUPPRESS check.
        mrconso_row("C0000003", "GO", "OP", "GO:0000003", "obsolete thing", suppress="O"),
    ]
    mrconso = tmp_path / "MRCONSO.RRF"
    mrconso.write_text("".join(rows))
    idfile = tmp_path / "ids"
    idfile.write_text("".join(f"UMLS:{cui}\tbiolink:BiologicalProcess\n" for cui in ["C1158785", "C2249862", "C2249863", "C0000002", "C0000003"]))
    outfile = tmp_path / "concord"

    build_sets(str(mrconso), str(idfile), str(outfile), {"GO": "GO", "MSH": "MESH"})

    pairs = {tuple(line.rstrip("\n").split("\t")) for line in outfile.read_text().splitlines()}
    assert pairs == {
        ("UMLS:C1158785", "eq", "GO:0045943"),
        ("UMLS:C0000002", "eq", "GO:0000002"),
        ("UMLS:C0000002", "eq", "MESH:D000002"),
    }
