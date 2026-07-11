# CLAUDE.md — docs/sources/

Cross-cutting conventions for working with source/cross-reference data, for Claude Code. Per-source
narrative docs (what a source is, how it's ingested) live in `docs/sources/<PREFIX>/` — see
[`README.md`](README.md) for the index; add there, not here, when you learn something non-obvious
about one specific source.

## An OBO `hasDbXref` is not an equivalence

Concords are fed to `glom()` as equivalence assertions, but many ontologies use
`oboInOwl:hasDbXref` to mean "this term is *about* that thing". MP is the worst offender: it xrefs
the anatomy an abnormality occurs in (`MP:0009873` "abnormal aorta tunica media morphology" →
`MA:0002903`), the process a phenotype perturbs (`MP:0002998` "abnormal bone remodeling" →
`GO:0046849` "bone remodeling"), plus citations and bare Wikipedia URLs. **Always audit the
target-prefix breakdown of a new source's xrefs before trusting them** (section 3 of the
source-impact report, or `cut -f3 <concord> | sed 's/:.*//' | sort | uniq -c`).

Two filters exist on `ubergraph.build_sets()`:

- `ignore_list=[...]` blocks named target prefixes and **fails open** — a namespace the source
  newly starts emitting is silently trusted (`anatomy.build_anatomy_obo_relationships`).
- `allowed_prefixes=[...]` is the complement and **fails closed** — only listed prefixes are
  written, so a new namespace is dropped until someone reviews it. Prefer this for a source whose
  xrefs are mostly junk (`diseasephenotype.MP_XREF_ALLOWED_PREFIXES`).

Both are matched against `Text.get_prefix_or_none()`, which **upper-cases**, so entries must be
upper-case: `"MPATH"`, `"HTTP"` — a lower-case entry silently never matches. Worked example:
`docs/sources/MP/mappings.md`.

## Bad-xref files

`input_data/*_badxrefs.txt` drop individual `subject object` pairs (**space** separated, `#`
comments) from a concord before glom — for individually wrong pairs that survive prefix filtering.
See the code comments at `diseasephenotype.DEFAULT_BAD_XREFS` and the `disease_compendia`
Snakemake rule (`src/snakefiles/diseasephenotype.snakefile`) for the registration gotcha: a key
must be added in **both** places. `compute_cliques_for_impact_report()` now raises if a key names
no concord basename (a typo), but a key added to one dict and not the other — or forgotten
entirely — still fails open, so a unit test asserting a new key exists and its pairs parse remains
the cheap guard for that.

## Keeping two prefixes disjoint

`glom()`'s `unique_prefixes` only forbids *duplicate same-prefix* identifiers in a clique; it does
**not** stop two *different* prefixes from co-occurring, and dropping one source's concord is also
insufficient (other sources' concords bridge them directly or transitively). To guarantee two
prefixes never share a clique, run a **post-glom split** as the last step of the shared
clique-builder so the build and the source-impact report agree — see
`diseasephenotype.split_mutually_exclusive_cliques` /
`MUTUALLY_EXCLUSIVE_PREFIX_GROUPS = [[HP, MP]]` (mirrors the type-driven split in `chemicals.py`)
and `docs/sources/MP/disjointness.md`. A split can strand an identifier that is in a concord but no
ids file (an out-of-date mapping); `create_typed_sets` drops such an untypeable clique with a
warning rather than aborting the build.

## Leftover UMLS

`src/createcompendia/leftover_umls.py` (rule `leftover_umls`) runs last and sweeps up every valid
UMLS concept in MRCONSO that no other compendium already claimed, writing each as a
single-identifier clique into `compendia/umls.txt`. The manual `STY_OVERRIDES` /
`TYPE_COMBO_OVERRIDES` tables at the top of that module — including the "runs last, so an override
never fires for a CUI another pipeline already typed" reach caveat — are documented in the module
itself. See [`docs/sources/UMLS/Leftover.md`](UMLS/Leftover.md) for the coverage report and the
drift test that keeps the tables honest.
