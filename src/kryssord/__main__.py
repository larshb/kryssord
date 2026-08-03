from __future__ import annotations

import argparse
import sys

from .client import KryssordClient


def main() -> None:
    if len(sys.argv) == 1:
        from .tui import run

        run()
        return

    parser = argparse.ArgumentParser(prog="kryssord", description="Search kryssord.org")
    parser.add_argument("word", nargs="?", default="", help="hint word, e.g. hund")
    parser.add_argument(
        "-p", "--pattern", default="", help="letter pattern, ? = one letter, * = any letters, e.g. 'b???'"
    )
    args = parser.parse_args()

    if not args.word and not args.pattern:
        parser.error("provide a word and/or --pattern")

    with KryssordClient() as client:
        results = client.search(word=args.word, pattern=args.pattern)

    if not results:
        print("Ingen treff.", file=sys.stderr)
        return

    for r in results:
        seen = r.last_seen.isoformat() if r.last_seen else "-"
        print(f"{r.word:<20} lengde={r.length:<3} ord={r.word_count:<2} brukt={r.users:<5} sist={seen}")


if __name__ == "__main__":
    main()
