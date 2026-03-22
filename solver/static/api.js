/**
 * api.js — shared API helpers
 *
 * Exposes window.api for use by search.js and solver.js.
 */

window.api = {
  /**
   * Look up words on kryssord.org via the backend proxy.
   *
   * If clue+pattern returns 0 results, automatically retries with
   * the pattern promoted to the clue (pattern-only search).
   *
   * @param {string} clue     - The clue text (a). May be empty if pattern is set.
   * @param {string} pattern  - The pattern string (b), e.g. "kr?ss?rd". May be empty.
   * @returns {Promise<{words, total, cached, usedFallback}>}
   */
  async lookup(clue, pattern) {
    let a = clue.trim();
    let b = pattern.trim();

    // b → a promotion: if no clue, search by pattern as clue
    if (!a && b) { a = b; b = ""; }
    if (!a) throw new Error("Ledetekst er påkrevd");

    const result = await _fetch(a, b);

    // Fallback: if clue+pattern gave 0 results and there is a pattern to retry with
    if (result.words.length === 0 && b) {
      const fallback = await _fetch(b, "");
      if (fallback.words.length > 0) {
        return { ...fallback, usedFallback: true };
      }
    }

    return { ...result, usedFallback: false };
  },
};

async function _fetch(a, b) {
  const params = new URLSearchParams({ a });
  if (b) params.set("b", b);
  const res  = await fetch(`/api/lookup?${params}`);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || data.error || "Ukjent feil");
  return data;
}
