from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DataTable

from .models import HistoryEntry

HISTORY_COLUMNS = ("Ord", "Mønster", "Treff", "Sist søkt")


class HistoryScreen(ModalScreen[HistoryEntry | None]):
    """Modal list of past searches, newest first. Enter picks one, Escape cancels."""

    BINDINGS = [Binding("escape", "dismiss_screen", "Lukk")]

    CSS = """
    HistoryScreen {
        align: center middle;
    }
    #history-table {
        width: 80%;
        height: 80%;
        border: solid $accent;
    }
    """

    def __init__(self, entries: list[HistoryEntry]) -> None:
        super().__init__()
        self._entries = entries

    def compose(self) -> ComposeResult:
        yield DataTable(id="history-table")

    def on_mount(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.border_title = "Søkehistorikk"
        table.add_columns(*HISTORY_COLUMNS)
        table.cursor_type = "row"
        for entry in self._entries:
            table.add_row(
                entry.word or "-",
                entry.pattern or "-",
                str(entry.result_count),
                entry.timestamp.astimezone().strftime("%Y-%m-%d %H:%M"),
            )
        table.focus()

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.cursor_row < len(self._entries):
            self.dismiss(self._entries[event.cursor_row])
