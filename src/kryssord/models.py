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


@dataclass(frozen=True, slots=True)
class NaobSearchEntry:
    """One row from a naob.no search-results listing."""

    word: str
    slug: str


@dataclass(frozen=True, slots=True)
class NaobSense:
    """One numbered sense ("1", "1.1", ...) within a naob.no entry."""

    number: str
    text: str
    examples: list[str]


@dataclass(frozen=True, slots=True)
class NaobIdiom:
    """One fixed expression/idiom ("uttrykk") built on a naob.no headword."""

    phrase: str
    meaning: str


@dataclass(frozen=True, slots=True)
class NaobEntry:
    """A full naob.no dictionary entry, fetched from /ordbok/<slug>."""

    word: str
    slug: str
    word_class: str | None
    inflection: str | None
    etymology: str | None
    senses: list[NaobSense]
    idioms: list[NaobIdiom]
    idiom_count: int
