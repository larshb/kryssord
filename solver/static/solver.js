/**
 * solver.js — "Løs alle" (Solve All) logic
 *
 * Depends on window.grid (grid.js) and window.showBanner (search.js).
 * Triggered by the toolbar button or Ctrl+Shift+S.
 *
 * Flow:
 *   1. Run a solve pass — query all unsolved words that have clues.
 *   2. Collect unambiguous hits (exactly 1 result, no conflict) → preview yellow.
 *   3. If candidates found → show Godta/Forkast banner, done.
 *   4. If no candidates AND there are words missing clues → start clue prompt cycle:
 *        - Jump cursor to first missing-clue word, highlight it
 *        - Show inline clue input in the banner footer
 *        - Enter saves clue + advances to next; Esc aborts cycle
 *        - After all prompted (or Esc), re-run from step 1
 *   5. Repeat until no new candidates and no missing clues remain.
 */

(function () {

  // -------------------------------------------------------------------------
  // Entry points
  // -------------------------------------------------------------------------

  document.getElementById("solve-all-btn").addEventListener("click", runSolver);
  document.addEventListener("solveAll", runSolver);  // Ctrl+Shift+S from grid.js

  // -------------------------------------------------------------------------
  // Main solver — outer loop
  // -------------------------------------------------------------------------

  async function runSolver() {
    const g   = window.grid;
    const btn = document.getElementById("solve-all-btn");

    btn.disabled    = true;
    btn.textContent = "⏳ Løser…";

    const snapshot = _snapshot(g);  // pre-solve snapshot for Forkast

    let totalCandidates = [];
    let iterations = 0;
    const MAX_ITER = 10;  // safety cap

    while (iterations++ < MAX_ITER) {
      // --- Solve pass ---
      const { candidates, skipped } = await _solvePass(g);
      totalCandidates = totalCandidates.concat(candidates);

      if (candidates.length > 0) {
        // New progress — show Godta/Forkast and stop here.
        // User can re-run after accepting if they want another pass.
        btn.disabled    = false;
        btn.textContent = "🤖 Løs alle";

        const n   = totalCandidates.length;
        const m   = skipped;
        const msg = `Fant ${n} entydige løsning${n !== 1 ? "er" : ""}. ${m} ord uten entydig løsning.`;

        window.showBanner(msg, [
          { label: "✓ Godta",   action: () => g.commitCandidates(totalCandidates) },
          { label: "✗ Forkast", action: () => _restoreSnapshot(g, snapshot) },
        ]);
        return;
      }

      // --- No new candidates this pass ---
      // Find words that are unsolved and have no clue at all
      const missingClueWords = _missingClueWords(g);

      if (!missingClueWords.length) {
        // Nothing left to do
        break;
      }

      // --- Prompt cycle for missing clues ---
      btn.textContent = "⏳ Venter på ledetekst…";
      const gotAny = await _promptMissingClues(g, missingClueWords);

      if (!gotAny) break;  // user pressed Esc without entering any clues
      // Loop: re-run solve pass with newly entered clues
    }

    btn.disabled    = false;
    btn.textContent = "🤖 Løs alle";

    if (!totalCandidates.length) {
      window.showBanner("Ingen entydige løsninger funnet.", []);
    }
  }

  // -------------------------------------------------------------------------
  // Single solve pass — returns { candidates, skipped }
  // -------------------------------------------------------------------------

  async function _solvePass(g) {
    const candidates = [];
    let skipped = 0;

    for (const word of _sortedWords(g)) {
      const clueEntry = g.clues[word.dir][word.num];
      const clue = clueEntry?.text?.trim() || "";
      if (!clue) { skipped++; continue; }

      const pattern = word.cells.map(([r, c]) => g.cells[r][c].letter || "?").join("");
      if (!pattern.includes("?")) { skipped++; continue; }  // already solved

      let data;
      try {
        const params = new URLSearchParams({ a: clue, b: pattern });
        const res = await fetch(`/api/lookup?${params}`);
        if (!res.ok) { skipped++; continue; }
        data = await res.json();
      } catch (_) { skipped++; continue; }

      if (data.words.length !== 1) { skipped++; continue; }

      const str = data.words[0].word.toUpperCase();
      if (str.length !== word.cells.length) { skipped++; continue; }

      const hasConflict = word.cells.some(([r, c], i) => {
        const existing = g.cells[r][c].letter;
        return existing && existing !== str[i];
      });
      if (hasConflict) { skipped++; continue; }

      _previewWord(g, word, str);
      candidates.push({ word, str });
    }

    return { candidates, skipped };
  }

  // -------------------------------------------------------------------------
  // Missing-clue prompt cycle
  //
  // For each word in the list:
  //   - Jump cursor to the word
  //   - Show a banner with an inline text input + Enter/Esc instructions
  //   - Wait for user to press Enter (save + next) or Esc (abort cycle)
  //
  // Returns true if at least one clue was entered, false if Esc on first word.
  // -------------------------------------------------------------------------

  function _promptMissingClues(g, words) {
    return new Promise((resolve) => {
      let idx       = 0;
      let anyEntered = false;

      function promptWord(word) {
        // Jump cursor to word start
        g.moveTo(word.cells[0][0], word.cells[0][1], word.dir);

        // Highlight the word distinctly (reuse word-hl; cursor already on it)
        // The normal highlight from moveTo is sufficient.

        const arrow = word.dir === "across" ? "→" : "↓";
        const label = `Ledetekst for ${word.num} ${arrow} (${word.cells.length} bokstaver):`;

        _showCluePrompt(label, {
          onConfirm: (text) => {
            if (text.trim()) {
              g.setClueText(word.num, word.dir, text.trim());
              anyEntered = true;
            }
            idx++;
            if (idx < words.length) {
              promptWord(words[idx]);
            } else {
              _hideCluePrompt();
              resolve(anyEntered);
            }
          },
          onAbort: () => {
            _hideCluePrompt();
            resolve(anyEntered);
          },
        });
      }

      promptWord(words[0]);
    });
  }

  // -------------------------------------------------------------------------
  // Inline clue prompt — replaces the banner with an input field
  // -------------------------------------------------------------------------

  // Lazily build the prompt UI once and reuse it
  let _promptEl = null;

  function _ensurePromptEl() {
    if (_promptEl) return;

    // We inject a second banner-like bar above the existing #banner
    _promptEl = document.createElement("div");
    _promptEl.id = "clue-prompt";
    _promptEl.style.cssText = `
      position: fixed;
      bottom: 16px;
      left: 50%;
      transform: translateX(-50%);
      background: #fff;
      border: 1px solid #aaa;
      border-radius: 6px;
      box-shadow: 0 4px 16px rgba(0,0,0,0.15);
      padding: 10px 14px;
      font-size: 0.88rem;
      display: none;
      align-items: center;
      gap: 8px;
      z-index: 101;
      white-space: nowrap;
    `;

    _promptEl.innerHTML = `
      <span id="clue-prompt-label" style="color:#555"></span>
      <input id="clue-prompt-input" type="text"
             autocomplete="off" spellcheck="false"
             style="padding:4px 7px;border:1px solid #ccc;border-radius:4px;
                    font-size:0.88rem;width:200px;outline:none;font-family:system-ui,sans-serif">
      <span style="color:#aaa;font-size:0.78rem">[Enter=neste &nbsp; Esc=avslutt]</span>
    `;

    document.body.appendChild(_promptEl);
  }

  function _showCluePrompt(label, { onConfirm, onAbort }) {
    _ensurePromptEl();

    const labelEl = document.getElementById("clue-prompt-label");
    const input   = document.getElementById("clue-prompt-input");

    labelEl.textContent = label;
    input.value         = "";
    _promptEl.style.display = "flex";
    input.focus();

    // Remove any previous listeners by replacing the node
    const fresh = input.cloneNode(true);
    input.parentNode.replaceChild(fresh, input);

    fresh.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        onConfirm(fresh.value);
      }
      if (e.key === "Escape") {
        e.preventDefault();
        onAbort();
      }
    });

    // Re-focus after a tick so the keydown from triggering Enter doesn't bleed through
    setTimeout(() => fresh.focus(), 0);
  }

  function _hideCluePrompt() {
    if (_promptEl) _promptEl.style.display = "none";
    // Return focus to grid after prompting
    document.getElementById("grid").focus();
  }

  // -------------------------------------------------------------------------
  // Words missing a clue (unsolved, no clue text)
  // Sorted by same priority as solve pass so the prompt order feels natural
  // -------------------------------------------------------------------------

  function _missingClueWords(g) {
    return _sortedWords(g).filter((word) => {
      const entry = g.clues[word.dir][word.num];
      const clue  = entry?.text?.trim() || "";
      const pattern = word.cells.map(([r, c]) => g.cells[r][c].letter || "?").join("");
      return !clue && pattern.includes("?");  // no clue and not fully solved
    });
  }

  // -------------------------------------------------------------------------
  // Word priority sort
  // Order: % solved desc, length desc, row asc, col asc, across before down
  // -------------------------------------------------------------------------

  function _sortedWords(g) {
    const words = [];
    for (const [n, e] of Object.entries(g.clues.across))
      if (e.cells.length >= 2) words.push({ num: +n, dir: "across", ...e });
    for (const [n, e] of Object.entries(g.clues.down))
      if (e.cells.length >= 2) words.push({ num: +n, dir: "down",   ...e });

    words.sort((a, b) => {
      const pctDiff = _pctSolved(g, b) - _pctSolved(g, a);
      if (pctDiff) return pctDiff;
      if (b.cells.length !== a.cells.length) return b.cells.length - a.cells.length;
      if (a.cells[0][0] !== b.cells[0][0]) return a.cells[0][0] - b.cells[0][0];
      if (a.cells[0][1] !== b.cells[0][1]) return a.cells[0][1] - b.cells[0][1];
      return (a.dir === "across" ? 0 : 1) - (b.dir === "across" ? 0 : 1);
    });
    return words;
  }

  function _pctSolved(g, word) {
    return word.cells.filter(([r, c]) => g.cells[r][c].letter).length / word.cells.length;
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
      if (!g.cells[r][c].letter) {
        const letSpan = td.querySelector(".letter");
        if (letSpan) letSpan.textContent = str[i];
      }
    }
  }

  // -------------------------------------------------------------------------
  // Snapshot / restore
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
