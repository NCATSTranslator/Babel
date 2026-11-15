#!/usr/bin/env python
"""Count where hp.owl attaches its publication xrefs (PMID, PMC, doi): on a class, or on an axiom.

HP cites the papers a term was curated from almost entirely as ``oboInOwl:hasDbXref`` on the
*definition axiom* (an ``owl:Axiom`` whose ``owl:annotatedSource`` is the class and whose
``owl:annotatedProperty`` is ``IAO:0000115``). That is the OBO convention for a definition source, and
UberGraph's xref query (``UberGraph.get_subclasses_and_xrefs()``) never sees it, because it reads
``?class oboInOwl:hasDbXref ?xref`` only. A publication xref attached to the *class itself* is read as
a mapping, and ``ubergraph.build_sets()`` writes it into ``disease/concords/HP`` as an equivalence.

This loads ``hp.owl`` and reports both counts, plus every class-level publication xref with its
label -- the rows that reach the HP concord, and the ones to report upstream.

Usage::

    uv run python docs/sources/HP/pmid-xrefs/scripts/count_publication_xrefs.py path/to/hp.owl
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

import pyoxigraph

# Allow running this script directly from a checkout without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from src.prefixes import DOI, PMC, PMID  # noqa: E402
from src.util import Text  # noqa: E402

PUBLICATION_PREFIXES = {PMID.upper(), PMC.upper(), DOI.upper(), "PMCID"}
HP_IRI = "http://purl.obolibrary.org/obo/HP_"

CLASS_LEVEL = """
PREFIX oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?class ?xref ?label WHERE {
  ?class oboInOwl:hasDbXref ?xref .
  OPTIONAL { ?class rdfs:label ?label }
  FILTER(isIRI(?class))
}
"""

AXIOM_LEVEL = """
PREFIX oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT ?property ?xref WHERE {
  ?axiom a owl:Axiom ;
         owl:annotatedSource ?class ;
         owl:annotatedProperty ?property ;
         oboInOwl:hasDbXref ?xref .
  FILTER(STRSTARTS(STR(?class), "http://purl.obolibrary.org/obo/HP_"))
}
"""


def is_publication(xref):
    return (Text.get_prefix_or_none(xref.strip()) or "") in PUBLICATION_PREFIXES


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("hp_owl", type=Path)
    args = parser.parse_args(argv)

    store = pyoxigraph.Store()
    store.bulk_load(path=str(args.hp_owl), format=pyoxigraph.RdfFormat.RDF_XML)
    version = [
        str(t.object)
        for t in store.quads_for_pattern(None, pyoxigraph.NamedNode("http://www.w3.org/2002/07/owl#versionIRI"), None)
    ]
    print(f"# hp.owl version: {', '.join(sorted(version))}")

    axiom_counts = Counter()
    for row in store.query(AXIOM_LEVEL):
        xref = row["xref"].value
        if is_publication(xref):
            axiom_counts[row["property"].value.rsplit("/", 1)[-1]] += 1
    print("\n# Publication xrefs on axioms of HP classes (by annotated property); UberGraph does not read these")
    for prop, n in sorted(axiom_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"{prop}\t{n}")

    class_level = sorted(
        (row["class"].value.replace(HP_IRI, "HP:"), row["xref"].value, row["label"].value if row["label"] else "")
        for row in store.query(CLASS_LEVEL)
        if row["class"].value.startswith(HP_IRI) and is_publication(row["xref"].value)
    )
    print("\n# Publication xrefs on HP classes themselves; UberGraph reads these as mappings")
    print(f"count\t{len(class_level)}")
    for curie, xref, label in class_level:
        print(f"{curie}\t{label}\t{xref}")


if __name__ == "__main__":
    main()
