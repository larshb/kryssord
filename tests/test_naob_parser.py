from pathlib import Path

from kryssord.naob_parser import parse_entry, parse_search_results

FIXTURES = Path(__file__).parent / "fixtures"


def test_parses_search_results():
    html = (FIXTURES / "naob_search_hund.html").read_text()
    results = parse_search_results(html)

    assert len(results) == 2
    first = results[0]
    assert first.word == "hund"
    assert first.slug == "hund"


def test_parses_full_entry_with_senses_examples_etymology_and_idioms():
    html = (FIXTURES / "naob_entry_hund.html").read_text()
    entry = parse_entry(html, "hund")

    assert entry is not None
    assert entry.word == "hund"
    assert entry.slug == "hund"
    assert entry.word_class == "substantiv"
    assert entry.inflection == "MODERAT BOKMÅL en; hunden, hunder"
    assert entry.etymology == "av norrønt hundr"

    assert len(entry.senses) == 9
    assert entry.senses[0].number == "1"
    assert "rovdyr" in entry.senses[0].text
    assert "ha, holde hund" in entry.senses[0].examples

    assert entry.idiom_count == 24
    assert len(entry.idioms) == 8  # capped sample, not the full 24
    assert all(idiom.phrase for idiom in entry.idioms)


def test_parses_single_implicit_sense_entry_with_no_numbering():
    """biff (adjective, slang) has exactly one meaning -- naob.no skips the
    numbered outline entirely for these, so this is the shape that
    previously parsed as zero senses."""
    html = (FIXTURES / "naob_entry_biff.html").read_text()
    entry = parse_entry(html, "biff_2")

    assert entry is not None
    assert entry.word == "biff"
    assert entry.word_class == "adjektiv"
    assert entry.etymology.startswith("fra svensk biff")

    assert len(entry.senses) == 1
    assert entry.senses[0].number == "1"
    assert entry.senses[0].text == "muntlig bifalt; godtatt; i orden"

    assert entry.idiom_count == 1
    assert entry.idioms[0].phrase == "saken er biff"
    assert "i orden" in entry.idioms[0].meaning


def test_parses_examples_capped_and_cross_reference_folded_into_sense_text():
    html = (FIXTURES / "naob_entry_bok.html").read_text()
    entry = parse_entry(html, "bok")

    assert entry is not None
    first = entry.senses[0]
    assert "kodeks" in first.text  # cross-reference folded into the definition
    assert len(first.examples) == 2  # capped at MAX_EXAMPLES_PER_SENSE, not all available

    assert entry.idiom_count == 17
    assert len(entry.idioms) == 8


def test_parse_entry_missing_article_returns_none():
    assert parse_entry("<html><body>not an entry page</body></html>", "xyz") is None
