"""Single source of truth for UMLS semantic-type -> Biolink Model mappings.

Babel assigns a Biolink Model class to every UMLS concept based on its UMLS semantic type.
Historically this lived in two disconnected forms:

1. **Partition maps** -- hardcoded dicts in each ``src/createcompendia/*.py`` ``write_umls_ids()``
   that decide which *typed compendium* claims a CUI. They key on the MRSTY semantic-type *tree
   number* column (e.g. ``A1.4.1.2.1.7``). These are Babel's own decisions; the Biolink Model is
   not consulted.
2. **Biolink catch-all** -- ``src/createcompendia/leftover_umls.py`` consults the Biolink Model's
   own ``STY:T###`` mappings via ``Toolkit.get_element_by_mapping`` for the residual CUIs that no
   typed compendium claimed.

This module unifies both. The canonical key everywhere is the UMLS **tree number** (STN); the
Type Unique Identifier (TUI, e.g. ``T116``) is translated to/from the tree number via
:data:`SEMANTIC_NETWORK` when needed (e.g. to query the Biolink Model, which keys on ``STY:T###``).

:data:`UMLS_TYPE_MAP` is the one place that records, per tree number, which compendium owns it and
what Biolink class it gets, plus -- where Babel deliberately diverges from the Biolink Model -- a
tracking GitHub issue and a ``disagrees_with_biolink`` flag. The flag drives the redundancy test in
``tests/datahandlers/test_umls_semantic_types.py`` that fails once the Biolink Model itself adopts
our mapping (signalling the override is no longer needed).

Per-compendium blocklists are intentionally **not** centralized here -- they remain local to each
``createcompendia`` module, because they are component-specific exclusion logic rather than
type assignments.

The rest of ``src/datahandlers/umls/__init__.py`` should be split into subfiles; this module is the
first piece of that package. See https://github.com/NCATSTranslator/Babel/issues/802.
"""

from dataclasses import dataclass

