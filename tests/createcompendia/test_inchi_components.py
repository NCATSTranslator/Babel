"""
Unit tests for src/createcompendia/inchi_components.py: splitting multi-component InChIs with RDKit, reading the
reviewed component list, and reducing a salt or hydrate to its parent.

Every InChI below is copied verbatim from PubChem's CID-InChI-Key.gz (downloaded 2026-11-10), with its CID. The
expected component keys were checked against PubChem's own records for the parents: guanidine (CID 3520,
ZRALSGWEFCBTJO-UHFFFAOYSA-N), pethidine (CID 4058, XADCESSVHJOZHK-UHFFFAOYSA-N) and hydrogen chloride (CID 313,
VEXZGXHMUGYJMC-UHFFFAOYSA-N).
"""

import gzip

import pytest

from src.createcompendia.inchi_components import (
    DECISIONS_TSV_HEADER,
    is_multi_component,
    parent_key,
    read_component_decisions,
    resolve_parent,
    split_inchi,
    write_inchi_components,
    write_salt_parents,
)

# CID 5750, pethidine hydrochloride.
PETHIDINE_HCL = "InChI=1S/C15H21NO2.ClH/c1-3-18-14(17)15(9-11-16(2)12-10-15)13-7-5-4-6-8-13;/h4-8H,3,9-12H2,1-2H3;1H"
# CID 5742, guanidine hydrochloride.
GUANIDINE_HCL = "InChI=1S/CH5N3.ClH/c2-1(3)4;/h(H5,2,3,4);1H"
# CID 1301, naproxen sodium.
NAPROXEN_NA = "InChI=1S/C14H14O3.Na/c1-9(14(15)16)10-3-4-12-8-13(17-2)6-5-11(12)7-10;/h3-9H,1-2H3,(H,15,16);/q;+1/p-1"
# CID 3939, lithium hydroxide: standard InChI writes hydroxide as a deprotonated water component.
LITHIUM_HYDROXIDE = "InChI=1S/Li.H2O/h;1H2/q+1;/p-1"
# CID 11194182 (a large fused polyaromatic tetrahydrochloride): its main fragment sanitizes but RDKit can't kekulize
# it when generating the InChI, which crashed the first full run.
UNKEKULIZABLE = "InChI=1S/C78H42N4O4.4ClH/c1-81(5-9-85-13-11-83-7-3-79)15-75-67-53-43-32-23-19-20-22-27-21(19)28-25-30(23)38(43)49-41-34(25)45-36(28)47-40(27)48-37-29(22)26-31-24(20)33(32)44-39(31)50-42-35(26)46(37)58-62-52(42)64(60(50)68(75)54(44)53)74-66-65-71-61(51(41)63(59(49)67)73(65)78(74,75)18-81)57(45)69-55(47)56(48)70(58)77(72(62)66)17-82(2,16-76(69,71)77)6-10-86-14-12-84-8-4-80;;;;/h3-18,79-80H2,1-2H3;4*1H/q+2;;;;/p-2"
# CID 53389302, "Pentafoil knot": a five-iron molecular knot on which RDKit's InChI parser never returns. It stalled
# the first full run.
PENTAFOIL_KNOT = "InChI=1S/C160H170N30O10.5Fe/c1-11-131-31-51-151(181-101-131)152-52-32-132(102-182-152)12-2-122-22-42-142(172-92-122)112-163-63-73-193-83-84-194-74-64-164-114-144-44-24-124(94-174-144)5-15-135-35-55-155(185-105-135)156-56-36-136(106-186-156)16-6-126-26-46-146(176-96-126)116-167-67-77-197-87-88-198-78-68-168-118-148-48-28-128(98-178-148)9-19-139-39-59-159(189-109-139)160-60-40-140(110-190-160)20-10-130-30-50-150(180-100-130)120-170-70-80-200-90-89-199-79-69-169-119-149-49-29-129(99-179-149)8-18-138-38-58-158(188-108-138)157-57-37-137(107-187-157)17-7-127-27-47-147(177-97-127)117-166-66-76-196-86-85-195-75-65-165-115-145-45-25-125(95-175-145)4-14-134-34-54-154(184-104-134)153-53-33-133(103-183-153)13-3-123-23-43-143(173-93-123)113-162-62-72-192-82-81-191-71-61-161-111-141-41-21-121(1)91-171-141;;;;;/h21-60,91-120H,1-20,61-90H2;;;;;/q;5*+2"
# CID 4058, pethidine itself: a single component.
PETHIDINE = "InChI=1S/C15H21NO2/c1-3-18-14(17)15(9-11-16(2)12-10-15)13-7-5-4-6-8-13/h4-8H,3,9-12H2,1-2H3"

