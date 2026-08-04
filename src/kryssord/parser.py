from __future__ import annotations

from datetime import date

from bs4 import BeautifulSoup

from .models import Result


def parse_results(html: str) -> list[Result]:
    """Parse the results table out of a kryssord.org search.php response.

    Note: kryssord.org caps results at ~8-9 rows for anonymous requests
    regardless of the "Fant N" total in the header -- the rest is gated
    behind their own login ("logg inn for tilgang til flere treff"). This
    only returns what's actually present in the markup.
    """
    soup = BeautifulSoup(html, "lxml")
    results = []
    for row in soup.select("div.results table tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 5:
            continue
        word, word_count, length, users, last_seen = (c.get_text(strip=True) for c in cells)
        results.append(
            Result(
                word=word,
                word_count=int(word_count),
                length=int(length),
                users=int(users) if users else 0,
                last_seen=date.fromisoformat(last_seen) if last_seen else None,
            )
        )
    return results
