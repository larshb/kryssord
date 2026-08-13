import pytest
import requests

from kryssord.naob_client import NaobClient


@pytest.fixture
def client(tmp_path):
    c = NaobClient(cache_path=tmp_path / "naob_cache.sqlite", min_interval=0)
    yield c
    c.close()


def _fake_response(status_code, headers=None, text=""):
    response = requests.Response()
    response.status_code = status_code
    response.headers.update(headers or {})
    response._content = text.encode("utf-8")
    return response


def test_search_empty_query_raises(client):
    with pytest.raises(ValueError):
        client.search("   ")


def test_search_no_hits_redirect_returns_empty_without_following(client, monkeypatch):
    calls = []

    def fake_get(url, params=None, allow_redirects=True):
        calls.append((url, params, allow_redirects))
        return _fake_response(307, headers={"Location": "/nulltreff/xyzabc"})

    monkeypatch.setattr(client, "_get", fake_get)

    assert client.search("xyzabc") == []
    assert len(calls) == 1
    assert calls[0][2] is False  # never asked requests to follow the redirect


def test_search_single_hit_redirect_returns_one_result(client, monkeypatch):
    """naob.no redirects straight to /ordbok/<slug> (not a results list) when
    there's exactly one match -- this must not be read as zero hits."""
    monkeypatch.setattr(client, "_get", lambda *a, **k: _fake_response(307, headers={"Location": "/ordbok/jul"}))

    results = client.search("jul")

    assert len(results) == 1
    assert results[0].word == "jul"
    assert results[0].slug == "jul"


def test_get_entry_404_returns_none(client, monkeypatch):
    monkeypatch.setattr(client, "_get", lambda *a, **k: _fake_response(404))
    assert client.get_entry("does-not-exist") is None
