from __future__ import annotations

import requests
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Input, Static

from .client import KryssordClient
from .history import HistoryStore
from .models import Result

RESULT_COLUMNS = ("Ord", "Ant. ord", "Lengde", "Bruker", "Sist sett")


class KryssordApp(App):
    """Keyboard-only crossword lookup for kryssord.org.

    Flow: type a word/hint, Enter, (optionally) type a letter pattern
    ('.' = one unknown letter, '*' = any number of unknown letters),
    Enter -> results.
    """

    BINDINGS = [Binding("ctrl+q", "quit", "Avslutt")]

    CSS = """
    #status {
        height: auto;
        padding: 0 1;
        color: $text-muted;
    }
    """

    def __init__(self, client: KryssordClient | None = None, history: HistoryStore | None = None) -> None:
        super().__init__()
        self._client = client or KryssordClient()
        self._history = history or HistoryStore()
        self._owns_client = client is None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(id="word", placeholder="Ord/hint...")
        yield Input(id="pattern", placeholder="Mønster: . = én bokstav, * = flere...")
        yield Static(id="status")
        yield DataTable(id="results")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#results", DataTable)
        table.add_columns(*RESULT_COLUMNS)
        table.cursor_type = "row"
        self.query_one("#word", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "word":
            self.query_one("#pattern", Input).focus()
        elif event.input.id == "pattern":
            self._start_search()

    def _start_search(self) -> None:
        word = self.query_one("#word", Input).value.strip()
        pattern = self.query_one("#pattern", Input).value.strip().replace(".", "?")

        if not word and not pattern:
            self._set_status("Skriv inn ord og/eller mønster.")
            self.query_one("#word", Input).focus()
            return

        self._set_status("Søker...")
        self._run_search(word, pattern)

    @work(thread=True, exclusive=True)
    def _run_search(self, word: str, pattern: str) -> None:
        try:
            results = self._client.search(word=word, pattern=pattern)
        except requests.RequestException as exc:
            self.call_from_thread(self._set_status, f"Feil ved søk: {exc}")
            return
        self.call_from_thread(self._show_results, word, pattern, results)

    def _show_results(self, word: str, pattern: str, results: list[Result]) -> None:
        self._history.record(word, pattern, len(results))

        table = self.query_one("#results", DataTable)
        table.clear()
        for r in results:
            seen = r.last_seen.isoformat() if r.last_seen else "-"
            table.add_row(r.word, str(r.word_count), str(r.length), str(r.users), seen)

        self._set_status("Ingen treff." if not results else "")

        self.query_one("#word", Input).value = ""
        self.query_one("#pattern", Input).value = ""
        self.query_one("#word", Input).focus()

    def _set_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_unmount(self) -> None:
        if self._owns_client:
            self._client.close()


def run() -> None:
    KryssordApp().run()


if __name__ == "__main__":
    run()
