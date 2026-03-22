/**
 * solver.js — "Løs alle" (Solve All) logic
 *
 * Depends on window.grid (grid.js) and window.showBanner (search.js).
 * Triggered by the toolbar button or Ctrl+Shift+S.
 *
 * Flow:
 *   1. Collect all unsolved words that have a clue, sorted by priority.
 *   2. Query /api/lookup for each sequentially (so earlier fills inform later patterns).
 *   3. Words with exactly 1 result and no conflicts → candidate list.
 *   4. Preview all candidates with yellow .candidate highlight progressively.
 *   5. Show banner: Godta (commit) or Forkast (discard).
 */

(function () {

  // -------------------------------------------------------------------------
  // Entry points
  // -------------------------------------------------------------------------

  document.getElementById("solve-all-btn").addEventListener("click", runSolver);
  document.addEventListener("solveAll", runSolver);  // Ctrl+Shift+S from grid.js

  // -------------------------------------------------------------------------
  // Main solver
  // -------------------------------------------------------------------------

  async function runSolver() {
    const g = window.grid;

    // Disable button while running
    const btn = document.getElementById("solve-all-btn");
    btn.disabled = true;
    btn.textContent = "⏳ Løser…";

    // Snapshot pre-solve state for Forkast
    const snapshot = _snapshot(g);

    const candidates = [];   // { word, str } — unambiguous hits
    let skipped = 0;         // words with 0 or >1 results, or no clue

    // Get sorted candidate words
    const words = _sortedWords(g);

    for (const word of words) {
      const clueEntry = g.clues[word.dir][word.num];
      const clue = clueEntry?.text?.trim() || "";
      if (!clue) { skipped++; continue; }

      // Build pattern using current grid state (including any already-previewed candidates)
      // Use only '?' for unknowns — never '*' in automated lookups
      const pattern = word.cells.map(([r, c]) => g.cells[r][c].letter || "?").join("");
      const allUnknown = !pattern.includes("?") === false && !/[A-ZÆØÅ]/.test(pattern);

      // Check if word is already fully solved
      if (!pattern.includes("?")) { skipped++; continue; }

      // Fetch
      let data;
      try {
        const params = new URLSearchParams({ a: clue, b: pattern });
        const res = await fetch(`/api/lookup?${params}`);
        if (!res.ok) { skipped++; continue; }
        data = await res.json();
      } catch (_) { skipped++; continue; }

      if (data.words.length !== 1) { skipped++; continue; }

      const str = data.words[0].word.toUpperCase();

      // Length guard
      if (str.length !== word.cells.length) { skipped++; continue; }

      // Conflict check against committed grid letters (not preview)
      const hasConflict = word.cells.some(([r, c], i) => {
        const existing = g.cells[r][c].letter;
        return existing && existing !== str[i];
      });
      if (hasConflict) { skipped++; continue; }

      // Preview progressively — show yellow fill immediately
      _previewWord(g, word, str);
      candidates.push({ word, str });
    }

    // Re-enable button
    btn.disabled = false;
    btn.textContent = "🤖 Løs alle";

    if (!candidates.length) {
      window.showBanner("Ingen entydige løsninger funnet.", []);
      return;
    }

    const n = candidates.length;
    const m = skipped;
    const msg = `Fant ${n} entydige løsning${n !== 1 ? "er" : ""}. ${m} ord uten entydig løsning.`;

    window.showBanner(msg, [
      {
        label: "✓ Godta",
        action: () => {
          g.commitCandidates(candidates);
        },
      },
      {
        label: "✗ Forkast",
        action: () => {
          _restoreSnapshot(g, snapshot);
        },
      },
    ]);
  }

  // -------------------------------------------------------------------------
  // Word priority sort
  // Order: % solved desc, length desc, row asc, col asc, across before down
  // -------------------------------------------------------------------------

  function _sortedWords(g) {
    const words = [];

    for (const [numStr, entry] of Object.entries(g.clues.across)) {
      if (entry.cells.length >= 2) words.push({ num: +numStr, dir: "across", ...entry });
    }
    for (const [numStr, entry] of Object.entries(g.clues.down)) {
      if (entry.cells.length >= 2) words.push({ num: +numStr, dir: "down", ...entry });
    }

    words.sort((a, b) => {
      // 1. % solved letters — descending
      const pctA = _pctSolved(g, a);
      const pctB = _pctSolved(g, b);
      if (pctB !== pctA) return pctB - pctA;

      // 2. Word length — descending
      if (b.cells.length !== a.cells.length) return b.cells.length - a.cells.length;

      // 3. Row of first cell — ascending
      const rowA = a.cells[0][0], rowB = b.cells[0][0];
      if (rowA !== rowB) return rowA - rowB;

      // 4. Col of first cell — ascending
      const colA = a.cells[0][1], colB = b.cells[0][1];
      if (colA !== colB) return colA - colB;

      // 5. Orientation — across (0) before down (1)
      return (a.dir === "across" ? 0 : 1) - (b.dir === "across" ? 0 : 1);
    });

    return words;
  }

  function _pctSolved(g, word) {
    const filled = word.cells.filter(([r, c]) => g.cells[r][c].letter).length;
    return filled / word.cells.length;
  }

  // -------------------------------------------------------------------------
  // Preview — yellow highlight without committing to model
  // -------------------------------------------------------------------------

  function _previewWord(g, word, str) {
    for (let i = 0; i < word.cells.length; i++) {
      const [r, c] = word.cells[i];
      const td = g._td(r, c);
      if (!td) continue;
      td.classList.add("candidate");
      // Only show the preview letter if the cell is currently empty
      if (!g.cells[r][c].letter) {
        const letSpan = td.querySelector(".letter");
        if (letSpan) letSpan.textContent = str[i];
      }
    }
  }

  // -------------------------------------------------------------------------
  // Snapshot / restore for Forkast
  // -------------------------------------------------------------------------

  function _snapshot(g) {
    return {
      cells: g.cells.map(row => row.map(c => ({ ...c }))),
      clues: JSON.parse(JSON.stringify(g.clues)),
    };
  }

  function _restoreSnapshot(g, snapshot) {
    g.cells = snapshot.cells;
    g.clues = snapshot.clues;
    g._renderAll();
    g._renderHighlights();
    g._fireSelectionChange();
  }

})();
