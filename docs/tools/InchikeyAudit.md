# InChIKey audit

```bash
uv run babel-inchikey-audit --build <local build dir> [--lookup-build <dir or URL>] \
    [--structure-file babel_downloads/UNICHEM/structure.tsv.gz] [--mesh-ownership <file>] --out <dir>
```

Answers: **which records were attached by xref to a chemical structure they are not, and which
concord edge attached them?**

The InChIKey is the solid part of a chemical clique: the records that carry that structure define
what the clique is. The audit takes that core as given and asks whether everything else the xrefs
joined to it belongs there.

## Why it is needed

The chemical pipeline runs `glom()` with `unique_prefixes=[INCHIKEY]`, so an xref joining two
records that both carry an InChIKey is refused. A record with no structure (a biologic, a polymer,
a mixture) has no key to protect it. One bad xref attaches it to an unrelated keyed clique, and
because drug databases name the structure-less side well, the clique often takes its name from it.

The worked example is ofatumumab. DrugCentral's `identifier` table gives `DrugCentral:4951`
(ofatumumab) PubChem CID 8254, which is dimethyl ether. That single edge puts the antibody's
ChEMBL, DrugBank, GtoPdb, UNII and UMLS records into the dimethyl-ether clique, and in 2026jul22
that clique, `CHEBI:28887`, displays as "Ofatumumab".

## How it works

It needs no rebuild and no `glom()` replay. `src/model/glom_edges.py` reconstructs the fate of
every chemical concord edge (applied, refused by the InChIKey guard, or removed by a pre-glom
filter) from a finished build's `Concord.parquet` and chemical `Edge.parquet` files. It raises if
any edge crossing cliques is left unexplained, which means the model has drifted from the pipeline.
Two steps outside `glom()` are modelled:

- **Pre-glom filters:** `remove_overused_xrefs`, and the CUI-ownership skip, for builds that have
  it.
- **The post-glom #83 split:** `create_typed_sets()` moves `MolecularMixture`-typed members into
  their own keyless clique. Each one is rejoined to the parent holding its CIDs' keys, rebuilding
  the **pre-split set**.

`src/model/inchikey_audit.py` then does the following for each keyed pre-split set:

1. **Core:** the key, plus every member with an applied edge to an InChIKey.
2. **Components:** the connected groups of the remaining structure-less members, each attached to
   the core by **boundary edges**.
3. **Tier:** set by how many structure-bearing sources (UniChem's: ChEBI, ChEMBL, DrugBank,
   DrugCentral, GtoPdb, HMDB, PubChem, UNII) list a member of the component with no structure.
   - **A:** three or more.
   - **B:** one or two.
   - **T:** none, but a member is declared `Polypeptide`, `ComplexMolecularMixture` or
     `ChemicalMixture`.
4. **Triage (tier A only):** does the core's structure match that substance? This uses the core's
   heavy-atom count, from the UniChem standard InChI, and agreement between the names on either
   side of the boundary. The core is named by its PubChem CIDs' labels, because a core record can
   carry the biologic's name too: in 2026jul22, `CHEBI:193860` and `HMDB:HMDB0029845` have Tiron's
   structure but are labelled "Chymopapain".
   - **`belongs`:** names agree on a non-trivial core.
   - **`likely misattached`:** names disagree on a small-molecule core.
   - **`review`:** everything else.

The verdicts are about the attached substance, not the core's InChIKey. `likely misattached`
covers two cases:

- **Attached to an unrelated structure,** e.g. ofatumumab → dimethyl ether.
- **Attached to the structure of one of its parts,** e.g. an ADC → its payload, or PEG → ethylene
  glycol.

Both are fixed by blocking the boundary edge, but they go to different upstream reports.

Below tier A the signal is mostly noise. UniChem lags ChEBI, and the overused filter drops some
DrugCentral record→key links, so those records only look structure-less.

## Inputs

- **`--build`:** a local mirror of `duckdb/Concord.parquet` and
  `duckdb/parquet/filename=<Type>/Edge.parquet` for each `chemical_outputs` type. These are scanned
  in full.
- **`--lookup-build`:** supplies `Node.parquet` labels and `Identifier.parquet` types. These are
  only filtered, so the build's URL on stars works. It defaults to `--build`.
- **`--structure-file`:** UniChem's `structure.tsv.gz`, the pipeline's own download. Any release
  works, since an InChIKey always names the same InChI. A key missing from it triages as `review`
  and is logged.
- **`--mesh-ownership`:** `intermediate/umls/mesh_ownership.tsv`, for builds after the
  CUI-follows-MeSH rule. Leave it out for 2026jul22 and earlier.
- **`--badxrefs`:** `input_data/chemical_badxrefs.txt` as the build applied it, for builds made
  after that file existed. Leave it out for 2026jul22 and earlier. Like `--mesh-ownership` it has
  no default: a filter the build did not apply would relabel edges it did apply and hide them,
  while a missing filter the build did apply fails loudly as unexplained edges.

## Output

All files are under `--out`, tab-separated.

- **`components.tsv`:** one row per flagged component, giving the clique, key, tier, verdict,
  structure-source count, core heavy atoms, name score, boundary sources, members, and the labels
  on both sides.
- **`boundary_edges.tsv`:** the concord edges attaching each flagged component to its key, labelled.
  The `likely misattached` rows are the candidate pairs to block.
- **`refused_edges.tsv`:** xrefs the InChIKey guard refused. They are harmless in the build but are
  source errors worth reporting.
- **`summary.tsv`:** counts of edge verdicts, and of components by tier and verdict.

## Limits

- **Pre-conflation only.** Errors made by DrugChemical conflation are invisible to it. For example,
  `UMLS:C0063328` "idose" holds `RXCUI:2672089` "iDose", which merges D-idose with travoprost.
- **No PubChem-internal errors.** It cannot see an error inside PubChem when no concord edge is
  involved, such as a depositor's wrong structure.
- **ChEBI class entries.** A ChEBI class entry that carries one member's structure joins the core,
  not a component.
- **Thresholds.** `TIER_A_MIN_SOURCES`, `NAME_AGREEMENT_MIN` and the heavy-atom cut-offs were set by
  reading every tier A component of 2026jul22. They are documented at their definitions.

## Acting on the results

Components reviewed as wrong go to `input_data/chemical_badxrefs.txt`, which
`build_untyped_compendia()` drops before `glom()`. List every boundary edge of the component, so
it separates cleanly, and state the category and reason in a comment. Before adding an entry,
check the component's guard-refused edges (`refused_edges.tsv`): once the component has no key,
those xrefs are accepted, and they decide which clique it joins next.

The first 55 components were reviewed from 2026jul22's tier A, as 75 pairs. 56 more were kept,
mostly polymers and mixtures whose core is PubChem's own representation of that substance
(heparin, sevelamer, polysorbate 80). Some errors start upstream and cannot be blocked from here:
`CHEBI:193860` and `HMDB:HMDB0029845` carry Tiron's structure under the name "Chymopapain", and
ChEBI's own PEG record sits with ethylene glycol.
