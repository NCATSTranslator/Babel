# Metadata in Babel

Babel emits `metadata.yaml` files alongside the data it generates so that
downstream consumers — and humans reviewing a build — can answer "what is in
this file, where did it come from, and how was it filtered?" without re-reading
the snakefiles. This document is the schema reference.

The metadata format is not hard-locked. It is established by example, by the
helpers in [`src/metadata/provenance.py`](../src/metadata/provenance.py), and
by the worked examples linked below. If you need fields that don't yet exist,
add them and update this document.

This document currently covers metadata files emitted by the build. Other
Babel metadata — compendium-internal taxon flags, IC values, conflation
provenance — is not yet covered here. As that information moves into
metadata.yaml or its own per-area document, this file should grow to reference
it.

## Where metadata lives

There are three kinds of metadata file, distinguished by location and naming:

- **Download metadata** — `babel_downloads/<SOURCE>/metadata.yaml`. Records
  what was fetched from an external source. Written by some data handlers via
  `write_download_metadata`; not every download produces one.
- **Concord metadata** — `babel_outputs/intermediate/<TYPE>/concords/metadata-<NAME>.yaml`,
  next to the concord file `<NAME>` it describes. Records the concord's
  provenance, what filters were applied, and counts derived from walking the
  concord file. Written by `write_concord_metadata` (or `write_combined_metadata`
  when the concord aggregates several upstream inputs).
- **Compendium metadata** — `babel_outputs/metadata/<COMPENDIUM>.yaml`, named
  after the final compendium file. Records cliques counts and recursively
  aggregates the concord metadata that fed into it. Written by
  `write_compendium` in `src/babel_utils.py`.

## Helpers in `src/metadata/provenance.py`

Four functions, used in this layered way:

- `write_metadata(filename, typ, name, *, sources, url, description, counts, combined_from)` —
  the base helper. Writes the schema below to `filename`. Used directly for
  ad-hoc cases (e.g. `typ="transform"` for label-extraction rules in
  `complexportal.py`, `hgncfamily.py`, `pantherfamily.py`).
- `write_download_metadata(filename, *, name, url, description, sources, counts)` —
  thin wrapper that forwards to `write_metadata` with `typ="download"`.