from src.categories import (
    ACTIVITY,
    AGENT,
    ANATOMICAL_ENTITY,
    BIOLOGICAL_PROCESS,
    CELL,
    CELLULAR_COMPONENT,
    CHEMICAL_ENTITY,
    CLINICAL_FINDING,
    DEVICE,
    DISEASE,
    DRUG,
    FOOD,
    MOLECULAR_ACTIVITY,
    ORGANISM_TAXON,
    PHENOMENON,
    PHENOTYPIC_FEATURE,
    PHYSICAL_ENTITY,
    PROCEDURE,
    PROTEIN,
    PUBLICATION,
    SMALL_MOLECULE,
)
from src.util import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# UMLS Semantic Network: TUI <-> tree number <-> name.
#
# Generated from babel_downloads/UMLS/MRSTY.RRF (columns TUI|STN|STY). The UMLS Semantic Network
# is a small, controlled vocabulary that changes very rarely between UMLS releases, so it is
# hardcoded here to keep this module self-contained and usable offline. A --pipeline drift test
# (test_semantic_network_matches_mrsty) re-derives this from MRSTY.RRF and fails if UMLS ever
# changes it, so we notice at upgrade time. Each TUI maps 1:1 to a tree number.
# ---------------------------------------------------------------------------
SEMANTIC_NETWORK: dict[str, tuple[str, str]] = {
    "T071": ("A", "Entity"),
    "T072": ("A1", "Physical Object"),
    "T001": ("A1.1", "Organism"),
    "T194": ("A1.1.1", "Archaeon"),
    "T007": ("A1.1.2", "Bacterium"),
    "T204": ("A1.1.3", "Eukaryote"),
    "T008": ("A1.1.3.1", "Animal"),
    "T010": ("A1.1.3.1.1", "Vertebrate"),
    "T011": ("A1.1.3.1.1.1", "Amphibian"),
    "T012": ("A1.1.3.1.1.2", "Bird"),
    "T013": ("A1.1.3.1.1.3", "Fish"),
    "T015": ("A1.1.3.1.1.4", "Mammal"),
    "T016": ("A1.1.3.1.1.4.1", "Human"),
    "T014": ("A1.1.3.1.1.5", "Reptile"),
    "T004": ("A1.1.3.2", "Fungus"),
    "T002": ("A1.1.3.3", "Plant"),
    "T005": ("A1.1.4", "Virus"),
    "T017": ("A1.2", "Anatomical Structure"),
    "T018": ("A1.2.1", "Embryonic Structure"),
    "T190": ("A1.2.2", "Anatomical Abnormality"),
    "T019": ("A1.2.2.1", "Congenital Abnormality"),
    "T020": ("A1.2.2.2", "Acquired Abnormality"),
    "T021": ("A1.2.3", "Fully Formed Anatomical Structure"),
    "T023": ("A1.2.3.1", "Body Part, Organ, or Organ Component"),
    "T024": ("A1.2.3.2", "Tissue"),
    "T025": ("A1.2.3.3", "Cell"),
    "T026": ("A1.2.3.4", "Cell Component"),
    "T028": ("A1.2.3.5", "Gene or Genome"),
    "T073": ("A1.3", "Manufactured Object"),
    "T074": ("A1.3.1", "Medical Device"),
    "T203": ("A1.3.1.1", "Drug Delivery Device"),
    "T075": ("A1.3.2", "Research Device"),
    "T200": ("A1.3.3", "Clinical Drug"),
    "T167": ("A1.4", "Substance"),
    "T103": ("A1.4.1", "Chemical"),
    "T120": ("A1.4.1.1", "Chemical Viewed Functionally"),
    "T121": ("A1.4.1.1.1", "Pharmacologic Substance"),
    "T195": ("A1.4.1.1.1.1", "Antibiotic"),
    "T122": ("A1.4.1.1.2", "Biomedical or Dental Material"),
    "T123": ("A1.4.1.1.3", "Biologically Active Substance"),
    "T125": ("A1.4.1.1.3.2", "Hormone"),
    "T126": ("A1.4.1.1.3.3", "Enzyme"),
    "T127": ("A1.4.1.1.3.4", "Vitamin"),
    "T129": ("A1.4.1.1.3.5", "Immunologic Factor"),
    "T192": ("A1.4.1.1.3.6", "Receptor"),
    "T130": ("A1.4.1.1.4", "Indicator, Reagent, or Diagnostic Aid"),
    "T131": ("A1.4.1.1.5", "Hazardous or Poisonous Substance"),
    "T104": ("A1.4.1.2", "Chemical Viewed Structurally"),
    "T109": ("A1.4.1.2.1", "Organic Chemical"),
    "T114": ("A1.4.1.2.1.5", "Nucleic Acid, Nucleoside, or Nucleotide"),
    "T116": ("A1.4.1.2.1.7", "Amino Acid, Peptide, or Protein"),
    "T197": ("A1.4.1.2.2", "Inorganic Chemical"),
    "T196": ("A1.4.1.2.3", "Element, Ion, or Isotope"),
    "T031": ("A1.4.2", "Body Substance"),
    "T168": ("A1.4.3", "Food"),
    "T077": ("A2", "Conceptual Entity"),
    "T078": ("A2.1", "Idea or Concept"),
    "T079": ("A2.1.1", "Temporal Concept"),
    "T080": ("A2.1.2", "Qualitative Concept"),
    "T081": ("A2.1.3", "Quantitative Concept"),
    "T169": ("A2.1.4", "Functional Concept"),
    "T022": ("A2.1.4.1", "Body System"),
    "T082": ("A2.1.5", "Spatial Concept"),
    "T030": ("A2.1.5.1", "Body Space or Junction"),
    "T029": ("A2.1.5.2", "Body Location or Region"),
    "T085": ("A2.1.5.3", "Molecular Sequence"),
    "T086": ("A2.1.5.3.1", "Nucleotide Sequence"),
    "T087": ("A2.1.5.3.2", "Amino Acid Sequence"),
    "T088": ("A2.1.5.3.3", "Carbohydrate Sequence"),
    "T083": ("A2.1.5.4", "Geographic Area"),
    "T033": ("A2.2", "Finding"),
    "T034": ("A2.2.1", "Laboratory or Test Result"),
    "T184": ("A2.2.2", "Sign or Symptom"),
    "T032": ("A2.3", "Organism Attribute"),
    "T201": ("A2.3.1", "Clinical Attribute"),
    "T170": ("A2.4", "Intellectual Product"),
    "T185": ("A2.4.1", "Classification"),
    "T089": ("A2.4.2", "Regulation or Law"),
    "T171": ("A2.5", "Language"),
    "T090": ("A2.6", "Occupation or Discipline"),
    "T091": ("A2.6.1", "Biomedical Occupation or Discipline"),
    "T092": ("A2.7", "Organization"),
    "T093": ("A2.7.1", "Health Care Related Organization"),
    "T094": ("A2.7.2", "Professional Society"),
    "T095": ("A2.7.3", "Self-help or Relief Organization"),
    "T102": ("A2.8", "Group Attribute"),
    "T096": ("A2.9", "Group"),
    "T097": ("A2.9.1", "Professional or Occupational Group"),
    "T098": ("A2.9.2", "Population Group"),
    "T099": ("A2.9.3", "Family Group"),
    "T100": ("A2.9.4", "Age Group"),
    "T101": ("A2.9.5", "Patient or Disabled Group"),
    "T051": ("B", "Event"),
    "T052": ("B1", "Activity"),
    "T053": ("B1.1", "Behavior"),
    "T054": ("B1.1.1", "Social Behavior"),
    "T055": ("B1.1.2", "Individual Behavior"),
    "T056": ("B1.2", "Daily or Recreational Activity"),
    "T057": ("B1.3", "Occupational Activity"),
    "T058": ("B1.3.1", "Health Care Activity"),
    "T059": ("B1.3.1.1", "Laboratory Procedure"),
    "T060": ("B1.3.1.2", "Diagnostic Procedure"),
    "T061": ("B1.3.1.3", "Therapeutic or Preventive Procedure"),
    "T062": ("B1.3.2", "Research Activity"),
    "T063": ("B1.3.2.1", "Molecular Biology Research Technique"),
    "T064": ("B1.3.3", "Governmental or Regulatory Activity"),
    "T065": ("B1.3.4", "Educational Activity"),
    "T066": ("B1.4", "Machine Activity"),
    "T067": ("B2", "Phenomenon or Process"),
    "T068": ("B2.1", "Human-caused Phenomenon or Process"),
    "T069": ("B2.1.1", "Environmental Effect of Humans"),
    "T070": ("B2.2", "Natural Phenomenon or Process"),
    "T038": ("B2.2.1", "Biologic Function"),
    "T039": ("B2.2.1.1", "Physiologic Function"),
    "T040": ("B2.2.1.1.1", "Organism Function"),
    "T041": ("B2.2.1.1.1.1", "Mental Process"),
    "T042": ("B2.2.1.1.2", "Organ or Tissue Function"),
    "T043": ("B2.2.1.1.3", "Cell Function"),
    "T044": ("B2.2.1.1.4", "Molecular Function"),
    "T045": ("B2.2.1.1.4.1", "Genetic Function"),
    "T046": ("B2.2.1.2", "Pathologic Function"),
    "T047": ("B2.2.1.2.1", "Disease or Syndrome"),
    "T048": ("B2.2.1.2.1.1", "Mental or Behavioral Dysfunction"),
    "T191": ("B2.2.1.2.1.2", "Neoplastic Process"),
    "T049": ("B2.2.1.2.2", "Cell or Molecular Dysfunction"),
    "T050": ("B2.2.1.2.3", "Experimental Model of Disease"),
    "T037": ("B2.3", "Injury or Poisoning"),
}

