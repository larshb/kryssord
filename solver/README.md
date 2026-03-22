# Kryssordløser

A browser-based Norwegian crossword solver with an interactive grid UI. Look up words by clue and pattern against [kryssord.org](https://kryssord.org), fill them into the grid, and let the solver find unambiguous solutions automatically.

## Features

- Interactive crossword grid — keyboard-first, mouse optional
- Per-word clue storage and auto-built pattern from known letters
- Live word lookup with persistent cache (no repeat requests)
- **Løs alle** — automatically solves unambiguous words, with prompts for missing clues
- Save/load grids as JSON files (browser download + file picker)
- localStorage autosave between sessions

## Requirements

- Python 3.10+
- `fastapi`, `uvicorn[standard]`

## Installation

```bash
pip install -r requirements.txt
```

## Running

```bash
python3 -m uvicorn main:app --reload
```

Then open [http://localhost:8000](http://localhost:8000).

For auto-reloading static files during development:

```bash
python3 -m uvicorn main:app --reload \
  --reload-include="*.html" \
  --reload-include="*.js" \
  --reload-include="*.css"
```

## Usage

### Grid navigation

| Key | Action |
|-----|--------|
| Arrow keys | Move cursor |
| Letter (A–Z, Æ, Ø, Å) | Fill cell and advance |
| Backspace | Clear cell and retreat |
| Delete | Clear cell and stay |
| Space | Toggle cell open ↔ black |
| Enter | Switch direction (across ↔ down) |
| Tab / Shift+Tab | Jump to next / previous word |
| Ctrl+Z | Undo last change |
| Escape | Return focus to grid |

### Search

1. Navigate to a word — the sidebar shows its clue field and pattern
2. Type a clue (or just use the pattern)
3. Press **Enter** to search
4. Use **↑/↓** to navigate results, **Enter** to fill the word into the grid

Pattern boxes are auto-built from the grid. Use `?` for a single unknown character and `*` for any number of unknowns (manual searches only).

If no results are found for clue + pattern, the search automatically retries using the pattern alone.

### Løs alle

Click **🤖 Løs alle** or press **Ctrl+Shift+S** to run the automatic solver.

- Words with exactly one unambiguous result are filled in with a yellow highlight
- If some words have no clue, you are prompted to enter them one by one before the solver re-runs
- Confirm with **✓ Godta** to commit, or **✗ Forkast** to discard all changes

### Save / load

- **Lagre** — downloads the current grid as a `.json` file
- **Åpne** — opens a file picker to load a previously saved grid
- The grid is also autosaved to `localStorage` on every change and restored on next visit

### Clear letters

**Tøm bokstaver** in the toolbar clears all letters while keeping the grid layout and all clues intact.

## File format

Grids are saved as a simplified [ipuz](http://www.ipuz.org/)-compatible JSON:

```json
{
  "version": "kryssord/1",
  "title": "",
  "dimensions": { "width": 13, "height": 13 },
  "puzzle":   [["#", {"cell": 1}, ...]],
  "solution": [["#", "K", null, ...]],
  "clues": {
    "Across": [{"number": 1, "clue": "nøtt", "cells": [[0,1],[0,2]]}],
    "Down":   [{"number": 1, "clue": "",     "cells": [[0,1],[1,1]]}]
  }
}
```

## Project structure

```
crossword/
├── main.py          # FastAPI app — /api/lookup, /api/cache
├── kryssord.py      # kryssord.org HTML scraper
├── cache.py         # shelve-backed persistent cache
├── static/
│   ├── index.html   # single-page app
│   ├── api.js       # shared fetch helper (clue+pattern with fallback)
│   ├── grid.js      # grid model, rendering, keyboard/mouse interaction
│   ├── search.js    # sidebar: clue input, pattern boxes, results
│   ├── solver.js    # Løs alle logic and missing-clue prompt cycle
│   └── fileio.js    # save (download) and load (file picker)
├── cache/           # auto-created — shelve lookup cache
└── requirements.txt
```

## Notes

- **Norwegian characters**: æ, ø, å are handled natively by the browser. On non-Nordic keyboards you may need to copy-paste them into the clue field.
- **Cache**: lookups are cached indefinitely on localhost. Use **⚙ Innstillinger → Tøm hurtigbuffer** to clear if you get stale results.
- **Render deployment**: the app runs on Render's free Python tier. Note that the `shelve` cache is lost on each redeploy (but not on restart). Consider swapping to `sqlite3` for better persistence.

## Disclaimer

This tool scrapes [kryssord.org](https://kryssord.org) for word lookups. Use responsibly — the persistent cache minimises the number of requests made to the upstream site.
