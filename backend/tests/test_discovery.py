from app.crawler.contracts import normalize_url


def test_normalize_url_strips_tracking_and_fragment():
    base = "https://punchng.com"
    assert (
        normalize_url("https://punchng.com/story/?utm_source=rss&utm_medium=feed", base)
        == "https://punchng.com/story/"
    )
    assert normalize_url("/story/#comments", base) == "https://punchng.com/story/"
    assert (
        normalize_url("https://x.example/a?fbclid=123&id=7", base)
        == "https://x.example/a?id=7"
    )
    assert normalize_url("mailto:x@y.z", base) is None
    assert normalize_url("javascript:void(0)", base) is None


from datetime import datetime
from pathlib import Path

import pytest

from app.crawler.contracts import DiscoveryError
from app.crawler.discovery import discover
from app.models import Country, Site

FIXTURES = Path(__file__).parent / "fixtures"


def _site(**kwargs):
    defaults = dict(
        country_id=1, name="Test", base_url="https://punchng.com",
        language="en", discovery_method="rss", feed_url="https://punchng.com/feed/",
    )
    defaults.update(kwargs)
    return Site(**defaults)


def test_rss_discovery_normalizes_dedupes_and_dates():
    feed_xml = (FIXTURES / "sample_feed.xml").read_text(encoding="utf-8")
    site = _site()
    got = discover(site, fetch_text=lambda url: feed_xml)
    urls = [c.url for c in got]
    assert urls == [
        "https://punchng.com/story-one/",
        "https://punchng.com/story-two/",
        "https://partner.example/wire-story",
    ]
    assert got[0].title == "Story one"
    assert got[0].published_at == datetime(2026, 7, 9, 10, 0, 0)
    assert got[2].published_at is None


def test_rss_discovery_unparseable_raises():
    site = _site()
    with pytest.raises(DiscoveryError):
        discover(site, fetch_text=lambda url: "this is not xml at all <<<")


def test_listing_discovery_heuristic_same_domain_depth():
    html = (FIXTURES / "sample_listing.html").read_text(encoding="utf-8")
    site = _site(
        base_url="https://www.ghanaweb.com", discovery_method="listing",
        feed_url=None, listing_url="https://www.ghanaweb.com/news/",
    )
    got = discover(site, fetch_text=lambda url: html)
    assert [c.url for c in got] == [
        "https://www.ghanaweb.com/news/2026/07/ghana-cocoa-forecast",
        "https://www.ghanaweb.com/news/2026/07/energy-project",
    ]
    assert got[0].title == "Cocoa forecast raised"


def test_listing_discovery_with_selector():
    html = (FIXTURES / "sample_listing.html").read_text(encoding="utf-8")
    site = _site(
        base_url="https://www.ghanaweb.com", discovery_method="listing",
        feed_url=None, listing_url="https://www.ghanaweb.com/news/",
        listing_selector=".headlines a",
    )
    got = discover(site, fetch_text=lambda url: html)
    assert len(got) == 2


def test_listing_fetch_error_raises_discovery_error():
    site = _site(discovery_method="listing", listing_url="https://x.example/")

    def boom(url):
        raise OSError("connection refused")

    with pytest.raises(DiscoveryError):
        discover(site, fetch_text=boom)
