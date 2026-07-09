# Ubergraph: what its IRIs look like, and how Babel filters them

Ubergraph is queried over SPARQL (`src/ubergraph.py`) and is the source of the shared label,
synonym, and description files under `babel_downloads/common/ubergraph/`. Unlike most Babel
sources it is not a single vocabulary: it is a merged reasoned triplestore over dozens of OBO
ontologies, so a single query returns identifiers from ~200 prefixes at once, plus a tail of
things that are not ontology terms at all.

This page records what actually comes back, because the filtering code that deals with it is
subtle and currently wrong in ways that are easy to miss.

## The filter as it stands today

`src/datahandlers/obo.py` repeats this guard three times, once each in `pull_uber_labels()`,
`pull_uber_descriptions()`, and `pull_uber_synonyms()`:

```python
prefix in ["http", "ro"] or prefix.startswith("t") or "#" in prefix
```

It is trying to reject four different things at once, and it only partly succeeds.

## What Ubergraph returns that is not a CURIE

### Bare IRIs

`Text.opt_to_curie()` recognises a fixed list of IRI patterns (OBO PURLs, Orphanet, EFO, OMIM,
identifiers.org, and a few more). Anything it does not recognise, and anything whose conversion
would produce a string with no colon, raises `ValueError`. The three result loops in
`src/ubergraph.py` catch that and **fall back to using the raw IRI as-is**, so strings like
`http://www.w3.org/2000/01/rdf-schema#label` flow downstream as if they were CURIEs. The
`prefix in ["http", ...]` clause exists to catch those.

It does not catch `https://` — see "Known leaks" below.

### Blank nodes

Ubergraph serialises blank nodes as `t` followed by digits, e.g. `t27502167`. These have no
colon, so `Text.get_prefix()` raises `ValueError` on them. `UberGraph.is_blank_node()` already
recognises this shape precisely (leading `t`, all remaining characters digits).

The `prefix.startswith("t")` clause in `obo.py` is a looser restatement of that check. It is
**live only in `pull_uber_labels()`**, which extracts the prefix with a bare `iri.split(":")[0]`
and so sees the whole colon-less blank node as the "prefix". In `pull_uber_descriptions()` and
`pull_uber_synonyms()`, which use `Text.get_prefix()`, the `ValueError` is caught first and the
row is skipped before the `startswith("t")` test ever runs — the clause is dead code there.

The clause is also over-broad: it would reject any legitimate lowercase prefix beginning with
`t`. None exists in `src/prefixes.py` today (`TCDB` is the only `t` prefix and it is uppercase),
so nothing is lost, but that is luck rather than design.

### Fragment IRIs mangled into fake CURIEs

`Text.opt_to_curie()` converts OBO PURLs by taking the last path segment and splitting it on `_`.
When the last segment contains a fragment, the result is a syntactically invalid CURIE rather
than a `ValueError`:

| Input IRI | `opt_to_curie()` output |
|---|---|
| `http://purl.obolibrary.org/obo/UBERON_0000001` | `UBERON:0000001` |
| `http://purl.obolibrary.org/obo/uberon/core#part_of` | `core#part:of` |
| `http://purl.obolibrary.org/obo/OBO_REL#part_of` | `OBO:REL#:part:of` |

The `"#" in prefix` clause catches the first of these two failures. It misses the second, because
there the `#` lands in the local part and the prefix (`OBO`) looks innocuous.

This mangling is a property of `opt_to_curie()`'s heuristic, not of Ubergraph or of RDF. An OWL
ingest via pyoxigraph would not produce it — there a blank node is a `BlankNode` *type*, not a
`t\d+` string, and IRIs are not string-split.

### Relation Ontology terms

`RO:0002213` "positively regulates", `RO:0002548` "end, days post coitum", and ~770 others are
perfectly well-formed CURIEs. They are predicates, not entities, so Babel has no compendium for
them. The `"ro"` entry in the filter's list is trying to exclude them.

This is the important structural observation: **`"ro"` is a policy exclusion smuggled into a
syntax check.** The other three clauses ask "is this even a CURIE?"; this one asks "do we want
this vocabulary?". Conflating them is why the syntax half of the check was never scrutinised.

## Known leaks

Measured against the 3,816,207-row `babel_downloads/common/ubergraph/labels` from the
2026-06-30 download:

| Leak | Rows in `labels` | Why it slips through |
|---|---|---|
| `https://purl.brain-bican.org/…`, `https://orcid.org/…`, wikidata, `w3id.org/sssom` | 8,762 | the filter tests `"http"`, not `"https"` |
| `RO:0002213` and friends | 772 | the filter tests lowercase `"ro"`; `opt_to_curie()` emits `RO` |
| `OBO:REL#:part:of` | 1 | the `#` is in the local part, not the prefix |

`synonyms.jsonl` leaks 1,331 `https:` rows the same way. `descriptions.jsonl` is clean. Bare
`http://` IRIs and blank nodes are correctly dropped from all three.

The `https://` rows break down as 6,895 BICAN taxonomy terms, 1,327 BICAN ontology terms, and a
couple of dozen ORCIDs, Wikidata entries, and SSSOM URLs. The BICAN terms are real, labelled
cell-type identifiers — worth a deliberate decision rather than an accidental one.

To reproduce the histogram:

```bash
cut -f1 babel_downloads/common/ubergraph/labels | awk -F: '{print $1}' | sort | uniq -c | sort -rn
```

## Why the leaks are currently harmless

`NodeFactory` (`src/node.py`) loads the common labels into a dict keyed by CURIE and looks
entries up by identifier. No compendium contains an identifier with an `https` or `RO` prefix, so
the junk rows are never read. They cost memory, not correctness. Nothing in the output is wrong
today — but the invariant "everything in this file is a CURIE Babel could use" does not hold, and
the next vocabulary Ubergraph adds under an unrecognised namespace will land here silently.

Tracked in [NCATSTranslator/Babel#898](https://github.com/NCATSTranslator/Babel/issues/898), which
proposes splitting the syntax check (move it into `src/ubergraph.py`, reusing `is_blank_node()`)
from the policy exclusion (move it into `config.yaml`), and lists the research needed before the
policy list can be written.
