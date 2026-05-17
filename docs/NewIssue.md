# Filing a Babel Issue

This guide explains how to file a useful issue — whether you spotted a problem in the Babel output
files, through the [Node Normalizer], or through the [Name Resolver].

## Where to file

- **Clique content** (wrong identifiers, wrong Biolink type, wrong preferred label, missing
  synonyms, bad descriptions): file here in the [Babel issue tracker].
- **Node Normalizer application** (unexpected errors, API misbehaviour, issues specific to
  the web service): file in the [Node Normalizer issue tracker].
- **Name Resolver application** (unexpected errors, search results ranked incorrectly, issues
  specific to the web service): file in the [Name Resolver issue tracker].

If you are not sure, file in the [Babel issue tracker] and we will sort it out.

## What to include

A good issue report makes it easy for us to reproduce and fix the problem quickly. Please include:

- The identifiers or concept names that are behaving incorrectly, ideally as a table or
  TSV/CSV attachment.
- What you expected Babel to return and what it actually returned.
- Which frontend you noticed the problem in: [Node Normalizer], [Name Resolver], or direct
  inspection of Babel output files.
- Any additional context that will help replicate the problem, such as which Babel build or
  release you are using.

## Filling in the project fields

When you file an issue in the [Babel sprints GitHub project], three fields help us understand
how urgently it needs to be addressed. Fill them in if you can; developers will review them
during triage and adjust if needed.

### Priority

How urgent is this to fix?

| Value | Meaning |
|-------|---------|
| **Critical** | Causes outright failures or produces seriously wrong results that are actively misleading downstream users right now. |
| **High** | Significantly degrades the quality or usability of Babel outputs, but a workaround exists. |
| **Medium** | A noticeable quality problem, but not one that breaks workflows. |
| **Low** | A minor issue or a nice-to-have improvement. |

### Impact

How beneficial will fixing this issue be to Babel users?

| Value | Meaning |
|-------|---------|
| **Enormous** | Will significantly improve clique or output quality, or will make future development substantially easier. |
| **High** | Will provide a large benefit to users or developers. |
| **Medium** | Will provide a moderate benefit to users or developers. |
| **Low** | Will provide a small benefit to users or developers. |

### Size

How much effort do you think this fix will require? (Developers may adjust this estimate.)

| Value | Approximate effort |
|-------|--------------------|
| **XS** | Trivial change — a configuration tweak or a one-line fix. |
| **S** | Small — a few hours of focused work. |
| **M** | Medium — up to a day or two of work. |
| **L** | Large — requires investigation and several days of implementation. |
| **XL** | Extra large — a substantial piece of work that may span multiple sprints. |

## Grouping related issues

If your issue looks like it may be caused by the same underlying bug as an existing issue, set the
**Parent issue** field to that issue. This helps developers see patterns and fix related issues
together.

You can also set the **Component** field to identify which part of Babel is affected:

| Component | What it covers |
|-----------|----------------|
| Process | The overall pipeline for running Babel |
| Cliques and identifiers | What identifiers are or are not in a clique |
| Downloaders | Code that downloads source data |
| Metadata | Information content, taxon, or other metadata stored on nodes |
| Biolink types | How Biolink semantic types are assigned to cliques |
| Conflations | GeneProtein and DrugChemical conflation |
| Preferred labels | How preferred labels are chosen |
| Synonyms | Which synonyms are included |
| New data sources | Requests to add a new data source |
| Validation and reports | Validating Babel output or producing a report |
| Documentation | Improving or fixing Babel documentation |
| NodeNorm | [Node Normalizer] frontend |
| NameRes | [Name Resolver] frontend |

## Tracking when your issue will be addressed

Babel development is organized into two-week **sprints** using the
[Babel sprints GitHub project]. You can use the project board to see:

- **Backlog** — issues that have been triaged and are waiting to be scheduled.
- **Ready** — issues that are queued for the current or next sprint.
- **In progress** — issues being actively worked on right now.
- **Needs review** — issues with a pull request awaiting review.
- **Done** — issues completed in recent sprints.

In general, a **Critical + Enormous** issue will be scheduled very quickly, while a **Low + Low**
issue may sit in the backlog for a long time. To estimate when your issue is likely to be
addressed, look at how many **Critical** and **High** priority issues are currently in the backlog
ahead of yours.

[Babel issue tracker]: https://github.com/NCATSTranslator/Babel/issues/
[Node Normalizer issue tracker]: https://github.com/NCATSTranslator/NodeNormalization/issues/
[Name Resolver issue tracker]: https://github.com/NCATSTranslator/NameResolution/issues/
[Babel sprints GitHub project]: https://github.com/orgs/NCATSTranslator/projects/36
[Name Resolver]: https://github.com/NCATSTranslator/NameResolution
[Node Normalizer]: https://github.com/NCATSTranslator/NodeNormalization
