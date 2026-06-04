# Memory tools

Diagnostic tools for sizing Babel's memory requirements. Output here informs the
`mem=` resources on Snakemake rules (see `slurm/README.md`) and the
`@pytest.mark.min_memory_gb(n)` guards on memory-hungry pipeline tests (see
`tests/README.md`).

## estimate_rdf_load_memory.py

Estimates the peak RAM needed to bulk-load one or more RDF files into an
in-memory `pyoxigraph.Store` — the pattern used by data handlers such as
`ChemblRDF` (`src/datahandlers/chembl.py`) that load a whole dump before
querying it. An indexed in-memory triple store can need many times the
file's on-disk size, so guessing is unreliable.

The tool streams the input in small chunks into a store, samples resident memory
against bytes consumed, and extrapolates linearly to the full file. It stops once
RSS crosses a ceiling (`--rss-ceiling-gib`, default 16) or a fraction of the
input is loaded (`--max-fraction`, default 0.30), so it never exhausts RAM — you
can estimate a 120 GiB load on a 32 GiB laptop.

```bash
# ChEMBL: load cco.ttl (tiny) first, then the big molecule dump, like ChemblRDF
uv run python tools/memory/estimate_rdf_load_memory.py \
    babel_downloads/CHEMBL.COMPOUND/cco.ttl \
    babel_downloads/CHEMBL.COMPOUND/chembl_latest_molecule.ttl
```

Format is inferred from the extension (`.ttl`, `.nt`, `.nq`, `.trig`,
`.rdf`/`.owl`/`.xml`); override with `--format TURTLE` etc.

### Interpreting the output

Each line prints quads loaded, bytes read, current and peak RSS, and the
projected full-load size. Early percentages are noisy (fixed startup overhead
dominates) and settle as more loads. Because the store indexes as it loads, the
real peak is usually a bit above the linear projection — treat the number as a
floor and add headroom.

### macOS caveat

This estimate is most trustworthy on **Linux**. macOS transparently compresses
memory, so once the working set is large the resident page count stops growing
while the store keeps expanding, and the projection drifts downward and
understates the requirement. On macOS, trust the early-region projection (before
`current RSS` plateaus) and prefer Linux for an authoritative number.

### Worked example: ChEMBL (2026-05 dump)

The ChEMBL molecule TTL is ~15.8 GiB on disk. On a 32 GiB macOS laptop the
early-region samples (before memory compression flattened RSS) gave a marginal
cost of ~0.57 GiB per million quads over an estimated ~215M quads, projecting a
full in-memory load of roughly **120–150 GiB**. This confirms the
`chembl_labels_and_smiles` rule's `mem="128G"` is appropriate, and that the
`min_memory_gb(128)` guard on the `test_chembl` pipeline tests is right — a
60 GiB host would not be enough.