# Reverse index: tree number -> TUI.
_TREE_NUMBER_TO_TUI: dict[str, str] = {stn: tui for tui, (stn, _name) in SEMANTIC_NETWORK.items()}


def tui_to_tree_number(tui: str) -> str:
    """Translate a UMLS TUI (e.g. ``T116``) to its semantic-type tree number (e.g. ``A1.4.1.2.1.7``)."""
    if tui not in SEMANTIC_NETWORK:
        raise ValueError(f"Unknown UMLS TUI: {tui!r}")
    return SEMANTIC_NETWORK[tui][0]


def tree_number_to_tui(tree_number: str) -> str:
    """Translate a UMLS semantic-type tree number (e.g. ``A1.4.1.2.1.7``) to its TUI (e.g. ``T116``)."""
    if tree_number not in _TREE_NUMBER_TO_TUI:
        raise ValueError(f"Unknown UMLS semantic-type tree number: {tree_number!r}")
    return _TREE_NUMBER_TO_TUI[tree_number]


def tree_number_name(tree_number: str) -> str:
    """Return the human-readable name for a UMLS semantic-type tree number."""
    return SEMANTIC_NETWORK[tree_number_to_tui(tree_number)][1]


# ---------------------------------------------------------------------------
# The unified UMLS-type -> Biolink-class registry.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UMLSTypeAssignment:
    """One UMLS semantic-type -> Biolink-class assignment, keyed by tree number.

    :param tree_number: UMLS semantic-type tree number (the canonical key), e.g. ``B2.2.1.2.1.2``.
    :param biolink_type: The Biolink class Babel **actually assigns** to CUIs of this type (a
        constant from :mod:`src.categories`), or ``None`` if this tree number is recorded for
        documentation/validation only (e.g. the gene path) and assigns no class through this
        registry.
    :param compendium: The createcompendia module that owns CUIs of this type
        (``"chemicals"``, ``"protein"``, ``"anatomy"``, ``"diseasephenotype"``, ``"process"``,
        ``"taxon"``, ``"gene"``), or ``None`` for a leftover-only assignment that exists purely to
        override the Biolink Model in the ``leftover_umls`` catch-all.
    :param proposed_biolink_type: The Biolink class Babel argues the Biolink **Model itself** should
        map the corresponding ``STY:T###`` to. Set this to record a tracked disagreement with the
        Biolink Model. It may equal ``biolink_type`` (we have already applied our preferred type and
        want the Model to follow) or differ from it (we propose a change we have not yet applied --
        e.g. because the target class is not an output of the owning compendium). When ``None``,
        Babel does not dispute the Biolink Model's mapping for this type.
    :param issue: GitHub issue URL. Required whenever ``proposed_biolink_type`` is set.
    :param allow_xfail_when_adopted: If True, the redundancy test xfails (rather than hard-fails)
        when the Biolink Model adopts ``proposed_biolink_type`` -- a grace window before the entry
        is removed.
    :param note: Free-text rationale, co-located with the assignment.
    """

    tree_number: str
    biolink_type: str | None
    compendium: str | None
    proposed_biolink_type: str | None = None
    issue: str | None = None
    allow_xfail_when_adopted: bool = True
    note: str = ""

    @property
    def disagrees_with_biolink(self) -> bool:
        """True if this entry records a proposed change to the Biolink Model's own mapping."""
        return self.proposed_biolink_type is not None


