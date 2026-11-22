"""Generic helpers that the rest of Babel builds on: DuckDB connections, memory diagnostics, FTP downloads, and (in
time) logging, config and other download helpers.

``src/util.py`` and the generic parts of ``src/babel_utils.py`` are to move here, the rest of ``babel_utils`` into
``src/model/``; see https://github.com/NCATSTranslator/Babel/issues/1223. Put a new generic helper here rather than in
either of those. Don't name a module after a third-party package (``duckdb.py``, ``yaml.py``): a caller doing
``from src.utils import duckdb`` beside ``import duckdb`` would silently replace the real package.
"""