HCL_PARENT = "VEXZGXHMUGYJMC-UHFFFAOYSA"
WATER_PARENT = "XLYOFNOQVPJJNP-UHFFFAOYSA"
SODIUM_ION_PARENT = "FKNQFGJONOIPTF-UHFFFAOYSA"
LITHIUM_ION_PARENT = "HBBGRARXTFLTSG-UHFFFAOYSA"


def write_decisions(path, rows):
    """Write a component list with the given (parent key, decision) rows."""
    lines = ["\t".join(DECISIONS_TSV_HEADER)] + [f"{key}\t{decision}\t\t\t\t" for key, decision in rows]
    path.write_text("\n".join(lines) + "\n")
    return str(path)


# SPLITTING


@pytest.mark.unit
def test_multi_component_is_read_from_the_formula_layer():
    """A dot in the formula layer marks a multi-component InChI; a single compound is not one."""
    assert is_multi_component(PETHIDINE_HCL)
    assert not is_multi_component(PETHIDINE)


@pytest.mark.unit
def test_split_hydrochloride_gives_parent_and_hcl_keys():
    """Pethidine HCl should split into pethidine (PubChem's own key for CID 4058) and HCl, largest first."""
    assert [(key, heavy) for key, heavy, _ in split_inchi(PETHIDINE_HCL)] == [
        ("XADCESSVHJOZHK-UHFFFAOYSA-N", 18),
        ("VEXZGXHMUGYJMC-UHFFFAOYSA-N", 1),
    ]


@pytest.mark.unit
def test_split_sodium_salt_keeps_the_anion_charge():
    """Naproxen sodium should split into the naproxen anion (-M) and the sodium cation."""
    keys = [key for key, _, _ in split_inchi(NAPROXEN_NA)]
    assert keys == ["CMWTZPSULFXXJA-UHFFFAOYSA-M", "FKNQFGJONOIPTF-UHFFFAOYSA-N"]


@pytest.mark.unit
def test_unparseable_inchi_returns_none():
    """An InChI RDKit can't parse should give None, so the caller counts it and the record keeps its own key."""
    assert split_inchi("InChI=1S/not-an-inchi") is None


@pytest.mark.unit
def test_fragment_that_cannot_be_kekulized_returns_none():
    """A fragment RDKit sanitizes but can't kekulize for its InChI should make the InChI unsplittable, not crash."""
    assert split_inchi(UNKEKULIZABLE) is None


@pytest.mark.unit
def test_parent_key_drops_protonation_block():
    """A component's parent key is its InChIKey without the protonation block."""
    assert parent_key("CMWTZPSULFXXJA-UHFFFAOYSA-M") == "CMWTZPSULFXXJA-UHFFFAOYSA"
    with pytest.raises(ValueError):
        parent_key("CMWTZPSULFXXJA-UHFFFAOYSA")


@pytest.mark.unit
def test_write_inchi_components_from_pubchem_lines(tmp_path):
    """Only multi-component InChIs should be written, one row per component, from PubChem's three-column file."""
    pubchem = tmp_path / "CID-InChI-Key.gz"
    with gzip.open(pubchem, "wt") as f:
        f.write(f"4058\t{PETHIDINE}\tXADCESSVHJOZHK-UHFFFAOYSA-N\n")
        f.write(f"5750\t{PETHIDINE_HCL}\tWCNLCIJMFAJCPX-UHFFFAOYSA-N\n")
    out = tmp_path / "components.tsv"
    counts = write_inchi_components(str(pubchem), str(out), processes=1)
    rows = [line.split("\t")[:2] for line in out.read_text().splitlines()[1:]]
    assert rows == [
        ["WCNLCIJMFAJCPX-UHFFFAOYSA-N", "XADCESSVHJOZHK-UHFFFAOYSA-N"],
        ["WCNLCIJMFAJCPX-UHFFFAOYSA-N", "VEXZGXHMUGYJMC-UHFFFAOYSA-N"],
    ]
    assert counts == {"multi_component_inchis": 1, "component_rows": 2, "unparseable_inchis": 0, "timed_out_inchis": 0}


@pytest.mark.unit
def test_hanging_inchi_times_out_without_losing_its_chunk(tmp_path):
    """The pentafoil knot hangs RDKit's parser: it should be counted as timed out, and its chunk-mates still split."""
    pubchem = tmp_path / "CID-InChI-Key.gz"
    with gzip.open(pubchem, "wt") as f:
        f.write(f"53389302\t{PENTAFOIL_KNOT}\tSAXWRJNZTZOAOQ-UHFFFAOYSA-N\n")
        f.write(f"5750\t{PETHIDINE_HCL}\tWCNLCIJMFAJCPX-UHFFFAOYSA-N\n")
    out = tmp_path / "components.tsv"
    counts = write_inchi_components(str(pubchem), str(out), processes=1, chunk_timeout=1, item_timeout=2)
    assert {line.split("\t")[0] for line in out.read_text().splitlines()[1:]} == {"WCNLCIJMFAJCPX-UHFFFAOYSA-N"}
    assert counts["timed_out_inchis"] == 1
    assert counts["multi_component_inchis"] == 2