def _assign(tree_numbers, biolink_type, compendium, **kwargs) -> list[UMLSTypeAssignment]:
    """Helper: build one assignment per tree number, all sharing the same fields."""
    return [UMLSTypeAssignment(tn, biolink_type, compendium, **kwargs) for tn in tree_numbers]


# The single source of truth. Each tree number appears exactly once (enforced at import by
# _validate()). Grouped by owning compendium to mirror the createcompendia modules that consume it.
_ASSIGNMENTS: list[UMLSTypeAssignment] = [
    # -- anatomy.py (was anatomy.write_umls_ids) --
    *_assign(
        ["A1.2", "A1.2.1", "A1.2.3.1", "A1.2.3.2", "A2.1.4.1", "A2.1.5.1", "A2.1.5.2"],
        ANATOMICAL_ENTITY,
        "anatomy",
    ),
    UMLSTypeAssignment("A1.2.3.3", CELL, "anatomy"),  # Cell
    UMLSTypeAssignment("A1.2.3.4", CELLULAR_COMPONENT, "anatomy"),  # Cell Component
    # -- chemicals.py (was chemicals.write_umls_ids) --
    *_assign(
        [
            "A1.4.1.1.1.1",  # Antibiotic
            "A1.4.1.1.3.2",  # Hormone
            "A1.4.1.1.3.4",  # Vitamin
            "A1.4.1.1.3.5",  # Immunologic Factor
            "A1.4.1.1.4",  # Indicator, Reagent, or Diagnostic Aid
            "A1.4.1.2",  # Chemical Viewed Structurally
            "A1.4.1.2.1",  # Organic Chemical
            "A1.4.1.2.1.5",  # Nucleic Acid, Nucleoside, or Nucleotide
            "A1.4.1.2.2",  # Inorganic Chemical
            "A1.4.1.2.3",  # Element, Ion, or Isotope
        ],
        CHEMICAL_ENTITY,
        "chemicals",
    ),
    UMLSTypeAssignment("A1.3.3", DRUG, "chemicals"),  # Clinical Drug
    # -- protein.py (was protein.write_umls_ids) --
    # Receptor (A1.4.1.1.3.6) and Enzyme (A1.4.1.1.3.3) are proteins; chemicals.py excludes them
    # via its local blocklist so they land here, not in chemicals.
    UMLSTypeAssignment("A1.4.1.2.1.7", PROTEIN, "protein"),  # Amino Acid, Peptide, or Protein (T116)
    UMLSTypeAssignment("A1.4.1.1.3.6", PROTEIN, "protein"),  # Receptor (T192)
    UMLSTypeAssignment("A1.4.1.1.3.3", PROTEIN, "protein"),  # Enzyme (T126)
    # -- diseasephenotype.py (was diseasephenotype.write_umls_ids) --
    *_assign(
        [
            "B2.2.1.2.1",  # Disease or Syndrome
            "A1.2.2.1",  # Congenital Abnormality
            "A1.2.2.2",  # Acquired Abnormality
            "B2.3",  # Injury or Poisoning
            "B2.2.1.2",  # Pathologic Function
            "B2.2.1.2.1.1",  # Mental or Behavioral Dysfunction
            "B2.2.1.2.2",  # Cell or Molecular Dysfunction
            "A1.2.2",  # Anatomical Abnormality
        ],
        DISEASE,
        "diseasephenotype",
    ),
    # B2.2.1.2.1.2 "Neoplastic Process" -- Babel assigns Disease today; we propose PhenotypicFeature
    # (#111). NOT applied yet: although both are diseasephenotype outputs (so flipping moves no CUI
    # between compendia), it would retype ~50k CUIs Disease -> PhenotypicFeature, and #111 itself
    # flags uncertainty about the consequences. Tracked here so the redundancy test watches the
    # Biolink Model; flip biolink_type to PHENOTYPIC_FEATURE to run that experiment on a build.
    UMLSTypeAssignment(
        "B2.2.1.2.1.2",
        DISEASE,
        "diseasephenotype",
        proposed_biolink_type=PHENOTYPIC_FEATURE,
        issue="https://github.com/NCATSTranslator/Babel/issues/111",
        note="Neoplastic Process reads better as a phenotypic feature than a disease (#111). "
        "Proposed but not applied; flipping biolink_type retypes ~50k CUIs within diseasephenotype.",
    ),
    *_assign(
        [
            "A2.2",  # Finding
            "A2.2.1",  # Laboratory or Test Result
            "A2.2.2",  # Sign or Symptom
            "A2.3",  # Organism Attribute
        ],
        PHENOTYPIC_FEATURE,
        "diseasephenotype",
    ),
    # -- processactivitypathway.py (was processactivitypathway.write_umls_ids) --
    UMLSTypeAssignment("B2.2.1.1.4", MOLECULAR_ACTIVITY, "process"),  # Molecular Function
    *_assign(
        [
            "B2.2.1.1",  # Physiologic Function
            "B2.2.1.1.1",  # Organism Function
            "B2.2.1.1.2",  # Organ or Tissue Function
            "B2.2.1.1.3",  # Cell Function
            "B2.2.1.1.4.1",  # Genetic Function (covers UMLS STY T045; see #257)
        ],
        BIOLOGICAL_PROCESS,
        "process",
    ),
    # -- taxon.py (was taxon.write_umls_ids) --
    *_assign(
        [
            "A1.1",  # Organism
            "A1.1.1",  # Archaeon
            "A1.1.2",  # Bacterium
            "A1.1.3",  # Eukaryote
            "A1.1.3.1",  # Animal
            "A1.1.3.1.1",  # Vertebrate
            "A1.1.3.1.1.1",  # Amphibian
            "A1.1.3.1.1.2",  # Bird
            "A1.1.3.1.1.3",  # Fish
            "A1.1.3.1.1.4",  # Mammal
            "A1.1.3.1.1.5",  # Reptile
            "A1.1.3.2",  # Fungus
            "A1.1.3.3",  # Plant
            "A1.1.4",  # Virus
        ],
        ORGANISM_TAXON,
        "taxon",
    ),
    # -- gene.py (documentation only) --
    # gene.py uses a bespoke MRCONSO cross-check, not this registry. Recorded here with no
    # biolink_type so the partition is documented and validation can see this tree number is
    # accounted for. Do NOT derive gene's category_map from this entry.
    UMLSTypeAssignment(
        "A1.2.3.5",
        None,
        "gene",
        note="Gene or Genome (T028). gene.py filters this tree directly with extra MRCONSO checks; "
        "this entry is documentation only and assigns no Biolink class through the registry.",
    ),
]

