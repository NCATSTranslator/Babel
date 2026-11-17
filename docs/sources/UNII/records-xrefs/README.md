# UNII records' PubChem and CAS cross-references

FDA's `Latest_UNII_Records.txt` gives most UNIIs a PubChem CID (`PUBCHEM` column) and a CAS number
(`RN` column). Babel used to read neither, so a UNII that UniChem couldn't link by InChIKey stayed
in a clique of its own beside the PubChem record for the same substance. The case that found it was
rabbit insulin ([#1171](https://github.com/NCATSTranslator/Babel/issues/1171),
[#1225](https://github.com/NCATSTranslator/Babel/issues/1225)): `UNII:LWB6BD8SN9` "INSULIN RABBIT"
names `PUBCHEM.COMPOUND:118984376`, and the two were separate cliques in every build from 2025jan23
to 2026jul22.

`chemicals.write_unii_records_concords()` now writes both columns. The chemical build reads only the
PubChem one (`config.yaml: chemical_concords` lists `UNII_PUBCHEM`, last). This page records the
measurement behind that choice.

## What the measurement is

[`scripts/measure_unii_records_xrefs.py`](./scripts/measure_unii_records_xrefs.py) runs the
production writer and the production `remove_overused_xrefs()` over a records file. It then looks
up every endpoint's clique in a finished build's chemical `Edge.parquet` files and replays
`glom()`'s merge rule over those cliques. A pair joins two cliques unless both carry an InChIKey and
the keys differ. `UNII_PUBCHEM` is applied first, as the build applies it, and `UNII_CAS` is then
layered on top to show what adding it would change.

For each pair that joins two existing cliques, the script also compares the InChIKey the UNII
record states with the one the joined clique carries. That is the quality check: where FDA gives a
structure, a correct link lands on a clique with that structure.

The script is a model, not a rebuild. It starts from the build's typed cliques, so it cannot see
the post-glom MolecularMixture split (#83), and it misses keys that `write_compendium()` drops from
Drug and Food cliques. The next build's clique diff is the check on it.

The output in [`output/`](./output/) comes from the 4 Aug 2026 records file
(`UNII_Records_4Aug2026.txt`) against the 2026jul22 build:

- `summary.json`: every figure below.
- `joining-pairs.tsv`: each pair that joins two cliques, with both cliques' names, types and the
  InChIKey verdict.
- `merged-groups.tsv`: the merged groups under `UNII_PUBCHEM`.
- `refused-pairs.tsv`: the pairs glom would refuse on InChIKey.

To regenerate:

```bash
uv run python docs/sources/UNII/records-xrefs/scripts/measure_unii_records_xrefs.py \
    --records babel_downloads/UNII/Latest_UNII_Records.txt \
    --build-url <published build root> --build-name <build> \
    --output-dir docs/sources/UNII/records-xrefs/output
```

## Results on 2026jul22

| | `UNII_PUBCHEM` (used) | `UNII_CAS` (not used) |
|---|---|---|
| Rows written | 126,503 | 129,367 |
| … after `remove_overused_xrefs()` | 126,316 | 128,981 |
| Already in one clique | 115,623 | 114,565 |
| Join two existing cliques | 4,741 | 2,065 |
| Add a CURIE that was in no clique | 3,624 | 6,142 |
| Refused on InChIKey | 2,299 | 5,198 |

Of the joining pairs whose UNII record states an InChIKey:

| Joined clique's InChIKey | `UNII_PUBCHEM` | `UNII_CAS` |
|---|---|---|
| The same | 3,762 | 429 |
| Same skeleton, different stereo or protonation | 66 | 593 |
| Different skeleton | 27 | 23 |

### Why `UNII_PUBCHEM` ships

- **It is right almost every time it can be checked.** In 3,762 of 3,855 checkable joins the
  clique already carries the structure FDA gives. Most of these are UNIIs that UniChem's FDA source
  has not linked yet, sitting in a `ChemicalEntity` clique of their own beside the `SmallMolecule`
  clique for their structure.
- **The 27 different-skeleton joins are mostly salts, hydrates and tautomers.** The two records draw
  the same substance with different counterions or waters, which changes the InChIKey's first
  block: `UNII:DZ74H2AHA7` "MORPHINE PHTHALATE PENTAHYDRATE", `UNII:ZS69RE9S4G` "CEFMINOX SODIUM
  HEPTAHYDRATE". About two are FDA errors: `UNII:J4D4KL8LKM` "2,6-DIMETHYL-1,4-DIOXANE, TRANS-"
  names a CID for an unrelated chloro-methoxy compound.
- **The 883 joins that can't be checked by structure are the ones this was for**: 425 proteins, 364
  mixtures and 36 nucleic acids, among them rabbit insulin. A sample of them matches by name
  ("APATORSEN SODIUM", "UROCORTIN-2", "TERLIPRESSIN ACETATE").
- **No join chains more than three cliques together.** 4,737 merged groups are two cliques and two
  are three, so a wrong CID costs one merge rather than a cascade.

### Why `UNII_CAS` doesn't

- **It joins the wrong stereoisomer more often than the right one.** Where the UNII states a
  structure, 593 of its 1,045 checkable joins land on a clique with a different stereo or
  protonation state, against 429 on the same one. A CAS number is often stereo-unspecified, and
  PubChem attaches CAS numbers to records loosely.
- **Its joins without a stated structure are worse still.** Examples include `UNII:1FHM3D7Z49`
  "TELITACICEPT" with a tetra-iodophenyl porphyrin and "BUTANOL (MIXED ISOMERS)" with butyl alcohol.
- **It gains nothing for #1171.** Beef insulin's `UNII:576O9IZ534 → CAS:11070-73-8` is refused on
  InChIKey: the beef clique carries human insulin zinc's key through `CHEBI:228608` and
  `PUBCHEM.COMPOUND:24839622`.

### Why polymers are skipped

PubChem represents a polymer by its monomers or repeat unit, so `UNII:58QVG85GW3` "POLYVINYL
ACETATE PHTHALATE" names `PUBCHEM.COMPOUND:161821` "Ethenyl acetate;phthalic acid". These are the
"polymer → monomer" links that `babel-inchikey-audit` flags. The skip removes 133 pairs that would
have joined two cliques (`UNII_SUBSTANCE_TYPES_WITHOUT_XREFS` in `chemicals.py`).

### #1171's insulins

With `UNII_PUBCHEM`, rabbit insulin's UNII and CID share a clique, and pork's still do (they already
did in 2026jul22). Beef's don't: the records file gives `UNII:576O9IZ534` no CID, and its CAS link
is refused as above.
