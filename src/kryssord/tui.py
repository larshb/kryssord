from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, urlencode

import requests
from rich.markup import escape
from textual import work
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.events import Resize
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Static

from .client import SEARCH_URL as KRYSSORD_SEARCH_URL
from .client import KryssordClient
from .history import HistoryStore, dedupe_history
from .history_screen import HistoryScreen
from .models import HistoryEntry, NaobEntry, Result
from .naob_client import BASE_URL as NAOB_BASE_URL
from .naob_client import NaobClient
from .paths import default_data_dir

RESULT_COLUMNS = ("Ord", "Lengde")

# A monospace terminal cell is roughly twice as tall as it is wide, so raw
# column/row counts don't reflect the *visual* aspect ratio. This corrects
# for that when deciding whether the window is landscape enough for a
# side-by-side layout. The threshold sits between a half-screen 16:9 window
# (~0.89 width:height) and a half-screen 16:10 window (~0.80) -- roughly
# where the user wants the switch to happen.
GLYPH_ASPECT = 0.5
LAYOUT_SWITCH_ASPECT = 0.86


def _is_landscape(width: int, height: int) -> bool:
    return (width * GLYPH_ASPECT) / height >= LAYOUT_SWITCH_ASPECT


DEFAULT_THEME = "ansi-dark"


def _default_theme_path() -> Path:
    return default_data_dir() / "theme.txt"

# naob.no can have several homograph entries for the same headword (e.g.
# "vise" as two different nouns and a verb) -- cap how many full entries get
# fetched for one word so a pathological case can't spam the site.
MAX_NAOB_ENTRIES = 5

# naob.no's own accent color for section headings (ETYMOLOGI, UTTRYKK, ...),
# reused here for our equivalent labels. Hardcoded rather than theme-derived
# because this is reproducing NAOB's own document styling, not app chrome.
NAOB_RED = "#a54242"


def _format_naob_entry(entry: NaobEntry) -> str:
    word = escape(entry.word)
    header = f"[bold]{word}[/bold] ({escape(entry.word_class)})" if entry.word_class else f"[bold]{word}[/bold]"
    lines = [header]
    if entry.inflection:
        lines.append(escape(entry.inflection))
    if entry.etymology:
        lines.append(f"[bold {NAOB_RED}]Opphav:[/] {escape(entry.etymology)}")

    lines.append("")
    for s in entry.senses:
        lines.append(f"[bold]{escape(s.number)}[/]  {escape(s.text)}")
        for example in s.examples:
            lines.append(f"    [italic]eks: {escape(example)}[/]")

    if entry.idiom_count:
        idiom_bits = []
        for i in entry.idioms:
            phrase = f"[bold]{escape(i.phrase)}[/]"
            idiom_bits.append(f"{phrase} — {escape(i.meaning)}" if i.meaning else phrase)
        remaining = entry.idiom_count - len(entry.idioms)
        suffix = f" (+{remaining} flere uttrykk)" if remaining > 0 else ""
        lines.append("")
        lines.append(f"[bold {NAOB_RED}]Uttrykk:[/] " + "; ".join(idiom_bits) + suffix)

    return "\n".join(lines)


def _format_naob_entries(entries: list[NaobEntry]) -> str:
    return "\n\n".join(_format_naob_entry(entry) for entry in entries)


def _looks_like_pattern(text: str) -> bool:
    """True if `text` uses wildcard syntax (. / ? / *) rather than being a plain word."""
    return any(c in text for c in ".?*")


