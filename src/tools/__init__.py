"""Babel developer tooling: thin CLI frontends over the library code in ``src/``.

Each tool is a subpackage exposing a console script (see ``[project.scripts]`` in
``pyproject.toml``). Logic that models Babel data — cliques, compendia, concords —
belongs in ``src/`` beside the code it models, not here, so that a second tool or a
pipeline rule can reuse it. See ``docs/tools/README.md`` for the convention, the index
of tools, and the two documented exceptions (``slurm`` and ``memory``, which model
SLURM and RDF artifacts rather than Babel data and so are self-contained).

Bash scripts invoked by path live in ``scripts/`` instead; see ``scripts/README.md``.
"""
