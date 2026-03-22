# Norsk Kryssord – App Specification

## Overview

A browser-based Norwegian crossword solver with an interactive grid UI. The user fills in a crossword
grid, enters clues per word, and gets live word suggestions scraped from kryssord.org. Supports
incremental solving — the grid does not need to be fully defined before you start solving.

---

## Architecture

```
Browser (HTML/CSS/JS — single-page app)
        │  fetch /api/lookup
        ▼
Python Web Server  (FastAPI + uvicorn)
  - Serves static SPA
  - Proxies lookup requests
  - Manages persistent disk cache
        │  HTTP scrape
        ▼
kryssord.org  /search.php?a={clue}&b={pattern}
```

---

## Upstream Scraper (`KryssordOrg`)

The provided `KryssordOrg` class is the canonical scraper. No changes to its public interface are
needed. The backend wraps it with caching and error handling. Key constraints:

- `a` (clue) is **always required** and must be non-empty. `a=*` is **not** a valid fallback.
- `b` (pattern) is optional; omit it entirely if no pattern is known.
- Wildcards: `?` = exactly one unknown character, `*` = zero or more unknown characters.
- **`*` is for manual use only.** In "Løs alle", all empty cells must be sent as `?` (not `*`),
  so the pattern length is always exact. Using `*` in automated lookups would match words of the
  wrong length and produce false positives.

---

## Backend (Python)

### Stack
- **FastAPI** + **uvicorn** — serves both the SPA and the API
- **Standard library only** for scraping (`urllib`, `re`) — no httpx needed
- **`shelve`** (stdlib) for persistent disk cache — no third-party cache library needed

### Render free-tier considerations
The app is designed to deploy on Render's free Python tier with minimal changes:

- **Ephemeral filesystem** — Render does not persist files between deploys. The `shelve` cache
  and `saves/` directory will be wiped on each redeploy. For localhost this is fine. For Render:
  - Accept cache-loss-on-redeploy as a known limitation (cache repopulates from use), **or**
  - Swap `shelve` for `sqlite3` (stdlib) with a single `cache` table — survives restarts within
    the same deploy, same stdlib-only constraint.
  - `localStorage` autosave lives in the user's browser and is unaffected either way.
- **Single process, synchronous scraping** — wrap `KryssordOrg.search()` in FastAPI's
  `run_in_threadpool` to avoid blocking the async event loop. One-line change, optional for MVP.
- **Minimize JS files** — prefer server-rendered HTML fragments (via Jinja2, included in FastAPI)
  over multiple JS modules where the logic is non-trivial to maintain. The grid itself needs JS
  for interactivity, but sidebar state, results rendering, and the Løs alle banner can be
  server-rendered or inline-templated to reduce the JS surface area.
- **requirements.txt** must stay minimal: `fastapi`, `uvicorn[standard]`. Nothing else.

### Endpoints

#### `GET /`
Serves `static/index.html`.

#### `GET /api/lookup`

Wraps `KryssordOrg.search()` with caching.

**Query params:**

| Param | Required | Notes |
|-------|----------|-------|
| `a`   | Yes | Clue text. Must be non-empty. |
| `b`   | No  | Pattern string. Omit if unknown. |

**Constraint:** If `a` is empty and `b` is also empty/absent, return `400 Bad Request`.  
If only `b` is provided (no `a`), return `400` with a message explaining that a clue is required.

**Response `200`:**
```json
{
  "words": [{"word": "kryssord", "link": "/search.php?a=kryssord"}],
  "total": 1,
  "query": {"a": "nøtt", "b": "kr*o?d"},
  "cached": false
}
```

**Response `400`:**
```json
{"error": "Ledetekst (a) er påkrevd"}
```

**Response `502`:**
```json
{"error": "Oppslag feilet", "detail": "..."}
```

#### `DELETE /api/cache`
Clears the entire shelve cache. Returns `{"ok": true, "cleared": N}` where N is the number of
entries removed. Used by the "Tøm hurtigbuffer" button in settings.

#### `GET /api/save` and `POST /api/save`
Load and persist the current grid state (see Persistence section).

### Caching

- Use Python's `shelve` module backed by a local file (e.g. `cache/lookups.db`).
- Cache key: `f"{a}|{b}"` (lowercased, stripped).
- **No TTL for MVP** — cached forever on localhost. Add TTL later if deploying publicly.
- The `cached` flag in the response lets the frontend optionally show a cache indicator.
- Cache survives server restarts.

