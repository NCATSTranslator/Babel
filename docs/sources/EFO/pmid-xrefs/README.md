# EFO's PMID xrefs are citations, not equivalences

EFO records the paper a term was curated from as a class-level `oboInOwl:hasDbXref`, in exactly
the shape it uses for a mapping. EFO 3.95.0's `efo.owl` has, for
[`EFO:0020008`](http://www.ebi.ac.uk/efo/EFO_0020008) "campesterol measurement":

```xml
<oboInOwl:hasDbXref>PMID:11432711</oboInOwl:hasDbXref>
```

and for [`EFO:0007836`](http://www.ebi.ac.uk/efo/EFO_0007836) "coenzyme Q10 measurement",
`<oboInOwl:hasDbXref>PMID:27149984 </oboInOwl:hasDbXref>`. Neither is the same thing as the
publication it cites. But `efo.make_concords()` wrote every hasDbXref target into `concords/EFO`,
and every concord row reaches `glom()` as an equivalence assertion, so each such row claimed that a
measurement or phenotype *is* a paper.

## What Babel does

`PMID` is in `diseasephenotype.EFO_EXCLUDED_XREF_PREFIXES`, so `efo.make_concords()` drops these
rows where the concord is built, alongside EFO's xrefs to MP. It is a categorical exclusion, not an
overuse rule, because no EFO→PMID row could be an equivalence however few terms cite the paper (see
[`../../CLAUDE.md`](../../CLAUDE.md), "Overuse filtering or a prefix exclusion?").

## What it changes

Measured over the 2025dec11 build's disease intermediate files by
[`scripts/replay_drop_pmid_xrefs.py`](scripts/replay_drop_pmid_xrefs.py), which replays the
production `compute_cliques_for_impact_report()` with and without the PMID rows; its output is
[`replay_drop_pmid_xrefs.txt`](replay_drop_pmid_xrefs.txt).

- `concords/EFO` loses 6,204 rows (6,198 distinct pairs; six rows were written twice) naming 460
  PMIDs. Every one is listed in
  [`dropped-pmid-xrefs-2025dec11.csv`](dropped-pmid-xrefs-2025dec11.csv), from
  `uv run babel-overused-xrefs --min-subjects 1 --target-prefixes PMID`.
- **No clique changes.** The 136 PMIDs named by more than one row were already removed by the
  unscoped overuse filter on `concords/EFO`; one,
  [`PMID:29875488`](http://www.ncbi.nlm.nih.gov/pubmed/29875488), is cited by 1,978 measurement
  terms. The other 324 did reach `glom()` as clique members, but each joined only its own EFO term,
  and `write_compendium()` dropped it, since no disease or phenotype class registers the PMID
  prefix. No PMID appears in 2025dec11's `Disease` or `PhenotypicFeature` `Edge` tables.

So the defect was latent. It turns real the first time a PMID that EFO cites once is also named by
another disease concord: `glom()` would merge the two cliques through the paper. HP already writes
PMID xrefs ([`HP:0032417`](http://purl.obolibrary.org/obo/HP_0032417) → `PMID:32866505`), though
neither of its two is one EFO cites.

## What is still open

The replay's first section tabulates everything else EFO's hasDbXref points at, and several
namespaces have the same shape: measurement terms xref the analyte they measure (2,581 `uniprot`
rows, plus `HMDB`, `KEGG COMPOUND`, `PubChem`, `CAS`), and a few xref people and resources
(`ORCID`, `RRID`). None of these reached a 2025dec11 disease or phenotype clique either, but none is
an equivalence, so each is a candidate for the same exclusion. They are left for a separate change,
[#1200](https://github.com/NCATSTranslator/Babel/issues/1200), since excluding a namespace a disease
source could legitimately share deserves its own measurement.

## Re-running

Assemble a build's `intermediate/disease/` (`concords/` and `ids/`; 2025dec11's are published at
`https://stars.renci.org/var/babel/2025dec11/intermediate/disease/`), then:

```bash
uv run python docs/sources/EFO/pmid-xrefs/scripts/replay_drop_pmid_xrefs.py <intermediate>
uv run babel-overused-xrefs --concord <intermediate>/disease/concords/EFO \
  --out docs/sources/EFO/pmid-xrefs/dropped-pmid-xrefs-<build>.csv --min-subjects 1 --target-prefixes PMID
```

Both need a concord built *before* this exclusion; a build with it has no PMID rows to measure.
