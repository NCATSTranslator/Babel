# Replaying conflate_synonyms() over a finished build

`conflate_synonyms()` (`src/synonyms/synonymconflation.py`) writes `GeneProteinConflated.txt.gz`
and `DrugChemicalConflated.txt.gz`. To see what a change to it does to real output without a
rebuild, [`scripts/replay_conflated_synonyms.py`](scripts/replay_conflated_synonyms.py) runs the
old and the new function over a finished build's own inputs and diffs them. The inputs are the
conflation file, each compendium rebuilt from the DuckDB `Edge` Parquet exports, and each type's
synonym file, all read in place.

The script is a one-off. Turning it into a reusable `babel-replay-conflated-synonyms` tool, with
its logic in `src/`, is [#1229](https://github.com/NCATSTranslator/Babel/issues/1229).

The old function is read from a git ref (`--old-ref`, default `2026jul22`). The script first checks
its replay against the conflated file the build published. Only if every record matches are the
reconstructed inputs faithful, so read the second diff only after the first comes back clean.
Records outside the replayed cliques pass through both versions unchanged, so the diff covers the
whole file, or the whole sample.

GeneProtein's full merge needed 512G on the cluster. `--sample 100` replays the conflation groups
whose primary ID hashes into a fixed 1%. Each run caches its downloads and an `edges.duckdb` copy of
the `Edge` tables (about 5 GB each) in `--workdir`, so put that under `data/`.

The replay only covers what `conflate_synonyms()` itself does. It feeds the old and new function
the same published synonym files, so it can't see a change to how those files are written. Since
PR #1179, `conflate_synonyms()` doesn't filter types at all. The filter that leaves out
`OntologyClass` is in `write_compendium()`, and
[`../../synonyms/ontology-class/`](../../synonyms/ontology-class/README.md) measures it instead.

## PR #1176 against 2026jul22

PR #1176 rewrote how `conflate_synonyms()` claims and merges a conflated group's records. Replayed
against the `2026jul22` tag on a laptop, it changes no record in either file:

| Conflation   | Replayed                            | Old replay vs published | New vs old replay |
|--------------|-------------------------------------|------------------------:|------------------:|
| DrugChemical | all 8,624 lines, 8,218 records      |      8,218 identical    |   8,218 identical |
| GeneProtein  | 1% sample: 159,813 lines and records |    159,813 identical    | 159,813 identical |

Each case #1176 changes would have changed a record: a record keyed on a non-leader clique member, a
clique with two records, two conflation lines sharing a primary ID, or a clique that shares a CURIE
with a conflated one. None occurs in DrugChemical, or in the GeneProtein sample.
[`../split-cliques/`](../split-cliques/README.md) checks the full files and finds no clique claimed
by two groups, so the new error doesn't fire on this build. DrugChemical took about 15 minutes and
the GeneProtein sample about 25, most of it spent streaming the synonym files.
