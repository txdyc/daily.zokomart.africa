from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


@dataclass
class CandidateArticle:
    url: str
    title: str | None = None
    published_at: datetime | None = None  # naive UTC


@dataclass
class ExtractedArticle:
    title: str
    paragraphs: list[str] = field(default_factory=list)
    main_image_url: str | None = None
    published_at: datetime | None = None  # naive UTC


@dataclass
class FetchedPage:
    url: str
    html: str
    markdown: str | None = None  # present when fetched via Crawl4AI


class DiscoveryError(Exception):
    pass


class FetchError(Exception):
    pass


class ExtractionFailed(Exception):
    pass


def normalize_url(url: str, base_url: str) -> str | None:
    """Absolute URL with fragment and tracking params removed; None if not http(s)."""
    absolute = urljoin(base_url, url.strip())
    parts = urlparse(absolute)
    if parts.scheme not in ("http", "https"):
        return None
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.startswith("utm_") and k not in TRACKING_KEYS
    ]
    return urlunparse(
        (parts.scheme, parts.netloc, parts.path, parts.params, urlencode(query), "")
    )
