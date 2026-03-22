"""
Persistent cache backed by Python's shelve module.

Cache key convention: "{a}|{b}" (both lowercased and stripped).
No TTL for MVP — entries live until manually cleared via clear().
The shelf file is created automatically under the given directory.
"""

import shelve
import os
from pathlib import Path


class Cache:
    def __init__(self, path: str = "cache/lookups"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._path = path

    def _key(self, a: str, b: str) -> str:
        return f"{a.strip().lower()}|{b.strip().lower()}"

    def get(self, a: str, b: str) -> dict | None:
        """Return cached result or None."""
        with shelve.open(self._path) as db:
            return db.get(self._key(a, b))

    def set(self, a: str, b: str, value: dict) -> None:
        """Store a result."""
        with shelve.open(self._path) as db:
            db[self._key(a, b)] = value

    def clear(self) -> int:
        """Delete all entries. Returns number of entries cleared."""
        with shelve.open(self._path) as db:
            count = len(db)
            db.clear()
        return count

    def size(self) -> int:
        """Return number of cached entries."""
        with shelve.open(self._path) as db:
            return len(db)