# RESOLVING A PARENT


@pytest.mark.unit
def test_salt_resolves_to_parent_when_counterion_is_dropped():
    """With HCl marked drop, pethidine HCl should map to pethidine's parent key."""
    keys = [key for key, _, _ in split_inchi(PETHIDINE_HCL)]
    assert resolve_parent(keys, {HCL_PARENT: "drop"}) == "XADCESSVHJOZHK-UHFFFAOYSA"


@pytest.mark.unit
def test_unlisted_counterion_blocks_the_mapping():
    """An unreviewed component is kept, so a salt whose counterion isn't listed keeps its own key."""
    keys = [key for key, _, _ in split_inchi(NAPROXEN_NA)]
    assert resolve_parent(keys, {HCL_PARENT: "drop"}) is None


@pytest.mark.unit
def test_keep_decision_blocks_like_an_unlisted_component():
    """A component marked keep (e.g. a metal centre) must never be dropped."""
    keys = [key for key, _, _ in split_inchi(NAPROXEN_NA)]
    assert resolve_parent(keys, {SODIUM_ION_PARENT: "keep"}) is None


@pytest.mark.unit
def test_all_components_dropped_keeps_own_key():
    """If every component is on the drop list (hydroxide as water, lithium), there is no parent to map to."""
    keys = [key for key, _, _ in split_inchi(LITHIUM_HYDROXIDE)]
    assert resolve_parent(keys, {WATER_PARENT: "drop", LITHIUM_ION_PARENT: "drop"}) is None
    assert resolve_parent(keys, {WATER_PARENT: "drop"}) == LITHIUM_ION_PARENT


# THE REVIEWED LIST


@pytest.mark.unit
def test_read_component_decisions(tmp_path):
    """A valid list should load into {parent key: decision}."""
    path = write_decisions(tmp_path / "list.tsv", [(HCL_PARENT, "drop"), (SODIUM_ION_PARENT, "keep")])
    assert read_component_decisions(path) == {HCL_PARENT: "drop", SODIUM_ION_PARENT: "keep"}


@pytest.mark.unit
@pytest.mark.parametrize(
    "rows",
    [
        [(HCL_PARENT, "remove")],  # unknown decision
        [(HCL_PARENT + "-N", "drop")],  # a full key, not a parent key
        [(HCL_PARENT, "drop"), (HCL_PARENT, "keep")],  # listed twice
    ],
)
def test_read_component_decisions_rejects_bad_edits(tmp_path, rows):
    """A bad edit to the reviewed list should fail loudly rather than silently change what gets dropped."""
    with pytest.raises(ValueError):
        read_component_decisions(write_decisions(tmp_path / "list.tsv", rows))


# WRITING SALT PARENTS


@pytest.mark.unit
def test_write_salt_parents_resolves_blocks_and_counts(tmp_path):
    """Pethidine HCl should resolve, naproxen sodium stay blocked (Na+ unlisted), and LiOH have every part dropped."""
    pubchem = tmp_path / "CID-InChI-Key.gz"
    with gzip.open(pubchem, "wt") as f:
        f.write(f"5750\t{PETHIDINE_HCL}\tWCNLCIJMFAJCPX-UHFFFAOYSA-N\n")
        f.write(f"1301\t{NAPROXEN_NA}\tCDBRNDSHEYLDJV-UHFFFAOYSA-M\n")
        f.write(f"3939\t{LITHIUM_HYDROXIDE}\tWMFOQBRAJBCJND-UHFFFAOYSA-M\n")
    components = tmp_path / "components.tsv"
    write_inchi_components(str(pubchem), str(components), processes=1)
    decisions = write_decisions(
        tmp_path / "list.tsv", [(HCL_PARENT, "drop"), (WATER_PARENT, "drop"), (LITHIUM_ION_PARENT, "drop")]
    )
    out = tmp_path / "salt_parents.tsv"
    counts = write_salt_parents(str(components), decisions, str(out))
    assert out.read_text().splitlines() == [
        "salt_parent_key\tparent_key",
        "WCNLCIJMFAJCPX-UHFFFAOYSA\tXADCESSVHJOZHK-UHFFFAOYSA",
    ]
    assert counts == {"records": 3, "resolved": 1, "every_component_dropped": 1, "blocked": 1}
