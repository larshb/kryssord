from datetime import date

from kryssord.history import HistoryStore
from kryssord.history_screen import HistoryScreen
from kryssord.models import NaobEntry, NaobIdiom, NaobSearchEntry, NaobSense, Result
from kryssord.tui import KryssordApp, _format_naob_entries, _format_naob_entry
from textual.widgets import DataTable, Input, Static


class StubClient:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, word="", pattern=""):
        self.calls.append((word, pattern))
        return self.results


class StubNaobClient:
    def __init__(self, search_results=None, entries_by_slug=None):
        self.search_results = search_results if search_results is not None else []
        self.entries_by_slug = entries_by_slug or {}
        self.search_calls = []
        self.entry_calls = []

    def search(self, query):
        self.search_calls.append(query)
        return self.search_results

    def get_entry(self, slug):
        self.entry_calls.append(slug)
        return self.entries_by_slug.get(slug)


CANNED_RESULTS = [
    Result(word="hund", word_count=1, length=4, users=5, last_seen=date(2020, 1, 1)),
    Result(word="katt", word_count=1, length=4, users=3, last_seen=None),
]


async def test_full_search_flow_translates_dot_and_records_history(tmp_path):
    client = StubClient(CANNED_RESULTS)
    history = HistoryStore(path=tmp_path / "history.jsonl")
    app = KryssordApp(client=client, history=history, naob_client=StubNaobClient(), theme_path=tmp_path / "theme.txt")

    async with app.run_test() as pilot:
        await pilot.press(*"hund")
        await pilot.press("enter")
        await pilot.press(*"b..")
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()

        # typed lowercase, but the fields show/search uppercase (crossword style)
        assert client.calls == [("HUND", "B??")]

        table = app.query_one("#results", DataTable)
        assert table.row_count == 2
        assert table.get_cell_at((0, 0)) == "HUND"

        assert app.query_one("#word", Input).value == ""
        assert app.query_one("#pattern", Input).value == ""
        assert app.focused is app.query_one("#word", Input)

    entries = history.load_all()
    assert len(entries) == 1
    assert entries[0].word == "HUND"
    assert entries[0].pattern == "B??"
    assert entries[0].result_count == 2


async def test_empty_submit_shows_validation_and_skips_search(tmp_path):
    client = StubClient([])
    history = HistoryStore(path=tmp_path / "history.jsonl")
    app = KryssordApp(client=client, history=history, naob_client=StubNaobClient(), theme_path=tmp_path / "theme.txt")

    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause()

        assert client.calls == []
        assert str(app.query_one("#status", Static).render())
        assert app.focused is app.query_one("#word", Input)

    assert history.load_all() == []


async def test_arrow_keys_navigate_results_while_word_field_focused(tmp_path):
    client = StubClient(CANNED_RESULTS)
    history = HistoryStore(path=tmp_path / "history.jsonl")
    naob_client = StubNaobClient()
    app = KryssordApp(client=client, history=history, naob_client=naob_client, theme_path=tmp_path / "theme.txt")

    async with app.run_test() as pilot:
        await pilot.press(*"hund")
        await pilot.press("enter")
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()

        table = app.query_one("#results", DataTable)
        assert table.cursor_row == 0
        assert app.focused is app.query_one("#word", Input)  # focus stayed on #word

        await pilot.press("down")
        await pilot.pause()
        assert table.cursor_row == 1
        # moving the highlight (without pressing Enter) previews that row's
        # word in the NAOB panel, without re-running the kryssord search
        assert naob_client.search_calls[-1] == "katt"
        assert client.calls == [("HUND", "")]

        await pilot.press("up")
        await pilot.pause()
        assert table.cursor_row == 0


async def test_wildcard_in_word_field_searches_immediately_and_skips_naob_for_the_pattern(tmp_path):
    client = StubClient(CANNED_RESULTS)
    history = HistoryStore(path=tmp_path / "history.jsonl")
    naob_client = StubNaobClient()
    app = KryssordApp(client=client, history=history, naob_client=naob_client, theme_path=tmp_path / "theme.txt")

    async with app.run_test() as pilot:
        await pilot.press(*"hu.d")
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()

        # "." got translated to "?" and the search fired on the first Enter,
        # without waiting on the pattern field
        assert client.calls == [("HU?D", "")]
        assert app.query_one("#pattern", Input).value == ""

        # the wildcard string itself ("hu?d") isn't a real headword, and no
        # result gets auto-previewed until the results pane is navigated to
        assert naob_client.search_calls == []

        await pilot.press("down")  # navigating in from #word moves to row 0 -> row 1
        await pilot.pause()
        assert naob_client.search_calls == ["katt"]

    entries = history.load_all()
    assert len(entries) == 1
    assert entries[0].word == "HU?D"


