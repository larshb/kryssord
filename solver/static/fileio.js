/**
 * fileio.js — save and load grid files
 *
 * Save: serialises grid to ipuz-inspired JSON and triggers a browser download.
 * Load: opens a file picker, reads the JSON, deserialises into the grid.
 *
 * Depends on window.grid (grid.js).
 * No backend calls — pure client-side file I/O.
 */

(function () {

  // -------------------------------------------------------------------------
  // Save — download as .json
  // -------------------------------------------------------------------------

  document.getElementById("save-btn").addEventListener("click", _save);

  function _save() {
    const data = _serialize();
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    const url  = URL.createObjectURL(blob);

    const a    = document.createElement("a");
    a.href     = url;
    a.download = _filename(data.title);
    a.click();

    URL.revokeObjectURL(url);
  }

  function _filename(title) {
    const base = (title || "kryssord").replace(/[^a-zæøå0-9]/gi, "_").toLowerCase();
    const ts   = new Date().toISOString().slice(0, 10);   // YYYY-MM-DD
    return `${base}_${ts}.json`;
  }

  // -------------------------------------------------------------------------
  // Load — file picker → deserialise
  // -------------------------------------------------------------------------

  // Hidden file input reused on every load click
  const fileInput = document.createElement("input");
  fileInput.type   = "file";
  fileInput.accept = ".json,application/json";

  document.getElementById("open-btn").addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    if (!file) return;
    fileInput.value = "";   // reset so same file can be reloaded

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = JSON.parse(e.target.result);
        _deserialize(data);
      } catch (err) {
        window.showBanner(`Kunne ikke lese filen: ${err.message}`, []);
      }
    };
    reader.readAsText(file, "utf-8");
  });

  // -------------------------------------------------------------------------
  // Serialise — ipuz-inspired JSON (matches spec grid format)
  // -------------------------------------------------------------------------

  function _serialize() {
    const g = window.grid;

    // puzzle[r][c]: "#" for black, {cell: N} for numbered open, {cell: 0} for plain open
    const puzzle = g.cells.map(row =>
      row.map(c => c.black ? "#" : { cell: c.clueNum || 0 })
    );

    // solution[r][c]: "#" for black, letter or null for open
    const solution = g.cells.map(row =>
      row.map(c => c.black ? "#" : (c.letter || null))
    );

    // clues: Across / Down arrays
    const cluesAcross = Object.entries(g.clues.across)
      .sort(([a], [b]) => +a - +b)
      .map(([num, entry]) => ({
        number: +num,
        clue:   entry.text || "",
        cells:  entry.cells,
      }));

    const cluesDown = Object.entries(g.clues.down)
      .sort(([a], [b]) => +a - +b)
      .map(([num, entry]) => ({
        number: +num,
        clue:   entry.text || "",
        cells:  entry.cells,
      }));

    return {
      version:    "kryssord/1",
      title:      "",
      dimensions: { width: g.cols, height: g.rows },
      puzzle,
      solution,
      clues: {
        Across: cluesAcross,
        Down:   cluesDown,
      },
    };
  }

  // -------------------------------------------------------------------------
  // Deserialise — restore grid from saved JSON
  // -------------------------------------------------------------------------

  function _deserialize(data) {
    const g = window.grid;

    // Basic validation
    if (!data.dimensions || !data.puzzle || !data.solution) {
      throw new Error("Ugyldig format — mangler dimensions, puzzle eller solution");
    }

    const { width, height } = data.dimensions;

    // Rebuild cells
    g._buildCells(height, width);

    for (let r = 0; r < height; r++) {
      for (let c = 0; c < width; c++) {
        const pCell = data.puzzle[r]?.[c];
        const sCell = data.solution[r]?.[c];

        g.cells[r][c].black  = pCell === "#";
        g.cells[r][c].letter = (sCell && sCell !== "#") ? sCell : "";
      }
    }

    // Re-number and rebuild clue index
    g._numberCells();

    // Restore clue texts by matching word start positions
    for (const dir of ["Across", "Down"]) {
      const dirKey  = dir.toLowerCase();
      const entries = data.clues?.[dir] ?? [];
      for (const saved of entries) {
        // Find the current clue entry whose first cell matches saved.cells[0]
        const [sr, sc] = saved.cells?.[0] ?? [];
        for (const [num, entry] of Object.entries(g.clues[dirKey])) {
          const [er, ec] = entry.cells[0];
          if (er === sr && ec === sc) {
            entry.text = saved.clue || "";
            break;
          }
        }
      }
    }

    // Re-render
    g._renderTable();
    g._renderHighlights();
    g._fireSelectionChange();
    g._autosave();
  }

})();
