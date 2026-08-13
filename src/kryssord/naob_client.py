from __future__ import annotations

from .http import CachedHttpClient
from .models import NaobEntry, NaobSearchEntry
from .naob_parser import parse_entry, parse_search_results

BASE_URL = "https://naob.no"
SEARCH_URL = f"{BASE_URL}/søk"

_REDIRECT_CODES = (301, 302, 303, 307, 308)


class NaobClient(CachedHttpClient):
    """Client for naob.no (Det Norske Akademis ordbok), which exposes no
    JSON API -- pages are scraped from server-rendered HTML.

    On zero hits, naob.no redirects to /nulltreff/<query>, a path its own
    robots.txt disallows for crawlers -- this client never follows that
    redirect, it just reports zero results. On exactly one hit, it instead
    redirects straight to /ordbok/<slug> (skipping the results list) --
    that's reported as a single-item result, not zero.

    Search is headword-only (naob.no's own "fritekst" full-text mode is
    much noisier and isn't exposed here).
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(cache_filename="naob_http_cache.sqlite", **kwargs)

    def search(self, query: str) -> list[NaobSearchEntry]:
        query = query.strip()
        if not query:
            raise ValueError("search() requires a query")

        response = self._get(SEARCH_URL, params={"q": query}, allow_redirects=False)
        if response.status_code in _REDIRECT_CODES:
            location = response.headers.get("Location", "")
            slug = location.removeprefix("/ordbok/")
            if location.startswith("/ordbok/") and slug:
                return [NaobSearchEntry(word=query, slug=slug)]
            return []
        response.raise_for_status()
        return parse_search_results(response.text)

    def get_entry(self, slug: str) -> NaobEntry | None:
        slug = slug.strip()
        if not slug:
            raise ValueError("get_entry() requires a slug")

        response = self._get(f"{BASE_URL}/ordbok/{slug}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return parse_entry(response.text, slug)
