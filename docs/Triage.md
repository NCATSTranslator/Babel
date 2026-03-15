# Babel Issue Triage

This document describes how issues in the [Babel issue tracker] are triaged and prioritized using
the [Babel sprints GitHub project]. It is written for two audiences:

- **Part 1: For users of Babel outputs** — how to file a useful bug report, how to assign
  priority, impact and size when you file an issue, and how to read the project board to estimate
  when your issue is likely to be addressed.
- **Part 2: For Babel developers** — how to triage incoming issues, how to add automated tests,
  and how to select issues for the next sprint.

---

## Part 1: Reporting and tracking issues (for users)

### Filing a bug report

Before filing an issue, check whether a similar issue already exists in the
[Babel issue tracker]. If it does, you can add a comment with additional examples or "+1" the
issue to signal that it affects you too. You can also add your issue as a sub-issue of an existing
issue if the same underlying bug seems to be the cause.

When filing a new issue, please include:

- The identifiers or concept names that are behaving incorrectly (ideally as a table or TSV/CSV
  attachment).
- What you expected Babel to return and what it actually returned.
- Which frontend you noticed the problem in: [Node Normalizer], [Name Resolver], or direct
  inspection of Babel output files.
- Any additional context that will help replicate the problem.

### Assigning priority, impact and size

When you file an issue, please fill in three fields in the [Babel sprints GitHub project] to
help us understand how urgently it needs to be addressed. If you are unsure about any of these,
please leave them blank. Developers will fill them in during triage.

#### Priority

How urgent is this to fix?

| Value        | Meaning                                                                                                               |
|--------------|-----------------------------------------------------------------------------------------------------------------------|
| **Critical** | Causes outright failures or produces seriously wrong results that are actively misleading downstream users right now. |
| **High**     | Significantly degrades the quality or usability of Babel outputs, but a workaround exists.                            |
| **Medium**   | A noticeable quality problem, but not one that breaks workflows.                                                      |
| **Low**      | A minor issue or a nice-to-have improvement.                                                                          |

#### Impact

How beneficial will fixing this issue be to Babel users?

| Value        | Meaning                                                                                                    |
|--------------|------------------------------------------------------------------------------------------------------------|
| **Enormous** | Will significantly improve clique or output quality, or will make future development substantially easier. |
| **High**     | Will provide a large benefit to users or developers.                                                       |
| **Medium**   | Will provide a moderate benefit to users or developers.                                                    |
| **Low**      | Will provide a small benefit to users or developers.                                                       |

#### Size

How much effort do you think this fix will require? (This is an estimate; developers may adjust it.)

| Value  | Approximate effort                                                        |
|--------|---------------------------------------------------------------------------|
| **XS** | Trivial change — a configuration tweak or a one-line fix.                 |
| **S**  | Small — a few hours of focused work.                                      |
| **M**  | Medium — up to a day or two of work.                                      |
| **L**  | Large — requires investigation and several days of implementation.        |
| **XL** | Extra large — a substantial piece of work that may span multiple sprints. |

### Grouping related issues

If your issue looks like it may be caused by the same underlying bug as an existing issue, you
can set the **Parent issue** field to that issue. This helps developers see patterns and fix
related issues together.

You can also set the **Component** property to identify which part of Babel is affected:

| Component               | What it covers                                                |
|-------------------------|---------------------------------------------------------------|
| Process                 | The overall pipeline for running Babel                        |
| Cliques and identifiers | What identifiers are or are not in a clique                   |
| Downloaders             | Code that downloads source data                               |
| Metadata                | Information content, taxon, or other metadata stored on nodes |
| Biolink types           | How Biolink semantic types are assigned to cliques            |
| Conflations             | GeneProtein and DrugChemical conflation                       |
| Preferred labels        | How preferred labels are chosen                               |
| Synonyms                | Which synonyms are included                                   |
| New data sources        | Requests to add a new data source                             |
| Validation and reports  | Validating Babel output or producing a report                 |
| Documentation           | Improving or fixing Babel documentation                       |
| NodeNorm                | [Node Normalizer] frontend                                    |
| NameRes                 | [Name Resolver] frontend                                      |

### Tracking when your issue will be addressed

Babel development is organized into two-week **sprints** using the
[Babel sprints GitHub project]. You can use the project board to see:

- **Backlog** — issues that have been triaged and are waiting to be scheduled.
- **Ready** — issues that are queued for the current or next sprint.
- **In progress** — issues being actively worked on right now.
- **Needs review** — issues with a pull request awaiting review.
- **Done** — issues completed in recent sprints.

At the start of each sprint, leftover items from the previous sprint are carried forward, and
then the highest-priority issues from the backlog are added. If an issue is unexpectedly large
or is displaced by a higher-priority item, it may be deferred to a later sprint. In general, a
**Critical + Enormous** issue will be scheduled very quickly, while a **Low + Low** issue may
sit in the backlog for a long time.

To estimate when your issue is likely to be addressed, look at how many **Critical** and **High**
priority issues are currently in the backlog ahead of yours. Issues are typically ordered by
priority first and then impact.

---

## Part 2: Triage guide (for developers)

### Triage checklist

When a new issue arrives, work through the following steps:

