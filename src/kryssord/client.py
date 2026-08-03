from __future__ import annotations

import time
from datetime import timedelta
from pathlib import Path

import requests
import requests_cache

from .models import Result
from .parser import parse_results
from .paths import default_data_dir

SEARCH_URL = "https://www.kryssord.org/search.php"

# Identifies this tool honestly rather than posing as a browser; kryssord.org's
# robots.txt disallows bulk AI crawlers (ClaudeBot, GPTBot, ...) but this is a
# personal, cached, rate-limited client -- not a crawler.
USER_AGENT = "kryssord-tui/0.1 (personal crossword-solving CLI; cached, rate-limited)"

DEFAULT_EXPIRE_AFTER = timedelta(days=7)
DEFAULT_MIN_INTERVAL = 1.0  # seconds between real (non-cached) requests


def _default_cache_path() -> Path:
    return default_data_dir() / "http_cache.sqlite"


class KryssordClient:
    """Client for kryssord.org, which exposes no JSON API -- search.php
    returns HTML that this client scrapes.

    A local cache (via requests_cache) means repeat searches never hit the
    network, and a minimum interval between *new* requests keeps fresh
    lookups from hammering the site.

    Search fields, both optional (at least one is required):
      word    -- free-text hint/clue search (site's "Spørreord" field)
      pattern -- letter pattern (site's "mønster" field), where
                 `?` = exactly one unknown letter, `*` = zero or more
                 unknown letters, e.g. "b???" or "hu*".
    """

    def __init__(
        self,
        cache_path: str | Path | None = None,
        expire_after: timedelta = DEFAULT_EXPIRE_AFTER,
        min_interval: float = DEFAULT_MIN_INTERVAL,
    ) -> None:
        cache_path = Path(cache_path) if cache_path else _default_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        self._session = requests_cache.CachedSession(
            cache_name=str(cache_path),
            backend="sqlite",
            expire_after=expire_after,
            allowable_methods=("GET",),
            allowable_codes=(200,),
        )
        self._session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "nb-NO,nb;q=0.9,no;q=0.8,en;q=0.5",
            }
        )
        self._min_interval = min_interval
        self._next_allowed_at: float | None = None

    def search(self, word: str = "", pattern: str = "") -> list[Result]:
        word = word.strip()
        pattern = pattern.strip()
        if not word and not pattern:
            raise ValueError("search() requires a word and/or a pattern")

        response = self._get(SEARCH_URL, params={"a": word, "b": pattern})
        response.raise_for_status()
        return parse_results(response.text)

    def _get(self, url: str, params: dict) -> requests.Response:
        request = requests.Request("GET", url, params=params)
        if not self._session.cache.contains(request=request):
            self._wait_for_next_slot()
        response = self._session.get(url, params=params, timeout=10)
        if not getattr(response, "from_cache", False):
            self._next_allowed_at = time.monotonic() + self._min_interval
        return response

    def _wait_for_next_slot(self) -> None:
        if self._next_allowed_at is None:
            return
        remaining = self._next_allowed_at - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "KryssordClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
