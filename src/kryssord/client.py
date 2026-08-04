from __future__ import annotations

from .http import CachedHttpClient
from .models import Result
from .parser import parse_results

SEARCH_URL = "https://www.kryssord.org/search.php"


class KryssordClient(CachedHttpClient):
    """Client for kryssord.org, which exposes no JSON API -- search.php
    returns HTML that this client scrapes.

    Search fields, both optional (at least one is required):
      word    -- free-text hint/clue search (site's "Spørreord" field)
      pattern -- letter pattern (site's "mønster" field), where
                 `?` = exactly one unknown letter, `*` = zero or more
                 unknown letters, e.g. "b???" or "hu*".
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(cache_filename="kryssord_http_cache.sqlite", **kwargs)

    def search(self, word: str = "", pattern: str = "") -> list[Result]:
        word = word.strip()
        pattern = pattern.strip()
        if not word and not pattern:
            raise ValueError("search() requires a word and/or a pattern")

        response = self._get(SEARCH_URL, params={"a": word, "b": pattern})
        response.raise_for_status()
        return parse_results(response.text)
