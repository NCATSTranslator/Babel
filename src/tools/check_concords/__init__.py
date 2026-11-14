"""``babel-check-concords`` — would any row of these concords fail Babel's concord parser?

The parser is :func:`src.model.intermediates.parse_concord_line` and the tally is
:func:`src.model.intermediates.scan_concord_lines`; ``cli.py`` only finds the files (locally, or under a
published build's HTTP directory listing) and prints the result. See ``docs/tools/CheckConcords.md``.
"""