### Non-functional
- Timeout: 10s on upstream requests.
- Encoding: UTF-8 throughout; Norwegian chars (æ, ø, å) must round-trip correctly.
- No rate limiting needed for MVP given persistent caching.

### File structure

```
crossword/
├── main.py              # FastAPI app, /api/lookup, /api/save, static mount
├── kryssord.py          # KryssordOrg scraper class (as provided)
├── cache.py             # Shelve-backed cache wrapper (get/set)
├── static/
│   ├── index.html       # Entry point — loads JS modules
│   ├── grid.js          # Grid model, cell state, word extraction
│   ├── search.js        # Sidebar: clue input, pattern display, results
│   ├── solver.js        # "Solve all" logic
│   └── style.css
├── saves/               # Auto-created; holds grid save files (JSON)
├── cache/               # Auto-created; holds shelve cache DB
└── requirements.txt     # fastapi, uvicorn
```

---

## Grid Format: ipuz-inspired JSON

Rather than adopting a full ipuz library dependency, the saved grid uses a **simplified ipuz-compatible
subset** stored as plain JSON. This makes future full ipuz interop straightforward without the
complexity now.

```json
{
  "version": "kryssord/1",
  "title": "",
  "dimensions": {"width": 13, "height": 13},
  "puzzle": [
    [{"cell": 0}, {"cell": 1}, {"cell": "#"}, "..."],
    "..."
  ],
  "solution": [
    [null, "K", "#", "..."],
    "..."
  ],
  "clues": {
    "Across": [{"number": 1, "clue": "nøtt", "cells": [[0,1],[0,2],[0,3]]}],
    "Down":   [{"number": 1, "clue": "",     "cells": [[0,1],[1,1],[2,1]]}]
  }
}
```

- `puzzle[row][col]` — `"#"` = black cell; `{"cell": N}` = open cell (N = clue number or 0).
- `solution[row][col]` — the letter placed there, or `null` if empty, `"#"` if black.
- `clues` are keyed by direction. Each entry records the clue text and the ordered list of cells.
- The frontend reads and writes this format via `/api/save`. The backend treats it as opaque JSON.

**File naming:** `saves/{title or "grid"}_{timestamp}.json`. Autosave on every change.

---

## Frontend (Web GUI)

### Layout

```
┌──────────────────────────────────────────────────────────┐
│  Norsk Kryssordløser   [13×13 ▾]  [Ny]  [Åpne]  [Lagre] │
│                                          [🤖 Løs alle]   │
├─────────────────────────────┬────────────────────────────┤
│                             │  1 → LEDETEKST             │
│                             │  ┌────────────────────┐    │
│   INTERACTIVE GRID          │  │ nøtt               │    │
│                             │  └────────────────────┘    │
│  ┌──┬──┬──┬──┬──┐           │                            │
│  │1 │  │■ │  │  │           │  MØNSTER                   │
│  ├──┼──┼──┼──┼──┤           │  [K][R][_][_][O][_][D]     │
│  │  │2 │  │  │  │           │                            │
│  ├──┼──┼──┼──┼──┤           │  [🔍 Søk]  ← Enter         │
│  │■ │  │  │■ │  │           │  ──────────────────────    │
│  └──┴──┴──┴──┴──┘           │  RESULTATER (3)            │
│                             │  > kryssord (8)            │
│  [←][→][↑][↓] navigasjon   │    kringkord (9)           │
│  [Space] = svart celle      │    kruttord (8)            │
│  [Enter] = bytt retning     │                            │
└─────────────────────────────┴────────────────────────────┘
```

### Grid behaviour

**Cell types:**
- **Open cell** — accepts letters.
- **Black cell** — blocked; rendered filled/dark.
- Cells start as open by default. Users don't need to define every black cell before solving —
  the grid is usable in a partially-defined state.

**Navigation (keyboard-first):**

| Key | Action |
|-----|--------|
| Arrow keys | Move active cell in that direction |
| Letter (A–Z, Æ, Ø, Å) | Fill cell, advance in active direction |
| Backspace | Clear current cell, move back |
| Delete | Clear current cell, stay |
| Space | Toggle cell: open ↔ black |
| Tab | Jump to next word (in clue number order) |
| Shift+Tab | Jump to previous word |
| Enter (on grid) | Switch direction: across ↔ down |
| Enter (in clue/search field) | Trigger search |
| Escape | Return focus to grid |
| Ctrl+Z | Undo last change |
| Ctrl+Shift+S | Trigger "Løs alle" |