# Tracked disagreements with the Biolink Model that we have NOT yet applied, because doing so needs
# work beyond this registry (e.g. a new compendium output). They keep the biolink_type Babel uses
# today (so build behavior is unchanged) but record a proposed_biolink_type so the redundancy test
# tracks the Biolink Model and tells us if/when our proposal is adopted.
#
# A2.2 (Finding) and A2.2.1 (Laboratory or Test Result) are owned by diseasephenotype above
# (PhenotypicFeature). We attach the #569 disagreement by overlaying these fields onto those
# existing entries rather than duplicating tree numbers (which validation forbids).
_DISAGREEMENT_OVERLAY: dict[str, dict] = {
    "A2.2": {
        "proposed_biolink_type": PHENOMENON,
        "issue": "https://github.com/NCATSTranslator/Babel/issues/569",
        "note": "T033 Finding: Babel assigns PhenotypicFeature via the diseasephenotype partition, "
        "but proposes biolink:Phenomenon (#569/#548). Not applied yet because Phenomenon is not "
        "currently a diseasephenotype output. The Biolink Model currently maps STY:T033 to nothing.",
    },
    "A2.2.1": {
        "proposed_biolink_type": CLINICAL_FINDING,
        "issue": "https://github.com/NCATSTranslator/Babel/issues/569",
        "note": "T034 Laboratory or Test Result: Babel assigns PhenotypicFeature, but proposes "
        "biolink:ClinicalFinding (#569), a subclass of PhenotypicFeature. Not applied yet. The "
        "Biolink Model currently maps STY:T034 to biolink:Phenomenon.",
    },
}


