"""Add `tests/fixtures/` to `sys.path` so `tinypkg` is importable."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