class KryssordApp(App):
    """Keyboard-only crossword lookup for kryssord.org.

    Flow: type a word/hint, Enter, (optionally) type a letter pattern
    ('.' = one unknown letter, '*' = any number of unknown letters),
    Enter -> results. The word field itself also accepts wildcards (e.g.
    "hu.d" or "hu*d") -- typing one there and pressing Enter searches
    immediately, skipping the separate pattern field.
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Avslutt"),
        Binding("up", "results_cursor_up", "Bla opp", show=False),
        Binding("down", "results_cursor_down", "Bla ned", show=False),
        Binding("ctrl+o", "open_kryssord", "Åpne kryssord.org"),
        Binding("ctrl+n", "open_naob", "Åpne NAOB"),
        Binding("ctrl+r", "open_history", "Historikk"),
    ]

    CSS = """
    #status {
        height: auto;
        padding: 0 1;
        color: $text-muted;
    }
    #main-row {
        height: 1fr;
    }
    #results {
        /* $primary is blue in most themes, incl. the ansi-dark default */
        width: 1fr;
        height: 1fr;
        border: solid $primary;
    }
    #naob-panel {
        /* $error is red/red-ish in every built-in theme */
        width: 1fr;
        height: 1fr;
        border: solid $error;
        padding: 0 1;
    }
    #main-row.stacked {
        layout: vertical;
    }
    #main-row.stacked #results {
        height: 2fr;
    }
    #main-row.stacked #naob-panel {
        height: 1fr;
    }
    """

    def __init__(
        self,
        client: KryssordClient | None = None,
        history: HistoryStore | None = None,
        naob_client: NaobClient | None = None,
        theme_path: str | Path | None = None,
    ) -> None:
        super().__init__()
        self._client = client or KryssordClient()
        self._history = history or HistoryStore()
        self._naob_client = naob_client or NaobClient()
        self._owns_client = client is None
        self._owns_naob_client = naob_client is None
        self._last_results: list[Result] = []
        self._last_pattern_raw: str = ""
        self._last_search_word: str = ""
        self._last_search_pattern: str = ""
        self._current_naob_slugs: list[str] = []
        self._suppress_naob_highlight = False
        self._theme_path = Path(theme_path) if theme_path else _default_theme_path()
        self.theme = self._load_theme()

    def _load_theme(self) -> str:
        if self._theme_path.exists():
            saved = self._theme_path.read_text().strip()
            if saved:
                return saved
        return DEFAULT_THEME

    def watch_theme(self, old_theme: str, new_theme: str) -> None:
        self._theme_path.parent.mkdir(parents=True, exist_ok=True)
        self._theme_path.write_text(new_theme)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(id="word", placeholder="Ord/hint, evt. mønster (. / *)...")
        yield Input(id="pattern", placeholder="Mønster: . = én bokstav, * = flere...")
        yield Static(id="status")
        with Horizontal(id="main-row"):
            yield DataTable(id="results")
            with VerticalScroll(id="naob-panel"):
                yield Static(id="naob")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#results", DataTable)
        table.add_columns(*RESULT_COLUMNS)
        table.cursor_type = "row"
        table.border_title = "kryssord.org"
        self.query_one("#word", Input).focus()
        self._update_layout_orientation(self.size.width, self.size.height)

        naob_panel = self.query_one("#naob-panel")
        naob_panel.border_title = "naob.no"
        self._set_naob_text("Velg et treff (Enter) for å slå opp i NAOB.")

    def on_resize(self, event: Resize) -> None:
        # Prefer the terminal's actual reported pixel size (many terminals
        # support the XTWINOPS query Textual uses for this) over the
        # character-count approximation -- it's exact instead of guessing
        # at the glyph aspect ratio.
        if event.pixel_size is not None and event.pixel_size.height:
            landscape = (event.pixel_size.width / event.pixel_size.height) >= LAYOUT_SWITCH_ASPECT
        else:
            landscape = _is_landscape(event.size.width, event.size.height)
        self.query_one("#main-row").set_class(not landscape, "stacked")

    def _update_layout_orientation(self, width: int, height: int) -> None:
        self.query_one("#main-row").set_class(not _is_landscape(width, height), "stacked")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id not in ("word", "pattern"):
            return
        upper = event.value.upper()
        if event.value != upper:
            cursor = event.input.cursor_position
            event.input.value = upper
            event.input.cursor_position = cursor

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "word":
            word_value = self.query_one("#word", Input).value.strip()
            if _looks_like_pattern(word_value):
                # a= supports wildcards standalone (e.g. "hu?d") -- no need to
                # wait on a separate pattern field in that case.
                self._start_search()
            else:
                self.query_one("#pattern", Input).focus()
        elif event.input.id == "pattern":
            self._start_search()

    def _start_search(self) -> None:
        word_raw = self.query_one("#word", Input).value.strip()
        word = word_raw.replace(".", "?")
        pattern_raw = self.query_one("#pattern", Input).value.strip()
        pattern = pattern_raw.replace(".", "?")

        if not word and not pattern:
            self._set_status("Skriv inn ord og/eller mønster.")
            self.query_one("#word", Input).focus()
            return

        self._last_pattern_raw = pattern_raw
        self._set_status("Søker...")
        self._run_search(word, pattern)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        # Fires as the cursor moves (e.g. arrow keys), even without pressing
        # Enter -- browsing the results previews each word's NAOB entry.
        # Suppressed right after a search populates the table, since that
        # triggers this for row 0 too, even though the user hasn't actually
        # navigated there themselves -- the a= clue's own NAOB lookup should
        # stick until they do.
        if self._suppress_naob_highlight:
            return
        if event.data_table.id != "results" or event.cursor_row >= len(self._last_results):
            return
        word = self._last_results[event.cursor_row].word
        self._lookup_naob(word)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "results" or event.cursor_row >= len(self._last_results):
            return

        word = self._last_results[event.cursor_row].word.upper()
        self.query_one("#word", Input).value = word
        self.query_one("#pattern", Input).value = self._last_pattern_raw

        pattern = self._last_pattern_raw.replace(".", "?")
        self._set_status("Søker...")
        self._run_search(word, pattern, focus_after="results")

    def action_results_cursor_up(self) -> None:
        self.query_one("#results", DataTable).action_cursor_up()

    def action_results_cursor_down(self) -> None:
        self.query_one("#results", DataTable).action_cursor_down()

    def action_open_kryssord(self) -> None:
        if not self._last_search_word and not self._last_search_pattern:
            self._set_status("Ingen søk å åpne ennå.")
            return
        query = urlencode({"a": self._last_search_word, "b": self._last_search_pattern})
        webbrowser.open(f"{KRYSSORD_SEARCH_URL}?{query}")
        self._set_status("Åpnet kryssord.org i nettleser.")

    def action_open_naob(self) -> None:
        if not self._current_naob_slugs:
            self._set_status("Ingen NAOB-oppføring å åpne ennå.")
            return
        for slug in self._current_naob_slugs:
            webbrowser.open(f"{NAOB_BASE_URL}/ordbok/{quote(slug, safe='')}")
        self._set_status(f"Åpnet {len(self._current_naob_slugs)} NAOB-oppføring(er) i nettleser.")

    def action_open_history(self) -> None:
        entries = dedupe_history(self._history.load_all())
        if not entries:
            self._set_status("Ingen søkehistorikk ennå.")
            return
        self.push_screen(HistoryScreen(entries), callback=self._on_history_selected)

    def _on_history_selected(self, entry: HistoryEntry | None) -> None:
        if entry is None:
            return
        self.query_one("#word", Input).value = entry.word
        self.query_one("#pattern", Input).value = entry.pattern
        self._start_search()

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        yield SystemCommand("Historikk", "Bla i søkehistorikk", self.action_open_history)
        yield SystemCommand("Åpne kryssord.org", "Åpne siste søk i nettleser", self.action_open_kryssord)
        yield SystemCommand("Åpne NAOB", "Åpne viste NAOB-oppføringer i nettleser", self.action_open_naob)

    @work(thread=True, exclusive=True)
    def _run_search(self, word: str, pattern: str, focus_after: str = "word") -> None:
        try:
            results = self._client.search(word=word, pattern=pattern)
        except requests.RequestException as exc:
            self.call_from_thread(self._set_status, f"Feil ved søk: {exc}")
            return
        self.call_from_thread(self._show_results, word, pattern, results, focus_after)

    def _show_results(self, word: str, pattern: str, results: list[Result], focus_after: str = "word") -> None:
        self._last_results = results
        self._last_search_word = word
        self._last_search_pattern = pattern
        self._history.record(word, pattern, len(results))

        # Populating the table below triggers an incidental row-highlight
        # for row 0, even though the user hasn't actually navigated there --
        # suppress that one lookup so it doesn't briefly override the a=
        # clue's own NAOB entry with the top result's.
        self._suppress_naob_highlight = True
        table = self.query_one("#results", DataTable)
        table.clear()
        for r in results:
            table.add_row(r.word.upper(), str(r.length))
        self.call_after_refresh(self._stop_suppressing_naob_highlight)

        self._set_status("Ingen treff." if not results else "")

        if focus_after == "word":
            self.query_one("#word", Input).value = ""
            self.query_one("#pattern", Input).value = ""
            self.query_one("#word", Input).focus()
        else:
            self.query_one("#results", DataTable).focus()

        if word and not _looks_like_pattern(word):
            self._lookup_naob(word)

    def _stop_suppressing_naob_highlight(self) -> None:
        self._suppress_naob_highlight = False

    def _lookup_naob(self, word: str) -> None:
        self._set_naob_text(f"Slår opp «{word}» i NAOB...")
        self._run_naob_lookup(word)

    @work(thread=True, exclusive=True, group="naob")
    def _run_naob_lookup(self, word: str) -> None:
        try:
            matches = self._naob_client.search(word)
        except requests.RequestException as exc:
            self.call_from_thread(self._clear_naob, f"Feil ved NAOB-oppslag: {exc}")
            return

        exact_matches = [m for m in matches if m.word.lower() == word.lower()]
        if not exact_matches:
            self.call_from_thread(self._clear_naob, f"Ingen NAOB-oppføring for «{word}».")
            return

        entries = []
        for match in exact_matches[:MAX_NAOB_ENTRIES]:
            try:
                entry = self._naob_client.get_entry(match.slug)
            except requests.RequestException as exc:
                self.call_from_thread(self._clear_naob, f"Feil ved NAOB-oppslag: {exc}")
                return
            if entry is not None:
                entries.append(entry)

        if not entries:
            self.call_from_thread(self._clear_naob, f"Ingen NAOB-oppføring for «{word}».")
            return

        self.call_from_thread(self._show_naob_entries, entries)

    def _show_naob_entries(self, entries: list[NaobEntry]) -> None:
        self._current_naob_slugs = [e.slug for e in entries]
        self._set_naob_text(_format_naob_entries(entries))

    def _clear_naob(self, message: str) -> None:
        self._current_naob_slugs = []
        self._set_naob_text(message)

    def _set_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def _set_naob_text(self, message: str) -> None:
        self.query_one("#naob", Static).update(message)

    def on_unmount(self) -> None:
        if self._owns_client:
            self._client.close()
        if self._owns_naob_client:
            self._naob_client.close()


def run() -> None:
    KryssordApp().run()


if __name__ == "__main__":
    run()