**Mouse:**
- Left-click on open cell: select cell; second click on same cell toggles direction.
- Left-click on black cell: make open.
- Right-click on open cell: make black (same as Space).

**Word detection:**
A "word" is any run of ≥ 2 consecutive open cells in a row or column, bounded by black cells or
grid edges. Single isolated open cells are not treated as words. Words are auto-numbered in
reading order (left-to-right, top-to-bottom).

**Active word highlight:**
When a cell is selected, the full word run it belongs to is highlighted. The active cell itself
has a cursor highlight distinct from the word highlight.

**Letter conflicts:**
If a result is applied and its letters conflict with existing grid letters, conflicting cells are
highlighted red. A small confirmation banner appears:
*"N konflikter – bruk likevel? [Ja] [Nei]"*

---

### Sidebar — Search Panel

**Ledetekst (clue field):**
- Plain text input, Norwegian characters supported natively.
- Placeholder text: *"Ledetekst (eller mønster)"* — hints that a pattern alone is also accepted.
- Auto-populated with any stored clue for the active word.
- Clue is saved back to the grid model on blur or Enter.
- **If the clue field is empty but a pattern is present:** promote `b` → `a`, send no `b`.
  This is done in the frontend before the request fires; no backend change needed.
- **If both fields are empty:** search button stays disabled.

**Mønster (pattern display):**
- Rendered as individual letter boxes, one per cell of the active word.
- Known letters show their letter; empty cells show `_`.
- Boxes are editable — click or Tab into a box to override or type a wildcard (`?` or `*`).
- `*` (multi-character wildcard) is only meaningful in manual searches — it is never used in automated Løs alle lookups, where all unknowns are sent as `?`.
- Pattern is constructed from grid state: known letters → letter, empty cell → `?`.
- User edits to the pattern are **ephemeral per search** — they do not write back to the grid.

**Søk button / Enter:**
- Calls `GET /api/lookup?a={clue}&b={pattern}`.
- Disabled and greyed out if clue field is empty.
- Shows a spinner while loading.
- Shows a small 💾 icon if result came from cache.

**Results list:**
- Ordered as returned by upstream.
- Each item: `kryssord (8)` — word + letter count.
- Click or press Enter on a focused result to fill it into the grid.
- Results list is keyboard-navigable with ↑/↓ after search returns; focus moves automatically.

---

### "Løs alle" — Solve All

The Solve All button walks every unsolved word in the grid and finds **unambiguous solutions**
(exactly 1 result). Only words that have a saved clue are queried.

**Flow:**

1. User triggers **🤖 Løs alle** (button or Ctrl+Shift+S).
2. For each unsolved word with a clue, call `/api/lookup` using the clue and current partial pattern.
3. Words with exactly 1 result are collected as *candidates*.
4. All candidates are filled into the grid simultaneously with a **yellow highlight**.
5. A banner appears:
   *"Fant N entydige løsninger. M ord uten entydig løsning. [✓ Godta] [✗ Forkast]"*
6. **Godta:** highlights removed, letters committed to grid.
7. **Forkast:** yellow cells cleared, grid restored to pre-solve state.

**Progressive rendering:** Cells fill in as each lookup resolves — don't wait for all to finish.

**Edge cases:**
- If a candidate conflicts with an already-filled letter, it is excluded from the automatic fill
  and counted among "uten entydig løsning".
- If no candidates found at all, show: *"Ingen entydige løsninger funnet."*

---

## Persistence

### Autosave (localStorage) — MVP
- On every grid change, serialize full grid JSON to `localStorage` key `kryssord_autosave`.
- On app load, if autosave exists: *"Gjenoppta siste økt? [Ja] [Ny start]"*
- Covers all localhost use without any backend save endpoint.

### File save/load (v1)
- **Save:** `POST /api/save` with grid JSON → writes to `saves/` → returns filename.
- **Load:** `GET /api/save?file={name}` → returns grid JSON.
- Toolbar lists available saves in a dropdown.
- Format: ipuz-inspired JSON described above.

---

## Norwegian Language & Keyboard

- All UI labels in Norwegian. Code comments in English.
- Browser handles æ/ø/å natively in all input fields — no special handling needed.
- Wildcards `?` and `*` are only entered in pattern boxes, not in grid cells.
- Known limitation: non-Nordic keyboards require compose key or copy-paste for æ/ø/å. Document
  in README; not a blocker.

---

## Out of Scope (MVP)

