# Plant Ontology (PO) source notes

The Plant Ontology (<https://obofoundry.org/ontology/po.html>) describes plant anatomy and plant
development stages. Babel takes its anatomy branch into the anatomy pipeline, read from UberGraph.

## What comes in

- **1,312 PO terms**, everything under
  [`PO:0025131`](http://purl.obolibrary.org/obo/PO_0025131) "plant anatomical entity" except the
  two branches below. The 206 under
  [`PO:0009002`](http://purl.obolibrary.org/obo/PO_0009002) "plant cell" are typed `biolink:Cell`
  and the other 1,106 `biolink:GrossAnatomicalStructure`.
- **71 NCIt plant parts**, added to the anatomy `ids/NCIT` as `biolink:AnatomicalEntity`. NCIt
  keeps them in a branch Babel did not read before; "Which NCIt terms are plant anatomy" below
  says how they are chosen.
- **75 name-match pairs** in `concords/PO`, joining PO to 31 MeSH descriptors and 44 NCIt plant
  parts. [`mappings.md`](./mappings.md) explains why a name match and what it was checked against.

In a local build, 62 PO terms join a clique that already existed and the other 1,250 become
single-identifier cliques. That is expected rather than a sign of a missed mapping: nothing else
Babel reads describes plant anatomy at this level of detail (`mappings.md` has the search).

## What is left out, and why

- **Development stages.**
  [`PO:0009012`](http://purl.obolibrary.org/obo/PO_0009012) "plant structure development stage"
  (296 terms) is not anatomy. Babel has no life-stage pipeline, and Biolink's `LifeStage` does not
  register PO.
- **Spaces and substances, for now.**
  [`PO:0025117`](http://purl.obolibrary.org/obo/PO_0025117) "plant anatomical space" (35 terms)
  and [`PO:0025161`](http://purl.obolibrary.org/obo/PO_0025161) "portion of plant substance" (16
  terms: sap, resin, cuticle) are neither gross structures nor cells. Their correct type is
  `biolink:AnatomicalEntity`, which Biolink 4.4.3 does not register PO for, so
  `write_compendium()` would drop them. They are excluded in `ANATOMY_OBO_SOURCES` until
  [biolink-model#1862](https://github.com/biolink/biolink-model/pull/1862) is in the Biolink
  version `config.yaml` pins. Then move them from `exclude_roots` to `subtype_roots` as
  `ANATOMICAL_ENTITY`; three more curated NCIt pairs (Cuticle, Resin, Sap) start matching when
  that happens.
- **PO's own cross-references.** There is no xref concord. PO's roughly 1,200 `hasDbXref` values are
  image links, tracker tickets (`PO_GIT`), species databases (`PLANTS`, `MANSFELD`, `FNA`) and
  citations. The only ones naming a vocabulary Babel reads are 13 to GO, which point at
  biological processes (an abscission zone citing "abscission"), and one to CL ("meristematic
  cell" citing the broader "stem cell"). None is an equivalence.

## Typing

A clique that holds a PO term takes PO's type (`classify_anatomy_clique()` trusts PO after GO, CL,
UBERON and EMAPA). Without that, a clique of one PO term, one MeSH descriptor and one UMLS CUI is
typed `biolink:AnatomicalEntity` by majority, and the PO term is dropped because Biolink does not
register PO for that class.

The effect on existing cliques is that 28 MeSH plant-structure cliques move from
`AnatomicalEntity.txt` to `GrossAnatomicalStructure.txt`, and "Trichomes" moves there from
`CellularComponent.txt`. No member is lost in the move:
[`on-addition/clique-diff.summary.json`](./on-addition/clique-diff.summary.json) records 31
changed cliques and 0 dropped members, and
[`on-addition/clique-diff.csv`](./on-addition/clique-diff.csv) lists them.

## Which NCIt terms are plant anatomy

NCIt files plant parts under
[`NCIT:C79611`](http://purl.obolibrary.org/obo/NCIT_C79611) "Plant Part", a branch of
"Plant-based Natural Product". It is FDA's vocabulary for naming the part of a plant a botanical
drug is made from, and its 576 terms are of two kinds: structures ("Bark", "Sepal", "Flower Bud")
and materials ("Acer rubrum Pollen", "Oat", "Psyllium Husk"). No sub-branch separates them; the
materials sit under the structures ("Acer rubrum Pollen" under "Pollen").

Two of NCIt's own annotations do separate them. A term is taken when it has:

- **no `FDA_UNII_Code`**: a UNII means FDA has registered the term as a substance; and
- **`Semantic_Type` "Plant"**.

That selects 71 terms (`fetch_ncit_plant_parts()`). Compared with a term-by-term review of the
branch's 74 direct children ([`curation/po_ncit.tsv`](./curation/po_ncit.tsv), column
`in_anatomy`):

| | Terms |
|---|---|
| Kept by the curator and by the rule | 60 of 61 |
| Kept by the curator, not by the rule | 1: the branch root, which NCIt types "Classification" |
| Left out by the curator, taken by the rule | 4: Fiber, Mycelium, Sclerotium, Chamomile |
| Below the reviewed level, taken by the rule | 7: Berry; Seed, Without Shell; Stem, Woody; Valerian Root; Senega Root; Nux Vomica Seed; Smoking Tobacco |

The first three in the last row are plant parts the review had not reached. The other eight
unwanted terms are source errors, a material with no UNII or a fungal structure typed "Plant", and
come in as single-identifier anatomy cliques. They are the accepted cost of a rule over a
hand-kept list, and they correct themselves when NCIt does.

## An animal anatomy term is not a plant structure

UBERON and EMAPA describe animals only, so a cross-reference from either to a MeSH Plant Structures
descriptor is a homonym. Two existed, and each merged a plant structure into an animal clique:

- [`UBERON:0010008`](http://purl.obolibrary.org/obo/UBERON_0010008) "placental cotyledon" cites
  `MESH:D018548` "Cotyledon", the seed leaf, and its CUI.
- [`UBERON:0000312`](http://purl.obolibrary.org/obo/UBERON_0000312) "inner cambium layer of
  periosteum" cites `MESH:D058506` "Cambium"
  ([#1272](https://github.com/NCATSTranslator/Babel/issues/1272)).

PO made both worse. PO "cotyledon" joined the placental clique, which UBERON types
`AnatomicalEntity`, and was dropped; PO "cambium" joined the periosteum.

So the anatomy build skips any concord pair that links a UBERON or EMAPA term to a MeSH descriptor
in tree A18, or to the CUI that follows one (`joins_animal_anatomy_to_plant_structure()`). Three
rows are skipped today. GO and CL are not covered:
[`GO:0090406`](http://purl.obolibrary.org/obo/GO_0090406) "pollen tube" really is MeSH's "Pollen
Tube".

The other half of #1272 is untouched: UMLS itself puts `FMA:234358` "Cambial layer of periosteum"
in the plant cambium CUI.

## Synonyms

PO writes each synonym's scope, and for a translation its language, inside the synonym string:
`"wood (exact)"`, `"radices (exact, plural)"`, `"planta entera (Spanish, exact)"`. Every one of its
5,606 synonyms but one ends in such a tag. `clean_po_synonym()` in `src/datahandlers/obo.py` strips
the tag and drops the 2,793 translations (Spanish, Japanese, German), since Babel keeps English
names only.

The tags were tabulated over the whole ontology before the cleaner was written. They use eight
words in 16 combinations, and nothing is left unrecognized:
[`synonyms/tag_counts.json`](./synonyms/tag_counts.json), regenerated by
[`synonyms/analyze_synonym_tags.py`](./synonyms/analyze_synonym_tags.py).

## Not done here

- **UMLS plant-part CUIs with no MeSH descriptor stay in taxon.** UMLS types plant parts as T002
  "Plant", which Babel maps to `biolink:OrganismTaxon`
  ([#1142](https://github.com/NCATSTranslator/Babel/issues/1142)). A CUI with a MeSH descriptor
  follows it into anatomy already. The 44 NCIt plant parts whose CUI has only NCI atoms ("Bark",
  "Anther", "Corolla") now have an NCIt and often a PO identifier in anatomy, while the CUI is
  still a separate taxon clique. Letting a CUI with no MeSH owner follow its NCIt plant part
  belongs in `rule umls_mesh_ownership`, and moves CUIs out of taxon, so it needs its own change.

## Files

- [`mappings.md`](./mappings.md): the name-match concord, what it was validated against, and the
  search for an existing mapping source.
- [`curation/`](./curation/): the curated PO mappings for MeSH A18 and NCIt plant parts. A
  validation set, not a build input.
- [`impact-report.md`](./impact-report.md): generated by `uv run source-impact-report --source PO`
  from a local `anatomy` build.
- [`on-addition/`](./on-addition/): the build-vs-build clique diff for the addition.
- [`synonyms/`](./synonyms/): the synonym-tag analysis.

Implementation: `src/createcompendia/anatomy.py`, `src/snakefiles/anatomy.snakefile`,
`src/datahandlers/obo.py` (synonyms), `config.yaml` (`anatomy_*`).
