# Rust in Babel

Babel's expensive rules are CPU-bound single-threaded Python. From the `babel-1.18` Snakemake
`benchmark:` TSVs, the five costliest rules all run at ~100% of one core:

| Rule | Wall | CPU | `mean_load` | `max_rss` |
|------|------|-----|-------------|-----------|
| `generate_pubmed_concords` | 71,947 s (20 h) | 71,753 s | 99.7% | 31 GB |
| `protein_compendia` | 19,876 s | 19,844 s | 99.8% | 246 GB |
| `chemical_compendia` | 19,643 s | 19,569 s | 99.5% | 335 GB |
| `geneprotein_conflated_synonyms` | 15,719 s | 15,702 s | 99.8% | 98 GB |
| `gene_compendia` | 15,400 s | 15,178 s | 98.5% | 179 GB |

The build backend is therefore [maturin](https://www.maturin.rs/), and the project builds as a
mixed Rust/Python package: a `cdylib` crate under this directory compiled into `src/_accel`,
alongside the ordinary Python in `../src`.

## Rules for adding a Rust function

**Measure first, from the benchmark TSVs.** Not from reading code for quadratic-looking shapes.
Three candidate targets picked that way all turned out to be wrong: `SynonymFilter.should_suppress`
looks like an O(labels × entries) scan but `../input_data/obsolete_synonyms.yaml` holds three
entries; concord parsing looks like the obvious string-manipulation target but runs 159,283 lines in
0.148 s; and each genuinely expensive rule examined had a pure-Python defect (an eagerly evaluated
f-string feeding a suppressed `logger.debug`, a missing `elem.clear()`) worth more than any port.
Check `mean_load` before assuming a slow rule is CPU-bound — `get_ensembl` is 6,665 s wall but only
257 s CPU, so Rust would do nothing for it.

**The FFI boundary is coarse.** A `#[pyfunction]` takes a whole input — a file path to parse, or
the full in-memory state to transform — and does the whole job in one call. It never takes one row
or one CURIE. Crossing pyo3 once per CURIE costs more than the Python it replaces, so a per-row
entry point would be *slower* while looking like an optimisation. File-parsing functions open their
own files, so there is no entry point that could accept a row; state transforms like `glom` take
the entire clique state and a file's worth of groups per call, never a single group.

**Rust is the implementation — there is no Python fallback and no runtime toggle.** Once a function
lands here it is the only code path; the Python it replaced is deleted, not kept as a parallel copy.
Correctness is therefore guarded by tests, not by a second implementation to fall back on: the unit
suite exercises each accelerator through its real callers, and targeted synthetic tests pin the
exact semantics (see `../tests/test_glom.py`). A Rust toolchain is a hard build prerequisite, so a
missing or stale build fails loudly at DAG-parse time rather than silently running a slower path.

**Bump `ABI_VERSION` in the same commit** as any change to an accelerated function's signature or
semantics — in both `src/lib.rs` and `_REQUIRED_ABI_VERSION` in `../src/accel.py`. See
"Staleness" below.

## Using it from Python

Import through [`../src/accel.py`](../src/accel.py), never `src._accel` directly:

```python
from src.accel import accel

accel.glom(conc_set, newgroups, unique_prefixes=["INCHIKEY"])
```

`accel` is the compiled module, guaranteed present and current — `src/accel.py` raises at import if
either condition fails (see below). Most callers don't import it at all: the accelerated function is
re-exported from the module that used to hold the Python version (e.g. `src.babel_utils.glom`), so
call sites are unchanged.

**A missing or stale extension raises; it does not fall back.** Every snakefile does a top-level
`import src.foo` at DAG-parse time, so a build that regressed fails in the first second of a run,
with the fix in the message, instead of silently producing nothing eleven hours in. This is correct
because a Rust toolchain is a hard build prerequisite (#975): anyone who can run Babel at all has
the extension, so its absence means the build broke, not that the environment lacks Rust. The active
extension is logged once at INFO, which lands in the SLURM job log that `babel-slurm-errors` reads.

## Staleness

The extension is installed **editable**: the compiled artifact lands in the checkout at
`src/_accel.*.so` (gitignored), and that is the copy `PYTHONPATH=.` finds. A `git pull` that brings
new Rust source does **not** rebuild it, so without a guard a stale binary would be used silently
— potentially for a 12-hour rule.

So `../src/accel.py` compares the extension's `ABI_VERSION` against its own `_REQUIRED_ABI_VERSION`
and raises if they disagree. The check runs at import, i.e. at DAG-parse time, so a stale build
fails in the first second of a run. To fix one:

```bash
uv sync --reinstall-package babel-pipeline
```

What the guard does not catch is editing the Rust body without bumping the constant — there is no
parallel Python implementation to diff against, so review and the unit suite are the only checks on
that. Bump early, bump often.

## Building

A Rust toolchain is a build prerequisite for **every** environment now, because `[tool.uv] package
= true` means every `uv run` and `uv sync` builds the project, and building the project invokes
cargo.

- **Locally:** `uv sync`. If `cargo` is not on `$PATH`, uv bootstraps a toolchain itself (via
  `puccinialin`) rather than failing — convenient, but it silently downloads ~600 MB into a
  platform cache directory that `UV_CACHE_DIR` does **not** cover. Installing rustup yourself
  (`brew install rustup && rustup default stable`, or <https://rustup.rs>) avoids that.
- **CI:** `dtolnay/rust-toolchain@stable` plus `Swatinem/rust-cache@v2` in `test.yml`. The
  formatting workflow deliberately runs snakefmt with `uv run --no-project` so that a lint job does
  not build the project at all.
- **Docker:** the image installs rustup rather than `apt install cargo`. Debian bookworm ships
  cargo 1.63, which is *exactly* pyo3 0.23's minimum, so the next pyo3 bump would break the image
  with an error that reads as unrelated. rustup also honours `../rust-toolchain.toml`, which apt's
  cargo ignores.
- **Hatteras:** `uv sync` runs once on the login node and compute nodes reuse the `.venv` from
  `/projects`, so compilation happens in one place. Make sure a toolchain is available there before
  a build — `uv sync --frozen` fails outright without one, before Snakemake starts. See
  [`../slurm/README.md`](../slurm/README.md).

`../rust-toolchain.toml` pins the channel (`stable`) rather than an exact version: nothing here
publishes a wheel, so the value of pinning is that everyone's cargo comes from the same place
rather than from whatever a distro packages. The hard floor is `rust-version` in `Cargo.toml`.

## Layout

| Path                     | What                                                                                                                                                    |
|--------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| `Cargo.toml`             | The crate. `version` is `0.0.0` on purpose — maturin takes the distribution version from the root `../pyproject.toml`, and nothing publishes this crate |
| `src/lib.rs`             | The `#[pymodule]`: module doc, `ABI_VERSION`, registrations. Functions go in their own modules, split from the first one                                |
| `src/glom.rs`            | The union-find clique builder that replaced `babel_utils.glom` (re-exported there); see its module docs for the algorithm and parallelism               |
| `../src/accel.py`        | The only thing that imports the compiled module                                                                                                         |
| `src/_accel.pyi`         | Hand-written stub. There is no mypy here, so it enforces nothing; it exists so a reader who does not read Rust can see what the module offers           |
| `../rust-toolchain.toml` | Channel pin                                                                                                                                             |

## History

[PR #588](https://github.com/NCATSTranslator/Babel/pull/588) took a different approach — 19
standalone binaries under `babel_io/src/bin/` invoked from Snakemake `shell:` blocks — and is worth
reading as a cautionary tale. It targeted datacollect label/synonym rules totalling roughly 1.5 h of
CPU, under 2% of the pipeline, two of them download-bound where Rust does nothing; the one binary
aimed at an expensive rule (`build_compendia.rs`) is a 72-line stub. 3,252 lines across 44 files,
unmerged. Hence the "measure first" and "one path, deep" rules above.

The in-process pyo3 model that replaced it fits the codebase better regardless: 245 of Babel's
Snakemake rules are `run:` blocks with no `script:` directives and no subprocess boundaries, so an
importable extension needs no rule rewriting, whereas standalone binaries would mean converting
rules to `shell:` one at a time.
