import pytest

import app.crawler.fetcher as fetcher
from app.crawler.contracts import FetchError


class FakeResponse:
    def __init__(self, text="<html>hi</html>", status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise fetcher.httpx.HTTPStatusError("boom", request=None, response=None)


def test_fetch_text_uses_browser_headers(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, timeout=None, follow_redirects=None):
        captured["headers"] = headers
        return FakeResponse("payload")

    monkeypatch.setattr(fetcher.httpx, "get", fake_get)
    assert fetcher.fetch_text("https://x.example/") == "payload"
    assert "Mozilla" in captured["headers"]["User-Agent"]


def test_fetch_page_falls_back_to_httpx_when_crawl4ai_unavailable(monkeypatch):
    def unavailable(url):
        raise fetcher.Crawl4AIUnavailable("not installed")

    monkeypatch.setattr(fetcher, "_fetch_with_crawl4ai", unavailable)
    monkeypatch.setattr(
        fetcher.httpx, "get",
        lambda url, headers=None, timeout=None, follow_redirects=None: FakeResponse("<p>ok</p>"),
    )
    page = fetcher.fetch_page("https://x.example/a")
    assert page.html == "<p>ok</p>"
    assert page.markdown is None


def test_fetch_page_with_retry_retries_once(monkeypatch):
    calls = {"n": 0}

    def flaky(url):
        calls["n"] += 1
        if calls["n"] == 1:
            raise FetchError("timeout")
        return fetcher.FetchedPage(url=url, html="<p>second try</p>")

    monkeypatch.setattr(fetcher, "fetch_page", flaky)
    monkeypatch.setattr(fetcher.time, "sleep", lambda s: None)
    page = fetcher.fetch_page_with_retry("https://x.example/a")
    assert page.html == "<p>second try</p>"
    assert calls["n"] == 2


def test_fetch_page_with_retry_gives_up(monkeypatch):
    def always_fail(url):
        raise FetchError("timeout")

    monkeypatch.setattr(fetcher, "fetch_page", always_fail)
    monkeypatch.setattr(fetcher.time, "sleep", lambda s: None)
    with pytest.raises(FetchError):
        fetcher.fetch_page_with_retry("https://x.example/a")


def test_fetch_text_rendered_delegates_to_fetch_page(monkeypatch):
    monkeypatch.setattr(
        fetcher,
        "fetch_page",
        lambda url: fetcher.FetchedPage(url=url, html="<p>rendered</p>", markdown="m"),
    )
    assert fetcher.fetch_text_rendered("https://x.example/listing") == "<p>rendered</p>"
