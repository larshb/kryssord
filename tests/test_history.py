from datetime import datetime, timedelta, timezone

from kryssord.history import HistoryStore, dedupe_history
from kryssord.models import HistoryEntry


def test_record_and_load_round_trip(tmp_path):
    store = HistoryStore(path=tmp_path / "history.jsonl")

    store.record(word="hund", pattern="", result_count=8)
    store.record(word="", pattern="b???", result_count=0)

    entries = store.load_all()

    assert len(entries) == 2
    assert entries[0].word == "hund"
    assert entries[0].result_count == 8
    assert entries[1].pattern == "b???"
    assert entries[1].result_count == 0


def test_load_all_missing_file_returns_empty(tmp_path):
    store = HistoryStore(path=tmp_path / "does_not_exist.jsonl")
    assert store.load_all() == []


def test_dedupe_history_collapses_repeats_to_latest_and_sorts_newest_first():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    entries = [
        HistoryEntry(word="HUND", pattern="", result_count=8, timestamp=t0),
        HistoryEntry(word="KATT", pattern="B??", result_count=2, timestamp=t0 + timedelta(minutes=1)),
        HistoryEntry(word="HUND", pattern="", result_count=9, timestamp=t0 + timedelta(minutes=2)),
    ]

    result = dedupe_history(entries)

    assert len(result) == 2
    assert result[0].word == "HUND"
    assert result[0].result_count == 9  # the later occurrence won
    assert result[1].word == "KATT"


def test_dedupe_history_empty_list():
    assert dedupe_history([]) == []
