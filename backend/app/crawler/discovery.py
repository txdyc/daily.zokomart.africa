from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urlparse

import feedparser
from bs4 import BeautifulSoup

from app.crawler.contracts import CandidateArticle, DiscoveryError, normalize_url
from app.models import Site
from app.timeutil import to_naive_utc

MAX_CANDIDATES = 20


def discover(site: Site, fetch_text: Callable[[str], str]) -> list[CandidateArticle]:
    """Return up to MAX_CANDIDATES newest article candidates for a site.

    fetch_text(url) -> str is injected so tests run offline.
    """
    if site.discovery_method == "rss":
        return _discover_rss(site, fetch_text)
    return _discover_listing(site, fetch_text)


def _discover_rss(site: Site, fetch_text) -> list[CandidateArticle]:
    try:
        raw = fetch_text(site.feed_url)
    except Exception as e:
        raise DiscoveryError(f"Cannot fetch feed {site.feed_url}: {e}") from e
    parsed = feedparser.parse(raw)
    if not parsed.entries:
        reason = getattr(parsed, "bozo_exception", "no entries")
        raise DiscoveryError(f"Cannot parse feed {site.feed_url}: {reason}")
    candidates: list[CandidateArticle] = []
    for entry in parsed.entries:
        url = normalize_url(entry.get("link", ""), site.base_url)
        if not url:
            continue
        published = None
        if entry.get("published_parsed"):
            published = to_naive_utc(
                datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            )
        candidates.append(
            CandidateArticle(url=url, title=entry.get("title"), published_at=published)
        )
    return _dedupe_keep_order(candidates)[:MAX_CANDIDATES]


def _discover_listing(site: Site, fetch_text) -> list[CandidateArticle]:
    try:
        html = fetch_text(site.listing_url)
    except Exception as e:
        raise DiscoveryError(f"Cannot fetch listing {site.listing_url}: {e}") from e
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.select(site.listing_selector) if site.listing_selector else soup.find_all("a")
    domain = urlparse(site.base_url).netloc
    candidates: list[CandidateArticle] = []
    for a in anchors:
        href = a.get("href")
        if not href:
            continue
        url = normalize_url(href, site.base_url)
        if not url:
            continue
        parts = urlparse(url)
        if parts.netloc != domain:
            continue
        if not site.listing_selector:
            depth = len([p for p in parts.path.split("/") if p])
            if depth < 2:
                continue
        title = a.get_text(strip=True) or None
        candidates.append(CandidateArticle(url=url, title=title))
    return _dedupe_keep_order(candidates)[:MAX_CANDIDATES]


def _dedupe_keep_order(candidates: list[CandidateArticle]) -> list[CandidateArticle]:
    seen: set[str] = set()
    out = []
    for c in candidates:
        if c.url in seen:
            continue
        seen.add(c.url)
        out.append(c)
    return out
