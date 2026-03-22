/**
 * grid.js — crossword grid model and interaction
 *
 * Exports a single `Grid` instance as `window.grid` for use by search.js and solver.js.
 *
 * State model:
 *   cells[row][col] = { black: bool, letter: str|"", clueNum: int|null }
 *   clues[dir][number] = { text: str, cells: [[r,c],...] }  (dir = "across"|"down")
 *
 * The grid table is fully owned and rebuilt by this module.
 * Other modules interact only through the Grid API, never by touching the DOM directly.
 */

class Grid {
  constructor() {
    this.rows = 13;
    this.cols = 13;

    // cells[r][c] = { black, letter, clueNum }
    this.cells = [];

    // clues["across"|"down"][number] = { text, cells: [[r,c],...] }
    this.clues = { across: {}, down: {} };

    // Cursor state
    this.curRow = 0;
    this.curCol = 0;
    this.dir = "across"; // "across" | "down"

    // Single-level undo: snapshot of { cells, clues } before last mutation
    this.lastState = null;

    // Callbacks registered by other modules
    this._onSelectionChange = [];  // fired when cursor/direction/word changes
    this._onCellChange = [];       // fired when a letter or black-state changes

    this._init();
  }

  // -------------------------------------------------------------------------
  // Initialisation
  // -------------------------------------------------------------------------

  _init() {
    this._buildCells();
    this._renderTable();
    this._bindKeys();
    this._bindToolbar();
    this._loadAutosave();
  }

  _buildCells(rows = this.rows, cols = this.cols) {
    this.rows = rows;
    this.cols = cols;
    this.cells = Array.from({ length: rows }, () =>
      Array.from({ length: cols }, () => ({ black: false, letter: "", clueNum: null }))
    );
    this.clues = { across: {}, down: {} };
    this._numberCells();
  }

  // -------------------------------------------------------------------------
  // Cell numbering — assigns clue numbers in reading order
  // -------------------------------------------------------------------------

  _numberCells() {
    // Clear old numbers
    for (let r = 0; r < this.rows; r++)
      for (let c = 0; c < this.cols; c++)
        this.cells[r][c].clueNum = null;

    let num = 1;
    for (let r = 0; r < this.rows; r++) {
      for (let c = 0; c < this.cols; c++) {
        if (this.cells[r][c].black) continue;
        const startsAcross = this._isWordStart(r, c, "across");
        const startsDown   = this._isWordStart(r, c, "down");
        if (startsAcross || startsDown) {
          this.cells[r][c].clueNum = num++;
        }
      }
    }
    this._rebuildClueIndex();
  }

  // A cell starts a word in direction if:
  //   - it is open
  //   - the previous cell in that direction is black or off-grid
  //   - the next cell in that direction is open (run length >= 2)
  _isWordStart(r, c, dir) {
    if (this.cells[r][c].black) return false;
    if (dir === "across") {
      const prevBlocked = c === 0 || this.cells[r][c - 1].black;
      const nextOpen    = c + 1 < this.cols && !this.cells[r][c + 1].black;
      return prevBlocked && nextOpen;
    } else {
      const prevBlocked = r === 0 || this.cells[r - 1][c].black;
      const nextOpen    = r + 1 < this.rows && !this.cells[r + 1][c].black;
      return prevBlocked && nextOpen;
    }
  }

  // Build clueIndex: dir -> number -> { cells: [[r,c],...] }
  // Preserves existing clue text across renumbering.
  _rebuildClueIndex() {
    const oldClues = this.clues;
    this.clues = { across: {}, down: {} };

    for (let r = 0; r < this.rows; r++) {
      for (let c = 0; c < this.cols; c++) {
        const num = this.cells[r][c].clueNum;
        if (!num) continue;
        for (const dir of ["across", "down"]) {
          if (!this._isWordStart(r, c, dir)) continue;
          const cells = this._wordCells(r, c, dir);
          if (cells.length < 2) continue;
          // Try to preserve clue text by matching on cell position
          const oldText = this._findOldClueText(oldClues[dir], cells);
          this.clues[dir][num] = { text: oldText, cells };
        }
      }
    }
  }

  // Find old clue text by matching the first cell of a word
  _findOldClueText(oldDir, cells) {
    if (!cells.length) return "";
    const [r, c] = cells[0];
    for (const entry of Object.values(oldDir)) {
      if (entry.cells.length && entry.cells[0][0] === r && entry.cells[0][1] === c)
        return entry.text;
    }
    return "";
  }

