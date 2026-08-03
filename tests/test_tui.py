from datetime import date

from kryssord.history import HistoryStore
from kryssord.models import Result
from kryssord.tui import KryssordApp
from textual.widgets import DataTable, Input, Static


class StubClient:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, word="", pattern=""):
        self.calls.append((word, pattern))
        return self.results


CANNED_RESULTS = [
    Result(word="hund", word_count=1, length=4, users=5, last_seen=date(2020, 1, 1)),
    Result(word="katt", word_count=1, length=4, users=3, last_seen=None),
]


async def test_full_search_flow_translates_dot_and_records_history(tmp_path):
    client = StubClient(CANNED_RESULTS)
    history = HistoryStore(path=tmp_path / "history.jsonl")
    app = KryssordApp(client=client, history=history)

    async with app.run_test() as pilot:
        await pilot.press(*"hund")
        await pilot.press("enter")
        await pilot.press(*"b..")
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert client.calls == [("hund", "b??")]

        table = app.query_one("#results", DataTable)
        assert table.row_count == 2

        assert app.query_one("#word", Input).value == ""
        assert app.query_one("#pattern", Input).value == ""
        assert app.focused is app.query_one("#word", Input)

    entries = history.load_all()
    assert len(entries) == 1
    assert entries[0].word == "hund"
    assert entries[0].pattern == "b??"
    assert entries[0].result_count == 2


async def test_empty_submit_shows_validation_and_skips_search(tmp_path):
    client = StubClient([])
    history = HistoryStore(path=tmp_path / "history.jsonl")
    app = KryssordApp(client=client, history=history)

    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause()

        assert client.calls == []
        assert str(app.query_one("#status", Static).render())
        assert app.focused is app.query_one("#word", Input)

    assert history.load_all() == []
