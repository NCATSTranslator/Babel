# PO mappings

## No source maps PO to anything Babel reads

Before writing a matching rule, these were checked for an existing PO mapping (November 2026):

| Source | Result |
|---|---|
| PO's own xrefs | Citations, image links and species databases; see the README. |
| NCIt "Plant Part" branch | No cross-references at all, to PO or anything else. |
| MeSH, UMLS | MeSH publishes no outbound mappings. UMLS 2026AA has no PO source. |
| UberGraph | One GO term cites a PO term as an xref; no other ontology does, as an xref or a match. |
| Wikidata | A "Plant Ontology ID" property exists ([P13866](https://www.wikidata.org/wiki/Property:P13866)) but is on 4 items. |
| EBI OxO | No direct mapping from any PO anatomy term to MeSH, NCIt, UMLS, SNOMED CT, UBERON or FMA. Two-hop results are homonyms (PO "coma" to "Comatose"). |
| EFO | 43 terms cite both a PO term and a MeSH or NCIt term, giving 41 pairs; see below. |

EFO is the only one with real coverage, and it is weaker than the rule below. Against the
curation, 23 of its pairs agree, 7 conflict (its "microspore" term ties MeSH and NCIt "Pollen" to
PO "microspore" and "generative cell"), 2 map a term the curator left unmapped, and 9 point outside
the plant branches altogether (NCIt "Seed" in the radiotherapy sense). 17 of the EFO terms involved
are obsolete: EFO replaced its own plant terms with imported PO terms, and the cross-references
stayed on the retired ones.

Wikidata is the natural long-term home. Babel already reads it for anatomy, so PO IDs added there
would arrive as an ordinary sourced concord and this rule could retire.

## The rule

`match_plant_part_names()` in `src/createcompendia/anatomy.py` pairs a term with the PO term of
the same name. `build_po_label_relationships()` runs it twice, for:

- the preferred names of the MeSH descriptors in tree A18 "Plant Structures", and
- the labels of the NCIt plant parts (README, "Which NCIt terms are plant anatomy"),

each against the label and English exact synonyms of the PO terms in `ids/PO`. Names are compared
after `normalize_plant_part_name()`: lower-cased, the word "plant" dropped, plurals reduced. Rows
are written as `PO:… label_match MESH:…`.

Three properties make it safe:

- **Both sides are plant vocabularies.** Run against all of anatomy, the same comparison pairs PO
  "root" with "tooth root", PO "placenta" with the animal organ and PO "cortex" with the brain's.
  Limited to MeSH A18 and NCIt plant parts, those homonyms cannot occur.
- **Preferred names only on the MeSH and NCIt side.** MeSH lists parts as entry terms of the
  whole: "Anther, Plant" and "Petal, Plant" are entry terms of "Flowers", and "Bulb, Plant" of
  "Plant Roots". Matching entry terms would map each whole to its parts.
- **One-to-one, with no winner picked.** A name that fits two PO terms is left unmatched, and so
  is every term claiming a PO term that another term in the same vocabulary also claims.

## Validation against a curated set

Both vocabularies were mapped to PO by hand first: all 41 MeSH A18 descriptors
([`curation/po_mesh.tsv`](./curation/po_mesh.tsv)) and the 74 direct children of NCIt "Plant Part"
([`curation/po_ncit.tsv`](./curation/po_ncit.tsv)). An empty `po` column means the curator chose no
mapping. The curation is not read by the build. It is what the rule is measured against, by
`tests/pipeline/test_po_pipeline.py`, which fails if the rule writes a pair that contradicts it.

In a local build:

| | MeSH A18 | NCIt plant parts |
|---|---|---|
| Pairs the rule writes | 31 | 44 |
| Same as the curation | 31 | 40 |
| Differ from the curation | 0 | 3 |
| On a term the curation did not cover | 0 | 1 |
| Curated pairs the rule does not find | 3 | 7 |

The three that differ, pinned as `KNOWN_DISAGREEMENTS` in the test:

- `NCIT:C79619` "Blade" is paired with
  [`PO:0025060`](http://purl.obolibrary.org/obo/PO_0025060) "lamina". The curator chose
  [`PO:0020039`](http://purl.obolibrary.org/obo/PO_0020039) "leaf lamina", reading NCIt's Latin
  synonym as the leaf blade.
- `NCIT:C79690` "Stalk" is paired with
  [`PO:0025066`](http://purl.obolibrary.org/obo/PO_0025066) "stalk". The curator chose none: NCIt
  means "Caulis Principalis", the main stem.
- `NCIT:C1502` "Fiber" is paired with
  [`PO:0025407`](http://purl.obolibrary.org/obo/PO_0025407) "plant fiber cell", which has "fiber"
  as an exact synonym. The curator left "Fiber" out of anatomy as a product (dietary fiber).

The uncovered term is `NCIT:C73861` "Berry", paired with
[`PO:0030108`](http://purl.obolibrary.org/obo/PO_0030108) "berry fruit".

The ten curated pairs the rule does not find are left unjoined, not joined wrongly:

- Different names: MeSH "Plant Cone" (PO "strobilus"), "Plant Stomata" ("stomatal complex"),
  "Germ Cells, Plant" ("plant gamete"); NCIt "Leaf Bud" ("vegetative bud"), "Branch Stem"
  ("branch"), "Node" ("shoot axis node"), and "Plant Part" itself, which the NCIt rule does not
  take.
- NCIt "Cuticle", "Resin" and "Sap", whose PO terms are in a branch excluded until the Biolink
  change lands (README, "What is left out").

## Output

`babel_outputs/intermediate/anatomy/concords/PO`, with `metadata-PO.yaml` beside it. The same rule
writes `intermediate/anatomy/mesh_plant_structures.tsv`, the list of MeSH plant structures the
anatomy build uses to keep animal anatomy terms out of plant cliques.
