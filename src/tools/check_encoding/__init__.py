"""Survey Babel label, synonym and compendium files for encoding damage.

A thin CLI (:mod:`src.tools.check_encoding.cli`, installed as ``babel-check-encoding``) over
:mod:`src.synonyms.encoding`, which holds the detector. The same detector runs inside the pipeline
via :func:`src.synonyms.encoding.check_encoding`, where it *raises* rather than reports -- so use
this tool to find out what a build already contains before relying on the raising check.

See ``docs/tools/CheckEncoding.md``.
"""
