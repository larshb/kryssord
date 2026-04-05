import re
import urllib.request
import urllib.parse


class KryssordOrg:
    def __init__(self, url: str = "https://kryssord.org"):
        self.url = url

    def _download_html(self, url: str):
        response = urllib.request.urlopen(url)
        return response.read()

    def _parse_html(
        self,
        html: bytes,
        word_regex=r"<td class=\"word\">\s*?<a href=\"(.*?)\">\s*?([^\s]+.*?)\s*?<\/a>\s*?<\/td>",
    ):
        text = html.decode("utf-8")
        for match in re.findall(word_regex, text):
            yield {"word": match[1], "link": match[0]}

    def search(self, a: str, b: str, endpoint: str = "/search.php"):
        params = {"a": a, "b": b}
        url = f"{self.url}{endpoint}" + "?" + urllib.parse.urlencode(params)
        html = self._download_html(url)
        return {
            "url": url,
            "query": {"a": a, "b": b},
            "results": list(self._parse_html(html)),
        }


# --- Flask -----------------------------------------------------------------------------------------
import flask
from flask_cors import CORS

app = flask.Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

kryssord = KryssordOrg()


@app.route("/")
def wakeup():
    return flask.jsonify({"status": "alive"})


@app.route("/search")
def search():
    a = flask.request.args.get("a")  # required
    b = flask.request.args.get("b")  # optional
    if not a:
        return flask.jsonify({"error": "Search word (a) required"}), 400
    if not b:
        b = ""
    search = kryssord.search(a, b)
    return flask.jsonify(search)


if __name__ == "__main__":
    app.run(debug=True)
