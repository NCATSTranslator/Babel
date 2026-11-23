"""In-memory fakes that let a unit test run write_compendium() without a Biolink Model, downloads or a build."""

from types import SimpleNamespace

import pytest

import src.babel_utils as babel_utils


class FakeNodeFactory:
    """Stands in for NodeFactory: keeps every identifier, labels it from the `labels` it is given, and gives each type
    the ancestors in `ancestors` (just the type itself by default), so the test needs no Biolink Model."""

    # Biolink type -> what get_ancestors() returns for it. A test that needs real ancestors sets this with monkeypatch.
    ancestors = {}

    def __init__(self, *args):
        pass

    def create_node(self, input_identifiers, node_type, labels, extra_prefixes):
        if not input_identifiers:
            return None
        identifiers = []
        for curie in input_identifiers:
            identifier = {"identifier": curie}
            if curie in labels:
                identifier["label"] = labels[curie]
            identifiers.append(identifier)
        return {"identifiers": identifiers, "type": node_type}

    def get_ancestors(self, node_type):
        return self.ancestors.get(node_type, [node_type])

    def apply_labels(self, input_identifiers, labels, node_types):
        return list(input_identifiers)


class FakePropertyList:
    """Stands in for PropertyList, giving NCIT:C16375 one malformed HAS_ALTERNATIVE_ID CURIE."""

    def get_all(self, curie, predicate=None):
        if curie == "NCIT:C16375":
            return [SimpleNamespace(value="NCIT:C16375 extra", source="test")]
        return []


@pytest.fixture
def fake_write_compendium_env(tmp_path, monkeypatch):
    """Replace write_compendium()'s config, factories and property list with in-memory fakes, and return the output
    directory. The synonym factory finds no synonyms; a test that needs some replaces `babel_utils.SynonymFactory`."""
    config = {
        "output_directory": str(tmp_path),
        "download_directory": str(tmp_path / "downloads"),
        "biolink_version": "test",
        "preferred_name_boost_prefixes": {},
    }
    monkeypatch.setattr(babel_utils, "get_config", lambda: config)
    monkeypatch.setattr(babel_utils, "NodeFactory", FakeNodeFactory)
    monkeypatch.setattr(babel_utils, "PropertyList", FakePropertyList)
    empty = SimpleNamespace(
        get_synonyms=lambda *args, **kwargs: [],
        get_ic=lambda node: None,
        get_descriptions=lambda ids: {},
        get_taxa=lambda ids: {},
        close=lambda: None,
    )
    for factory in ["SynonymFactory", "InformationContentFactory", "DescriptionFactory", "TaxonFactory"]:
        monkeypatch.setattr(babel_utils, factory, lambda *args: empty)
    return tmp_path
