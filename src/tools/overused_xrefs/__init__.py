"""``babel-overused-xrefs`` — audit one concord file for xref targets claimed by many subjects.

The analysis lives in :mod:`src.model.concords` (and the label loading in
:mod:`src.reports.source_impact`), so a pipeline rule or another tool can reuse it; ``cli.py``
is argparse and CSV writing over the top. See ``docs/tools/OverusedXrefs.md``.
"""