  // -------------------------------------------------------------------------
  // Word helpers
  // -------------------------------------------------------------------------

  // Return ordered list of [r,c] cells belonging to the word starting at r,c in dir
  _wordCells(r, c, dir) {
    const cells = [];
    let cr = r, cc = c;
    while (cr >= 0 && cr < this.rows && cc >= 0 && cc < this.cols && !this.cells[cr][cc].black) {
      cells.push([cr, cc]);
      if (dir === "across") cc++; else cr++;
    }
    return cells;
  }

  // Find the word (number, dir) that contains cell [r,c] in given direction
  _wordAt(r, c, dir) {
    // Walk backward to find the start of the run
    let sr = r, sc = c;
    if (dir === "across") { while (sc > 0 && !this.cells[sr][sc - 1].black) sc--; }
    else                  { while (sr > 0 && !this.cells[sr - 1][sc].black) sr--; }
    const num = this.cells[sr][sc].clueNum;
    if (!num) return null;
    const entry = this.clues[dir][num];
    if (!entry || entry.cells.length < 2) return null;
    return { num, dir, cells: entry.cells };
  }

  // Return all words sorted by clue number, across before down
  _allWords() {
    const words = [];
    for (const num of Object.keys(this.clues.across).map(Number).sort((a,b)=>a-b))
      words.push({ num, dir: "across", ...this.clues.across[num] });
    for (const num of Object.keys(this.clues.down).map(Number).sort((a,b)=>a-b))
      words.push({ num, dir: "down", ...this.clues.down[num] });
    return words;
  }

  // The word currently under the cursor (may be null for isolated cells)
  activeWord() {
    return this._wordAt(this.curRow, this.curCol, this.dir);
  }

  // Pattern string for a word (known letters or "?" for blanks)
  patternForWord(word) {
    return word.cells.map(([r, c]) => this.cells[r][c].letter || "?").join("");
  }

  // -------------------------------------------------------------------------
  // DOM rendering
  // -------------------------------------------------------------------------

  _renderTable() {
    const tbody = document.getElementById("grid-body");
    tbody.innerHTML = "";
    for (let r = 0; r < this.rows; r++) {
      const tr = document.createElement("tr");
      for (let c = 0; c < this.cols; c++) {
        const td = document.createElement("td");
        td.dataset.r = r;
        td.dataset.c = c;
        td.addEventListener("click",       (e) => this._onClick(e, r, c));
        td.addEventListener("contextmenu", (e) => this._onRightClick(e, r, c));
        tr.appendChild(td);
      }
      tbody.appendChild(tr);
    }
    this._renderAll();
  }

  // Re-render every cell (used after bulk changes)
  _renderAll() {
    this._numberCells();
    for (let r = 0; r < this.rows; r++)
      for (let c = 0; c < this.cols; c++)
        this._renderCell(r, c);
    this._renderHighlights();
  }

  _renderCell(r, c) {
    const td = this._td(r, c);
    if (!td) return;
    const cell = this.cells[r][c];

    // Classes (preserve highlight classes — renderHighlights handles those)
    td.classList.toggle("black", cell.black);

    // Rebuild interior only for non-black cells
    if (!cell.black) {
      // Number span
      let numSpan = td.querySelector(".num");
      if (!numSpan) { numSpan = document.createElement("span"); numSpan.className = "num"; td.appendChild(numSpan); }
      numSpan.textContent = cell.clueNum ? cell.clueNum : "";

      // Letter span
      let letSpan = td.querySelector(".letter");
      if (!letSpan) { letSpan = document.createElement("span"); letSpan.className = "letter"; td.appendChild(letSpan); }
      letSpan.textContent = cell.letter;
    } else {
      td.innerHTML = "";
    }
  }

  _renderHighlights() {
    // Clear all highlight classes
    for (let r = 0; r < this.rows; r++)
      for (let c = 0; c < this.cols; c++) {
        const td = this._td(r, c);
        td.classList.remove("cursor", "word-hl", "conflict", "candidate");
      }

    // Highlight active word
    const word = this.activeWord();
    if (word) {
      for (const [r, c] of word.cells) {
        if (r !== this.curRow || c !== this.curCol)
          this._td(r, c).classList.add("word-hl");
      }
    }

    // Cursor cell
    if (!this.cells[this.curRow][this.curCol].black)
      this._td(this.curRow, this.curCol).classList.add("cursor");
  }

