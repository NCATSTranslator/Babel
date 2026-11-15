# GO's publication xrefs are citations, not equivalences

`processactivitypathway.build_process_obo_relationships()` builds `process/concords/GO` from
UberGraph's xrefs of GO's three roots. UberGraph serves a class-level `oboInOwl:hasDbXref` as an
xref, and a few GO classes carry the paper they were curated from that way. Every concord row
reaches `glom()` as an equivalence, so each such row asserted that a process *is* a paper.

| Build | Row |
|---|---|
| 2025dec11, 2026jul22, live UberGraph 2026-11-15 | [`GO:0052165`](http://purl.obolibrary.org/obo/GO_0052165) "symbiont-mediated perturbation of host phytoalexin production" → `PMID:28805743` |
| 2025dec11, 2026jul22, live UberGraph 2026-11-15 | [`GO:0180012`](http://purl.obolibrary.org/obo/GO_0180012) "co-transcriptional RNA 3'-end processing, cleavage and polyadenylation pathway" → `PMID:31499460` |
| 2025dec11 only | [`GO:0050212`](http://purl.obolibrary.org/obo/GO_0050212) "progesterone 11-alpha-monooxygenase activity" → `PMID:39766209` |

`GO_XREF_IGNORE_PREFIXES` (PMID, PMC, doi) is passed as the `ignore_list` of all three
`build_sets()` calls, so these are never written.

None of them merged anything. Each names a different paper, so no two GO terms shared one, and no
other process concord names a publication at all (the 2026jul22 `Concord.parquet`, in
[`../../publication-xrefs/`](../../publication-xrefs/README.md)). No process, activity or pathway
class registers a publication prefix, so `write_compendium()` dropped each PMID from its clique.

They are dropped anyway because the build now fails on any concord row pairing a publication with
anything else; see [`../../publication-xrefs/README.md`](../../publication-xrefs/README.md).

To list what live UberGraph serves:

```bash
uv run python -c '
from src.ubergraph import UberGraph
from src.util import Text
ug = UberGraph()
for root in ["GO:0007165", "GO:0008150", "GO:0003674"]:
    for go, xrefs in ug.get_subclasses_and_xrefs(root).items():
        for x in xrefs:
            if (Text.get_prefix_or_none(x) or "") in {"PMID", "PMC", "PMCID", "DOI"}:
                print(go, x, sep="\t")' | sort -u
```
