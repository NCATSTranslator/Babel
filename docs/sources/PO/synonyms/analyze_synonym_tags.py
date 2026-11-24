"""Characterize the trailing "(...)" tags the Plant Ontology writes inside its synonym strings.

PO's synonym *values* carry their own scope and language, e.g. ``"wood (exact)"``,
``"planta entera (Spanish, exact)"``, ``"macrostrobili (related, plural)"``. Babel reads synonyms
from UberGraph as plain strings, so without cleaning every PO synonym would reach Name Resolver
with that tag attached. Before deciding how to clean them, this script tabulates every trailing
parenthetical on every PO synonym, over the whole ontology rather than a sample.

It queries UberGraph for all four oboInOwl synonym predicates on every ``PO_`` class and writes
``tag_counts.json`` next to this file:

- ``synonyms``: total synonym strings.
- ``by_shape``: how many strings end in each *shape* of parenthetical, where a shape is the tag
  with any language name replaced by ``<Language>`` (so "(Spanish, exact)" and "(Japanese, exact)"
  count together).
- ``languages``: how many strings carry each language name.
- ``no_trailing_parenthetical``: strings with no trailing "(...)" at all.
- ``unrecognized``: every trailing parenthetical ``clean_po_synonym()`` does not recognize, with
  a count and one example. These are kept verbatim by the cleaner, so they should be genuine
  parts of a name.

Run from the repository root::

    uv run python docs/sources/PO/synonyms/analyze_synonym_tags.py
"""

import json
import re
from collections import Counter
from pathlib import Path

from src.datahandlers.obo import PO_SYNONYM_LANGUAGES, PO_SYNONYM_TAG, clean_po_synonym
from src.triplestore import TripleStore

QUERY = """
prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
prefix owl: <http://www.w3.org/2002/07/owl#>
prefix oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
SELECT ?cls ?pred ?val
from <http://reasoner.renci.org/ontology>
WHERE {
  VALUES ?pred { oboInOwl:hasRelatedSynonym oboInOwl:hasNarrowSynonym oboInOwl:hasBroadSynonym oboInOwl:hasExactSynonym }
  ?cls ?pred ?val .
  FILTER(STRSTARTS(STR(?cls), "http://purl.obolibrary.org/obo/PO_"))
}
"""

TRAILING_PARENTHETICAL = re.compile(r"\(([^()]*)\)\s*$")


def main():
    rows = TripleStore("https://ubergraph.apps.renci.org/sparql").query_template(
        inputs={}, outputs=["cls", "pred", "val"], template_text=QUERY
    )
    by_shape = Counter()
    languages = Counter()
    unrecognized = {}
    no_parenthetical = 0
    dropped = 0
    for row in rows:
        value = row["val"]
        match = TRAILING_PARENTHETICAL.search(value)
        if match is None:
            no_parenthetical += 1
            continue
        tag = match.group(1)
        shape_parts = []
        for part in (p.strip() for p in tag.split(",")):
            if part in PO_SYNONYM_LANGUAGES:
                languages[part] += 1
                shape_parts.append("<Language>")
            else:
                shape_parts.append(part)
        shape = "(" + ", ".join(shape_parts) + ")"
        by_shape[shape] += 1
        if PO_SYNONYM_TAG.search(value) is None:
            entry = unrecognized.setdefault(shape, {"count": 0, "example": value})
            entry["count"] += 1
        if clean_po_synonym(value) is None:
            dropped += 1

    result = {
        "synonyms": len(rows),
        "no_trailing_parenthetical": no_parenthetical,
        "dropped_by_clean_po_synonym": dropped,
        "by_shape": dict(by_shape.most_common()),
        "languages": dict(languages.most_common()),
        "unrecognized": dict(sorted(unrecognized.items(), key=lambda kv: -kv[1]["count"])),
    }
    out = Path(__file__).parent / "tag_counts.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out}: {len(rows)} synonyms, {len(by_shape)} tag shapes, {len(unrecognized)} unrecognized")


if __name__ == "__main__":
    main()
