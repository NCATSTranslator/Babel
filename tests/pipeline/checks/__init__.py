from typing import NamedTuple


class IdentifierCheck(NamedTuple):
    fixture: str        # session fixture name, e.g. "mesh_pipeline_outputs"
    compendium: str     # key in the fixture output dict, e.g. "chemicals", "protein"
    curie: str          # CURIE to look for in the compendium's intermediate ID file
    expected_type: str  # Biolink type (asserted if file has a type column, e.g. UMLS)
    issue: str          # GitHub issue URL that motivated this check


class ConcordCheck(NamedTuple):
    fixture: str        # session fixture providing the concords directory path
    curie1: str
    curie2: str
    should_xref: bool   # True = must be a direct xref pair; False = must NOT be
    issue: str          # GitHub issue URL that motivated this check
