import json
import os
from collections import defaultdict
from collections.abc import Iterator
from typing import NamedTuple

from src.babel_utils import TypedClique, write_compendium
from src.predicates import HAS_EXACT_SYNONYM
from src.util import get_logger

logger = get_logger(__name__)


class ManualTerm(NamedTuple):
    """A single hand-curated identifier with its Biolink type and names."""

    curie: str
    biolink_type: str
    preferred: str
    alternatives: list[str]


# Source-of-truth for hand-curated identifiers, as NDJSON (one JSON object per line -- the
# consortium's current standard). Each object has:
#   curie         -- the identifier, e.g. "EUPATH:0009259"
#   type          -- a Biolink class CURIE, e.g. "biolink:ClinicalFinding"
#   preferred     -- the preferred name (also written to the prefix's labels file)
#   alternatives  -- a list of zero or more synonym strings
# Adding a term is adding a line here, provided the term's prefix is listed in
# config["manual_prefixes"]. Blank lines are ignored.
DEFAULT_TERMS_FILE = "input_data/manual_terms.ndjson"


def read_manual_terms(terms_file: str = DEFAULT_TERMS_FILE) -> Iterator[ManualTerm]:
    """Yield one ManualTerm per non-blank NDJSON line."""
    with open(terms_file) as inf:
        for line in inf:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            yield ManualTerm(
                curie=obj["curie"],
                biolink_type=obj["type"],
                preferred=obj["preferred"],
                alternatives=list(obj.get("alternatives", [])),
            )


def write_manual_labels_and_synonyms(terms_file: str, download_directory: str, prefixes: list[str]) -> None:
    """
    Materialize the per-prefix ``labels`` and ``synonyms`` TSV files that SynonymFactory reads at
    build time (src/node.py:70-98). Follows the convention of src/datahandlers/umls.py: every name
    (preferred and alternative) is written as an hasExactSynonym, and the preferred name is also
    written to the ``labels`` file (which feeds the preferred-name path). Only prefixes listed in
    ``prefixes`` (i.e. config["manual_prefixes"]) are emitted, so every curated prefix must appear
    there or its term will have no names and be skipped downstream.
    """
    terms_by_prefix: dict[str, dict[str, ManualTerm]] = defaultdict(dict)
    for term in read_manual_terms(terms_file):
        prefix = term.curie.split(":", 1)[0]
        terms_by_prefix[prefix][term.curie] = term

    for prefix in prefixes:
        prefix_dir = os.path.join(download_directory, prefix)
        os.makedirs(prefix_dir, exist_ok=True)
        terms = terms_by_prefix.get(prefix, {})
        with (
            open(os.path.join(prefix_dir, "labels"), "w") as labels_f,
            open(os.path.join(prefix_dir, "synonyms"), "w") as synonyms_f,
        ):
            for curie in sorted(terms):
                term = terms[curie]
                if term.preferred:
                    labels_f.write(f"{curie}\t{term.preferred}\n")
                    synonyms_f.write(f"{curie}\t{HAS_EXACT_SYNONYM}\t{term.preferred}\n")
                for alternative in term.alternatives:
                    synonyms_f.write(f"{curie}\t{HAS_EXACT_SYNONYM}\t{alternative}\n")
    logger.info(f"Wrote manual labels/synonyms for {sorted(prefixes)} from {terms_file}.")


def build_manual_cliques(terms_file: str = DEFAULT_TERMS_FILE) -> tuple[list[TypedClique], list[str]]:
    """Return (cliques, extra_prefixes): one TypedClique per curated CURIE, in file order."""
    cliques: list[TypedClique] = []
    extra_prefixes: list[str] = []
    seen: set[str] = set()
    for term in read_manual_terms(terms_file):
        cliques.append(TypedClique(node_type=term.biolink_type, identifiers=[term.curie]))
        prefix = term.curie.split(":", 1)[0]
        if prefix not in seen:
            extra_prefixes.append(prefix)
            seen.add(prefix)
    return cliques, extra_prefixes


def build_manual(metadata_yamls: list[str], icrdf_filename: str, terms_file: str = DEFAULT_TERMS_FILE) -> None:
    """
    Build the manual compendium: a heterogeneous list of TypedClique handed to write_compendium with
    node_type=None (each clique keeps its own Biolink type). Every curated prefix is passed via
    extra_prefixes so NodeFactory does not strip identifiers whose prefix is absent from the type's
    Biolink id_prefixes (src/node.py:666-688). metadata_yamls may be empty ([]): write_compendium only
    uses it to record source-provenance filenames in metadata/<ofname>.yaml (babel_utils.py:968).
    """
    cliques, extra_prefixes = build_manual_cliques(terms_file)
    logger.info(f"Building manual compendium: {len(cliques)} term(s), extra_prefixes={extra_prefixes}.")
    write_compendium(
        metadata_yamls,
        cliques,
        "Manual.txt",
        None,
        extra_prefixes=extra_prefixes,
        icrdf_filename=icrdf_filename,
    )
