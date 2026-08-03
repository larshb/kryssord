from datetime import date
from pathlib import Path

from kryssord.parser import parse_results

FIXTURES = Path(__file__).parent / "fixtures"


def test_parses_result_rows():
    html = (FIXTURES / "hund_pattern.html").read_text()
    results = parse_results(html)

    assert len(results) == 8
    first = results[0]
    assert first.word
    assert first.length == 4
    assert isinstance(first.users, int)
    assert first.last_seen is None or isinstance(first.last_seen, date)


def test_no_results_returns_empty_list():
    html = (FIXTURES / "no_results.html").read_text()
    assert parse_results(html) == []
