# Leftover UMLS

The "leftover UMLS" step is the last thing the pipeline does. After every other compendium has been
built, `src/createcompendia/leftover_umls.py` (Snakemake rule `leftover_umls`) walks `MRCONSO.RRF`
and collects every valid UMLS concept that **no other compendium already claimed**, writing each one
as a single-identifier clique into `babel_outputs/compendia/umls.txt`. The point is coverage: even
when Babel can't merge a UMLS concept into a richer clique, downstream services (Node Normalization,
Name Resolver) can still return its label and a Biolink type. This addresses
[#579](https://github.com/NCATSTranslator/Babel/issues/579), and the typing corrections below
address [#569](https://github.com/NCATSTranslator/Babel/issues/569) and the umbrella
[#410](https://github.com/NCATSTranslator/Babel/issues/410).

## How a leftover concept gets its Biolink type

Each UMLS concept carries one or more **semantic types**. UMLS identifies a semantic type by a code
such as `T033`; that code is technically the "TUI", but the namespace UMLS and the Biolink Model
Toolkit (bmt) actually use is `STY` (the mapping key is `STY:T033`), so this code and the override
table use **STY** throughout.

`tui_to_biolink_type()` is a thin wrapper over bmt's `STY:<code>` mapping and returns exactly what
Biolink says (or `None` if Biolink has no mapping). For each concept:

1. Every semantic type is resolved to one of three outcomes — a Biolink type, a **rejection**
   (override maps it to `None`), or **unmapped** (Biolink has no mapping and there is no override).
2. If any semantic type is unmapped, the whole concept is skipped (we don't emit a concept we can't
   fully type) and reported as `NO_UMLS_TYPE`.
3. Rejected semantic types simply drop out. If nothing is left, the concept is skipped and reported
   as `REJECTED`.
4. If the surviving Biolink types disagree, `TYPE_COMBO_OVERRIDES` is consulted to pick one;
   otherwise the concept is skipped and reported as `MULTIPLE_UMLS_TYPES`.

## The override tables

The right place to fix a wrong UMLS-to-Biolink mapping is the Biolink Model itself, but it is hard
to anticipate how a Biolink change will land in real Babel data. The two tables at the top of
`leftover_umls.py` let us correct mappings locally and reversibly:

- **`STY_OVERRIDES: dict[str, str | None]`** — override the Biolink type bmt assigns to a single
  semantic type. `None` means "deliberately reject". Seeded from #569:
  - `T033` "Finding" → `biolink:Phenomenon` (Biolink has no STY mapping for it, so without this the
    concepts would be dropped as unmapped).
  - `T034` "Laboratory or Test Result" → `biolink:ClinicalFinding` (Biolink maps it to the broader
    `biolink:Phenomenon`).
- **`TYPE_COMBO_OVERRIDES: dict[frozenset[str], str]`** — when a concept resolves to more than one
  Biolink type, pick a single one (e.g. `{Device, Drug} → Drug`).

Every `STY_OVERRIDES` entry must cite the GitHub issue that motivates it.

## Keeping overrides honest: the drift test

`tests/createcompendia/test_leftover_umls.py` (marked `network`, because building a bmt toolkit
fetches the Biolink model) records, in `RECORDED_STY_BASELINE`, the Biolink `STY:<code>` mapping
that was current when each override was added, for the `biolink_version` pinned in `config.yaml`. On
each run it compares the live mapping against the recorded baseline:

- **Hard fail** when the live mapping diverges from the recorded baseline — Biolink changed
  underneath us, so the override (and the baseline) must be re-reviewed.
- **Warning only** when the live mapping has come to equal the override — Biolink now agrees, so the
  override is redundant and can be removed.

Because the test is `network`-marked it runs in the nightly/weekly cadences and on demand
(`uv run pytest tests/createcompendia/test_leftover_umls.py --network`), not on every PR. The most
important time to run it is when bumping `biolink_version`.

## Coverage report

The rule writes machine-readable CSVs to `babel_outputs/reports/umls/` (a directory so more UMLS
reports can be added later), alongside the human-readable log at `babel_outputs/reports/umls.txt`:

- `compendium-coverage.csv` — per input compendium: `total_umls_curies` and
  `single_umls_clique_count` (cliques whose only identifier is a single UMLS CURIE).
- `types-coverage.csv` — per Biolink type of the leftover cliques: how many were added, with a few
  sample `CURIE=label`s.
- `unmapped-types.csv` — per semantic type that was unmapped or rejected: status, affected CUI
  count, and sample CURIEs.
- `tui-sty.tsv` — the raw STY-code → semantic-type-name dump from `MRSTY.RRF`.