def _build_type_map(assignments=_ASSIGNMENTS, overlay=_DISAGREEMENT_OVERLAY) -> dict[str, UMLSTypeAssignment]:
    by_tree: dict[str, UMLSTypeAssignment] = {}
    for a in assignments:
        if a.tree_number in by_tree:
            raise ValueError(
                f"UMLS tree number {a.tree_number} is assigned twice "
                f"(to {by_tree[a.tree_number].compendium} and {a.compendium}); each tree number "
                f"must be owned by exactly one compendium."
            )
        by_tree[a.tree_number] = a
    # Apply the disagreement overlay onto existing entries (never creating duplicates).
    from dataclasses import replace

    for tree_number, fields in overlay.items():
        if tree_number not in by_tree:
            raise ValueError(f"disagreement overlay references unknown tree number {tree_number!r}")
        by_tree[tree_number] = replace(by_tree[tree_number], **fields)
    return by_tree


#: The single source of truth: tree number -> :class:`UMLSTypeAssignment`.
UMLS_TYPE_MAP: dict[str, UMLSTypeAssignment] = _build_type_map()


def _validate(type_map=None) -> None:
    """Validate the registry; raise ``ValueError`` on any inconsistency. Runs at import time."""
    if type_map is None:
        type_map = UMLS_TYPE_MAP
    valid_categories = _known_category_constants()
    for tree_number, a in type_map.items():
        if tree_number not in _TREE_NUMBER_TO_TUI:
            raise ValueError(
                f"UMLS_TYPE_MAP tree number {tree_number!r} is not in the UMLS Semantic Network "
                f"(SEMANTIC_NETWORK). Typo, or a UMLS upgrade changed the tree numbers?"
            )
        for field_name in ("biolink_type", "proposed_biolink_type"):
            value = getattr(a, field_name)
            if value is not None and value not in valid_categories:
                raise ValueError(
                    f"UMLS_TYPE_MAP[{tree_number!r}].{field_name}={value!r} is not a known "
                    f"src.categories constant."
                )
        if a.disagrees_with_biolink and not a.issue:
            raise ValueError(
                f"UMLS_TYPE_MAP[{tree_number!r}] proposes a Biolink Model change (proposed_biolink_type) "
                f"but has no issue URL; record the tracking issue."
            )


