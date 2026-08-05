# Credits & disclaimers

kryssord-tui is an independent, unofficial terminal tool. It is not affiliated
with, endorsed by, or sponsored by either of the sites it queries. All
trademarks and site names belong to their respective owners.

## kryssord.org

Word and letter-pattern search results are fetched live from
[kryssord.org](https://www.kryssord.org/), a Norwegian crossword-solving
aid. All credit for that data belongs to kryssord.org and its contributors.

- kryssord.org caps how many results it shows to anonymous requests
  (it prompts you to register/log in for access to more hits) — this tool
  only ever shows what kryssord.org itself returns to an anonymous request,
  nothing is being withheld or filtered on our end.
- Requests are cached and rate-limited (see `src/kryssord/http.py`) so this
  tool doesn't put unnecessary load on their servers.

## naob.no — Det Norske Akademis ordbok (NAOB)

Dictionary entries (definitions, word class, inflection, etymology, usage
examples, and idioms) are fetched live from
[naob.no](https://naob.no/), *Det Norske Akademis ordbok*, published by
*Det Norske Akademi for Språk og Litteratur*. All credit for that content —
the product of substantial editorial and lexicographic work — belongs to
NAOB and its editorial staff.

- Literary citations (author/work/year quotations) that appear on naob.no
  are deliberately not reproduced here — this tool only surfaces
  definitions, examples, and idioms, not the scholarly citation apparatus.
- NAOB is funded in part by public support and donations. If you find
  yourself relying on it through this tool, consider supporting the real
  thing directly — see naob.no's own funding/support page.

## This tool's own scope

kryssord-tui scrapes each site's public, unauthenticated HTML pages (no
private API keys or bypassed access controls are involved) and identifies
itself with its own honest User-Agent string rather than posing as a
browser or an undeclared crawler. It respects each site's `robots.txt`:
naob.no disallows crawling its `/nulltreff/` (no-hits) path, so this tool
detects that redirect and reports zero results without ever requesting
that page.