  _td(r, c) {
    return document.querySelector(`#grid-body tr:nth-child(${r + 1}) td:nth-child(${c + 1})`);
  }

  // -------------------------------------------------------------------------
  // Cursor movement
  // -------------------------------------------------------------------------

  moveTo(r, c, dir = this.dir) {
    r = Math.max(0, Math.min(this.rows - 1, r));
    c = Math.max(0, Math.min(this.cols - 1, c));
    this.curRow = r;
    this.curCol = c;
    this.dir = dir;
    this._renderHighlights();
    this._fireSelectionChange();
  }

  // Advance cursor one step in active direction, skipping black cells
  _advance() {
    let r = this.curRow, c = this.curCol;
    if (this.dir === "across") c++; else r++;
    // Skip black cells
    while (r < this.rows && c < this.cols && this.cells[r][c]?.black) {
      if (this.dir === "across") c++; else r++;
    }
    if (r < this.rows && c < this.cols) this.moveTo(r, c);
  }

  // Retreat cursor one step, skipping black cells
  _retreat() {
    let r = this.curRow, c = this.curCol;
    if (this.dir === "across") c--; else r--;
    while (r >= 0 && c >= 0 && this.cells[r]?.[c]?.black) {
      if (this.dir === "across") c--; else r--;
    }
    if (r >= 0 && c >= 0) this.moveTo(r, c);
  }

  // Jump to next/previous word (Tab / Shift+Tab)
  _jumpWord(delta) {
    const words = this._allWords();
    if (!words.length) return;
    const cur = this.activeWord();
    let idx = cur ? words.findIndex(w => w.num === cur.num && w.dir === cur.dir) : -1;
    idx = (idx + delta + words.length) % words.length;
    const w = words[idx];
    this.moveTo(w.cells[0][0], w.cells[0][1], w.dir);
  }

  // -------------------------------------------------------------------------
  // Mutations (all save undo state first)
  // -------------------------------------------------------------------------

  _saveUndo() {
    this.lastState = {
      cells: this.cells.map(row => row.map(c => ({ ...c }))),
      clues: JSON.parse(JSON.stringify(this.clues)),
    };
  }

  undo() {
    if (!this.lastState) return;
    this.cells = this.lastState.cells;
    this.clues = this.lastState.clues;
    this.lastState = null;
    this._renderAll();
    this._renderHighlights();
    this._fireSelectionChange();
    this._fireCellChange();
    this._autosave();
  }

  setLetter(r, c, letter) {
    if (this.cells[r][c].black) return;
    this._saveUndo();
    this.cells[r][c].letter = letter.toUpperCase();
    this._renderCell(r, c);
    this._renderHighlights();
    this._fireCellChange();
    this._autosave();
  }

  clearLetter(r, c) {
    if (this.cells[r][c].black) return;
    this._saveUndo();
    this.cells[r][c].letter = "";
    this._renderCell(r, c);
    this._renderHighlights();
    this._fireCellChange();
    this._autosave();
  }

  toggleBlack(r, c) {
    this._saveUndo();
    this.cells[r][c].black = !this.cells[r][c].black;
    if (this.cells[r][c].black) this.cells[r][c].letter = "";
    this._renderAll();
    this._renderHighlights();
    this._fireCellChange();
    this._autosave();
  }

  setBlack(r, c, isBlack) {
    if (this.cells[r][c].black === isBlack) return;
    this.toggleBlack(r, c);
  }

  // Fill an entire word from a string (used by search.js and solver.js)
  // Returns list of [r,c] positions that had a conflict with existing letters.
  fillWord(word, str, opts = {}) {
    const { preview = false } = opts; // preview=true adds .candidate class only
    if (str.length !== word.cells.length) return [];

    const conflicts = [];
    for (let i = 0; i < word.cells.length; i++) {
      const [r, c] = word.cells[i];
      const existing = this.cells[r][c].letter;
      if (existing && existing !== str[i].toUpperCase()) conflicts.push([r, c]);
    }

    if (preview) {
      // Just add visual highlight, don't commit
      for (let i = 0; i < word.cells.length; i++) {
        const [r, c] = word.cells[i];
        const td = this._td(r, c);
        td.classList.add("candidate");
        td.querySelector(".letter").textContent = str[i].toUpperCase();
      }
      return conflicts;
    }

    if (!conflicts.length || opts.force) {
      this._saveUndo();
      for (let i = 0; i < word.cells.length; i++) {
        const [r, c] = word.cells[i];
        this.cells[r][c].letter = str[i].toUpperCase();
        this._renderCell(r, c);
      }
      this._renderHighlights();
      this._fireCellChange();
      this._autosave();
    }
    return conflicts;
  }