1. **Reproduce or understand the report.** Read the issue carefully. Can the problem be confirmed
   from the description? If not, ask the reporter for more information (e.g. which Babel build
   they are using, example identifiers).

2. **Check for duplicates.** Search for existing issues that describe the same problem. If a
   duplicate exists, close the new issue with a reference to the original (or add the new issue
   as a sub-issue of the original).

3. **Set Priority, Impact and Size.** If the reporter has filled these in, review them and adjust
   if necessary. If they are blank, set them now based on your assessment. Don't be shy about
   changing them in the future if necessary.

4. **Set the Component field.** Choose the appropriate **Component** value (see table above)
   if that would be useful. This can help group together related issues and for filtering during
   sprint planning.

5. **Link to a parent issue.** If this issue is one instance of a broader known problem (e.g. a
   deprecated identifier source, or a class of missing cliques), set the **Parent issue** field.

6. **Set Status to Backlog.** Unless the issue is Critical and needs immediate scheduling, move
   it to the **Backlog** column.

7. **Add an automated test.** See the next section for how to embed tests directly in the issue
   description.

### Adding automated tests to issues

The [babel-validation] project can run automated checks against live NodeNorm and NameRes
instances that are triggered by issues. You can embed tests directly in issue descriptions or
comments using two syntaxes.

#### Wiki syntax (single assertion)

```text
{{BabelTest|AssertionType|param1|param2|...}}
```

For example, to assert that two CURIEs resolve to the same clique:

```text
{{BabelTest|ResolvesWith|MESH:D014867|DRUGBANK:DB09145}}
```

#### YAML syntax (multiple assertions)

Use a fenced code block with the language tag `yaml` and a top-level property `babel_tests`:

````text
This can be inserted anywhere in the issue.

```yaml
babel_tests:
  ResolvesWith:
    - ['MESH:D014867', 'DRUGBANK:DB09145']
  HasLabel:
    - ['MESH:D014867', 'Water']
```

Having text after the fenced code block (or multiple code blocks) is fine too.
````

#### Available assertion types

You can see an up-to-date list of supported assertions [in the Babel Validation repository](https://github.com/TranslatorSRI/babel-validation/blob/3eeeccfb0d15451e45ecade7603404e096b30fb0/src/babel_validation/assertions/README.md).

<!-- TODO: replace with the actual URL once https://github.com/TranslatorSRI/babel-validation/pull/67 has been merged. -->

**NodeNorm assertions:**

| Assertion            | What it tests                                                                 |
|----------------------|-------------------------------------------------------------------------------|
| `Resolves`           | Each CURIE returns a non-null result from NodeNorm.                           |
| `DoesNotResolve`     | Each CURIE intentionally fails to normalize.                                  |
| `ResolvesWith`       | Two or more CURIEs normalize to identical results.                            |
| `DoesNotResolveWith` | Two or more CURIEs do NOT resolve to the same entity.                         |
| `HasLabel`           | A CURIE's primary label exactly matches the expected string (case-sensitive). |
| `ResolvesWithType`   | CURIEs resolve with a specified Biolink semantic type.                        |

**NameRes assertions:**

| Assertion      | What it tests                                                                       |
|----------------|-------------------------------------------------------------------------------------|
| `SearchByName` | A CURIE appears in the top N NameRes results for a given text string (default N=5). |

**Special:**

| Assertion | Meaning                                                                          |
|-----------|----------------------------------------------------------------------------------|
| `Needed`  | Placeholder marking that a test needs to be written. Always fails as a reminder. |

When adding tests to an issue, use `{{BabelTest|Needed}}` as a placeholder if you know a test
is needed but do not yet know the exact expected values.

### Sprint planning

Sprints are two weeks long. At the start of each sprint:

1. **Carry over unfinished items.** Any issues still **In progress** or **Ready** that were not
   completed automatically move to the next sprint.

2. **Review the backlog.** Sort the backlog by Priority (descending) then Impact (descending).
   Consider Size to avoid overloading a sprint — a sprint full of XL issues will not complete on
   time.

3. **Select issues for the sprint.** Choose the highest-priority issues that together represent a
   realistic amount of work for two weeks. Move selected issues to **Ready**.

4. **Adjust if needed.** An issue may be removed from the current sprint mid-sprint if it turns
   out to be much larger than estimated, or if a Critical issue arrives that must take precedence.
   In either case, the deferred issue should be the first candidate for the next sprint.

#### Heuristics for issue selection

- Prefer **Critical** issues regardless of impact.
- Among **High** and **Medium** priority issues, prefer those with **Enormous** or **High** impact.
- Prefer **XS** and **S** issues when a sprint already contains several large items — clearing
  small issues reduces backlog pressure.
- Issues with automated tests (see above) are easier to verify once fixed; prefer these when all
  else is equal.
- Group issues sharing the same **Parent issue** or **Component** — fixing a class of bugs together
  is more efficient than fixing them one at a time across different sprints.

[Babel issue tracker]: https://github.com/NCATSTranslator/Babel/issues/
[Babel sprints GitHub project]: https://github.com/orgs/NCATSTranslator/projects/36
[babel-validation]: https://github.com/TranslatorSRI/babel-validation
[Name Resolver]: https://github.com/NCATSTranslator/NameResolution
[Node Normalizer]: https://github.com/NCATSTranslator/NodeNormalization
