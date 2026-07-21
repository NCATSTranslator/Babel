# CHEBI

ChEBI is ingested from two files pulled by `src/datahandlers/chebi.py`:

- `ChEBI_complete.sdf` — the structure file, read by `make_chebi_relations()` for labels, secondary
  identifiers, and KEGG COMPOUND / PubChem Compound cross-references.
- `database_accession.tsv` — the flat cross-reference table, used for the ChEBI entries that have no
  structure and so never appear in the SDF.

## Deliberately ignored: PubChem substance xrefs

The SDF carries PubChem cross-references under two separate tags, and Babel reads only one of them:

| Tag | Entries in babel-1.18 | Ingested? |
| --- | --- | --- |
| `PubChem Compound Database Links` | 180,991 | yes, as `PUBCHEM.COMPOUND` |
| `PubChem Substance Database Links` | 191,573 | **no** |

This is a deliberate choice, not an oversight. A PubChem substance is a submitter-deposited record,
so it is a much weaker equivalence assertion than a PubChem compound — several substance records
routinely describe the same chemical, and what they assert is "some depositor submitted this" rather
than "this is the same chemical". Compound IDs are the normalized entries and are what we want for
clique building.

`PUBCHEM.SUBSTANCE` does exist as a prefix (`src/prefixes.py`), so ingesting these later is a small
change if we ever want them: read the substance tag in `make_chebi_relations()` the same way the
compound tag is read. Consider first whether substance-level equivalence is strong enough for
`glom()`, which treats every concord row as an equivalence.

Note that this is not a behaviour change from before the babel-1.18 tag renames. ChEBI previously
published both under a single `PubChem Database Links` tag holding `SID: nnn CID: nnn` pairs, and
the code that parsed it extracted only the CIDs. ChEBI now does that separation for us.

## SDF tag names

ChEBI renames the SDF's data-item tags between releases, and an unrecognized tag is silently
ignored rather than raising — which in `babel-1.18` emptied both the secondary-identifier and
PubChem ingests without failing the build. See
[`sdf_tags/README.md`](./sdf_tags/README.md) for what broke, the checks that now catch it, and how
to re-audit the tags against a fresh download.
