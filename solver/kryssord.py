import urllib.request
import urllib.parse
import re


class KryssordOrg:
    def __init__(self, url: str = "https://kryssord.org"):
        self.url = url

    def _download_html(self, url: str) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read()

    def _parse_html(
        self,
        html: bytes,
        word_regex: str = r"<td class=\"word\">\s*?<a href=\"(.*?)\">\s*?([^\s]+.*?)\s*?<\/a>\s*?<\/td>",
        total_regex: str = r"Fant <strong>(\d+)</strong>",
    ) -> tuple[list[dict], int]:
        text = html.decode("utf-8")
        words = [
            {"word": match[1], "link": match[0]}
            for match in re.findall(word_regex, text)
        ]
        total_match = re.search(total_regex, text)
        total = int(total_match.group(1)) if total_match else len(words)
        return words, total

    def search(self, a: str, b: str = "", endpoint: str = "/search.php") -> dict:
        """
        Look up words on kryssord.org.

        a: clue text (required, non-empty)
        b: pattern string, e.g. "kr?ss?rd" (optional)
           Use '?' for a single unknown character.
           Use '*' for any number of unknown characters (manual searches only).
        """
        params: dict[str, str] = {"a": a}
        if b:
            params["b"] = b
        url = f"{self.url}{endpoint}?" + urllib.parse.urlencode(params)
        html = self._download_html(url)
        words, total = self._parse_html(html)
        return {
            "url": url,
            "query": {"a": a, "b": b},
            "results": {
                "words": words,
                "total": total,
            },
        }