def _known_category_constants() -> set[str]:
    """All ``biolink:`` class constants defined in :mod:`src.categories`."""
    from src import categories

    return {v for k, v in vars(categories).items() if k.isupper() and isinstance(v, str) and v.startswith("biolink:")}


_validate()


# ---------------------------------------------------------------------------
# Consumers: partition derivation + the leftover catch-all resolver.
# ---------------------------------------------------------------------------


def category_map_for(compendium: str) -> dict[str, str]:
    """Return the ``{tree_number: biolink_type}`` partition map for one compendium.

    This reproduces the hardcoded ``umlsmap`` dicts that used to live in each
    ``createcompendia/*.py`` ``write_umls_ids()``. It is passed straight to
    :func:`src.datahandlers.umls.write_umls_ids`.

    :param compendium: The owning compendium name (e.g. ``"chemicals"``).
    :return: Mapping of UMLS semantic-type tree number to Biolink class constant.
    """
    result = {a.tree_number: a.biolink_type for a in UMLS_TYPE_MAP.values() if a.compendium == compendium and a.biolink_type is not None}
    if not result:
        raise ValueError(f"No UMLS type assignments found for compendium {compendium!r}; is the name correct?")
    return result


def umls_tree_number_to_biolink_type(tree_number: str, tui: str, biolink_toolkit) -> str | None:
    """Resolve a UMLS semantic type to a Biolink class for the leftover catch-all.

    Babel's registry takes precedence: if ``tree_number`` has a Biolink class in
    :data:`UMLS_TYPE_MAP`, return it. Otherwise fall back to the Biolink Model's own mapping for
    the corresponding ``STY:T###`` (this is the long tail of semantic types Babel does not
    partition explicitly).

    :param tree_number: UMLS semantic-type tree number (MRSTY column 3).
    :param tui: UMLS Type Unique Identifier (MRSTY column 2), used for the Biolink Model fallback.
    :param biolink_toolkit: A ``bmt.Toolkit`` instance.
    :return: A Biolink class CURIE, or ``None`` if neither source yields one.
    """
    assignment = UMLS_TYPE_MAP.get(tree_number)
    if assignment is not None and assignment.biolink_type is not None:
        return assignment.biolink_type
    biolink_type = biolink_toolkit.get_element_by_mapping(f"STY:{tui}", most_specific=True, formatted=True, mixin=True)
    if biolink_type is None:
        logger.debug(f"No Biolink type found for UMLS TUI {tui} (tree number {tree_number})")
    return biolink_type


