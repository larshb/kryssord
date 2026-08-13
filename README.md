# kryssord-tui

A keyboard-driven terminal helper for Norwegian crosswords. Searches
[kryssord.org](https://www.kryssord.org/) for candidate answers and shows
matching [naob.no](https://naob.no/) (Det Norske Akademis ordbok) dictionary
entries — definitions, etymology, examples, and idioms — alongside them, so
you get context for unfamiliar words without leaving the terminal.

See [CREDITS.md](CREDITS.md) for attribution and how this tool identifies
itself to both sites.

## Install

```sh
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Run

```sh
.venv/bin/kryssord          # interactive TUI
.venv/bin/kryssord hund     # one-shot CLI search, prints results and exits
.venv/bin/kryssord hu.d     # "." / "?" = one unknown letter, "*" = any number
```

In the TUI: type a word/hint, Enter, optionally a letter pattern, Enter to
search. Arrow keys browse results (and preview NAOB entries) from any field.
`Ctrl+O` opens the current kryssord.org search in your browser, `Ctrl+N`
opens the NAOB entries shown, `Ctrl+R` opens search history — or reach any
of these through the command palette (`Ctrl+P`).

## Test

```sh
.venv/bin/pytest
```
