from __future__ import annotations

from bs4 import BeautifulSoup

from .models import NaobEntry, NaobIdiom, NaobSearchEntry, NaobSense

MAX_EXAMPLES_PER_SENSE = 2
MAX_IDIOMS = 8


def parse_search_results(html: str) -> list[NaobSearchEntry]:
    """Parse the results list out of a naob.no /søk response.

    Note: like kryssord.org, the page can claim far more "totalt" hits than
    it actually renders (naob.no caps the list around 100 entries) -- this
    only returns what's actually present in the markup.
    """
    soup = BeautifulSoup(html, "lxml")
    entries = []
    for item in soup.select("li.page_listItem__Eq_Zl"):
        link = item.select_one("a.page_wordLink__ZXDKJ")
        if link is None:
            continue
        word = link.get_text(strip=True)
        slug = link.get("href", "").removeprefix("/ordbok/")

        word_class_tag = item.select_one("span.ordklasse-shortform")
        word_class = word_class_tag.get_text(strip=True) if word_class_tag else None

        short_html = item.select_one("div.page_shortHtml__EorPn")
        short_definition = _definition_text(short_html, word_class_tag)

        entries.append(
            NaobSearchEntry(word=word, slug=slug, word_class=word_class, short_definition=short_definition)
        )
    return entries


def _definition_text(short_html, word_class_tag) -> str:
    if short_html is None:
        return ""
    if word_class_tag is not None:
        word_class_tag.extract()
    return " ".join(short_html.get_text(" ", strip=True).split())


def parse_entry(html: str, slug: str) -> NaobEntry | None:
    """Parse a full naob.no /ordbok/<slug> entry page.

    `slug` is the slug the page was fetched with (the caller already knows
    it from the request URL) -- the page itself has no reliable single
    place to scrape it back out of.

    naob.no renders each meaning group twice: a compact clickable "outline"
    (div.betydningsentry) and the full detail block it links to
    (div.betydning), which carries examples/idioms/citations nested inside
    it. Entries with only one overall meaning skip the outline entirely, so
    senses are parsed from div.betydning -- the form that's always present.
    """
    soup = BeautifulSoup(html, "lxml")
    article = soup.select_one("article.WordDefinition_root__6HPmg")
    if article is None:
        return None

    headword_tag = article.select_one("span.oppslagsord")
    word = headword_tag.get_text(strip=True) if headword_tag else ""

    word_class_tag = article.select_one(".ordklasseledd span")
    word_class = word_class_tag.get_text(strip=True) if word_class_tag else None

    inflection_tag = article.select_one(".contentheading")
    inflection = _clean_text(inflection_tag.get_text(" ", strip=True)) if inflection_tag else None

    etymology = _parse_etymology(article)
    senses = _parse_senses(article)
    idioms, idiom_count = _parse_idioms(article)

    return NaobEntry(
        word=word,
        slug=slug,
        word_class=word_class,
        inflection=inflection,
        etymology=etymology,
        senses=senses,
        idioms=idioms,
        idiom_count=idiom_count,
    )


def _parse_senses(article) -> list[NaobSense]:
    senses = []
    for group in article.select("div.betydning"):
        number_tag = group.find("span", class_="betydningnr", recursive=False)
        if number_tag is not None:
            number = number_tag.get_text(strip=True)
            start = number_tag.find_next_sibling(True)
        else:
            number = "1"
            start = group.find(True, recursive=False)

        text = _collect_inline_eske_text(start)
        if not text:
            continue

        examples = [
            _clean_text(ex.get_text(" ", strip=True))
            for ex in group.select(":scope > div.redeksseksjon li > div.redeks")
        ][:MAX_EXAMPLES_PER_SENSE]

        senses.append(NaobSense(number=number, text=text, examples=examples))
    return senses


def _collect_inline_eske_text(start) -> str:
    parts = []
    el = start
    while el is not None and el.name == "div" and "inline-eske" in (el.get("class") or []):
        parts.append(el.get_text(" ", strip=True))
        el = el.find_next_sibling(True)
    return _clean_text(" ".join(parts))


def _parse_etymology(article) -> str | None:
    heading = _find_heading(article, "ETYMOLOGI")
    if heading is None:
        return None
    text = _clean_text(heading.parent.get_text(" ", strip=True))
    text = text.removeprefix("ETYMOLOGI").strip()
    return text or None


def _find_heading(article, label: str):
    for tag in article.select(".overskrift"):
        if tag.get_text(strip=True) == label:
            return tag
    return None


def _parse_idioms(article) -> tuple[list[NaobIdiom], int]:
    # Like senses, idioms render twice (a compact outline + the full detail
    # block it links to), and single-idiom entries skip the outline -- so
    # this reads from the full-detail form (div.uttrykk.inline-eske), which
    # is always present, rather than the sometimes-absent outline.
    phrase_tags = article.select("div.uttrykk.inline-eske")
    idioms = []
    for phrase_tag in phrase_tags[:MAX_IDIOMS]:
        phrase = _clean_text(phrase_tag.get_text(" ", strip=True))
        meaning_container = phrase_tag.find_next_sibling("div", class_="uttrykksbetydning")
        meaning_tag = meaning_container.select_one("div.inline-eske") if meaning_container else None
        meaning = _clean_text(meaning_tag.get_text(" ", strip=True)) if meaning_tag else ""
        idioms.append(NaobIdiom(phrase=phrase, meaning=meaning))
    return idioms, len(phrase_tags)


def _clean_text(text: str) -> str:
    text = " ".join(text.split())
    return text.replace(" ;", ";").replace(" ,", ",")
