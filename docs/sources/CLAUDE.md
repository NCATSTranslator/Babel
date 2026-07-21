# CLAUDE.md — docs/sources/

Cross-cutting conventions for working with source/cross-reference data, for Claude Code. Per-source
narrative docs (what a source is, how it's ingested) live in `docs/sources/<PREFIX>/` — see
[`README.md`](README.md) for the index; add there, not here, when you learn something non-obvious
about one specific source.

## Investigating a source: commit the check, not the conclusion

When you characterize a source's data to justify a parsing decision — how a field is quoted, whether
a delimiter is safe to split on, whether a pattern is an artifact or real — the check itself belongs
in the repo, next to the per-source doc, as a script that regenerates its own output. A conclusion
recorded only in prose (a PR description, a paragraph here) cannot be re-run against next month's
download, and cannot be checked by a reviewer who doubts it.

This is not pedantry. In the #744 NCBIGene work, a count computed in a throwaway shell one-liner had
the wrong denominator, and nobody could see it until the same check was written into a committed
script — where it immediately disagreed with the prose. Two claims, both stated confidently, both
wrong, both caught only by making them reproducible.

So: keep the analysis script and its generated output under `docs/sources/<PREFIX>/`, have the
script import the production predicate it is reasoning about (rather than re-implementing it, which
lets the two drift), and where the finding constrains real output, add a `pipeline`-marked test that
asserts it over the full downloaded file. `docs/sources/NCBIGene/quoting/` is the worked example:
`analyze_quoting.py` and `double_prime_report.py` both import from `src/datahandlers/ncbigene.py`,
and `tests/pipeline/test_ncbigene.py` enforces the conclusion against every row.

### Markdown gets a sample; the CSV gets the rest

The generated Markdown is an *argument*, read top to bottom by a person: **5–10 examples is plenty**
to show a shape. Anything longer is a data dump that buries the finding — and if it is ranked purely
by frequency, its head is usually one shape repeated (NCBIGene's `''` tokens are all protein-subunit
names for the first dozen rows, hiding the chemical locants entirely). Sample deliberately: spread
across the list, or take the most common of each shape, and say in the report which you did.

Emit the exhaustive per-row record as a **CSV** beside the Markdown and commit it — that is what a
reviewer greps and what a future run diffs against (`shredded_pieces.csv`, one row per dropped
synonym). If the full record is big enough to be unwieldy in Git, leave it out and let the script
regenerate it locally; say so in the report, and make sure the script's default output path is the
one the report names.

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

## Storing generation scripts with the artifact

When a non-trivial script produces a **committed** artifact (an audit CSV, a curated mapping, a
report table) under a source's task directory, commit the script alongside it in a `scripts/`
subdirectory — e.g. `docs/sources/<PREFIX>/<task>/scripts/`. That way the artifact can be
regenerated after an upstream refresh, and the next change can reuse or adapt the script instead of
reverse-engineering how the file was built. Prefer scripts that
**import the production classification/parsing code** rather than reimplementing it, so the
committed artifact cannot drift from the pipeline. Worked example:
`docs/sources/DRUGBANK/food-and-extracts/scripts/generate_csvs.py`, which regenerates the two
DrugBank retype CSVs from the same `classify_food_or_extract` the build uses.

## Read source files as UTF-8

Default to UTF-8 when opening a downloaded source file. Reaching for `latin-1` or `windows-1252`
because a decode failed converts a loud `UnicodeDecodeError` into silent mojibake: the bytes always
decode, and `é` quietly becomes `Ã©` in every label and synonym the source contributes. Mojibake is
valid UTF-8, so it survives every downstream step and lands in Node Normalization as a real name.

Only use a single-byte codec when the source genuinely publishes in one, and say so in a comment
naming the evidence — `src/datahandlers/unii.py`'s `UNII_RECORDS_ENCODING` is the shape to follow.
`src/datahandlers/datacollect.py` (PubChem) reads `latin-1` and predates this rule; treat it as a
thing to verify, not a precedent.

Labels and synonyms are checked as they load and a damaged one aborts the build — see
[the encoding check](../Development.md#the-encoding-check). Survey a source's files before wiring
it in with `uv run babel-check-encoding babel_downloads/<PREFIX>/labels`
([docs](../tools/CheckEncoding.md)).
