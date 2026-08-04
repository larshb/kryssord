from __future__ import annotations

import time
from datetime import timedelta
from pathlib import Path

import requests
import requests_cache

from .paths import default_data_dir

# Identifies this tool honestly rather than posing as a browser or an
# undeclared crawler.
DEFAULT_USER_AGENT = "kryssord-tui/0.1 (personal crossword-solving CLI; cached, rate-limited)"

DEFAULT_EXPIRE_AFTER = timedelta(days=7)
DEFAULT_MIN_INTERVAL = 1.0  # seconds between real (non-cached) requests


class CachedHttpClient:
    """Shared cache + throttle plumbing for the site-specific clients.

    A local cache (via requests_cache) means repeat lookups never hit the
    network, and a minimum interval between *new* requests keeps fresh
    lookups from hammering the site.
    """

    def __init__(
        self,
        cache_filename: str,
        cache_path: str | Path | None = None,
        expire_after: timedelta = DEFAULT_EXPIRE_AFTER,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        cache_path = Path(cache_path) if cache_path else default_data_dir() / cache_filename
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
                "User-Agent": user_agent,
                "Accept-Language": "nb-NO,nb;q=0.9,no;q=0.8,en;q=0.5",
            }
        )
        self._min_interval = min_interval
        self._next_allowed_at: float | None = None

    def _get(self, url: str, params: dict | None = None, allow_redirects: bool = True) -> requests.Response:
        request = requests.Request("GET", url, params=params)
        if not self._session.cache.contains(request=request):
            self._wait_for_next_slot()
        response = self._session.get(url, params=params, timeout=10, allow_redirects=allow_redirects)
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

    def __enter__(self):
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
