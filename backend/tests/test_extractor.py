from datetime import datetime
from pathlib import Path

import pytest

from app.crawler.contracts import ExtractionFailed, FetchedPage
from app.crawler.extractor import extract
from app.models import Site

FIXTURES = Path(__file__).parent / "fixtures"


def _site(**kwargs):
    defaults = dict(
        country_id=1, name="Test", base_url="https://www.myjoyonline.com",
        language="en", discovery_method="rss",
    )
    defaults.update(kwargs)
    return Site(**defaults)


def test_generic_extraction_from_html():
    html = (FIXTURES / "article_en.html").read_text(encoding="utf-8")
    got = extract(FetchedPage(url="https://x/a", html=html), _site())
    assert got.title == "Bank of Ghana unveils new forex policy"
    assert got.main_image_url == "https://cdn.example/img/forex.jpg"
    assert got.published_at == datetime(2026, 7, 9, 10, 30)
    assert len(got.paragraphs) == 3  # "Ad" too short, "Share this..." boilerplate dropped
    assert got.paragraphs[0].startswith("The Bank of Ghana")


def test_selector_override_extraction():
    html = (FIXTURES / "article_override.html").read_text(encoding="utf-8")
    site = _site(
        title_selector="h2.headline",
        body_selector="div.story-text",
        image_selector="img.lead-photo",
        date_selector="span.pub-date",
    )
    got = extract(FetchedPage(url="https://x/b", html=html), site)
    assert got.title == "Le Sénégal accueille un salon agricole majeur"
    assert got.main_image_url == "https://cdn.example/salon.jpg"
    assert got.published_at == datetime(2026, 7, 8, 14, 0)
    assert len(got.paragraphs) == 2  # comments div not inside body_selector


def test_generic_extraction_prefers_markdown_when_present():
    md = (
        "First markdown paragraph that is definitely long enough to keep here.\n\n"
        "[a link-only line](https://x)\n\n"
        "Second markdown paragraph that is also long enough to pass the filter."
    )
    got = extract(
        FetchedPage(url="https://x/c", html="<html><h1>Title here</h1></html>", markdown=md),
        _site(),
    )
    assert got.paragraphs == [
        "First markdown paragraph that is definitely long enough to keep here.",
        "Second markdown paragraph that is also long enough to pass the filter.",
    ]


def test_quality_gate_raises_on_thin_page():
    with pytest.raises(ExtractionFailed):
        extract(
            FetchedPage(url="https://x/d", html="<html><h1>Only a title</h1><p>Too short.</p></html>"),
            _site(),
        )


def test_relative_image_url_is_resolved():
    html = (
        '<html><head>'
        '<meta property="og:title" content="Test Article">'
        '<meta property="og:image" content="../../public/img/logo.jpg">'
        '</head><body>'
        f'<p>{"a" * 50}</p><p>{"b" * 50}</p>'
        '</body></html>'
    )
    got = extract(
        FetchedPage(url="https://news.example.com/articles/123/test", html=html),
        _site(),
    )
    assert got.main_image_url == "https://news.example.com/public/img/logo.jpg"