def _resolve_one_tui(tui: str, biolink_toolkit) -> str | None:
    """Resolve a single UMLS TUI to a Biolink class, registry-first then Biolink Model."""
    if tui in SEMANTIC_NETWORK:
        return umls_tree_number_to_biolink_type(SEMANTIC_NETWORK[tui][0], tui, biolink_toolkit)
    # Not a real UMLS TUI (e.g. the NamedThing fallback key used by leftover_umls): ask Biolink
    # directly, preserving the historical behavior (which returns None and skips the CURIE).
    return biolink_toolkit.get_element_by_mapping(f"STY:{tui}", most_specific=True, formatted=True, mixin=True)


# A UMLS concept can carry several TUIs and thus resolve to several Biolink types. These specific
# combinations are reduced to a single winning type; any other multi-type result is left ambiguous
# (the caller reports and skips it). Moved verbatim out of leftover_umls.py.
_MULTI_TYPE_RESOLUTIONS: list[tuple[frozenset, str]] = [
    (frozenset({DEVICE, DRUG}), DRUG),
    (frozenset({DRUG, SMALL_MOLECULE}), SMALL_MOLECULE),
    (frozenset({AGENT, PHYSICAL_ENTITY}), AGENT),
    (frozenset({PHYSICAL_ENTITY, PUBLICATION}), PUBLICATION),
    (frozenset({ACTIVITY, PROCEDURE}), PROCEDURE),
    (frozenset({DRUG, FOOD}), FOOD),
]


def resolve_biolink_types(tuis, biolink_toolkit) -> tuple[list[str], str]:
    """Resolve a collection of UMLS TUIs to a Biolink type for the leftover catch-all.

    Each TUI is resolved registry-first (then via the Biolink Model). If any TUI is unresolved the
    whole result is dropped; recognized multi-type combinations are reduced to a single winner.

    :param tuis: An iterable of UMLS TUIs (e.g. the keys of a ``{tui: {names}}`` dict).
    :param biolink_toolkit: A ``bmt.Toolkit`` instance.
    :return: A tuple ``(types, types_as_str)`` where ``types`` is ``[]`` (drop), ``[one_type]``
        (resolved), or a list of length > 1 (still ambiguous, report and skip); ``types_as_str`` is
        a stable ``|``-joined summary for the report (with ``None`` shown as ``(None)``).
    """
    resolved = {_resolve_one_tui(tui, biolink_toolkit) for tui in tuis}
    as_set = {"(None)" if t is None else t for t in resolved}
    types_as_str = "|".join(sorted(as_set))

    types: list[str] = [] if None in resolved else list(resolved)
    for combo, winner in _MULTI_TYPE_RESOLUTIONS:
        if as_set == set(combo):
            types = [winner]
            break
    return types, types_as_str
