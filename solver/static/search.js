/**
 * search.js — sidebar search panel
 *
 * Depends on window.grid (set by grid.js).
 * Manages: clue input, pattern boxes, /api/lookup calls, results list,
 *          conflict handling, settings panel (cache clear).
 */

(function () {
  // -------------------------------------------------------------------------
  // DOM refs
  // -------------------------------------------------------------------------
  const wordIdEl      = document.getElementById("word-id");
  const clueInput     = document.getElementById("clue-input");
  const patternRow    = document.getElementById("pattern-row");
  const searchBtn     = document.getElementById("search-btn");
  const spinner       = document.getElementById("spinner");
  const cacheBadge    = document.getElementById("cache-badge");
  const resultsList   = document.getElementById("results-list");
  const resultsHeader = document.getElementById("results-header");
  const clearCacheBtn = document.getElementById("clear-cache-btn");
  const cacheStats    = document.getElementById("cache-stats");
  const settingsBody  = document.getElementById("settings-body");
  const settingsToggle= document.getElementById("settings-toggle");
  const banner        = document.getElementById("banner");
  const bannerText    = document.getElementById("banner-text");
  const bannerAccept  = document.getElementById("banner-accept");
  const bannerDiscard = document.getElementById("banner-discard");

  // -------------------------------------------------------------------------
  // State
  // -------------------------------------------------------------------------
  let currentWord   = null;  // word object from grid.activeWord()
  let patternValues = [];    // user-editable parallel array to currentWord.cells
  let focusedResult = -1;    // index into results list for keyboard nav

  // -------------------------------------------------------------------------
  // Grid callbacks
  // -------------------------------------------------------------------------
  window.grid.onSelectionChange((g) => {
    currentWord = g.activeWord();
    _updateWordLabel();
    _rebuildPattern();
    _loadClue();
    _updateSearchBtn();
    _clearResults();
  });

  // Re-sync pattern when letters change externally (e.g. solver fills a crossing word)
  window.grid.onCellChange(() => {
    if (!currentWord) return;
    _rebuildPattern();
  });

  // -------------------------------------------------------------------------
  // Word label
  // -------------------------------------------------------------------------
  function _updateWordLabel() {
    if (!currentWord) { wordIdEl.textContent = "—"; return; }
    const arrow = currentWord.dir === "across" ? "→" : "↓";
    wordIdEl.textContent = `${currentWord.num} ${arrow}`;
  }

  // -------------------------------------------------------------------------
  // Clue input
  // -------------------------------------------------------------------------
  function _loadClue() {
    if (!currentWord) { clueInput.value = ""; return; }
    const entry = window.grid.clues[currentWord.dir][currentWord.num];
    clueInput.value = entry ? (entry.text || "") : "";
  }

  function _saveClue() {
    if (!currentWord) return;
    window.grid.setClueText(currentWord.num, currentWord.dir, clueInput.value.trim());
  }

  clueInput.addEventListener("input", () => { _saveClue(); _updateSearchBtn(); });
  clueInput.addEventListener("blur",  _saveClue);
  clueInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter")     { e.preventDefault(); _doSearch(); }
    if (e.key === "Escape")    { document.getElementById("grid").focus(); }
    if (e.key === "ArrowDown" && resultsList.children.length) {
      e.preventDefault(); _focusResult(0);
    }
  });

  // -------------------------------------------------------------------------
  // Pattern boxes
  // -------------------------------------------------------------------------
  function _rebuildPattern() {
    patternRow.innerHTML = "";
    patternValues = [];
    if (!currentWord) return;

    currentWord.cells.forEach(([r, c], i) => {
      const letter = window.grid.cells[r][c].letter;
      const val    = letter || "";
      patternValues.push(val);

      const input = document.createElement("input");
      input.className   = "pat-box " + (val ? "filled" : "empty");
      input.maxLength   = 1;
      input.value       = val;
      input.placeholder = "_";
      input.dataset.i   = i;

      input.addEventListener("input", (e) => {
        const raw   = e.target.value.toUpperCase();
        const clean = /^[A-ZÆØÅ?*]$/.test(raw) ? raw : "";
        e.target.value     = clean;
        patternValues[i]   = clean;
        e.target.className = "pat-box " + (clean ? "filled" : "empty");
        _updateSearchBtn();
      });

      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter")      { e.preventDefault(); _doSearch(); }
        if (e.key === "Escape")     { document.getElementById("grid").focus(); }
        if (e.key === "ArrowRight") { e.preventDefault(); patternRow.children[i + 1]?.focus(); }
        if (e.key === "ArrowLeft")  { e.preventDefault(); patternRow.children[i - 1]?.focus(); }
        if (e.key === "ArrowDown" && resultsList.children.length) {
          e.preventDefault(); _focusResult(0);
        }
      });

      patternRow.appendChild(input);
    });
  }

  // Build the b= parameter string. Returns "" if word is fully known (no wildcards needed).
  function _patternString() {
    const s = patternValues.map(v => v || "?").join("");
    // Only send pattern if it adds information (contains a known letter or explicit wildcard)
    const hasInfo = /[A-ZÆØÅ]/.test(s) || s.includes("*");
    // Always send if there are known letters (helps narrow results);
    // send ? pattern only if word isn't entirely blank (all ? would just add noise)
    return hasInfo || s.length > 0 ? s : "";
  }

  // -------------------------------------------------------------------------
  // Search button state
  // -------------------------------------------------------------------------
  function _updateSearchBtn() {
    const clue    = clueInput.value.trim();
    const pattern = _patternString();
    searchBtn.disabled = (!clue && !pattern);
  }

  // -------------------------------------------------------------------------
  // Search
  // -------------------------------------------------------------------------
  searchBtn.addEventListener("click", _doSearch);

  async function _doSearch() {
    if (searchBtn.disabled) return;

    const clue    = clueInput.value.trim();
    const pattern = _patternString();
    if (!clue && !pattern) return;

    _setLoading(true);
    _clearResults();

    try {
      const data = await window.api.lookup(clue, pattern);
      _renderResults(data.words, data.cached);
    } catch (err) {
      _showError(err.message || "Kunne ikke nå serveren");
    } finally {
      _setLoading(false);
    }
  }

  function _setLoading(on) {
    searchBtn.disabled       = on;
    spinner.style.display    = on ? "inline-block" : "none";
    if (!on) _updateSearchBtn();
  }

  // -------------------------------------------------------------------------
  // Results
  // -------------------------------------------------------------------------
  function _clearResults() {
    resultsList.innerHTML    = "";
    resultsHeader.textContent= "Resultater";
    cacheBadge.textContent   = "";
    focusedResult            = -1;
  }

  function _showError(msg) {
    resultsHeader.textContent = "Feil";
    const li = document.createElement("li");
    li.style.cssText = "color:#c00;font-size:0.82rem;cursor:default";
    li.textContent   = msg;
    resultsList.appendChild(li);
  }

  function _renderResults(words, cached) {
    resultsHeader.textContent = `Resultater (${words.length})`;
    cacheBadge.textContent    = cached ? "💾 fra hurtigbuffer" : "";

    if (!words.length) {
      const li = document.createElement("li");
      li.style.cssText = "color:#888;font-style:italic;cursor:default";
      li.textContent   = "Ingen treff";
      resultsList.appendChild(li);
      return;
    }

    words.forEach((w, idx) => {
      const li = document.createElement("li");
      li.tabIndex = 0;

      const wordSpan    = document.createElement("span");
      wordSpan.className = "word-text";
      wordSpan.textContent = w.word.toUpperCase();

      const lenSpan    = document.createElement("span");
      lenSpan.className = "word-len";
      lenSpan.textContent = w.word.length;

      li.appendChild(wordSpan);
      li.appendChild(lenSpan);

      li.addEventListener("click",   ()  => _applyResult(w.word));
      li.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); _applyResult(w.word); }
        if (e.key === "ArrowDown")  { e.preventDefault(); _focusResult(idx + 1); }
        if (e.key === "ArrowUp")    { e.preventDefault(); _focusResult(idx - 1); }
        if (e.key === "Escape")     { document.getElementById("grid").focus(); }
      });

      resultsList.appendChild(li);
    });

    _focusResult(0);
  }

  function _focusResult(idx) {
    const items = Array.from(resultsList.querySelectorAll("li[tabindex]"));
    if (!items.length) return;
    idx = Math.max(0, Math.min(items.length - 1, idx));
    focusedResult = idx;
    items.forEach((el, i) => el.classList.toggle("focused", i === idx));
    items[idx].focus();
  }

  // -------------------------------------------------------------------------
  // Apply result to grid
  // -------------------------------------------------------------------------
  function _applyResult(word) {
    if (!currentWord) return;

    if (word.length !== currentWord.cells.length) {
      showBanner(`«${word.toUpperCase()}» passer ikke (${word.length} ≠ ${currentWord.cells.length} bokstaver)`, []);
      return;
    }

    const conflicts = window.grid.fillWord(currentWord, word);

    if (conflicts.length) {
      // Mark conflicting cells red
      conflicts.forEach(([r, c]) => window.grid._td(r, c).classList.add("conflict"));
      showBanner(
        `${conflicts.length} konflikt${conflicts.length > 1 ? "er" : ""} – bruk likevel?`,
        [
          { label: "Ja",  action: () => {
              conflicts.forEach(([r, c]) => window.grid._td(r, c).classList.remove("conflict"));
              window.grid.fillWord(currentWord, word, { force: true });
              document.getElementById("grid").focus();
          }},
          { label: "Nei", action: () => {
              conflicts.forEach(([r, c]) => window.grid._td(r, c).classList.remove("conflict"));
          }},
        ]
      );
    } else {
      document.getElementById("grid").focus();
    }
  }

  // -------------------------------------------------------------------------
  // Banner — shared with solver.js via window.showBanner
  // buttons: [{label, action}, ...]  — 0 buttons = auto-dismiss
  // -------------------------------------------------------------------------
  function showBanner(text, buttons = []) {
    bannerText.textContent = text;

    if (buttons[0]) {
      bannerAccept.textContent = buttons[0].label;
      bannerAccept.onclick     = () => { buttons[0].action(); banner.classList.add("hidden"); };
      bannerAccept.style.display = "";
    } else {
      bannerAccept.style.display = "none";
    }

    if (buttons[1]) {
      bannerDiscard.textContent = buttons[1].label;
      bannerDiscard.onclick     = () => { buttons[1].action(); banner.classList.add("hidden"); };
      bannerDiscard.style.display = "";
    } else {
      bannerDiscard.style.display = "none";
    }

    banner.classList.remove("hidden");
    if (!buttons.length) setTimeout(() => banner.classList.add("hidden"), 6000);
  }

  // Expose for solver.js
  window.showBanner = showBanner;

  // -------------------------------------------------------------------------
  // Settings panel
  // -------------------------------------------------------------------------
  settingsToggle.addEventListener("click", () => {
    settingsBody.classList.toggle("open");
    if (settingsBody.classList.contains("open")) _loadCacheStats();
  });

  async function _loadCacheStats() {
    try {
      const res  = await fetch("/api/cache/stats");
      const data = await res.json();
      cacheStats.textContent = `${data.entries} oppslag i hurtigbuffer`;
    } catch (_) { cacheStats.textContent = ""; }
  }

  clearCacheBtn.addEventListener("click", async () => {
    try {
      const res  = await fetch("/api/cache", { method: "DELETE" });
      const data = await res.json();
      cacheStats.textContent = `Tømt — ${data.cleared} slettet`;
      setTimeout(_loadCacheStats, 2500);
    } catch (_) { cacheStats.textContent = "Feil ved tømming"; }
  });

  // -------------------------------------------------------------------------
  // Boot
  // -------------------------------------------------------------------------
  _updateWordLabel();
  _updateSearchBtn();

})();
