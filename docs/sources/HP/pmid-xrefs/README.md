# HP's publication xrefs are citations, not equivalences

HP cites the papers a term was curated from as `oboInOwl:hasDbXref` on the term's *definition
axiom*, the OBO convention for a definition source. hp.owl 2026-09-01 has 7,115 such publication
xrefs on axioms, and UberGraph's xref query (`UberGraph.get_subclasses_and_xrefs()`) never reads
them: it reads `?class oboInOwl:hasDbXref ?xref` only.

But 32 PMIDs sit on 21 HP classes *themselves*. For
[`HP:0032417`](http://purl.obolibrary.org/obo/HP_0032417) "Periglomerular fibrosis":

```xml
<oboInOwl:hasDbXref>PMID:32866505</oboInOwl:hasDbXref>
```

which is the Renal Pathology Society's consensus definitions of glomerular lesions, cited elsewhere
in hp.owl on the definition axioms of other renal terms. UberGraph serves a class-level xref like
any mapping, so `ubergraph.build_sets()` wrote it into `disease/concords/HP`, and every concord row
reaches `glom()` as an equivalence: "periglomerular fibrosis *is* this paper".
[`HP:0034421`](http://purl.obolibrary.org/obo/HP_0034421) "Ejection click" → `PMID:21250045` is the
other row 2025dec11's concord carried. The rest are recent terms, mostly immunodeficiency phenotypes
(`HP:5210031` "Chronic decreased circulating IgM concentration", `HP:5210421` "Autoimmune
hepatitis", …), and live UberGraph served all 32 on 2026-11-15.
[`hp-publication-xrefs-2026-09-01.txt`](hp-publication-xrefs-2026-09-01.txt) lists every one with
its label, from [`scripts/count_publication_xrefs.py`](scripts/count_publication_xrefs.py).

## What Babel does

`diseasephenotype.HP_XREF_IGNORE_PREFIXES` adds Babel's publication prefixes — `PMID`, `PMC` and
`doi` — to the `ignore_list` of HP's `build_sets()` call, so these rows are never written. Nothing
is equivalent to a publication except another publication, so this is a categorical exclusion rather
than an overuse rule. EFO's citations are dropped the same way (`EFO_EXCLUDED_XREF_PREFIXES`).

## What it changes

[`scripts/replay_drop_publication_xrefs.py`](scripts/replay_drop_publication_xrefs.py) replays the
production `compute_cliques_for_impact_report()` with and without one concord's publication rows.
Its input was 2025dec11's disease intermediates, with HP's 2 PMID rows replaced by the 32 live
UberGraph serves, and the 18 HP terms newer than 2025dec11's `ids/HP` added to it (otherwise they
vanish for want of an ids row, which reads as a clique change). Output:
[`replay_drop_publication_xrefs.txt`](replay_drop_publication_xrefs.txt).

- **No clique changes**, out of 241,197.
- 6 of the 24 PMIDs are named by two or more HP rows and were already removed by the unscoped
  overuse filter on `concords/HP`. The other 18 reach `glom()` as clique members, each joined only
  to its own HP term, and `write_compendium()` drops them, since no disease or phenotype class
  registers PMID.
- No other 2025dec11 disease concord names any of HP's 24 PMIDs. EFO 3.95.0 cites one,
  `PMID:22343568`, but HP cites that from two classes, so HP's overuse filter drops it first.

So the defect is latent, as EFO's was. It turns real the first time one of those 18 papers is also
cited by another disease source: `glom()` would merge the two cliques through it.

The replay kept 2025dec11's other HP rows because live UberGraph's HP concord is very different: it
has 645 rows against 2025dec11's 17,962, having lost all its UMLS and SNOMEDCT xrefs (hp.owl
2026-09-01 has 51 `UMLS:` hasDbXrefs and no SNOMED ones). That is a separate change to how HP joins
its UMLS cliques, not something dropping the publication rows interacts with.

## Upstream

By the OBO convention HP follows everywhere else, these 32 citations belong on the definition
axioms. As of 2026-11-15 they have not been reported to HP. Babel's exclusion doesn't depend on that
fix.

## Re-running

```bash
uv run python docs/sources/HP/pmid-xrefs/scripts/count_publication_xrefs.py path/to/hp.owl
uv run python docs/sources/HP/pmid-xrefs/scripts/replay_drop_publication_xrefs.py <intermediate> --concord HP
```

The replay needs a concord built *before* this exclusion; with it, `concords/HP` has no publication
rows to measure. To rebuild one, call `build_sets()` as `build_disease_obo_relationships()` does but
with `ignore_list=["ICD"]`.