  // Commit previewed candidate cells (called by solver.js on Godta)
  commitCandidates(candidates) {
    // candidates: [{word, str}]
    this._saveUndo();
    for (const { word, str } of candidates) {
      for (let i = 0; i < word.cells.length; i++) {
        const [r, c] = word.cells[i];
        this.cells[r][c].letter = str[i].toUpperCase();
      }
    }
    this._renderAll();
    this._renderHighlights();
    this._fireCellChange();
    this._autosave();
  }

  // Discard previewed candidates — re-render from model (DOM previews are cleared)
  discardCandidates() {
    this._renderAll();
    this._renderHighlights();
  }

  // Set clue text for the active word
  setClueText(num, dir, text) {
    if (this.clues[dir][num]) {
      this.clues[dir][num].text = text;
      this._autosave();
    }
  }

  // -------------------------------------------------------------------------
  // New grid
  // -------------------------------------------------------------------------

  newGrid(rows, cols) {
    this._saveUndo();
    this._buildCells(rows, cols);
    this.curRow = 0;
    this.curCol = 0;
    this.dir = "across";
    this._renderTable();
    this._renderHighlights();
    this._fireSelectionChange();
    this._autosave();
  }

  // -------------------------------------------------------------------------
  // Keyboard handling
  // -------------------------------------------------------------------------

  _bindKeys() {
    document.addEventListener("keydown", (e) => this._onKey(e));
  }

  _onKey(e) {
    // Let Escape always return focus to the grid
    if (e.key === "Escape") {
      document.getElementById("grid").focus();
      e.preventDefault();
      return;
    }

    // Ctrl+Z: undo
    if (e.key === "z" && e.ctrlKey && !e.shiftKey) {
      this.undo();
      e.preventDefault();
      return;
    }

    // Ctrl+Shift+S: solve all (solver.js listens for custom event)
    if (e.key === "S" && e.ctrlKey && e.shiftKey) {
      document.dispatchEvent(new CustomEvent("solveAll"));
      e.preventDefault();
      return;
    }

    // Keys below only fire when focus is on the grid table or a cell
    const activeEl = document.activeElement;
    const gridFocused = activeEl === document.getElementById("grid")
      || document.getElementById("grid").contains(activeEl);

    // Tab / Shift+Tab navigate words regardless of focus (except when in a text input)
    if (e.key === "Tab" && activeEl.tagName !== "INPUT") {
      this._jumpWord(e.shiftKey ? -1 : 1);
      e.preventDefault();
      return;
    }

    if (!gridFocused) return;

    switch (e.key) {
      case "ArrowLeft":
        if (this.dir === "across") this._retreat();
        else this.moveTo(this.curRow, this.curCol, "across");
        e.preventDefault(); break;

      case "ArrowRight":
        if (this.dir === "across") this._advance();
        else this.moveTo(this.curRow, this.curCol, "across");
        e.preventDefault(); break;

      case "ArrowUp":
        if (this.dir === "down") this._retreat();
        else this.moveTo(this.curRow, this.curCol, "down");
        e.preventDefault(); break;

      case "ArrowDown":
        if (this.dir === "down") this._advance();
        else this.moveTo(this.curRow, this.curCol, "down");
        e.preventDefault(); break;

      case "Enter":
        this.dir = this.dir === "across" ? "down" : "across";
        this._renderHighlights();
        this._fireSelectionChange();
        e.preventDefault(); break;

      case " ":
        this.toggleBlack(this.curRow, this.curCol);
        e.preventDefault(); break;

      case "Backspace":
        if (this.cells[this.curRow][this.curCol].letter) {
          this.clearLetter(this.curRow, this.curCol);
        } else {
          this._retreat();
          this.clearLetter(this.curRow, this.curCol);
        }
        e.preventDefault(); break;

      case "Delete":
        this.clearLetter(this.curRow, this.curCol);
        e.preventDefault(); break;

      default: {
        // Letter input — single printable character
        if (e.key.length === 1 && !e.ctrlKey && !e.metaKey) {
          const letter = e.key.toUpperCase();
          // Accept A-Z plus Norwegian Æ Ø Å
          if (/^[A-ZÆØÅ]$/.test(letter)) {
            if (!this.cells[this.curRow][this.curCol].black) {
              this.setLetter(this.curRow, this.curCol, letter);
              this._advance();
            }
          }
          e.preventDefault();
        }
      }
    }
  }

