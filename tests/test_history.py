from kryssord.history import HistoryStore


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