- `write_concord_metadata(filename, *, name, concord_filename, url, description,
  sources, counts, combined_from)` — walks the concord file at `concord_filename`
  to populate `counts.concords` (line count, distinct CURIEs, per-predicate
  counts, per-prefix-pair counts), then calls `write_metadata` with
  `typ="concord"`. Pass `combined_from` when the concord was aggregated from
  multiple upstream inputs (see
  [Recursion via `combined_from`](#recursion-via-combined_from)).
- `write_combined_metadata(filename, typ, name, *, sources, url, description,
  counts, combined_from_filenames, also_combined_from)` —
  loads each YAML file in `combined_from_filenames`, indexes the resulting
  blocks by their `name` field, and writes a metadata record whose
  `combined_from` field is that index. `also_combined_from` is a dict of
  in-memory blocks to merge in alongside the loaded files. Used by
  `write_compendium` to roll the concord metadata up into the final compendium
  metadata.

If you add a new metadata-emitting site, prefer the most specific helper that
fits. Reach for `write_metadata` directly only when none of the typed helpers
fit.

## On-disk schema

Every metadata file has the same top-level shape:

```yaml
created_at: '<ISO 8601 timestamp>'
type: <see "type" below>
name: <human-readable name; required and used as the key in combined_from>
url: <canonical source URL, or '' if none applies>
description: <free-form prose>
sources:
  - name: <upstream source name>
    url: <upstream source URL>
    type: <optional: a label classifying this source>
counts: {...}
combined_from: {...} | []
```

`name` is **required** for any block that may appear in another file's
`combined_from`. `write_combined_metadata` raises if a child block lacks one.

### The `type` field

The `type` field tags what kind of artefact the file describes. Established
values:

- `download` — written by `write_download_metadata`. The artefact is a file
  fetched from an external source.
- `concord` — written by `write_concord_metadata`. The artefact is a concord
  file (`<curie>\t<predicate>\t<curie>` triples).
- `compendium` — written by `write_compendium` via `write_combined_metadata`.
  The artefact is a final compendium JSONL file.
- `transform` — written via `write_metadata` directly when an intermediate
  step extracts labels/synonyms from a downloaded source rather than
  producing a concord.

New `type` values are allowed when none of the above fit. Pick a stable
name, use it consistently across rules of the same kind, and add an entry
to the list above.

### The `counts` field

`counts` holds whatever quantitative information is appropriate for the
artefact. It is a dict so that new keys can be added without breaking
existing readers.

- **For concords** (written by `write_concord_metadata`), one key is always
  populated automatically:

  ```yaml
  counts:
    concords:
      count_concords: <int>            # rows in the concord file
      count_distinct_curies: <int>     # unique CURIEs across both subject and object
      predicates: { <predicate>: <count>, ... }
      prefix_counts: { '<predicate>(<prefix1>, <prefix2>)': <count>, ... }
  ```

  Per-input counts (when the concord aggregates upstream files in formats
  that aren't themselves concords) go under their own key under `counts`. The
  HP-MP concord uses `counts.sssom` for this:

  ```yaml
  counts:
    sssom:
      total_rows_input: <int>
      confidence_threshold: <float | null>
      rows_dropped_by_confidence: <int>
      rows_dropped_no_term_found: <int>
      rows_dropped_unaccepted_predicate: <int>
      predicates_dropped: { <predicate>: <count>, ... }
      rows_written: <int>
      predicates_kept: { <predicate>: <count>, ... }
  ```

  The convention is: name the per-input-counts key after the input format
  (e.g. `sssom`, or some future `obo`, `csv`, `sparql`), and record enough
  numbers that filter behaviour can be audited from the YAML alone.

- **For compendia** (written by `write_compendium`), top-level counts:

  ```yaml
  counts:
    cliques: <int>
    eq_ids: <int>
    synonyms: <int>
    property_sources: { <source>: <count>, ... }
  ```

- **For downloads and transforms**, `counts` is often omitted or holds simple
  totals (rows extracted, files downloaded). There's no fixed schema yet.

### Recursion via `combined_from`

`combined_from` is a dict keyed by the child block's `name`, with values that
are themselves metadata blocks of the same shape as this document describes.
This makes the format recursive: a compendium-level YAML contains the concord
YAMLs that fed it, and a multi-source concord YAML (like `metadata-HP_MP.yaml`)
contains the per-input blocks that fed it.

Mechanics from `write_combined_metadata`:

- Each YAML file in `combined_from_filenames` is loaded, validated to have a
  `name` field, and inserted into the dict under that name. If two children
  share a name, the existing entry is wrapped in a list and the new entry is
  appended (this is how `Disease.txt.yaml` ends up with two
  `build_disease_obo_relationships()` blocks side by side under that one key).
- `also_combined_from` lets a caller merge in already-built blocks (dicts
  rather than YAML files) without first writing them to disk. This is how
  `build_hp_mp_concords` records per-SSSOM-input provenance: it builds the
  per-input blocks in memory and passes them through `combined_from` to
  `write_concord_metadata`.

When there's nothing to aggregate, `combined_from` is `[]` (an empty list).
When there is, it's an object/dict.

## Conventions and gotchas

- **File naming.** Concord metadata is `metadata-<NAME>.yaml` next to its
  concord file `<NAME>`. Compendium metadata is `<COMPENDIUM>.yaml` (no
  `metadata-` prefix) under `babel_outputs/metadata/`. The
  `disease_compendia` / `chemical_compendia` / etc. rules expand
  `metadata-{ap}.yaml` for each entry in the corresponding `*_concords` list,
  so a new concord rule must produce a metadata file at the path Snakemake
  expects.
- **`name` must be unique within `combined_from`** unless deliberate
  duplication is the point. If it isn't, two blocks will collide into a list
  and downstream readers may not handle that as you'd expect.
- **Don't paste counts into documentation.** Numbers in markdown drift the
  moment a source updates; numbers in `metadata.yaml` are regenerated every
  build. Documentation describes filters and intent; metadata describes what
  actually happened.
- **`write_concord_metadata` raises** if `counts.concords` is already set in
  the `counts` dict you pass in — it will not overwrite. If you need to
  pre-populate other count keys, fine; just don't claim the `concords` key.
- **Empty / missing fields.** `sources` defaults to `[]`, `counts` to `{}`,
  `combined_from` to `[]` (list, not dict). The choice of `[]` for an empty
  `combined_from` instead of `{}` is a quirk of the helper rather than a
  promise to consumers; treat both as "nothing aggregated."
- **Errors are not yet captured.** When a download fails or a filter rejects
  every row, the metadata file may simply not exist or may show zero rows
  (see Pistoia's `rows_written: 0` in `metadata-HP_MP.yaml`). There is no
  standard for recording errors; that's a gap worth filling once a real use
  case appears.

## Examples in the repository

For quick reference, three real-world examples that exercise the format:

- Leaf concord, single input —
  `babel_outputs/intermediate/chemicals/concords/metadata-wikipedia_mesh_chebi.yaml`.
  Demonstrates the basic shape: `type: concord`, an empty `combined_from`,
  the auto-populated `counts.concords`.
- Concord aggregating multiple SSSOM inputs —
  `babel_outputs/intermediate/disease/concords/metadata-HP_MP.yaml`.
  Demonstrates `also_combined_from`-style recursion at the concord level
  with per-input `counts.sssom` blocks describing each filter stage.
- Compendium aggregating multiple concord metadata files —
  `babel_outputs/metadata/Disease.txt.yaml`. Demonstrates the deepest
  recursion in current use: the compendium's `combined_from` is keyed by
  concord name; each concord block has its own `combined_from` if it in turn
  aggregated upstream inputs.

## See also

- [`src/metadata/provenance.py`](../src/metadata/provenance.py) — the helpers.
- [`docs/AddingSources/README.md`](AddingSources/README.md) — when to emit
  metadata for a new source addition (item 2 of the checklist).
- [`docs/Architecture.md`](Architecture.md) — where concord and compendium
  files fit in the overall pipeline.