async def test_initial_search_also_looks_up_naob_for_the_typed_word(tmp_path):
    client = StubClient(CANNED_RESULTS)
    history = HistoryStore(path=tmp_path / "history.jsonl")
    naob_client = StubNaobClient(
        search_results=[NaobSearchEntry(word="hund", slug="hund", word_class="substantiv", short_definition="...")],
        entries_by_slug={
            "hund": NaobEntry(
                word="hund",
                slug="hund",
                word_class="substantiv",
                inflection="en; hunden, hunder",
                etymology="av norrønt hundr",
                senses=[NaobSense(number="1", text="temmet rovdyr i hundefamilien", examples=[])],
                idioms=[],
                idiom_count=0,
            )
        },
    )
    app = KryssordApp(client=client, history=history, naob_client=naob_client, theme_path=tmp_path / "theme.txt")

    async with app.run_test() as pilot:
        await pilot.press(*"hund")
        await pilot.press("enter")
        await pilot.press("enter")  # empty pattern
        await app.workers.wait_for_complete()
        await pilot.pause()

        # only the a= clue itself is looked up -- the incidental row-0
        # highlight from populating the table is suppressed, so it doesn't
        # briefly show a different word before settling on this one
        assert naob_client.search_calls == ["HUND"]
        naob_text = str(app.query_one("#naob", Static).render())
        assert "rovdyr" in naob_text


async def test_selecting_result_drills_down_and_shows_all_homograph_entries(tmp_path):
    client = StubClient(CANNED_RESULTS)
    history = HistoryStore(path=tmp_path / "history.jsonl")
    naob_client = StubNaobClient(
        search_results=[
            NaobSearchEntry(word="katt", slug="katt_1", word_class="substantiv", short_definition="..."),
            NaobSearchEntry(word="katt", slug="katt_2", word_class="substantiv", short_definition="..."),
        ],
        entries_by_slug={
            "katt_1": NaobEntry(
                word="katt",
                slug="katt_1",
                word_class="substantiv",
                inflection="en; katten, katter",
                etymology=None,
                senses=[NaobSense(number="1", text="tamkatt, husdyr", examples=[])],
                idioms=[],
                idiom_count=0,
            ),
            "katt_2": NaobEntry(
                word="katt",
                slug="katt_2",
                word_class="substantiv",
                inflection=None,
                etymology=None,
                senses=[NaobSense(number="1", text="dataspill med katt og mus", examples=[])],
                idioms=[],
                idiom_count=0,
            ),
        },
    )
    app = KryssordApp(client=client, history=history, naob_client=naob_client, theme_path=tmp_path / "theme.txt")

    async with app.run_test() as pilot:
        await pilot.press(*"hund")
        await pilot.press("enter")
        await pilot.press(*"b..")
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()

        table = app.query_one("#results", DataTable)
        table.focus()
        await pilot.pause()
        await pilot.press("down")  # move from row 0 "hund" to row 1 "katt"
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()

        # "HUND" from the initial search, "katt" from browsing to row 1, then
        # "katt" again as the explicit drill-down lookup -- no incidental
        # re-preview of row 0 when the table repopulates after the drill-down.
        assert naob_client.search_calls == ["HUND", "katt", "katt"]
        assert naob_client.entry_calls == ["katt_1", "katt_2", "katt_1", "katt_2"]

        assert client.calls[-1] == ("katt", "B??")
        assert app.query_one("#word", Input).value == "KATT"
        assert app.focused is table

        naob_text = str(app.query_one("#naob", Static).render())
        assert "tamkatt" in naob_text
        assert "dataspill med katt og mus" in naob_text
        assert "en; katten, katter" in naob_text


async def test_theme_defaults_to_ansi_dark_and_persists_across_runs(tmp_path):
    theme_path = tmp_path / "theme.txt"
    naob_client = StubNaobClient()

    app = KryssordApp(client=StubClient([]), history=HistoryStore(path=tmp_path / "h.jsonl"), naob_client=naob_client, theme_path=theme_path)
    async with app.run_test():
        assert app.theme == "ansi-dark"
        app.theme = "nord"
        assert theme_path.read_text().strip() == "nord"

    # a fresh app picks up the previously saved theme instead of the default
    app2 = KryssordApp(client=StubClient([]), history=HistoryStore(path=tmp_path / "h.jsonl"), naob_client=naob_client, theme_path=theme_path)
    async with app2.run_test():
        assert app2.theme == "nord"


