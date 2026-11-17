# Responding to normalization reports

How to answer a report that Babel's output is wrong for a particular identifier. These are reports
that two results are "the same thing", that one result is two things, or that a CURIE has the wrong
label or type. They come in through
[NCATSTranslator/Feedback](https://github.com/NCATSTranslator/Feedback/issues), the ARAX and other
reasoner trackers, NodeNormalization, and this repository. `docs/issues/CLAUDE.md` imports this
file, but nothing loads it automatically, because answering a report doesn't mean editing files
here. The root `AGENTS.md` points to it instead.

The worked example is the duplicate-drug reports of November 2026:

- reports: [RTXteam/RTX#2952](https://github.com/RTXteam/RTX/issues/2952), #1215 and
  [NCATSTranslator/Feedback#1438](https://github.com/NCATSTranslator/Feedback/issues/1438);
- the issues filed by cause: #1206, #1207, #1208, #1209 and #1232;
- the stopgap: PR #1211.

Read those threads for the shape of a complete answer.

## 1. Find out which build each deployment serves

A report names an environment ("on test", "in ARAX CI"), and each NodeNorm and NameRes deployment
serves one Babel build. Ask it, through its `/status`:

```bash
curl -s https://nodenorm-es.test.transltr.io/status | jq .babel_version
```

The deployments and their keys (`dev`, `exp`, `ci`, `test`, `prod`) are `NODENORM_INSTANCES` and
`NAMERES_INSTANCES` in
[`src/utils/translator_services.py`](../../src/utils/translator_services.py). They match
babel-validation's `tests/targets.ini` and the `target=` keys that Babel Explorer uses. A report
against an older build than dev may already be fixed: check before investigating.

## 2. Compare the CURIEs

```bash
uv run babel-compare-resolution <CURIEs from the report> --name <each drug name> --target dev --target test
```

[`docs/tools/CompareResolution.md`](../tools/CompareResolution.md) describes the output. It covers
what used to be done by hand:

- each CURIE's clique, with and without DrugChemical conflation;
- the same-named cliques that NameRes knows about;
- how each pair of separate cliques' InChIKeys relate;
- identifiers that two cliques share;
- a Babel Explorer link and a draft `babel_tests` block.

Put working files in a `data/<report>/` directory, as AGENTS.md says.

## 3. Find the cause

The relation the tool prints narrows the cause; confirming it takes the source data.

- **Go to each source's own record**, not to what Babel or UniChem made of it: the downloaded file
  in `babel_downloads/` (GtoPdb's `ligands.tsv`, which has an `InChIKey` column), or the source's
  API (PubChem's PUG REST, `/rest/pug/compound/cid/<cid>/property/InChIKey/JSON`). #1206 and
  #1207 were found this way. UniChem's key for a GtoPdb ligand or a PubChem CID differed from the
  source's own, and since cliques form on an exact InChIKey, the identifier left its drug.
- **"Why are these joined?"** is answered by the concords that fed the build:
  [babel-explorer](https://github.com/TranslatorSRI/babel-explorer)'s `xrefs` command.
  **"What did Babel decide?"** is answered by the build: NodeNorm, or the DuckDB `Edge` table,
  which can be queried in place over HTTP (see `docs/DataFormats.md`). Never answer the second
  from concords. AGENTS.md's Debugging section says why.
- **Check where the clique's label comes from.** A clique gets its preferred label from one member.
  In 2026jul22, a GtoPdb ligand in a stereo-unspecified clique lent it the drug's name, so a record
  nobody would otherwise have noticed showed up as a second copy of the drug.

### Causes seen so far

| What the tool shows | Cause | Tracked in |
|---|---|---|
| Same skeleton; one has no stereo layer | A stereo-unspecified record beside the stereo-specific drug. Babel keeps them apart on purpose; joining them is a conflation. | #1232 (rule 2 of #1173) |
| The same, and the drug's GtoPdb ID is in the stereo-less clique | UniChem's stereo-stripped GtoPdb structures | #1206 (fix: #1212) |
| A PubChem CID in a clique of its own, whose key differs from what PubChem publishes | UniChem's InChIKey for the CID is wrong | #1207 (fix: #1213) |
| Same skeleton, different stereo layers, with the drug's MeSH and RxNorm IDs split between the cliques | Two sources give the drug two different specified structures | #1208 |
| Same structure, different protonation; or a salt or hydrate | A charge state or a salt | #1173, #1214 (ChemicalParent conflation) |
| No InChIKey, with the same name across GtoPdb, ChEMBL and UNII | A biologic with no structure, unlinked across sources | #1209 |
| An identifier in two cliques, one typed `biolink:Protein` | A UMLS CUI typed T116 "Amino Acid, Peptide, or Protein", claimed by both Protein and a chemical compendium; NodeNorm serves one copy at random | #308 |

### Not duplicates

Say so in the reply, and guard them with `DoesNotResolveWith` so that no future fix merges them:

- a class and its member: ChEBI's class of erythromycins, and erythromycin A;
- an HCPCS procedure code ("INJECTION, AZITHROMYCIN, 500 MG ADMINISTERED") and the drug;
- an RxNorm combination product (omeprazole / sodium bicarbonate) and one of its ingredients;
- a racemate and an enantiomer that is a separate drug: omeprazole and esomeprazole (#559),
  citalopram and escitalopram;
- a PubChem deposit that really is another stereoisomer, whatever its depositor named it.

The racemate case also runs the other way. Milnacipran is sold as the racemate, so its
stereo-unspecified clique *is* the drug. #1232 records this so its conflation rule leaves it alone.

## 4. File one Babel issue per cause

- Search first, closed issues included. A match turns "file" into "comment on" or "reopen".
- Write one issue per cause, not one per report. A report usually holds several causes (RTX#2952
  held six), and one cause usually spans several reports (#1206 explains both RTX#2952 and
  Feedback#1438).
- When a broad issue turns out to hold a piece that can be scheduled on its own, split it into a
  sub-issue:
  `gh api -X POST repos/NCATSTranslator/Babel/issues/<parent>/sub_issues -F sub_issue_id=<id>`,
  where `<id>` is the new issue's numeric `id` from `gh api repos/NCATSTranslator/Babel/issues/<N>`,
  not its number. #1232 was split from #1173 this way.
- The Babel issue carries the BabelTests. babel-validation doesn't scan the Feedback or reasoner
  repositories, so tests placed there are never run.

## 5. Stopgap: manual DrugChemical rows

When the real fix is a code change for a later release, a row in
`input_data/manual_concords/drugchemical.tsv` can join two cliques under DrugChemical conflation in
the meantime (PR #1211).

- The file has **CRLF line endings**. Edit it in a way that keeps them: Python's text mode
  rewrites every line. Check that `git diff --stat` shows only the rows you meant to change.
- Every row needs a GitHub issue URL in its `url` column;
  `tests/createcompendia/test_drugchemical.py` fails without one. A temporary row cites the issue
  whose fix makes it redundant, and says so in its `notes`, so that one `grep` finds the set to
  delete. #1210 asks for a build report that flags redundant rows.
- A row only takes effect with `drug_chemical_conflate=true`. Say that in the reply, because a
  client that doesn't set the flag sees no change.
- Each CURIE in a row must resolve to a chemical-compendium clique, or the row is skipped
  (`_validate_and_apply_manual_concords()`). Check them on dev before adding the row.

## 6. Write BabelTests

AGENTS.md ("GitHub pull requests and issues") gives the basics and the assertion types;
[`docs/Triage.md`](../Triage.md#adding-automated-tests-to-issues) gives the syntax. What tripped us
up:

- **The harness reads issue bodies only.** A `babel_tests` block in a comment is never run.
- **It scans five repositories:** NCATSTranslator Babel, NodeNormalization and NameResolution, and
  TranslatorSRI babel-validation and babel-explorer.
- **It can't turn on conflation**, so a fix that only works as a conflation (a manual DrugChemical
  row, #1232, #1214) can't be tested yet. Say so with this exact sentence, so that every deferral
  can be found from that issue once it is fixed: "BabelTests can't cover this until
  TranslatorSRI/babel-validation#169 lets a test turn on conflation."
- **Counting:** a `ResolvesWith` list of three CURIEs counts as three assertions, so "9 failing out
  of 22" is per CURIE, not per list.
- **Assert what the fix should produce**, and add guards: `Resolves` for every CURIE, so that a
  failure can't hide a CURIE that stopped resolving altogether, and `DoesNotResolveWith` for each
  not-duplicate.
- **Run a block before relying on it.** Until babel-validation can be installed here (#1234), run it
  from a sibling checkout. It needs `GITHUB_TOKEN`:

  ```bash
  cd ../babel-validation
  GITHUB_TOKEN=$(gh auth token) uv run pytest tests/github_issues --target dev --issue 'NCATSTranslator/Babel#1206' -rxX
  ```

  An open issue should show as `XFAIL`, listing only the assertions its fix should change.
- **Someone else's issue:** never edit its text. With the maintainer's agreement, tests can be
  appended at the end of the body, below a `---` line, with a sentence naming who added them and
  linking the comment whose statements they check. #559 and #1165 are examples. Otherwise, offer
  the block in a comment for the author to add; #1215 is an example.

## 7. Reply to the reporter

- **Draft first.** Write each reply to `data/<report>/` and have a maintainer review it before it is
  posted. A reply speaks for the project.
- **Fully qualify every cross-repository reference.** In another repository a bare `#1211` means
  *that* repository's #1211, and in this one `Feedback#1438` doesn't link at all. Write
  `NCATSTranslator/Babel#1211` and `NCATSTranslator/Feedback#1438`. A qualified reference also puts
  the reply in the linked issue's timeline.
- **Give one row per drug:** what is going on, what changes in the next release (and whether that
  needs `drug_chemical_conflate=true`), and the issue tracking it. Link a Babel Explorer comparison
  for each row (`babel_explorer_url()`; TranslatorSRI/babel-explorer#76 tracks documenting the
  link format), so the reporter can see each deployment change as fixes roll out.
- **An interim reply is worth sending.** The linked issues and PRs change colour as they close and
  merge, which shows progress before there is time for a final report.
- **Write each paragraph on one line.** Don't hard-wrap GitHub text; AGENTS.md covers this.
