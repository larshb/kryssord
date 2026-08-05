from __future__ import annotations

import webbrowser
from pathlib import Path
from urllib.parse import quote, urlencode

import requests
from rich.markup import escape
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
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

DEFAULT_THEME = "ansi-dark"


def _default_theme_path() -> Path:
    return default_data_dir() / "theme.txt"

# naob.no can have several homograph entries for the same headword (e.g.
# "vise" as two different nouns and a verb) -- cap how many full entries get
# fetched for one word so a pathological case can't spam the site.
MAX_NAOB_ENTRIES = 5

# naob.no's own accent color for section headings (ETYMOLOGI, UTTRYKK, ...),
# reused here for our equivalent labels.
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
        Binding("o", "open_kryssord", "Åpne kryssord.org"),
        Binding("n", "open_naob", "Åpne NAOB"),
        Binding("h", "open_history", "Historikk"),
    ]

    CSS = """
    #status {
        height: auto;
        padding: 0 1;
        color: $text-muted;
    }
    #results {
        height: 2fr;
    }
    #naob-panel {
        height: 1fr;
        border: solid $accent;
        padding: 0 1;
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
        yield DataTable(id="results")
        with VerticalScroll(id="naob-panel"):
            yield Static(id="naob")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#results", DataTable)
        table.add_columns(*RESULT_COLUMNS)
        table.cursor_type = "row"
        self.query_one("#word", Input).focus()

        naob_panel = self.query_one("#naob-panel")
        naob_panel.border_title = "NAOB"
        self._set_naob_text("Velg et treff (Enter) for å slå opp i NAOB.")

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
        if event.data_table.id != "results" or event.cursor_row >= len(self._last_results):
            return
        word = self._last_results[event.cursor_row].word
        self._lookup_naob(word)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "results" or event.cursor_row >= len(self._last_results):
            return

        word = self._last_results[event.cursor_row].word
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

        table = self.query_one("#results", DataTable)
        table.clear()
        for r in results:
            table.add_row(r.word.upper(), str(r.length))

        self._set_status("Ingen treff." if not results else "")

        if focus_after == "word":
            self.query_one("#word", Input).value = ""
            self.query_one("#pattern", Input).value = ""
            self.query_one("#word", Input).focus()
        else:
            self.query_one("#results", DataTable).focus()

        # Populating the table above triggers an incidental row-highlight
        # (previewing row 0), which would otherwise race with -- and can
        # overwrite -- the lookup for the word that was actually searched
        # for. Schedule this one to run after that settles, so it always
        # wins and ends up as what's shown.
        if word and not _looks_like_pattern(word):
            self.call_after_refresh(self._lookup_naob, word)

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
