"""Unit tests for src/datahandlers/mesh.py

Tests cover:
  - write_ids() parameter validation
  - write_ids() SCR filtering logic (mock-based)
  - Mesh.get_scr_terms_mapped_to_trees() (inline pyoxigraph store)
"""
import io
from unittest.mock import MagicMock, patch

import pyoxigraph
import pytest

from src.categories import CHEMICAL_ENTITY, PROTEIN
from src.datahandlers.mesh import Mesh, write_ids

# ---------------------------------------------------------------------------
# Helpers for building an in-memory pyoxigraph store
# ---------------------------------------------------------------------------

_MESH_NS = "http://id.nlm.nih.gov/mesh/"
_MESHV_NS = "http://id.nlm.nih.gov/mesh/vocab#"


def _mesh(local: str) -> pyoxigraph.NamedNode:
    return pyoxigraph.NamedNode(f"{_MESH_NS}{local}")


def _meshv(local: str) -> pyoxigraph.NamedNode:
    return pyoxigraph.NamedNode(f"{_MESHV_NS}{local}")


def _quad(s, p, o) -> pyoxigraph.Quad:
    return pyoxigraph.Quad(s, p, o, pyoxigraph.DefaultGraph())


def _make_test_store() -> pyoxigraph.Store:
    """Return an in-memory Store with a small set of known MeSH-like triples.

    Fixture summary
    ---------------
    C000001 --mappedTo--> D12345 --treeNumber--> D12.776.123
                                   D12.776.123 --parentTreeNumber--> D12.776

    C000002 --preferredMappedTo--> D05678 --treeNumber--> D05.500.123
                                    D05.500.123 --parentTreeNumber--> D05.500
                                    D05.500     --parentTreeNumber--> D05

    C000003 --mappedTo--> D23456 --treeNumber--> D23.123
                                   D23.123 --parentTreeNumber--> D23
    """
    store = pyoxigraph.Store()
    mapped_to = _meshv("mappedTo")
    preferred_mapped_to = _meshv("preferredMappedTo")
    tree_number = _meshv("treeNumber")
    parent_tree = _meshv("parentTreeNumber")

    triples = [
        # C000001 under D12.776 (one hop)
        _quad(_mesh("C000001"), mapped_to, _mesh("D12345")),
        _quad(_mesh("D12345"), tree_number, _mesh("D12.776.123")),
        _quad(_mesh("D12.776.123"), parent_tree, _mesh("D12.776")),
        # C000002 under D05 (two hops via D05.500)
        _quad(_mesh("C000002"), preferred_mapped_to, _mesh("D05678")),
        _quad(_mesh("D05678"), tree_number, _mesh("D05.500.123")),
        _quad(_mesh("D05.500.123"), parent_tree, _mesh("D05.500")),
        _quad(_mesh("D05.500"), parent_tree, _mesh("D05")),
        # C000003 under D23 only (not protein)
        _quad(_mesh("C000003"), mapped_to, _mesh("D23456")),
        _quad(_mesh("D23456"), tree_number, _mesh("D23.123")),
        _quad(_mesh("D23.123"), parent_tree, _mesh("D23")),
    ]
    for quad in triples:
        store.add(quad)
    return store


def _make_mesh_with_store(store: pyoxigraph.Store) -> Mesh:
    """Construct a Mesh instance without loading a file, injecting a store."""
    obj = Mesh.__new__(Mesh)
    obj.m = store
    return obj


# ---------------------------------------------------------------------------
# Group 1: write_ids() parameter validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_write_ids_raises_when_both_scr_params_set(tmp_path):
    outfile = str(tmp_path / "out.txt")
    with pytest.raises(ValueError, match="cannot both be set"):
        write_ids(
            {},
            outfile,
            scr_exclude_trees=["D05"],
            scr_include_trees=["D12.776"],
        )


# ---------------------------------------------------------------------------
# Group 2: write_ids() filtering logic (Mesh mocked)
# ---------------------------------------------------------------------------


def _make_mock_mesh(
    tree_map: dict[str, list[str]],
    scr_chemical_terms: list[str],
    scr_mapped_to_trees: dict[tuple, set[str]] | None = None,
) -> MagicMock:
    """Return a configured MagicMock for the Mesh instance.

    tree_map: treenum → list of CURIE strings returned by get_terms_in_tree
    scr_chemical_terms: list returned by get_terms_with_type("SCR_Chemical")
    scr_mapped_to_trees: mapping of frozenset(top_treenums) → set of CURIEs
    """
    mock = MagicMock()
    mock.get_terms_in_tree.side_effect = lambda t: tree_map.get(t, [])
    mock.get_terms_with_type.return_value = scr_chemical_terms

    if scr_mapped_to_trees is not None:
        def _mapped(trees):
            return scr_mapped_to_trees.get(tuple(sorted(trees)), set())
        mock.get_scr_terms_mapped_to_trees.side_effect = _mapped

    return mock


