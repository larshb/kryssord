from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import HistoryEntry
from .paths import default_data_dir


def _default_history_path() -> Path:
    return default_data_dir() / "history.jsonl"


class HistoryStore:
    """Append-only log of past searches, persisted as JSON lines.

    Navigating history is a future feature; this just records searches so
    that data exists once that feature is built.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path else _default_history_path()

    def record(self, word: str, pattern: str, result_count: int) -> None:
        entry = HistoryEntry(
            word=word,
            pattern=pattern,
            result_count=result_count,
            timestamp=datetime.now(timezone.utc),
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {
                "word": entry.word,
                "pattern": entry.pattern,
                "result_count": entry.result_count,
                "timestamp": entry.timestamp.isoformat(),
            }
        )
        with self._path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def load_all(self) -> list[HistoryEntry]:
        if not self._path.exists():
            return []
        entries = []
        with self._path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                entries.append(
                    HistoryEntry(
                        word=data["word"],
                        pattern=data["pattern"],
                        result_count=data["result_count"],
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                    )
                )
        return entries
