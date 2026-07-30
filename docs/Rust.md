# Rust in Babel

> ## ⚠️ This document is an AI-written proposal. No human has reviewed or agreed to it.
>
> It was written by Claude (Claude Code) at @gaurav's request, to answer two questions that
> [PR #975](https://github.com/NCATSTranslator/Babel/pull/975) leaves open: **where in Babel would
> Rust actually help, and how should it be wired in?** It contains measurements, a recommendation,
> and an argument against that recommendation.
>
> **Nothing here is a decision.** The options being compared are set out in
> [How to integrate](#how-to-integrate) — in-process pyo3 (what #975 builds), a separate program at
> a Snakemake rule boundary, splitting a rule at a new file boundary, or not using Rust at all. The
> recommendation favours the second and third over the first; #975 currently implies the first.
> Choosing between them is a call for @gaurav and @SkyeAv, who have not seen this yet.
>
> It also corrects two factual errors in an earlier AI-written version of this file, which is a
> reason to check the rest rather than trust it. Every number below is reproducible from a committed
> script or from `data/babel-1.18/babel_outputs/benchmarks/`.

## Where the time actually goes

From `babel-1.18`'s Snakemake `benchmark:` TSVs (354 rules, 83.7 h summed). All five costliest rules
run at ~100% of a single core:

| Rule | Wall | CPU | `mean_load` | `max_rss` |
|------|------|-----|-------------|-----------|
| `generate_pubmed_concords` | 71,947 s (20 h) | 71,753 s | 99.7% | 31 GB |
| `protein_compendia` | 19,876 s | 19,844 s | 99.8% | 246 GB |
| `chemical_compendia` | 19,643 s | 19,569 s | 99.5% | 335 GB |
| `geneprotein_conflated_synonyms` | 15,719 s | 15,702 s | 99.8% | 98 GB |
| `gene_compendia` | 15,400 s | 15,178 s | 98.5% | 179 GB |

## Rule 0: measure first, and expect the answer to be "fix the Python"

Pick targets from the `benchmark:` TSVs of a real run, never by reading code for expensive-looking
shapes. Check `mean_load` before assuming a slow rule is CPU-bound — `get_ensembl` is 6,665 s wall
but only 257 s CPU, so no amount of Rust would touch it.

This is not generic advice. Every candidate examined so far has failed on contact with data:

| Candidate | Looked like | Actually |
|---|---|---|
| `SynonymFilter.should_suppress` | O(labels × entries) scan with regexes | `obsolete_synonyms.yaml` holds **3 entries** |
| concord parsing | the obvious string-manipulation target | **159,283 lines in 0.148 s** |
| `parse_pubmed_into_tsvs` | needs a fast XML parser | fed the pull parser **one line at a time** and never called `elem.clear()`; fixing both gave **1.94× and 16× less memory**, in Python |
| `conflate_synonyms` | JSON-heavy merge loop | serialised the entire in-memory structure to JSON for a **suppressed `logger.debug`**, twice more per record, plus a quadratic recompute |

Two more of the same kind are open, both in `write_compendium`'s setup, both untouched:

- **`get_biolink_model_toolkit` (`util.py:405`) has no cache.** It constructs
  `Toolkit(<raw.githubusercontent.com URL>)` on every call — a network fetch plus a linkml parse of
  `biolink-model.yaml`. `NodeFactory.__init__` calls it, `write_compendium` constructs a
  `NodeFactory` per call, and the chemical build calls `write_compendium` **8 times**
  (`config.yaml: chemical_outputs`). Eight fetches and eight full model parses per build.
- **`InformationContentFactory.__init__` (`node.py:368`) reads all of `icRDF.tsv`** — 3,940,399
  lines, 212 MB — calling `curies.Converter.compress()` per line, and is likewise constructed per
  `write_compendium` call. ~31.5 M `compress()` calls per chemical build, seven-eighths of them
  repeating identical work.

`chemical_compendia` is 19,643 s. **Profile it with `py-spy` (already a dev dependency) before
porting it to anything.** If it turns out to be factory-lookup-bound rather than compute-bound, Rust
is not the answer there at all.

## Where Rust would be most useful

Ranked by expected value, after the Python fixes above:

1. **`glom()`'s union-find — `babel_utils.py:1027`.** The strongest case in the codebase, and the
   only one where the win is *memory* rather than speed. The dict-of-sets rewrites every member's
   pointer on every merge (`:1159-1160`), and holds the state as Python objects: measured against
   the anatomy build, glom's representation costs **73 MB resident for a clique state that
   serialises to 4.8 MB — 15×**. That overhead is why `protein_compendia` and `chemical_compendia`
   sit at 246 GB and 335 GB and need `mem="512G"` reservations. A disjoint-set over interned integer
   IDs attacks the 500 GB headline directly, which nothing else here does.
2. **`conflate_synonyms` — `synonymconflation.py:22`.** 7.1 h across two rules, stdlib-only, JSONL
   in and JSONL out. But fix the discarded-work bugs and re-measure first; they may be most of it.
3. **`write_compendium`'s per-clique loop — `babel_utils.py:780-1000`.** Millions of iterations of
   CURIE splitting, prefix bucketing and JSON serialisation. Highest ceiling, but **profile before
   believing it**, and it is the one place where a file boundary is awkward (see below).

**Where Rust would not help, despite the size of the number:**

- **`generate_pubmed_concords` (20 h) is probably a Snakemake refactor, not a Rust one.** It parses
  ~1,500 *independent* `.xml.gz` files in a single rule at one core. Sharding it over a wildcard —
  with a merge step for the accumulating `pmid_status` dict — is a plausible route to roughly an
  hour with no Rust at all. There is also a separate effort to replace this rule with a parallel
  DuckDB load, which would supersede either approach. **Do not port this to Rust.**
- **Anything DuckDB already does.** `duckdb` is a dependency and already carries the entire export
  half of the pipeline (`src/exporters/duckdb_exporters.py`). It is compiled, parallel, and arrives
  as a prebuilt wheel that costs nobody a toolchain. For columnar aggregation and joins it beats
  hand-written Rust on every axis including engineering time.

## How to integrate

Four shapes. They compose — this is not one global choice.

| | Shape | Boundary | Who pays the build cost |
|---|-------|----------|-------------------------|
| **A** | in-process pyo3, one package (**what #975 builds**) | Python objects across FFI | everyone, every environment, forever |
| **B** | standalone program invoked from `shell:` | a file, at an existing rule edge | only people who touch Rust |
| **C** | split a rule at a *new* file boundary; implement one side in Rust | a file, at a new rule edge | only people who touch Rust |
| **D** | no Rust — DuckDB and other native libraries already in the tree | in-process, prebuilt wheel | nobody |

Neither B/C nor D is hypothetical. `untyped_chemical_compendia` → `chemical_compendia` is already
exactly C, at the heaviest point in the pipeline, and `protein.py:272-273` carries a TODO wishing
for the same split. `reports.snakefile:209-213` already invokes a console script from `shell:` with
config-derived roots threaded in as `params:` — the precedent for how an out-of-process stage learns
where the files are.

### What the measurement says

The one axis where A could beat B/C is the cost of getting data across. That was measured — see
[`rust-decision/README.md`](./rust-decision/README.md) for the method, which credits pyo3 with a
serialization cost of *zero* and compares against the unavoidable floor of building the Python
objects. Extrapolated to the chemical pipeline's 256,427,006 CURIEs against
`chemical_compendia`'s 19,643 s:

- **Maximum possible saving from going in-process: ~4 minutes, 1.3% of the rule.** That is a
  ceiling no pyo3 implementation can beat.
- **Switching the existing `repr(set)`/`ast.literal_eval` boundary to JSONL would save ~9.5 minutes
  — 2.2× more than in-process could ever save**, with no Rust involved.

So boundary cost does not justify A. The remaining criteria do most of the work, and they are not
about speed:

| Criterion | Favours |
|---|---|
| Can the stage be cut whole? *The only thing that can force A.* | `parse_pubmed_into_tsvs` and `conflate_synonyms` are stdlib-only, paths in and paths out — zero entanglement. The entanglement is all in `write_compendium`. |
| Build burden on people who write no Rust | **B/C.** `[tool.uv] package = true` + maturin means *every* `uv sync` needs cargo — for contributors touching no Rust, for the Docker image, for CI lint jobs. A structurally cannot avoid this; B/C makes `cargo build` optional. |
| Differential testing | **B/C.** This document requires "Python is the specification, a test proves Rust matches it". Out-of-process that test is `diff` on two files, which also covers serialization. In-process it is a Python-object equality harness with `frozenset` ordering hazards. |
| Observability | **B/C** — but note the coupling: a `benchmark:` TSV comes from a separate *rule*, not a separate *process*, so you only get it by paying for an intermediate file. Observability and boundary cost are the same decision. |
| Memory accounting under SLURM | **B/C.** Two sequenced peaks, independently reserved, versus one peak that is the sum. Chemicals, split, peaks at 132 GB then 335 GB; protein, unsplit, peaks at 246 GB in one reservation. |
| Reversibility | **B/C** — delete a binary, restore one `shell:` line. And this has a deadline: `rust/src/lib.rs` currently exports one constant and **zero functions**, so reverting today costs only a build-backend swap. That stops being true with the first real `#[pyfunction]`. |
| Who can reproduce a bug | **B/C** — a binary runs by hand against a file path; a `#[pyfunction]` is only reachable through a multi-hour Snakemake rule. |
| Failure isolation | **Neither, materially.** Every rule is already its own SLURM job (`slurm/config.yaml`, `jobs: 50`) and Snakemake retries a failed `run:` and a failed `shell:` identically. Do not lean on this. |

### Recommendation (not a decision)

**Default to B or C. Keep A for the case where Rust must sit inside a Python function that cannot be
split** — realistically only `write_compendium`, and only if profiling shows Rust would help there
at all. Keep #975's plumbing: it is the mechanism for the A case, it is already built and reviewed,
and its marginal cost is the toolchain requirement.

### The strongest argument against this recommendation

**Every new rule boundary is a new serialization format, and a format is a public interface that
needs versioning.** A new intermediate file has to be named, placed, made `temp()` or not, sized
into the disk budget — and then kept compatible across changes on both sides. Babel already has one
of these that nobody designed: `f"{set(s)}\n"` written at `chemicals.py:1110-1113` and read back
with `ast.literal_eval` at `:1165-1168`, a Python `repr` serving as a wire format. Adding *N* more
Rust-writes/Python-reads contracts is *N* more places for silent format drift. By contrast the pyo3
boundary is a function signature, covered by `src/_accel.pyi` and the `ABI_VERSION` guard.

Mitigation if B/C is chosen: **mandate JSONL for new boundaries and nothing else**, and rely on the
`diff`-based differential test to catch drift on the first CI run. The cost is real either way.

## The FFI boundary rule (if A is used)

A `#[pyfunction]` takes a **file path** and returns the whole parsed result. It never takes one row.
Crossing pyo3 once per CURIE costs more than the Python it replaces, so a per-row entry point would
be *slower* while looking like an optimisation. Enforced structurally: Rust functions open their own
files, so no entry point could accept a row.

Note the tension this creates, because it is the crux of the whole question: taken seriously, this
rule means every Rust entry point is already shaped like a standalone program. **The discipline that
makes pyo3 fast is the discipline that makes pyo3 unnecessary.**

## Using the in-process extension

Import through [`src/accel.py`](../src/accel.py), never `src._accel` directly:

```python
from src.accel import accel

def read_something(path):
    if accel is not None:
        return accel.read_something(path)
    return _read_something_python(path)
```

- **A missing extension falls back to Python rather than raising.** Every snakefile does a top-level
  `import src.foo` at DAG-parse time, so an `ImportError` would take down all 243 rules for a
  contributor without a toolchain, a reviewer, or a fork's CI. AGENTS.md's "a log warning is not a
  control" is about *wrong output*; a slower path producing identical bytes is not that.
- **A stale extension raises.** The extension is installed editable, so the compiled artifact lives
  in the checkout at `src/_accel.*.so` and `git pull` does not rebuild it. `ABI_VERSION` is compared
  at import — i.e. at DAG-parse time — so a stale build fails in the first second rather than eleven
  hours into a rule. Fix with `uv sync --reinstall-package babel-pipeline`.
- **`BABEL_DISABLE_RUST=1` forces the Python path**, which is how you A/B a port in one checkout. An
  environment variable rather than a `config.yaml` entry: which of two byte-identical
  implementations runs has no user-facing meaning, and `config.yaml` is threaded into Snakemake
  `params` and output paths where changing it could perturb a running DAG. Precedent:
  `BABEL_DUCKDB_TEMP_DIR`.
- **Keep the Python implementation as the reference**, with a test asserting the two produce
  identical output. The Python is the specification; the test is the proof. Bump `ABI_VERSION` in
  both `rust/src/lib.rs` and `src/accel.py` in the same commit as any semantic change.

## Building

A toolchain is a build prerequisite for **every** environment, because `[tool.uv] package = true`
means every `uv run` and `uv sync` builds the project, and building it invokes cargo.

- **Locally:** `uv sync`. Without `cargo` on `$PATH`, uv bootstraps a toolchain itself (via
  `puccinialin`) rather than failing — convenient, but it silently downloads ~600 MB into a platform
  cache directory that `UV_CACHE_DIR` does **not** cover. `brew install rustup && rustup default
  stable` (or <https://rustup.rs>) avoids that.
- **CI:** `dtolnay/rust-toolchain@stable` plus `Swatinem/rust-cache@v2` in `test.yml`. The
  formatting workflow runs snakefmt with `uv run --no-project` so a lint job does not build at all.
- **Docker:** rustup, not `apt install cargo` — Debian bookworm ships cargo 1.63, *exactly* pyo3
  0.23's minimum, so the next pyo3 bump would break the image with an unrelated-looking error.
  rustup also honours `rust-toolchain.toml`, which apt's cargo ignores.
- **Hatteras:** `uv sync` runs once on the login node and compute nodes reuse the `.venv` from
  `/projects`, so compilation happens in one place — but `uv sync --frozen` **fails outright**
  without a toolchain, before Snakemake starts. See [`slurm/README.md`](../slurm/README.md).

`rust-toolchain.toml` pins the channel (`stable`) rather than a version: nothing publishes a wheel,
so the value is that everyone's cargo comes from the same place. The hard floor is `rust-version` in
`rust/Cargo.toml`.

## Layout

| Path | What |
|------|------|
| `rust/Cargo.toml` | the crate. `version = "0.0.0"` on purpose — maturin takes the distribution version from the root `pyproject.toml`, and nothing publishes this crate |
| `rust/src/lib.rs` | the `#[pymodule]`: module doc, `ABI_VERSION`, registrations. Functions go in their own modules, split from the first one |
| `src/accel.py` | the only thing that imports the compiled module |
| `src/_accel.pyi` | hand-written stub. No mypy here, so it enforces nothing; it exists so a reader who does not read Rust can see what the module offers |
| `docs/rust-decision/` | the boundary-cost experiment behind the recommendation above |

## History, and a correction

[PR #588](https://github.com/NCATSTranslator/Babel/pull/588) built 19 standalone binaries under
`babel_io/src/bin/` invoked from `shell:` blocks. 3,252 lines across 44 files, unmerged since
September 2025. Its failure was **targeting**: those binaries covered datacollect label/synonym
rules totalling roughly 1.5 h of CPU — under 2% of the pipeline — two of them download-bound where
Rust does nothing, while `build_compendia.rs`, the one aimed at an expensive rule, is a 72-line
stub.

An earlier AI-written version of this file drew the wrong lesson from that, concluding "the
in-process model fits the codebase better" and supporting it with "245 of Babel's Snakemake rules
are `run:` blocks with no `script:` directives and no subprocess boundaries."
**Both halves were wrong.** The counts are **243 `run:` and 26 `shell:`**, and
`reports.snakefile:209-213` already threads config-derived roots into a console script — the exact
pattern that paragraph claimed did not exist.

## 588's lesson is about picking targets, not about which shape to use; that is why "Rule 0" above

leads this document.