async def test_open_kryssord_and_naob_in_browser(tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr("kryssord.tui.webbrowser.open", lambda url: opened.append(url))

    client = StubClient(CANNED_RESULTS)
    history = HistoryStore(path=tmp_path / "history.jsonl")
    naob_client = StubNaobClient(
        search_results=[
            NaobSearchEntry(word="hund", slug="hund_1", word_class="substantiv", short_definition=""),
            NaobSearchEntry(word="hund", slug="hund_2", word_class="substantiv", short_definition=""),
        ],
        entries_by_slug={
            "hund_1": NaobEntry(
                word="hund", slug="hund_1", word_class="substantiv", inflection=None, etymology=None,
                senses=[], idioms=[], idiom_count=0,
            ),
            "hund_2": NaobEntry(
                word="hund", slug="hund_2", word_class="substantiv", inflection=None, etymology=None,
                senses=[], idioms=[], idiom_count=0,
            ),
        },
    )
    app = KryssordApp(client=client, history=history, naob_client=naob_client, theme_path=tmp_path / "theme.txt")

    async with app.run_test() as pilot:
        # nothing searched yet -- both open actions should no-op with a status message
        app.action_open_kryssord()
        assert opened == []
        app.action_open_naob()
        assert opened == []

        await pilot.press(*"hund")
        await pilot.press("enter")
        await pilot.press(*"b..")
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()

        app.action_open_kryssord()
        assert opened == ["https://www.kryssord.org/search.php?a=HUND&b=B%3F%3F"]

        app.action_open_naob()
        assert opened[1:] == [
            "https://naob.no/ordbok/hund_1",
            "https://naob.no/ordbok/hund_2",
        ]


async def test_open_history_with_no_history_shows_status(tmp_path):
    app = KryssordApp(
        client=StubClient([]),
        history=HistoryStore(path=tmp_path / "history.jsonl"),
        naob_client=StubNaobClient(),
        theme_path=tmp_path / "theme.txt",
    )

    async with app.run_test() as pilot:
        app.action_open_history()
        await pilot.pause()

        assert len(app.screen_stack) == 1  # no modal pushed
        assert "Ingen søkehistorikk" in str(app.query_one("#status", Static).render())


async def test_selecting_history_entry_populates_fields_and_searches(tmp_path):
    client = StubClient(CANNED_RESULTS)
    history = HistoryStore(path=tmp_path / "history.jsonl")
    history.record(word="HUND", pattern="", result_count=8)
    history.record(word="KATT", pattern="B??", result_count=2)  # most recent
    app = KryssordApp(client=client, history=history, naob_client=StubNaobClient(), theme_path=tmp_path / "theme.txt")

    async with app.run_test() as pilot:
        app.action_open_history()
        await pilot.pause()

        assert isinstance(app.screen, HistoryScreen)
        await pilot.press("enter")  # top row = most recent = "KATT"/"B??"
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert not isinstance(app.screen, HistoryScreen)  # modal closed
        assert client.calls[-1] == ("KATT", "B??")
        # search completed normally -- fields cleared, focus back on #word
        assert app.query_one("#word", Input).value == ""
        assert app.focused is app.query_one("#word", Input)


async def test_escape_dismisses_history_without_searching(tmp_path):
    client = StubClient(CANNED_RESULTS)
    history = HistoryStore(path=tmp_path / "history.jsonl")
    history.record(word="HUND", pattern="", result_count=8)
    app = KryssordApp(client=client, history=history, naob_client=StubNaobClient(), theme_path=tmp_path / "theme.txt")

    async with app.run_test() as pilot:
        app.action_open_history()
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, HistoryScreen)
        assert client.calls == []


def test_format_naob_entry_includes_word_class_inflection_and_senses():
    entry = NaobEntry(
        word="hund",
        slug="hund",
        word_class="substantiv",
        inflection="en; hunden, hunder",
        etymology=None,
        senses=[
            NaobSense(number="1", text="temmet rovdyr", examples=[]),
            NaobSense(number="1.1", text="overført, om person", examples=[]),
        ],
        idioms=[],
        idiom_count=0,
    )
    text = _format_naob_entry(entry)

    assert "[bold]hund[/bold]" in text
    assert "substantiv" in text
    assert "en; hunden, hunder" in text
    assert "[bold]1[/]  temmet rovdyr" in text
    assert "[bold]1.1[/]  overført, om person" in text


def test_format_naob_entry_includes_etymology_examples_and_idioms():
    entry = NaobEntry(
        word="jul",
        slug="jul",
        word_class="substantiv",
        inflection="en; julen, juler",
        etymology="av gammeldansk jūl",
        senses=[
            NaobSense(number="1", text="høytid til minne om Kristi fødsel", examples=["komme hjem til jul"]),
        ],
        idioms=[NaobIdiom(phrase="hvit jul", meaning="juletid med snø")],
        idiom_count=8,
    )
    text = _format_naob_entry(entry)

    assert "[bold #a54242]Opphav:[/] av gammeldansk jūl" in text
    assert "[italic]eks: komme hjem til jul[/]" in text
    assert "[bold]hvit jul[/] — juletid med snø" in text
    assert "+7 flere uttrykk" in text


def test_format_naob_entries_joins_multiple_entries():
    entry_a = NaobEntry(
        word="vise",
        slug="vise_1",
        word_class="substantiv",
        inflection=None,
        etymology=None,
        senses=[],
        idioms=[],
        idiom_count=0,
    )
    entry_b = NaobEntry(
        word="vise",
        slug="vise_3",
        word_class="verb",
        inflection=None,
        etymology=None,
        senses=[],
        idioms=[],
        idiom_count=0,
    )

    text = _format_naob_entries([entry_a, entry_b])

    assert "substantiv" in text
    assert "verb" in text
    assert text.index("substantiv") < text.index("verb")
