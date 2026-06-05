#!/usr/bin/env python3
"""Backward-compatible shim for ``tools/slurm/errors.py``.

The error-aggregation logic moved into the ``tools.slurm`` package (alongside the
resource analyzer). This wrapper keeps the historical
``uv run tools/babel-errors.py ...`` invocation working; prefer
``uv run python -m tools.slurm errors ...`` for new usage.
"""

import sys
from pathlib import Path

# Ensure the repo root is importable when run as a loose script (sys.path[0] is tools/).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.slurm.errors import main  # noqa: E402

if __name__ == "__main__":
    main()
