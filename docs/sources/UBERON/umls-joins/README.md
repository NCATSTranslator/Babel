# Joining UBERON to UMLS

Many anatomical concepts used to ship as two anatomy cliques: one led by an UBERON term, and one
holding only UMLS (often a SNOMED CT "Entire X" concept, or a concept whose only anatomy source is
FMA). For example, [`UBERON:0000395`](http://purl.obolibrary.org/obo/UBERON_0000395) "cochlear
ganglion" and `UMLS:C1289388` "Entire spiral ganglion" were separate even though UBERON
cross-references that concept's SNOMED code. This page records how the anatomy pipeline joins them,
how the joins were reviewed, what that does to the compendia, and what was considered and rejected.

## What the pipeline does

### SNOMED CT: rename UBERON's SCTID xrefs

UBERON writes SNOMED CT xrefs as `SCTID:` (about 4,100 of them) while the UMLS concord writes
`SNOMEDCT:`, so none of UBERON's SNOMED xrefs could join a UMLS concept.
`config.yaml: anatomy_xref_prefixes` renames them, the same mechanism the disease pipeline uses
(see [`../../CLAUDE.md`](../../CLAUDE.md), "A missing prefix rename is the same bug, spelled
differently").

### FMA: use UBERON's FMA xrefs

`ANATOMY_OBO_IGNORE_LIST` drops FMA because CL uses FMA xrefs to mean "part of". CL terms are never
written from the UBERON root, though, and CL now comes from Wikidata, so `UBERON_OBO_IGNORE_LIST`
keeps UBERON's FMA xrefs (about 6,100). They are the only bridge to the many UMLS concepts whose
only anatomy source is FMA. GO and EMAPA keep the shared list; their FMA xrefs have not been
reviewed.

The anatomy UMLS concord maps a concept's FMA atoms but not its UWDA atoms
(`anatomy.ANATOMY_UMLS_SOURCES`), even though UWDA codes are FMA numbers, and skips obsolete atoms.
So a UMLS concept whose only FMA-numbered atom is from UWDA, or is obsolete, is not joined by
UBERON's FMA xref.

### FMA as an extra prefix for gross anatomy

Biolink registers FMA for `biolink:AnatomicalEntity` but not `biolink:GrossAnatomicalStructure`, so
`write_compendium()` drops an FMA CURIE from any clique typed gross anatomy. Joining UBERON to UMLS
moves thousands of UMLS+FMA cliques into UBERON gross anatomy cliques:
`GrossAnatomicalStructure.txt` now holds 5,079 FMA CURIEs, 3,023 of which main ships today, and all
of them would be dropped without `config.yaml: anatomy_extra_prefixes_by_biolink_class`, which ships
FMA as a temporary extra prefix. It is removed once
[biolink/biolink-model#1827](https://github.com/biolink/biolink-model/issues/1827) is released
([#1134](https://github.com/NCATSTranslator/Babel/issues/1134)).

### Wrong xrefs dropped

`input_data/anatomy_badxrefs.txt` drops 26 pairs that the new joins exposed, each with its reason:

- four single wrong UBERON xrefs found in the clique diff:
  [`UBERON:0012456`](http://purl.obolibrary.org/obo/UBERON_0012456) "Merkel nerve ending" →
  `MESH:D018862` "Merkel Cells" (already merged the nerve ending with
  [`CL:0000242`](http://purl.obolibrary.org/obo/CL_0000242) "Merkel cell" on main),
  [`UBERON:0008883`](http://purl.obolibrary.org/obo/UBERON_0008883) "osteoid" → `FMA:66830`
  "Bone matrix",
  [`UBERON:0003691`](http://purl.obolibrary.org/obo/UBERON_0003691) "epidural space" →
  `FMA:71228` "Cranial epidural space", and
  [`UBERON:0002464`](http://purl.obolibrary.org/obo/UBERON_0002464) "nerve trunk" →
  `SNOMEDCT:281248001` "Structure of nervous system of trunk";
- 21 found by reviewing the SNOMED joins (next section);
- [`UBERON:0010168`](http://purl.obolibrary.org/obo/UBERON_0010168) "collection of eyelashes" →
  `MESH:D002923` "Cilia", the cell organelle (*cilia* is Latin for eyelashes). This predates the
  change: a main build from the same downloads already merges the eyelashes with MeSH "Cilia",
  `NCIT:C32318` "Cilium" and `FMA:67181`, and the review below surfaced it.

### Reviewing the SNOMED joins

An UBERON SNOMED xref joins the UBERON term to whichever UMLS concept holds that SNOMED code. That
is right when the concept is the same thing, and wrong in two shapes, which
`anatomy.find_uberon_snomed_xrefs_to_review()` flags:

- **The UMLS concept lumps several SNOMED codes.** UMLS files "Structure of dentition" under its
  "Tooth" concept, so [`UBERON:0003672`](http://purl.obolibrary.org/obo/UBERON_0003672)
  "dentition" joined [`UBERON:0001091`](http://purl.obolibrary.org/obo/UBERON_0001091) "calcareous
  tooth". This is the shape that made SNOMED's structure/entire relationship unusable (below), and
  it can hit a direct xref just as well.
- **The UBERON term reaches several UMLS concepts.** A term with more than one SNOMED xref (77 of
  them, listed in [`multi-snomed-xrefs.csv`](./multi-snomed-xrefs.csv)), or one whose SNOMED code
  sits in two concepts, merges them all. That is right for synonyms and for SNOMED's own
  structure/entire pairs, and wrong when one is narrower:
  [`UBERON:0011877`](http://purl.obolibrary.org/obo/UBERON_0011877) "margin of tongue" xrefs only
  the left and the right margin.

Every flagged xref was reviewed. Where UMLS lumps the code, the pair dropped is the UMLS one, so the
code reaches only the UBERON term it names; seven such pairs, among them "Structure of lens vesicle"
inside "Optic vesicle" (the optic vesicle is
[`UBERON:0004128`](http://purl.obolibrary.org/obo/UBERON_0004128)) and "Structure of basement
membrane" inside "Basal lamina". Where the UBERON term xrefs a narrower or broader concept besides
its own, the UBERON xref is dropped; fourteen such pairs, among them "nerve" → "Entire peripheral
nerve", the phalanges of pedal digit 5 → the phalanges of "lesser toe" (any of toes 2-5), and
"urethral sphincter" → "Entire sphincter urethrae muscle" (the external sphincter only,
[`UBERON:0004919`](http://purl.obolibrary.org/obo/UBERON_0004919)). These xrefs are wrong upstream
too and are worth reporting to UBERON.

The 77 flagged xrefs that remain were judged correct or not clearly wrong, and are listed in
[`snomed-xref-review.csv`](./snomed-xref-review.csv) (from `scripts/snomed_xref_review.py`).
Five are open for a curator, because the two concepts are distinct in some anatomies and synonyms
in others: [`UBERON:0001075`](http://purl.obolibrary.org/obo/UBERON_0001075) "bony vertebral
centrum" (body vs. centrum of vertebra),
[`UBERON:0001282`](http://purl.obolibrary.org/obo/UBERON_0001282) "intralobular bile duct" (also
"Canal of Hering"), [`UBERON:0001414`](http://purl.obolibrary.org/obo/UBERON_0001414) "median
basilic vein" (also "median cubital vein"),
[`UBERON:0002374`](http://purl.obolibrary.org/obo/UBERON_0002374) "metacarpal bone" (also
"metacarpal of finger") and [`UBERON:0011124`](http://purl.obolibrary.org/obo/UBERON_0011124)
"xiphisternal joint" (both the symphysis and the synostosis).

`tests/pipeline/test_uberon_umls_joins.py` fails on any flagged xref that is in neither
`anatomy_badxrefs.txt` nor the CSV, so one added by a new UBERON or UMLS release is reviewed
rather than shipped unseen. To clear it, judge the new xrefs, drop the wrong ones, and regenerate
the CSV.

### UberGraph query filter

UberGraph infers every NCBITaxon class to be a subclass of
[`UBERON:0000465`](http://purl.obolibrary.org/obo/UBERON_0000465) "material anatomical entity", so
the unfiltered xref query from the UBERON root returned about 860,000 taxa and timed out.
`build_sets()` now filters descendents to the root's ontology in the query. This does not change
the concords; it only makes the anatomy build run.

## What it does to the compendia

A local anatomy build from the same downloads (UMLS 2026AA, UberGraph of 2026-11-18), compared with
`babel-clique-diff` against main plus only the UberGraph query filter. The summaries are in
[`clique-diff/`](./clique-diff/): `main-vs-branch` is the whole change, `main-vs-sctid` isolates
the SNOMED rename, and `sctid-vs-branch` isolates UBERON's FMA xrefs. The SNOMED-only build was
replayed from the full build's intermediates with UBERON's FMA xrefs removed; the other figures are
from `scripts/compare_builds.py`.

| | main | this change |
|---|---|---|
| UMLS CUIs in UBERON cliques | 3,534 | 10,204 |
| `AnatomicalEntity.txt` cliques | 147,548 | 140,893 |
| `GrossAnatomicalStructure.txt` cliques | 12,693 | 12,693 |
| `Cell.txt` cliques | 9,207 | 9,204 |
| `CellularComponent.txt` cliques | 9,470 | 9,458 |
| CURIEs dropped from every anatomy compendium | | 6 |

- **Merges are small.** 4,201 cliques merge two main cliques, 1,249 merge three, and 11 merge four
  or five. Almost all of the larger ones are an UBERON term with several UMLS synonyms, e.g.
  [`UBERON:0005351`](http://purl.obolibrary.org/obo/UBERON_0005351) "paraflocculus" or
  [`UBERON:0016925`](http://purl.obolibrary.org/obo/UBERON_0016925) "juxtaductal region of aortic
  arch".
- **Retyping is expected.** 5,065 main cliques that hold a UMLS CUI but no UBERON term move from
  `AnatomicalEntity.txt` to `GrossAnatomicalStructure.txt` because they now carry UBERON's type. 16
  more move between anatomy and `Cell.txt`/`CellularComponent.txt`, mostly UMLS concepts that UMLS
  types as "Cell Component" (brain nuclei, nerve endings) joining their UBERON term.
- **Six CURIEs are dropped**, all because a correct change moved them into a clique whose type
  Biolink does not register their prefix for: `FMA:62977` joins
  [`GO:0043209`](http://purl.obolibrary.org/obo/GO_0043209) "myelin sheath", `FMA:67181` "Cilium"
  leaves the eyelash clique for the `CellularComponent.txt` clique of MeSH "Cilia" once the eyelash
  xref is dropped, and four `SNOMEDCT:` CURIEs leave `Cell.txt`/`CellularComponent.txt` as their
  UMLS concepts join UBERON structures.
- **13 UMLS CUIs move from one UBERON term to another**, often to a more specific one, e.g. "Medulla
  segment of fasciculus gracilis" to
  [`UBERON:0002653`](http://purl.obolibrary.org/obo/UBERON_0002653) "gracile fasciculus of medulla".
- **No identifier lands in two compendia.** Of the CURIEs this change newly ships in anatomy (2,166
  FMA, 1 SNOMEDCT), none is in a non-anatomy compendium of the 2026jul22 release. 174 anatomy CURIEs
  are (157 MeSH, 10 UMLS, 6 NCIt and 1 SNOMEDCT, in Disease), the same 174 on main and on this
  branch, so they predate it.

### How many missed joins this fixes

`scripts/missed_umls_links.py` finds likely-missed joins lexically: a main clique holding a UMLS CUI
but no UBERON term, whose UMLS strings match exactly one UBERON label or exact synonym in a
different clique. It is a heuristic for measuring recall, not a mapping, and it misses many. A
candidate's bridge is counted only if the build can use it: codes are read with the build's own
source map and obsolete-atom filter. On main it finds 8,903 candidates:

| Bridge between the pair | Candidates | Joined by the SNOMED rename | Joined by this change |
|---|---|---|---|
| UBERON's SNOMED xref is the CUI's SNOMED code | 2,731 | 2,729 | 2,729 |
| UBERON's FMA xref is the CUI's FMA code | 2,959 | 0 | 2,943 |
| both | 251 | 251 | 251 |
| neither | 2,962 | 0 | 0 |
| **total** | **8,903** | **2,980** | **5,923** |

[`missed-umls-links-sample.csv`](./missed-umls-links-sample.csv) is a sample spread across these
groups. The full per-candidate list is regenerated to `data/uberon-umls/missed-umls-links.csv`.

The 16 FMA-bridged candidates that do not join are blocked on purpose: in 11 the FMA code is shared
by two UMLS concepts or two UBERON terms, so `remove_overused_xrefs()` drops it; in 4 the UMLS
concept joins a different UBERON term and anatomy keeps one UBERON term per clique; and one is the
dropped epidural-space xref.

Of the 2,962 with neither bridge, 2,136 are SNOMED CUIs where UBERON has no SNOMED xref, points at
the other half of SNOMED's structure/entire pair (below), or matches only an obsolete atom; 223 are
FMA concepts UBERON does not xref; 2 have only a UWDA atom; 185 come only from sources such as
LOINC, ICF or the veterinary SNOMED edition; and 416 are other UMLS-only concepts.

## Rejected: linking SNOMED "structure" and "entire" concepts

SNOMED CT models anatomy as Structure/Entire/Part triples: "X structure" means X *or any part of X*,
"Entire X" means the whole. UMLS keeps them as separate CUIs, and SNOMED links them with
`has_entire_anatomy_structure`. Using that relationship as an equivalence would join many more
pairs, and was tried and rejected:

- UBERON intends its SNOMED xrefs to point at the Entire concept, because the UBERON class is the
  entity and only Entire concepts can be made equivalent without incoherence
  ([obophenotype/uberon#3287](https://github.com/obophenotype/uberon/issues/3287)). Treating
  Structure as equivalent to Entire contradicts that.
- In a full build it produced wrong merges where a Structure atom sits in a broader UMLS CUI: UMLS
  files "Bone structure of knee joint region" under its general "Knee" CUI, so "Entire bone of knee
  joint region" joined [`UBERON:0001465`](http://purl.obolibrary.org/obo/UBERON_0001465) "knee".

Of UBERON's 4,118 SNOMED xrefs, 3,064 point at an Entire concept and 690 at a Structure concept.
[`sctid-structure-entire.csv`](./sctid-structure-entire.csv), from
`scripts/sctid_structure_entire.py`, proposes the Entire partner for each of the 690 (675 to
replace, 6 to remove because the term already xrefs the Entire concept, 9 for a curator). That list
is filed upstream as
[obophenotype/uberon#3786](https://github.com/obophenotype/uberon/issues/3786); once applied, the
SNOMED rename picks it up with no change here.

Following the 690 Structure xrefs directly does not reopen the rejected equivalence. Each joins
one UBERON term to the concept holding that one code, not every Entire concept to its Structure
partner, and a Structure code's UMLS concept is usually UMLS's main concept for the thing. Of the
687 (UBERON term, UMLS concept) pairs those xrefs join after the drops above, 535 are a concept that
also carries an FMA, MeSH or NCIt code, and 481 are joined anyway by another of the same term's
xrefs. The broader-CUI failure needs a lumped concept, which is the first shape the review above
flags; the lumps it found, such as dentition in "Tooth", are dropped.

## Also rejected: Wikidata UBERON↔UMLS mappings

Wikidata pairs UBERON IDs (P1554) with UMLS CUIs (P2892), the same source the pipeline uses for CL.
Filtered to one-to-one pairs it would add about 2,600 joins against the 2026jul22 release, but
nearly all of them are pairs the FMA xrefs already join; it added almost nothing for the pairs with
no bridge.

## Regenerating

From the repository root, after `uv run snakemake anatomy`, with a baseline build's compendia in
`<main compendia>` and, for the cross-compendium check, a published build's `duckdb/` export in
`<release duckdb>`:

```bash
uv run python docs/sources/UBERON/umls-joins/scripts/sctid_structure_entire.py
uv run python docs/sources/UBERON/umls-joins/scripts/snomed_xref_review.py
uv run python docs/sources/UBERON/umls-joins/scripts/missed_umls_links.py --before <main compendia> --after babel_outputs/compendia
uv run python docs/sources/UBERON/umls-joins/scripts/compare_builds.py --before <main compendia> --after babel_outputs/compendia --release-duckdb <release duckdb>
uv run babel-clique-diff --before <main compendia> --after babel_outputs/compendia --files AnatomicalEntity.txt GrossAnatomicalStructure.txt Cell.txt CellularComponent.txt --out-json main-vs-branch.summary.json --out-csv main-vs-branch.csv
```

Regenerate `snomed-xref-review.csv` only after judging any new rows it would add (see "Reviewing the
SNOMED joins"). The per-row clique-diff CSVs (2–3 MB each) are not committed; regenerate them with
the last command.
