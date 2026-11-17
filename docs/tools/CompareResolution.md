# Compare resolution

```bash
uv run babel-compare-resolution <CURIE> [...] [--name NAME] [--target dev] [--same A,B] [--different A,B]
```

Answers: **how do these CURIEs normalize on each NodeNorm deployment, and why are they separate?**

It is the first step in answering a report that two results "are the same thing", such as a
duplicate drug in ARAX or the Translator UI. The workflow it serves is in
[`docs/issues/AGENTS.md`](../issues/AGENTS.md).

For each `--target` (default `dev`; also `exp`, `ci`, `test`, `prod`) it:

- reads the deployment's Babel version from `/status`;
- normalizes every CURIE with and without DrugChemical conflation;
- tabulates each CURIE's clique: its leader, label, Biolink type and size, its `INCHIKEY` members,
  and its members with the prefixes in `--show-prefix` (default `GTOPDB`, `MESH`, `DRUGBANK`);
- says how each pair of separate cliques' InChIKeys relate (`classify_inchikey_pair()` in
  [`src/model/inchikeys.py`](../../src/model/inchikeys.py)). A pair that shares neither a
  skeleton nor a label is left out, so several drugs can be compared at once;
- lists any identifier that is a member of more than one of the cliques. Two compendia both claim
  such an identifier, which is #308's signature for UMLS CUIs typed T116;
- lists any CURIE whose clique differs between deployments.

It ends with a [Babel Explorer](https://translatorsri.github.io/babel-explorer/) link comparing the
same CURIEs across the same deployments, and a draft `babel_tests` block. `--same A,B` groups become
`ResolvesWith`, `--different A,B` groups become `DoesNotResolveWith`, and every CURIE that resolves
somewhere gets a `Resolves` guard. The draft is a starting point. Edit it to assert what the fix
should produce, then check it with babel-validation before it goes in an issue.

## Usage

```bash
# The ruxolitinib pair from RTXteam/RTX#2952 on dev and test
uv run babel-compare-resolution CHEBI:66919 CHEBI:91405 GTOPDB:5688 --target dev --target test

# Every NameRes hit labelled pregabalin or milnacipran, written to a file
uv run babel-compare-resolution --name pregabalin --name milnacipran --out data/feedback-1438/compare.md

# Draft tests: the ligand should join the drug; the stereo-less record should stay apart
uv run babel-compare-resolution --same GTOPDB:5688,CHEBI:66919 --different CHEBI:66919,CHEBI:91405
```

`--name` adds every NameRes hit whose label is the name, ignoring case and punctuation. These are
the "same name, separate result" nodes that a duplicate report describes. NameRes indexes the
DrugChemical-conflated cliques, so two hits there are separate even with conflation on. A hit that
only contains the name ("ruxolitinib phosphate") is a different substance and is left out.

A deployment that can't be reached is reported as unreachable, and the rest of the report is still
written.

## Reading the relations

| Relation | Usually means | Tracked in |
|---|---|---|
| same skeleton; one has no stereo layer | A stereo-unspecified record beside the drug, or a racemate beside an enantiomer. It can also be an isotope-labelled form, which the key can't distinguish. | #1232 |
| same skeleton; different stereo layers | Different stereoisomers (dexamethasone and betamethasone), or two sources disagreeing on the drug's structure | #1208 |
| same structure, different protonation | A charge state | #1214 (ChemicalParent conflation) |
| different skeleton | A salt, hydrate, tautomer or a different compound | #1214, #1208 |
| at least one has no InChIKey | A structure-less record: a biologic, a UMLS or MeSH concept, or a product | #1209, #308 |

The relation narrows the cause; it doesn't decide it. Before filing, check each source's own
record, and whether the "duplicate" is really a different thing: a class and its member, a billing
code, a combination product. [`docs/issues/AGENTS.md`](../issues/AGENTS.md) has the full taxonomy.

## Where the code lives

- [`src/utils/translator_services.py`](../../src/utils/translator_services.py) holds the NodeNorm
  and NameRes clients, the deployment URLs and the Babel Explorer link builder.
- [`src/reports/normalization_comparison.py`](../../src/reports/normalization_comparison.py) builds
  and renders the comparison. It does no network access.
- [`src/tools/compare_resolution/cli.py`](../../src/tools/compare_resolution/cli.py) holds the
  argument parsing and fetching.