  // -------------------------------------------------------------------------
  // Mouse handling
  // -------------------------------------------------------------------------

  _onClick(e, r, c) {
    document.getElementById("grid").focus();
    if (this.cells[r][c].black) {
      // Click on black cell → make it open
      this.setBlack(r, c, false);
      this.moveTo(r, c);
      return;
    }
    // Same cell: toggle direction
    if (r === this.curRow && c === this.curCol) {
      this.dir = this.dir === "across" ? "down" : "across";
      this._renderHighlights();
      this._fireSelectionChange();
    } else {
      this.moveTo(r, c);
    }
  }

  _onRightClick(e, r, c) {
    e.preventDefault();
    if (!this.cells[r][c].black) {
      this.setBlack(r, c, true);
    }
  }

  // -------------------------------------------------------------------------
  // Toolbar bindings
  // -------------------------------------------------------------------------

  _bindToolbar() {
    document.getElementById("new-grid-btn").addEventListener("click", () => {
      const cols = parseInt(document.getElementById("input-cols").value, 10) || 13;
      const rows = parseInt(document.getElementById("input-rows").value, 10) || 13;
      this.newGrid(rows, cols);
    });
  }

  // -------------------------------------------------------------------------
  // Autosave / restore (localStorage)
  // -------------------------------------------------------------------------

  _autosave() {
    try {
      localStorage.setItem("kryssord_autosave", JSON.stringify(this._serialize()));
    } catch (_) {}
  }

  _loadAutosave() {
    try {
      const raw = localStorage.getItem("kryssord_autosave");
      if (!raw) return;
      const data = JSON.parse(raw);
      if (confirm("Gjenoppta siste økt?")) {
        this._deserialize(data);
      } else {
        localStorage.removeItem("kryssord_autosave");
      }
    } catch (_) {}
  }

  _serialize() {
    return {
      version: "kryssord/1",
      dimensions: { width: this.cols, height: this.rows },
      cells: this.cells.map(row => row.map(c => ({
        black: c.black,
        letter: c.letter,
      }))),
      clues: {
        across: Object.fromEntries(
          Object.entries(this.clues.across).map(([n, v]) => [n, { text: v.text }])
        ),
        down: Object.fromEntries(
          Object.entries(this.clues.down).map(([n, v]) => [n, { text: v.text }])
        ),
      },
    };
  }

  _deserialize(data) {
    const { dimensions, cells, clues } = data;
    this._buildCells(dimensions.height, dimensions.width);
    for (let r = 0; r < this.rows; r++)
      for (let c = 0; c < this.cols; c++) {
        this.cells[r][c].black  = cells[r][c].black  ?? false;
        this.cells[r][c].letter = cells[r][c].letter ?? "";
      }
    this._numberCells();
    // Restore clue texts by matching word starts
    for (const dir of ["across", "down"]) {
      const saved = clues?.[dir] ?? {};
      for (const [num, entry] of Object.entries(this.clues[dir])) {
        if (saved[num]) entry.text = saved[num].text ?? "";
      }
    }
    this._renderTable();
    this._renderHighlights();
    this._fireSelectionChange();
  }

  // -------------------------------------------------------------------------
  // Event callbacks (pub/sub for search.js and solver.js)
  // -------------------------------------------------------------------------

  onSelectionChange(fn) { this._onSelectionChange.push(fn); }
  onCellChange(fn)      { this._onCellChange.push(fn); }

  _fireSelectionChange() { this._onSelectionChange.forEach(fn => fn(this)); }
  _fireCellChange()      { this._onCellChange.forEach(fn => fn(this)); }
}

// Instantiate and expose globally so search.js and solver.js can import it
window.grid = new Grid();
