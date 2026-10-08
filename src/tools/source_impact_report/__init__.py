"""Report what adding one data source does to Babel's cliques.

A thin CLI (:mod:`src.tools.source_impact_report.cli`) over library code in ``src/``:
:mod:`src.model.source` discovers where a source contributes, :mod:`src.model.glom_diff`
diffs the cliques of a re-glom with and without it, and :mod:`src.reports.source_impact`
renders the result. The CLI itself only parses arguments and owns ``PIPELINE_CONFIG``, the
registry mapping each Babel pipeline to its clique-computation helper.

See ``docs/tools/SourceImpactReport.md``.
"""
