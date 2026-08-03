from __future__ import annotations

import os
from pathlib import Path


def default_data_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "kryssord-tui"