- Full ipuz library compliance / export to third-party solvers
- Multi-user / cloud sync
- Printing / PDF export
- Mobile layout optimisation
- Offline word database / local solver
- Automatic clue suggestions

---

## Resolved Design Decisions

### 1. Grid size
Free-form N×M input in the toolbar. Two numeric fields (width, height) with a **Lag nytt brett**
button. No presets. Default 13×13.

### 2. Undo depth
Single undo level — store only the previous grid snapshot (`lastState`). `Ctrl+Z` swaps current
state with `lastState`. Simple to implement; sufficient for correcting mistakes.

### 3. "Løs alle" — word priority order
Words are sorted before querying, highest priority first:

1. **% solved letters** — descending (words where more letters are already known come first).
2. **Word length** — descending (longer words first, as they are more constraining).
3. **Row position** — ascending (top of grid first).
4. **Column position** — ascending (left first).
5. **Orientation** — across before down.

This means a half-filled long word near the top-left is queried before a short empty word near
the bottom-right.

### 4. Cache management
Add a **Tøm hurtigbuffer** button in a collapsible ⚙ settings panel in the toolbar. It calls
`DELETE /api/cache` on the backend, which clears the shelve DB. Show a brief confirmation:
*"Hurtigbuffer tømt."* The endpoint is trivial to implement alongside the lookup endpoint.

### 5. Pattern-only search (no clue entered)
If the clue field (`a`) is empty but a pattern (`b`) is present, **promote `b` to `a`** and
send no `b`. The user is effectively searching by pattern-as-clue. This is handled transparently
in the frontend before the request is sent — no backend change needed. The clue field placeholder
text should hint at this: *"Ledetekst (eller mønster)"*.


---

## MVP Implementation Roadmap

Each step is independently runnable and testable. Complete them in order.

### Step 1 — Backend skeleton (no frontend)
- `main.py`: FastAPI app with `/api/lookup` and `DELETE /api/cache`.
- `kryssord.py`: paste in the provided `KryssordOrg` class unchanged.
- `cache.py`: shelve wrapper with `get(key)` / `set(key, value)` / `clear()`.
- Verify with `curl` or a browser: `http://localhost:8000/api/lookup?a=nøtt&b=kr?ssord`
- ✅ Done when: lookup returns JSON, second call returns `"cached": true`.

### Step 2 — Static grid (no interaction)
- `static/index.html` + `style.css`: two-column layout (grid left, sidebar right).
- Hardcoded 13×13 table rendered from Python/Jinja2 or static HTML.
- No JS yet. Black cells via CSS class, letter cells as `<td>` with `contenteditable`.
- ✅ Done when: the page loads, looks right, and FastAPI serves it at `/`.

### Step 3 — Grid interaction (JS)
- `grid.js`: cell selection, direction toggle, keyboard navigation (arrows, letters,
  backspace, space for black cell, tab for next word, enter for direction switch).
- Word detection and numbering from current grid state.
- Active cell and active word highlighting.
- Single-level undo (`Ctrl+Z`).
- ✅ Done when: you can navigate, type letters, toggle black cells, and undo — all without mouse.

### Step 4 — Search sidebar (JS)
- `search.js`: clue field, pattern boxes (auto-built from active word), Søk button.
- On search: call `/api/lookup`, render results list.
- Click/Enter on result: fill word into grid with conflict detection.
- `b → a` promotion for pattern-only searches.
- ✅ Done when: you can look up a word by clue, see results, and fill one in.

### Step 5 — Autosave
- Serialize grid state to `localStorage` on every change.
- On load: offer to restore last session.
- ✅ Done when: grid survives a page reload.

### Step 6 — "Løs alle"
- `solver.js` (or inline in `grid.js`): collect unsolved words with clues, sort by priority,
  fire sequential `/api/lookup` calls, progressive yellow fill, accept/discard banner.
- ✅ Done when: Ctrl+Shift+S fills in unambiguous words with yellow, and Godta/Forkast work.

### Step 7 — Polish & Render deploy
- Add grid size input (N×M fields + "Lag nytt brett").
- Add ⚙ settings panel with "Tøm hurtigbuffer" button.
- Swap `shelve` → `sqlite3` if Render ephemeral FS is a problem.
- Add `Procfile`: `web: uvicorn main:app --host 0.0.0.0 --port $PORT`
- ✅ Done when: app runs on Render free tier and basic solve flow works end-to-end.

### Deferred (post-MVP)
- File save/load (`/api/save`) and save picker in toolbar.
- Full ipuz export.
- Mobile layout.
