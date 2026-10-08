"""Estimate the peak RAM an RDF dump needs when bulk-loaded into a ``pyoxigraph.Store``.

Self-contained by design: it models pyoxigraph's memory behaviour, not Babel data, so
there is nothing here for a pipeline rule to reuse. See ``docs/tools/Memory.md``.

Run it by path rather than as a console script::

    uv run python src/tools/memory/estimate_rdf_load_memory.py FILE [FILE ...]
"""
