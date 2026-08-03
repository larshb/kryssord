from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class Result:
    """One row from a kryssord.org search result."""

    word: str
    word_count: int
    length: int
    users: int
    last_seen: date | None


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """One past search, as recorded by HistoryStore."""

    word: str
    pattern: str
    result_count: int
    timestamp: datetime
