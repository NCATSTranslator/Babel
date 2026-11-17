"""``babel-compare-resolution`` — how do these CURIEs normalize on each NodeNorm deployment, and why are they separate?

The comparison and its rendering are :mod:`src.reports.normalization_comparison`; the InChIKey relations are
:mod:`src.model.inchikeys`; the service clients are :mod:`src.utils.translator_services`. ``cli.py`` only
fetches and writes. See ``docs/tools/CompareResolution.md``, and ``docs/issues/AGENTS.md`` for the workflow it
serves.
"""
