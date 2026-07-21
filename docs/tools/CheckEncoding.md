# Check encoding

`uv run babel-check-encoding` surveys Babel's label, synonym, and compendium files for encoding
damage, reporting what it finds instead of failing.

The same detector (`src/synonyms/encoding.py`) runs inside the pipeline, where it *raises* — see
[the encoding check](../Development.md#the-encoding-check) for that side. This tool is how you find
out what a build already contains before relying on the raising check, and how you triage a build
that failed it.

## What counts as damage

Two signals:

**Mojibake** — UTF-8 bytes decoded with a single-byte codec. `é` becomes `Ã©`, `'` becomes `â€™`.
The detector confirms it by encoding the text back to that codec and decoding those bytes as UTF-8:
if the round-trip succeeds and produces something different, the text was damaged, and the tool
reports the repaired guess alongside it.

Both codecs Babel reads with are tried — `cp1252` (UNII) and `latin-1` (PubChem). They damage text
differently: latin-1 turns bytes `0x80`-`0x9f` into C1 control characters where cp1252 turns them
into printable punctuation, so an en-dash misread as latin-1 needs the latin-1 round-trip to be
*repairable* rather than merely detectable.

Legitimate non-ASCII text cannot round-trip and so is never flagged — `α` in
`Nα-acetyl-L-lysine` has no cp1252 byte at all, and `Ménière disease` re-encodes to bytes that are
not valid UTF-8.

**Impossible characters** — C0 controls, DEL, U+FFFD REPLACEMENT CHARACTER (proof of a lossy
decode), and a byte-order mark left embedded in the text.

## Usage

```bash
# One file.
uv run babel-check-encoding babel_downloads/PUBCHEM.COMPOUND/labels

# A whole download or output directory.
uv run babel-check-encoding --recursive babel_downloads
uv run babel-check-encoding --recursive babel_outputs/compendia --out-tsv encoding_issues.tsv
```

`--recursive` picks up files named `labels` or `synonyms` (Babel's TSVs have no extension) and
anything ending in `.txt` (the compendium and synonym JSONL outputs). Line shape is detected from
the content, so all four formats can be scanned in one pass.

`--examples N` sets how many example rows to print per file (default 5). `--out-tsv` writes every
issue as `file, line, curie, text, reason`; the text is `repr()`-quoted so a control character in
the data cannot corrupt the TSV.

The exit code is 1 if anything was found, so a script can gate on it directly.

## Where damage comes from

Three ingests read their source with a single-byte codec, and are the first places to look:

- `src/datahandlers/datacollect.py` — PubChem `CID-Title.gz` and `CID-Synonym-filtered.gz` as
  `latin-1`.
- `src/datahandlers/unii.py` — `UNII_RECORDS_ENCODING = "windows-1252"`, and a second file as
  `latin-1`.

If the survey shows damage concentrated in `PUBCHEM.COMPOUND` or `UNII`, that is why. Before
changing how one of those files is read, characterize the whole download rather than a sample —
see ["Characterize a messy field before you parse it"](../Development.md) and the worked example in
[`docs/sources/NCBIGene/quoting/`](../sources/NCBIGene/quoting/).
