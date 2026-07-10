# MP mappings

## Mapping source

MP mappings in this integration are pulled exclusively from UberGraph xrefs using
`build_sets(..., set_type="xref")` from the MP root in disease/phenotype compendium assembly, and
then restricted to an allowlist of trusted target prefixes (see "Target-prefix allowlist" below).
SSSOM mappings from the Mouse-Human Ontology Mapping Initiative are **intentionally not loaded**.
See "SSSOM history and known failure modes" below for the reasoning.

## Output format

The MP concord file is tab-separated triples:

- `<MP_CURIE>  xref  <OTHER_CURIE>`

and is written to:

- `babel_outputs/intermediate/disease/concords/MP`

## Current behavior

- Rows are generated from MP terms reachable by `rdfs:subClassOf` from `MP:0000001`.
- Only normalized CURIE-style xrefs are retained.
- Only xrefs whose target prefix is on the allowlist below are written to the concord.
- No additional `other_prefixes` mapping is configured today. If review of the impact report shows
  xref namespaces that should be aliased (e.g. MSH → MESH), they can be added in a follow-up the
  same way `build_disease_obo_relationships` does for HPO.
- MP terms never merge with EFO terms: the reverse EFO→MP direction is filtered out of
  `concords/EFO` at the EFO source (EFO's direct xrefs to MP are untrusted). This is separate from
  the MP concord described here — see [`disjointness.md`](disjointness.md).

## Target-prefix allowlist

`MP_XREF_ALLOWED_PREFIXES` in `src/createcompendia/diseasephenotype.py` restricts the MP concord to
xref targets in `HP`, `MGI`, `MPATH` and `UMLS`. Everything else is dropped.

MP uses `oboInOwl:hasDbXref` to mean "this phenotype is **about** that thing", not "this phenotype
**is** that thing". Babel's concords, by contrast, are equivalence assertions fed to `glom()`. So
most MP xref targets are category errors — they point at the anatomy the abnormality occurs in, the
process it perturbs, or the paper that described it:

| Prefix | Rows | The targets are | Example |
|---|---|---|---|
| `Fyler` | 257 | Codes from a defunct 1980s congenital-heart-defect registry | [`MP:0000111`](http://purl.obolibrary.org/obo/MP_0000111) "cleft palate" → `Fyler:4876` |
| `CL` | 112 | The cell type the abnormality occurs in | [`MP:0010132`](http://purl.obolibrary.org/obo/MP_0010132) "decreased DN2 thymocyte number" → [`CL:0000806`](http://purl.obolibrary.org/obo/CL_0000806) "DN2 thymocyte" |
| `MA` | 85 | The mouse anatomical structure that is abnormal | [`MP:0009873`](http://purl.obolibrary.org/obo/MP_0009873) "abnormal aorta tunica media morphology" → [`MA:0002903`](http://purl.obolibrary.org/obo/MA_0002903) |
| `GO` | 76 | The biological process the phenotype perturbs | [`MP:0002998`](http://purl.obolibrary.org/obo/MP_0002998) "abnormal bone remodeling" → [`GO:0046849`](http://purl.obolibrary.org/obo/GO_0046849) "bone remodeling" |
| `MGI` | 70 | **Kept.** MGI phenotype-slim terms | [`MP:0002078`](http://purl.obolibrary.org/obo/MP_0002078) "abnormal glucose homeostasis" → [`MGI:2173579`](http://identifiers.org/mgi/2173579) |
| `FMA` | 30 | Human anatomy | [`MP:0011211`](http://purl.obolibrary.org/obo/MP_0011211) "abnormal common peroneal nerve morphology" → [`FMA:19039`](http://purl.obolibrary.org/obo/FMA_19039) |
| `https`, `http` | 18 | Wikipedia, Medscape and other web pages | [`MP:0030146`](http://purl.obolibrary.org/obo/MP_0030146) "abnormal digastric posterior belly morphology" → `https://en.wikipedia.org/wiki/Digastric_muscle` |
| `MPATH` | 4 | **Kept.** Mouse pathology lesions | [`MP:0002766`](http://purl.obolibrary.org/obo/MP_0002766) "situs inversus" → [`MPATH:720`](http://purl.obolibrary.org/obo/MPATH_720) |
| `NLX` | 4 | NeuroLex cell types | [`MP:0009955`](http://purl.obolibrary.org/obo/MP_0009955) "abnormal olfactory bulb tufted cell morphology" → `NLX:nifext_121` |
| `UMLS` | 2 | **Kept.** Phenotype concepts | [`MP:0012051`](http://purl.obolibrary.org/obo/MP_0012051) "spasticity" → [`UMLS:C0026838`](http://identifiers.org/umls/C0026838) "Muscle Spasticity" |
| `PMID` | 2 | Literature citations | [`MP:0030023`](http://purl.obolibrary.org/obo/MP_0030023) "abnormal meiotic telomere clustering" → [`PMID:1754386`](http://www.ncbi.nlm.nih.gov/pubmed/1754386) |
| `HP` | 2 | **Kept.** Genuine phenotype equivalences | [`MP:0012051`](http://purl.obolibrary.org/obo/MP_0012051) "spasticity" → [`HP:0001257`](http://purl.obolibrary.org/obo/HP_0001257) "Spasticity" |
| `NBO` | 1 | A behavior | [`MP:0012013`](http://purl.obolibrary.org/obo/MP_0012013) "abnormal innate avoidance response" → [`NBO:0000635`](http://purl.obolibrary.org/obo/NBO_0000635) |

Row counts are from the MP xref dump as of the 2026-06-30 build.

Two notes on the kept prefixes:

- `HP` targets are kept even though HP and MP must stay disjoint; the `[HP, MP]` post-glom split in
  [`disjointness.md`](disjointness.md) separates them regardless, so the allowlist does not need to
  duplicate that policy.
- Not every kept row is correct. [`MP:0009203`](http://purl.obolibrary.org/obo/MP_0009203)
  "external male genitalia hypoplasia" → [`UMLS:C0341787`](http://identifiers.org/umls/C0341787)
  "Bifid scrotum" is one of the two `UMLS` rows and is wrong: the MP term is broad, the UMLS
  concept is a specific malformation that UMLS and HP agree on
  ([`HP:0000048`](http://purl.obolibrary.org/obo/HP_0000048) "Bifid scrotum"). The `[HP, MP]`
  split would separate the resulting clique anyway, but the pair is dropped explicitly in
  `input_data/mp_badxrefs.txt` so it does not become a live bad merge if that policy is ever
  relaxed. [Babel#906](https://github.com/NCATSTranslator/Babel/issues/906) carries the BabelTest
  assertions that keep the clique honest; upstream reporting to MP is tracked in
  [Babel#905](https://github.com/NCATSTranslator/Babel/issues/905).

## Bad-xref file

`input_data/mp_badxrefs.txt` drops individual `subject object` pairs from the MP concord that
survive the allowlist but assert an equivalence that isn't one. It is keyed by concord basename
(`MP`) in `DEFAULT_BAD_XREFS` and in the `disease_compendia` Snakemake rule, alongside the existing
`badHPx.txt`, `mondo_badxrefs.txt` and `umls_badxrefs.txt`.

### Why an allowlist rather than an `ignore_list`

`build_sets()` has long supported an `ignore_list` of blocked target prefixes (see
`anatomy.build_anatomy_obo_relationships`). That fails **open**: a namespace MP newly starts
emitting is silently trusted. The MP concord instead passes `allowed_prefixes`, which fails
**closed** — a new namespace is dropped until someone reviews it and decides to add it. Given that
of the thirteen namespaces MP currently emits only four survive review, defaulting to "reject" is
the safer posture. If MP later ships better mappings, or if Babel starts ingesting one of the
ontologies above, add the prefix to `MP_XREF_ALLOWED_PREFIXES` as a deliberate decision.

Note that `build_sets()` matches allowlist entries against `Text.get_prefix_or_none()`, which
upper-cases, so entries must be upper-case: `"MPATH"`, not `"MPath"`.

## SSSOM history and known failure modes

A prior attempt to add MP (PR #300, branch `add-mammal-phenotype-ontology`, unmerged) combined
the UberGraph xref path above with SSSOM mapping sets from the
[Mouse-Human Ontology Mapping Initiative](https://github.com/mapping-commons/mh_mapping_initiative).
Seven SSSOM files were loaded with a confidence filter of 0.8 and an allowlist of
`skos:exactMatch`, `skos:closeMatch`, and `skos:relatedMatch`. That richer mapping set produced
controversial clique merges that could not be adjudicated without SME input, and the PR stalled.

Two concrete cases from that work, kept here as a regression watchlist:

- **`MP:0003342` "accessory spleen"** was cliqued with **`HP:0001748` "Polysplenia"**, a different
  human-phenotype term. The correct partner is `HP:0001747` "Accessory spleen". The error
  originated in an SSSOM "broad"-style mapping that conflated the two HP concepts. UberGraph
  alone does not assert this bridge, so the UberGraph-only path used in this PR avoids the
  failure — but a future SSSOM re-introduction must vet the broad-mapping predicate filter.

- **`MP:0001914` "hemorrhage"** was *not* cliqued with **`NCIT:C26791` "Hemorrhage"** even though
  the two concepts genuinely correspond. The bridge runs through EFO, and EFO is not loaded into
  UberGraph, so the equivalent xref is invisible to this pipeline. This is a coverage gap, not a
  correctness bug; a SSSOM path could close it but would have to be balanced against the
  accessory-spleen-class risk.

## How to use the impact report

The committed `impact-report.md` is the artefact intended to drive SME conversation about
revisiting SSSOM:

- Section 4 ("Clique impact") shows pure-new MP cliques (those without an HP/NCIT/MONDO partner),
  expanded existing cliques (MP joining an existing cluster), and any merges (MP bridging two
  previously-separate cliques). Sample merge entries are the most diagnostic — they're the
  candidates a reviewer should sanity-check against the actual concepts.
- If the sample merges look clean under UberGraph-only, SSSOM may be safe to add back with
  appropriate filtering.
- If sample merges include implausible bridges, that is itself useful evidence about which xref
  namespaces are over-promiscuous in MP's UberGraph profile.

That last review has now happened once, and produced the target-prefix allowlist above: nine of
MP's thirteen xref namespaces turned out to assert "is about" rather than "is equivalent to". The
document should be revisited again after SME review of SSSOM.

## Caveats

- Mapping coverage depends on UberGraph content and can change across updates. Watch for shifts
  in MP↔MESH and MP↔SNOMED counts when MP is upgraded.
- Some endpoint responses may be transiently unavailable; tests treat server-side issues as xfail
  where appropriate.