@pytest.mark.unit
@patch("src.datahandlers.mesh.Mesh")
def test_write_ids_scr_exclude_trees_removes_protein_scrs(mock_cls, tmp_path):
    mock_mesh = _make_mock_mesh(
        tree_map={"D02": ["MESH:D000002"]},
        scr_chemical_terms=["MESH:C000001", "MESH:C000002"],
        scr_mapped_to_trees={("D05",): {"MESH:C000001"}},
    )
    mock_cls.return_value = mock_mesh
    outfile = str(tmp_path / "out.txt")

    write_ids(
        {"D02": CHEMICAL_ENTITY},
        outfile,
        order=["EXCLUDE", CHEMICAL_ENTITY],
        extra_vocab={"SCR_Chemical": CHEMICAL_ENTITY},
        scr_exclude_trees=["D05"],
    )

    content = open(outfile).read()
    assert "MESH:D000002" in content
    assert "MESH:C000002" in content
    assert "MESH:C000001" not in content


@pytest.mark.unit
@patch("src.datahandlers.mesh.Mesh")
def test_write_ids_scr_include_trees_keeps_only_protein_scrs(mock_cls, tmp_path):
    include_trees = ["D05", "D08", "D12.776"]
    mock_mesh = _make_mock_mesh(
        tree_map={"D12.776": ["MESH:D000001"]},
        scr_chemical_terms=["MESH:C000001", "MESH:C000002"],
        scr_mapped_to_trees={tuple(sorted(include_trees)): {"MESH:C000001"}},
    )
    mock_cls.return_value = mock_mesh
    outfile = str(tmp_path / "out.txt")

    write_ids(
        {"D12.776": PROTEIN},
        outfile,
        order=[PROTEIN],
        extra_vocab={"SCR_Chemical": PROTEIN},
        scr_include_trees=include_trees,
    )

    content = open(outfile).read()
    assert "MESH:D000001" in content
    assert "MESH:C000001" in content
    assert "MESH:C000002" not in content


@pytest.mark.unit
@patch("src.datahandlers.mesh.Mesh")
def test_write_ids_default_includes_all_scr_terms(mock_cls, tmp_path):
    mock_mesh = _make_mock_mesh(
        tree_map={"D02": ["MESH:D000002"]},
        scr_chemical_terms=["MESH:C000001", "MESH:C000002"],
    )
    mock_cls.return_value = mock_mesh
    outfile = str(tmp_path / "out.txt")

    write_ids(
        {"D02": CHEMICAL_ENTITY},
        outfile,
        order=[CHEMICAL_ENTITY],
        extra_vocab={"SCR_Chemical": CHEMICAL_ENTITY},
    )

    content = open(outfile).read()
    assert "MESH:D000002" in content
    assert "MESH:C000001" in content
    assert "MESH:C000002" in content
    mock_mesh.get_scr_terms_mapped_to_trees.assert_not_called()


@pytest.mark.unit
@patch("src.datahandlers.mesh.Mesh")
def test_write_ids_exclude_flag_suppresses_term_from_output(mock_cls, tmp_path):
    mock_mesh = _make_mock_mesh(
        tree_map={"D02": ["MESH:D000002"], "D05": ["MESH:D000005"]},
        scr_chemical_terms=["MESH:C000001", "MESH:C000002"],
        scr_mapped_to_trees={("D05",): {"MESH:C000001"}},
    )
    mock_cls.return_value = mock_mesh
    outfile = str(tmp_path / "out.txt")

    write_ids(
        {"D02": CHEMICAL_ENTITY, "D05": "EXCLUDE"},
        outfile,
        order=["EXCLUDE", CHEMICAL_ENTITY],
        extra_vocab={"SCR_Chemical": CHEMICAL_ENTITY},
        scr_exclude_trees=["D05"],
    )

    content = open(outfile).read()
    assert "MESH:D000002" in content
    assert "MESH:C000002" in content
    assert "MESH:D000005" not in content  # in D05 tree → EXCLUDE
    assert "MESH:C000001" not in content  # mapped to D05 → EXCLUDE


# ---------------------------------------------------------------------------
# Group 3: get_scr_terms_mapped_to_trees() with inline pyoxigraph store
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def mesh_with_test_store():
    store = _make_test_store()
    return _make_mesh_with_store(store)


@pytest.mark.unit
def test_get_scr_terms_mapped_to_trees_direct_mapping(mesh_with_test_store):
    result = mesh_with_test_store.get_scr_terms_mapped_to_trees(["D12.776"])
    assert result == {"MESH:C000001"}


@pytest.mark.unit
def test_get_scr_terms_mapped_to_trees_transitive_parent(mesh_with_test_store):
    result = mesh_with_test_store.get_scr_terms_mapped_to_trees(["D05"])
    assert result == {"MESH:C000002"}


@pytest.mark.unit
def test_get_scr_terms_mapped_to_trees_preferred_mapped_to(mesh_with_test_store):
    # C000002 uses preferredMappedTo — covered by the D05 transitive test above,
    # but explicitly confirmed here for clarity.
    result = mesh_with_test_store.get_scr_terms_mapped_to_trees(["D05"])
    assert "MESH:C000002" in result


@pytest.mark.unit
def test_get_scr_terms_mapped_to_trees_multiple_top_treenums(mesh_with_test_store):
    result = mesh_with_test_store.get_scr_terms_mapped_to_trees(["D12.776", "D05"])
    assert result == {"MESH:C000001", "MESH:C000002"}
    assert "MESH:C000003" not in result


@pytest.mark.unit
def test_get_scr_terms_mapped_to_trees_no_match(mesh_with_test_store):
    result = mesh_with_test_store.get_scr_terms_mapped_to_trees(["D01"])
    assert result == set()
