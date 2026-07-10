# ZokoDaily Plan 2: Crawler & Translation Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn configured `site` rows into `published` articles: discovery → fetch → extract → translate+classify, scheduled by APScheduler and monitorable/triggerable from the admin API.

**Architecture:** New `app/crawler/` package (discovery, fetcher, extractor, LLM fallback, pipeline orchestrator) and `app/translate/` package (OpenAI-compatible client + translator), wired to APScheduler jobs started in the FastAPI lifespan. Sites remain data; no per-site code. All pytest tests run offline against fixture files and mocks; live crawling is verified manually at the end.

**Tech Stack:** feedparser, BeautifulSoup4, Crawl4AI (+Playwright Chromium) with httpx fallback, httpx for the LLM API, APScheduler.

**Spec:** `docs/superpowers/specs/2026-07-10-crawler-translation-pipeline-design.md`
**Working directory:** all commands run from `backend/` unless stated otherwise.

---

## File structure created/modified by this plan

```
backend/app/
├── timeutil.py                    # NEW: to_naive_utc, utcnow_naive
├── config.py                      # MOD: + scheduler_enabled
├── main.py                        # MOD: start/stop scheduler in lifespan
├── scheduler.py                   # NEW: build_scheduler + job functions
├── crawler/
│   ├── __init__.py                # NEW (empty)
│   ├── contracts.py               # NEW: dataclasses + exceptions + normalize_url
│   ├── discovery.py               # NEW: RSS + listing discovery
│   ├── fetcher.py                 # NEW: fetch_text (httpx), fetch_page (Crawl4AI→httpx)
│   ├── extractor.py               # NEW: selector/generic extraction + quality gate
│   ├── llm_extractor.py           # NEW: LLM fallback extraction
│   └── pipeline.py                # NEW: crawl_site orchestration
├── translate/
│   ├── __init__.py                # NEW (empty)
│   ├── client.py                  # NEW: chat_json (OpenAI-compatible)
│   └── translator.py              # NEW: translate_article, run_translation_sweep
├── api/admin/
│   ├── countries.py               # MOD: delete guard, duplicate 409
│   ├── sites.py                   # MOD: delete guard, duplicate 409, country_id 422
│   ├── crawl.py                   # NEW: crawl-runs list, crawl-now trigger
│   └── config.py                  # MOD: + test-translation endpoint
backend/tests/
├── conftest.py                    # MOD: + SCHEDULER_ENABLED=false
├── fixtures/                      # NEW: sample_feed.xml, sample_listing.html,
│                                  #      article_en.html, article_override.html
├── test_admin_integrity.py        # NEW (Task 1)
├── test_discovery.py              # NEW (Task 3)
├── test_fetcher.py                # NEW (Task 4)
├── test_extractor.py              # NEW (Task 5)
├── test_ai_client.py              # NEW (Task 6)
├── test_translator.py             # NEW (Task 7)
├── test_pipeline.py               # NEW (Task 8)
├── test_scheduler.py              # NEW (Task 9)
└── test_admin_crawl.py            # NEW (Task 10)
.gitignore                         # MOD: + *.db
```

---

### Task 1: Plan 1 carry-over integrity fixes

**Files:**
- Modify: `backend/app/api/admin/countries.py`
- Modify: `backend/app/api/admin/sites.py`
- Modify: `.gitignore` (repo root)
- Test: `backend/tests/test_admin_integrity.py`

- [ ] **Step 1: Write the failing tests — `backend/tests/test_admin_integrity.py`**

```python
import pytest

from app.models import AdminUser, Article, Country, Site
from app.security import hash_password


@pytest.fixture()
def auth_headers(client, db_session):
    db_session.add(AdminUser(username="admin", password_hash=hash_password("pw")))
    db_session.commit()
    token = client.post(
        "/api/admin/auth/login", json={"username": "admin", "password": "pw"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def ghana(db_session):
    country = Country(code="GH", name_en="Ghana", name_zh="加纳", flag_emoji="🇬🇭")
    db_session.add(country)
    db_session.commit()
    return country


@pytest.fixture()
def joy(db_session, ghana):
    site = Site(country_id=ghana.id, name="MyJoyOnline",
                base_url="https://www.myjoyonline.com", language="en",
                discovery_method="rss", feed_url="https://www.myjoyonline.com/feed/")
    db_session.add(site)
    db_session.commit()
    return site


def test_delete_country_with_sites_409(client, auth_headers, ghana, joy):
    r = client.delete(f"/api/admin/countries/{ghana.id}", headers=auth_headers)
    assert r.status_code == 409


def test_delete_site_with_articles_409(client, auth_headers, db_session, ghana, joy):
    db_session.add(Article(site_id=joy.id, country_id=ghana.id,
                           source_url="https://x/1", source_language="en",
                           title="t", paragraphs=["p"]))
    db_session.commit()
    r = client.delete(f"/api/admin/sites/{joy.id}", headers=auth_headers)
    assert r.status_code == 409


def test_delete_country_without_children_ok(client, auth_headers, ghana):
    r = client.delete(f"/api/admin/countries/{ghana.id}", headers=auth_headers)
    assert r.status_code == 204


def test_duplicate_country_code_409(client, auth_headers, ghana):
    r = client.post(
        "/api/admin/countries",
        json={"code": "GH", "name_en": "Ghana2", "name_zh": "加纳2", "flag_emoji": "🇬🇭"},
        headers=auth_headers,
    )
    assert r.status_code == 409


def test_duplicate_site_base_url_409(client, auth_headers, ghana, joy):
    r = client.post(
        "/api/admin/sites",
        json={"country_id": ghana.id, "name": "Copy",
              "base_url": "https://www.myjoyonline.com", "language": "en",
              "discovery_method": "rss"},
        headers=auth_headers,
    )
    assert r.status_code == 409


def test_site_with_unknown_country_422(client, auth_headers):
    r = client.post(
        "/api/admin/sites",
        json={"country_id": 9999, "name": "Ghost", "base_url": "https://ghost.example",
              "language": "en", "discovery_method": "rss"},
        headers=auth_headers,
    )
    assert r.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_admin_integrity.py -v`
Expected: FAIL — 409/422 assertions get 500/201/204

- [ ] **Step 3: Update `backend/app/api/admin/countries.py`** (add checks; full changed functions)

```python
from app.models import Article, Country, Site


@router.post("", response_model=CountryOut, status_code=201)
def create_country(body: CountryIn, db: Session = Depends(get_db)):
    if db.query(Country).filter_by(code=body.code).first() is not None:
        raise HTTPException(status_code=409, detail=f"Country code {body.code} already exists")
    country = Country(**body.model_dump())
    db.add(country)
    db.commit()
    db.refresh(country)
    return country


@router.delete("/{country_id}", status_code=204)
def delete_country(country_id: int, db: Session = Depends(get_db)):
    country = _get_or_404(db, country_id)
    has_children = (
        db.query(Site.id).filter_by(country_id=country_id).first() is not None
        or db.query(Article.id).filter_by(country_id=country_id).first() is not None
    )
    if has_children:
        raise HTTPException(
            status_code=409,
            detail="Country still has sites or articles; delete those first",
        )
    db.delete(country)
    db.commit()
```

- [ ] **Step 4: Update `backend/app/api/admin/sites.py`** (full changed functions)

```python
from app.models import Article, Country, Site


@router.post("", response_model=SiteOut, status_code=201)
def create_site(body: SiteIn, db: Session = Depends(get_db)):
    if db.get(Country, body.country_id) is None:
        raise HTTPException(status_code=422, detail=f"country_id {body.country_id} does not exist")
    if db.query(Site.id).filter_by(base_url=body.base_url).first() is not None:
        raise HTTPException(status_code=409, detail=f"Site with base_url {body.base_url} already exists")
    site = Site(**body.model_dump())
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.delete("/{site_id}", status_code=204)
def delete_site(site_id: int, db: Session = Depends(get_db)):
    site = _get_or_404(db, site_id)
    if db.query(Article.id).filter_by(site_id=site_id).first() is not None:
        raise HTTPException(
            status_code=409,
            detail="Site still has articles; delete those first",
        )
    db.delete(site)
    db.commit()
```

Also apply the same existence check to `update_site` (a PUT that moves a site to a
nonexistent `country_id` must 422):

```python
@router.put("/{site_id}", response_model=SiteOut)
def update_site(site_id: int, body: SiteIn, db: Session = Depends(get_db)):
    site = _get_or_404(db, site_id)
    if db.get(Country, body.country_id) is None:
        raise HTTPException(status_code=422, detail=f"country_id {body.country_id} does not exist")
    for field, value in body.model_dump().items():
        setattr(site, field, value)
    db.commit()
    db.refresh(site)
    return site
```

- [ ] **Step 5: Add `*.db` to repo-root `.gitignore`** (append line: `*.db`)

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/ -v`
Expected: all pass (existing suite + 6 new)

- [ ] **Step 7: Commit**

```bash
git add .gitignore backend/
git commit -m "fix(backend): guard deletes, 409 duplicates, validate site country_id"
```

---

### Task 2: Dependencies, time utils, crawler contracts

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/app/timeutil.py`, `backend/app/crawler/__init__.py`, `backend/app/crawler/contracts.py`
- Test: `backend/tests/test_discovery.py` (contracts portion — grows in Task 3)

- [ ] **Step 1: Update `backend/pyproject.toml` dependencies** (move httpx from dev to main, add new)

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy>=2.0",
    "pymysql>=1.1",
    "cryptography>=43",
    "pydantic-settings>=2.4",
    "bcrypt>=4.2",
    "pyjwt>=2.9",
    "httpx>=0.27",
    "feedparser>=6.0",
    "beautifulsoup4>=4.12",
    "crawl4ai>=0.6",
    "apscheduler>=3.10",
]

[dependency-groups]
dev = [
    "pytest>=8",
]
```

Run: `cd backend && uv sync`
Expected: resolves; crawl4ai pulls playwright (browser download happens in Task 11, not now).

- [ ] **Step 2: Write the failing test — normalize_url cases at top of `backend/tests/test_discovery.py`**

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_discovery.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.crawler'`

- [ ] **Step 4: Create the modules**

`backend/app/timeutil.py`:

```python
from datetime import datetime, timezone


def to_naive_utc(dt: datetime | None) -> datetime | None:
    """Normalize any datetime to naive UTC (MySQL DATETIME drops tzinfo silently)."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
```

`backend/app/crawler/__init__.py`: empty file.

`backend/app/crawler/contracts.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_discovery.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/timeutil.py backend/app/crawler/ backend/tests/test_discovery.py
git commit -m "feat(crawler): add dependencies, time utils, and crawler contracts"
```

---

### Task 3: Discovery (RSS + listing)

**Files:**
- Create: `backend/app/crawler/discovery.py`
- Create: `backend/tests/fixtures/sample_feed.xml`, `backend/tests/fixtures/sample_listing.html`
- Test: `backend/tests/test_discovery.py` (append)

- [ ] **Step 1: Create fixture files**

`backend/tests/fixtures/sample_feed.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Punch</title>
    <link>https://punchng.com</link>
    <item>
      <title>Story one</title>
      <link>https://punchng.com/story-one/?utm_source=rss</link>
      <pubDate>Thu, 09 Jul 2026 10:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Story two</title>
      <link>https://punchng.com/story-two/#comments</link>
      <pubDate>Thu, 09 Jul 2026 09:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Story one duplicate</title>
      <link>https://punchng.com/story-one/</link>
    </item>
    <item>
      <title>Syndicated external</title>
      <link>https://partner.example/wire-story</link>
    </item>
  </channel>
</rss>
```

`backend/tests/fixtures/sample_listing.html`:

```html
<html><body>
<nav><a href="/">Home</a><a href="/news/">News</a></nav>
<div class="headlines">
  <a href="/news/2026/07/ghana-cocoa-forecast">Cocoa forecast raised</a>
  <a href="https://www.ghanaweb.com/news/2026/07/energy-project?fbclid=abc">Energy project</a>
  <a href="https://twitter.com/ghanaweb">Twitter</a>
  <a href="/news/2026/07/ghana-cocoa-forecast">Cocoa forecast raised (duplicate)</a>
</div>
</body></html>
```

- [ ] **Step 2: Write the failing tests — append to `backend/tests/test_discovery.py`**

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_discovery.py -v`
Expected: FAIL with `ImportError` (no `app.crawler.discovery`)

- [ ] **Step 4: Create `backend/app/crawler/discovery.py`**

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_discovery.py -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/crawler/discovery.py backend/tests/
git commit -m "feat(crawler): RSS and listing discovery with URL normalization"
```

---

### Task 4: Fetcher (Crawl4AI with httpx fallback)

**Files:**
- Create: `backend/app/crawler/fetcher.py`
- Test: `backend/tests/test_fetcher.py`

- [ ] **Step 1: Write the failing tests — `backend/tests/test_fetcher.py`**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_fetcher.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.crawler.fetcher'`

- [ ] **Step 3: Create `backend/app/crawler/fetcher.py`**

```python
import asyncio
import logging
import time

import httpx

from app.crawler.contracts import FetchedPage, FetchError

logger = logging.getLogger(__name__)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
}

PAGE_TIMEOUT_SECONDS = 30.0
RETRY_BACKOFF_SECONDS = 10.0


class Crawl4AIUnavailable(Exception):
    pass


def fetch_text(url: str, timeout: float = PAGE_TIMEOUT_SECONDS) -> str:
    """Plain GET with browser headers — used for feeds and listing pages."""
    resp = httpx.get(url, headers=BROWSER_HEADERS, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def fetch_page(url: str) -> FetchedPage:
    """Fetch an article page. Crawl4AI (headless Chromium) first, httpx degraded mode second."""
    try:
        return _fetch_with_crawl4ai(url)
    except Crawl4AIUnavailable as e:
        logger.warning("Crawl4AI unavailable (%s); falling back to httpx for %s", e, url)
    except FetchError:
        raise
    try:
        return FetchedPage(url=url, html=fetch_text(url))
    except httpx.HTTPError as e:
        raise FetchError(f"httpx fetch failed for {url}: {e}") from e


def fetch_page_with_retry(url: str) -> FetchedPage:
    try:
        return fetch_page(url)
    except FetchError:
        time.sleep(RETRY_BACKOFF_SECONDS)
        return fetch_page(url)


def _fetch_with_crawl4ai(url: str) -> FetchedPage:
    try:
        from crawl4ai import AsyncWebCrawler
    except ImportError as e:
        raise Crawl4AIUnavailable(str(e)) from e

    async def _run() -> FetchedPage:
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)
            if not result.success:
                raise FetchError(result.error_message or f"crawl failed for {url}")
            return FetchedPage(
                url=url, html=result.html or "", markdown=str(result.markdown or "") or None
            )

    try:
        return asyncio.run(_run())
    except FetchError:
        raise
    except Exception as e:
        raise Crawl4AIUnavailable(f"Crawl4AI runtime error: {e}") from e
```

Note: a Crawl4AI *runtime* error (e.g. Chromium not installed) degrades to httpx rather
than failing the article — per spec §9. A clean `FetchError` from a successful Crawl4AI
session (page truly unreachable) propagates so retry/backoff applies.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_fetcher.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/crawler/fetcher.py backend/tests/test_fetcher.py
git commit -m "feat(crawler): page fetcher with Crawl4AI and httpx degraded mode"
```

---

### Task 5: Extractor (selectors → generic → quality gate)

**Files:**
- Create: `backend/app/crawler/extractor.py`
- Create: `backend/tests/fixtures/article_en.html`, `backend/tests/fixtures/article_override.html`
- Test: `backend/tests/test_extractor.py`

- [ ] **Step 1: Create fixture files**

`backend/tests/fixtures/article_en.html`:

```html
<html><head>
<meta property="og:title" content="Bank of Ghana unveils new forex policy" />
<meta property="og:image" content="https://cdn.example/img/forex.jpg" />
<meta property="article:published_time" content="2026-07-09T10:30:00+00:00" />
<title>Bank of Ghana unveils new forex policy - MyJoy</title>
</head><body>
<nav><a href="/">Home</a></nav>
<div class="content-area">
  <h1>Bank of Ghana unveils new forex policy</h1>
  <div class="post-body">
    <p>The Bank of Ghana on Thursday announced a set of foreign-exchange measures aimed at easing pressure on the cedi.</p>
    <p>Ad</p>
    <p>The governor's office said the policy will take effect from August, with commercial banks required to report daily currency positions.</p>
    <p>Share this article with your friends on social media platforms.</p>
    <p>Analysts welcomed the move, describing it as a pragmatic response to recent volatility in the market.</p>
  </div>
</div>
<footer><p>Copyright 2026 MyJoyOnline. All rights reserved worldwide press.</p></footer>
</body></html>
```

`backend/tests/fixtures/article_override.html`:

```html
<html><head><title>page title tag</title></head><body>
<h2 class="headline">Le Sénégal accueille un salon agricole majeur</h2>
<img class="lead-photo" src="https://cdn.example/salon.jpg" />
<span class="pub-date">2026-07-08T14:00:00+00:00</span>
<div class="story-text">
  <p>Le salon agricole a ouvert ses portes ce mardi à Dakar avec plus de deux cents exposants venus de toute la région.</p>
  <p>Les organisateurs attendent près de cinquante mille visiteurs pendant toute la durée de cet événement régional.</p>
</div>
<div class="comments"><p>Great event! Congratulations to everyone who organized this wonderful thing.</p></div>
</body></html>
```

- [ ] **Step 2: Write the failing tests — `backend/tests/test_extractor.py`**

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_extractor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.crawler.extractor'`

- [ ] **Step 4: Create `backend/app/crawler/extractor.py`**

```python
import re
from datetime import datetime

from bs4 import BeautifulSoup

from app.crawler.contracts import ExtractedArticle, ExtractionFailed, FetchedPage
from app.models import Site
from app.timeutil import to_naive_utc

MIN_PARAGRAPH_CHARS = 40
MIN_TOTAL_CHARS = 300
BOILERPLATE = re.compile(
    r"^(share this|read more|related article|follow us|subscribe|copyright|©|advertisement)",
    re.IGNORECASE,
)
LINK_ONLY = re.compile(r"^\W*!?\[[^\]]*\]\([^)]*\)\W*$")


def extract(page: FetchedPage, site: Site) -> ExtractedArticle:
    soup = BeautifulSoup(page.html, "html.parser")
    if site.body_selector:
        article = _extract_with_selectors(soup, site)
    else:
        article = _extract_generic(soup, page.markdown)
    if not _passes_quality_gate(article):
        raise ExtractionFailed(
            f"quality gate failed for {page.url}: "
            f"title={bool(article.title)}, paragraphs={len(article.paragraphs)}"
        )
    return article


def _extract_with_selectors(soup: BeautifulSoup, site: Site) -> ExtractedArticle:
    title = None
    if site.title_selector:
        el = soup.select_one(site.title_selector)
        title = el.get_text(strip=True) if el else None
    title = title or _og(soup, "og:title") or _h1(soup)

    paragraphs: list[str] = []
    body_root = soup.select_one(site.body_selector)
    if body_root is not None:
        paragraphs = _clean_paragraphs(
            p.get_text(" ", strip=True) for p in body_root.find_all("p")
        )

    image = None
    if site.image_selector:
        el = soup.select_one(site.image_selector)
        image = el.get("src") if el else None
    image = image or _og(soup, "og:image")

    published = None
    if site.date_selector:
        el = soup.select_one(site.date_selector)
        published = _parse_iso(el.get_text(strip=True)) if el else None
    published = published or _meta_published(soup)

    return ExtractedArticle(
        title=title or "", paragraphs=paragraphs,
        main_image_url=image, published_at=published,
    )


def _extract_generic(soup: BeautifulSoup, markdown: str | None) -> ExtractedArticle:
    title = _og(soup, "og:title") or _h1(soup)
    if markdown:
        raw = markdown.split("\n\n")
    else:
        container = _densest_paragraph_container(soup)
        raw = (
            [p.get_text(" ", strip=True) for p in container.find_all("p")]
            if container is not None
            else []
        )
    return ExtractedArticle(
        title=title or "",
        paragraphs=_clean_paragraphs(raw),
        main_image_url=_og(soup, "og:image"),
        published_at=_meta_published(soup),
    )


def _clean_paragraphs(raw) -> list[str]:
    out: list[str] = []
    for p in raw:
        p = re.sub(r"\s+", " ", p).strip()
        if len(p) < MIN_PARAGRAPH_CHARS:
            continue
        if BOILERPLATE.match(p):
            continue
        if LINK_ONLY.match(p):
            continue
        out.append(p)
    return out


def _passes_quality_gate(a: ExtractedArticle) -> bool:
    total = sum(len(p) for p in a.paragraphs)
    return bool(a.title) and (len(a.paragraphs) >= 2 or total >= MIN_TOTAL_CHARS)


def _densest_paragraph_container(soup: BeautifulSoup):
    """Element whose direct <p> children carry the most text — the article body."""
    best, best_len = None, 0
    for el in soup.find_all(True):
        total = sum(len(p.get_text(strip=True)) for p in el.find_all("p", recursive=False))
        if total > best_len:
            best, best_len = el, total
    return best


def _og(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", attrs={"property": prop})
    if tag is None:
        return None
    content = (tag.get("content") or "").strip()
    return content or None


def _h1(soup: BeautifulSoup) -> str | None:
    el = soup.find("h1")
    return el.get_text(strip=True) if el else None


def _meta_published(soup: BeautifulSoup) -> datetime | None:
    return _parse_iso(_og(soup, "article:published_time") or "")


def _parse_iso(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return to_naive_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_extractor.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/crawler/extractor.py backend/tests/
git commit -m "feat(crawler): selector and generic extraction with quality gate"
```

---

### Task 6: AI client + LLM extraction fallback

**Files:**
- Create: `backend/app/translate/__init__.py` (empty), `backend/app/translate/client.py`
- Create: `backend/app/crawler/llm_extractor.py`
- Test: `backend/tests/test_ai_client.py`

- [ ] **Step 1: Write the failing tests — `backend/tests/test_ai_client.py`**

```python
import json

import pytest

import app.translate.client as client_mod
from app.crawler.llm_extractor import extract_with_llm
from app.models import AppConfig
from app.translate.client import AIConfigMissing, AIError, chat_json


@pytest.fixture()
def ai_config(db_session):
    db_session.add_all([
        AppConfig(key="ai_base_url", value="https://api.test/v1"),
        AppConfig(key="ai_api_key", value="sk-test"),
        AppConfig(key="ai_model", value="test-model"),
    ])
    db_session.commit()


class FakeResponse:
    def __init__(self, content):
        self._content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def test_chat_json_posts_and_parses(monkeypatch, db_session, ai_config):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["model"] = json["model"]
        return FakeResponse('{"answer": 42}')

    monkeypatch.setattr(client_mod.httpx, "post", fake_post)
    assert chat_json(db_session, "sys", "user") == {"answer": 42}
    assert captured["url"] == "https://api.test/v1/chat/completions"
    assert captured["model"] == "test-model"


def test_chat_json_missing_key_raises(db_session):
    with pytest.raises(AIConfigMissing):
        chat_json(db_session, "sys", "user")


def test_chat_json_bad_json_raises_ai_error(monkeypatch, db_session, ai_config):
    monkeypatch.setattr(
        client_mod.httpx, "post",
        lambda url, headers=None, json=None, timeout=None: FakeResponse("not json"),
    )
    with pytest.raises(AIError):
        chat_json(db_session, "sys", "user")


def test_extract_with_llm_parses_article(monkeypatch, db_session, ai_config):
    payload = {
        "title": "Extracted title",
        "paragraphs": ["First paragraph text.", "  ", "Second paragraph text."],
        "image_url": "https://cdn.example/x.jpg",
        "published_at": "2026-07-09T08:00:00Z",
    }
    monkeypatch.setattr(
        client_mod.httpx, "post",
        lambda url, headers=None, json=None, timeout=None: FakeResponse(
            __import__("json").dumps(payload)
        ),
    )
    got = extract_with_llm(db_session, "<html><script>x</script><p>body</p></html>")
    assert got.title == "Extracted title"
    assert got.paragraphs == ["First paragraph text.", "Second paragraph text."]
    assert got.main_image_url == "https://cdn.example/x.jpg"
    assert got.published_at is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_ai_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.translate'`

- [ ] **Step 3: Create `backend/app/translate/client.py`** (and empty `backend/app/translate/__init__.py`)

```python
import json

import httpx
from sqlalchemy.orm import Session

from app.services.config_service import get_config

REQUEST_TIMEOUT_SECONDS = 120.0


class AIConfigMissing(Exception):
    pass


class AIError(Exception):
    pass


def chat_json(db: Session, system: str, user: str) -> dict:
    """One JSON-mode chat completion against the admin-configured OpenAI-compatible API.

    Config is read fresh from app_config on every call so admin changes apply
    without a restart.
    """
    base_url = get_config(db, "ai_base_url")
    api_key = get_config(db, "ai_api_key")
    model = get_config(db, "ai_model")
    if not api_key:
        raise AIConfigMissing("AI API key not configured")
    try:
        resp = httpx.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as e:
        raise AIError(f"AI request failed: {e}") from e
```

- [ ] **Step 4: Create `backend/app/crawler/llm_extractor.py`**

```python
import json

from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.crawler.contracts import ExtractedArticle, ExtractionFailed
from app.crawler.extractor import _parse_iso
from app.translate.client import AIError, chat_json

HTML_CAP_CHARS = 30_000

EXTRACT_SYSTEM = """You extract news articles from raw HTML.
Return ONLY a JSON object with exactly these keys:
{"title": string, "paragraphs": [string], "image_url": string or null, "published_at": ISO-8601 string or null}
- paragraphs: the article body split by its natural paragraphs, in order, no ads or navigation text.
- Do not translate anything; keep the source language."""


def extract_with_llm(db: Session, html: str) -> ExtractedArticle:
    trimmed = _trim_html(html)
    last_error: Exception | None = None
    for _ in range(2):
        try:
            data = chat_json(db, EXTRACT_SYSTEM, trimmed)
            title = (data.get("title") or "").strip()
            paragraphs = [p.strip() for p in data.get("paragraphs", []) if p and p.strip()]
            if not title or not paragraphs:
                raise ExtractionFailed("LLM returned empty title or paragraphs")
            return ExtractedArticle(
                title=title,
                paragraphs=paragraphs,
                main_image_url=data.get("image_url") or None,
                published_at=_parse_iso(data.get("published_at") or ""),
            )
        except (AIError, ExtractionFailed, json.JSONDecodeError) as e:
            last_error = e
    raise ExtractionFailed(f"LLM extraction failed: {last_error}")


def _trim_html(html: str, cap: int = HTML_CAP_CHARS) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "iframe", "svg"]):
        tag.decompose()
    return str(soup)[:cap]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_ai_client.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/translate/ backend/app/crawler/llm_extractor.py backend/tests/test_ai_client.py
git commit -m "feat(pipeline): OpenAI-compatible client and LLM extraction fallback"
```

---

### Task 7: Translator (translate + classify + sweep)

**Files:**
- Create: `backend/app/translate/translator.py`
- Test: `backend/tests/test_translator.py`

- [ ] **Step 1: Write the failing tests — `backend/tests/test_translator.py`**

```python
import pytest

import app.translate.translator as tr
from app.models import AppConfig, Article, Country, Site
from app.translate.client import AIError


@pytest.fixture()
def article(db_session):
    gh = Country(code="GH", name_en="Ghana", name_zh="加纳", flag_emoji="🇬🇭")
    site = Site(country=gh, name="MyJoyOnline", base_url="https://www.myjoyonline.com",
                language="en", discovery_method="rss")
    a = Article(site=site, country=gh, source_url="https://x/1", source_language="en",
                title="Economy grows", paragraphs=["Para one text.", "Para two text."],
                status="pending_translation")
    db_session.add(a)
    db_session.add(AppConfig(key="ai_api_key", value="sk-test"))
    db_session.commit()
    return a


GOOD = {"title_zh": "经济增长", "paragraphs_zh": ["第一段。", "第二段。"], "category": "business"}


def test_translate_success_publishes(monkeypatch, db_session, article):
    monkeypatch.setattr(tr, "chat_json", lambda db, s, u: dict(GOOD))
    tr.translate_article(db_session, article)
    assert article.status == "published"
    assert article.title_zh == "经济增长"
    assert article.paragraphs_zh == ["第一段。", "第二段。"]
    assert article.category == "business"
    assert article.translation_error is None


def test_count_mismatch_retries_then_succeeds(monkeypatch, db_session, article):
    responses = [
        {"title_zh": "经济增长", "paragraphs_zh": ["只有一段。"], "category": "business"},
        dict(GOOD),
    ]
    monkeypatch.setattr(tr, "chat_json", lambda db, s, u: responses.pop(0))
    tr.translate_article(db_session, article)
    assert article.status == "published"


def test_count_mismatch_twice_fails(monkeypatch, db_session, article):
    bad = {"title_zh": "经济增长", "paragraphs_zh": ["只有一段。"], "category": "business"}
    monkeypatch.setattr(tr, "chat_json", lambda db, s, u: dict(bad))
    tr.translate_article(db_session, article)
    assert article.status == "translation_failed"
    assert "mismatch" in article.translation_error


def test_unknown_category_coerced_to_society(monkeypatch, db_session, article):
    data = dict(GOOD, category="astrology")
    monkeypatch.setattr(tr, "chat_json", lambda db, s, u: dict(data))
    tr.translate_article(db_session, article)
    assert article.category == "society"


def test_api_error_marks_failed(monkeypatch, db_session, article):
    def boom(db, s, u):
        raise AIError("500 from provider")

    monkeypatch.setattr(tr, "chat_json", boom)
    tr.translate_article(db_session, article)
    assert article.status == "translation_failed"
    assert "500 from provider" in article.translation_error


def test_sweep_without_key_leaves_articles_pending(monkeypatch, db_session, article):
    db_session.query(AppConfig).filter_by(key="ai_api_key").update({"value": ""})
    db_session.commit()
    assert tr.run_translation_sweep(db_session) == 0
    assert article.status == "pending_translation"


def test_sweep_translates_batch(monkeypatch, db_session, article):
    monkeypatch.setattr(tr, "chat_json", lambda db, s, u: dict(GOOD))
    assert tr.run_translation_sweep(db_session) == 1
    assert article.status == "published"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_translator.py -v`
Expected: FAIL with `ModuleNotFoundError` (no `app.translate.translator`)

- [ ] **Step 3: Create `backend/app/translate/translator.py`**

```python
import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CATEGORIES,
    STATUS_PENDING_TRANSLATION,
    STATUS_PUBLISHED,
    STATUS_TRANSLATION_FAILED,
    Article,
)
from app.services.config_service import get_config
from app.translate.client import AIConfigMissing, chat_json

logger = logging.getLogger(__name__)

SWEEP_BATCH_SIZE = 10
ERROR_MAX_CHARS = 2000
DEFAULT_CATEGORY = "society"

SYSTEM_PROMPT = """You are a professional news translator for a Chinese audience.
Translate the given news article into Simplified Chinese and classify it.
Return ONLY a JSON object with exactly these keys:
{"title_zh": string, "paragraphs_zh": [string], "category": string}
- paragraphs_zh MUST contain exactly the same number of elements as the input paragraphs,
  translated one-to-one, in the same order. Never merge or split paragraphs.
- category MUST be one of: politics, business, sports, entertainment, society, technology, health."""


class TranslationError(Exception):
    pass


def translate_article(db: Session, article: Article) -> None:
    """Translate + classify one article; sets status and commits."""
    payload = json.dumps(
        {"title": article.title, "paragraphs": article.paragraphs}, ensure_ascii=False
    )
    try:
        data = _translate_with_retry(db, payload, expected=len(article.paragraphs))
    except AIConfigMissing:
        raise  # caller decides; sweep skips quietly
    except Exception as e:
        article.status = STATUS_TRANSLATION_FAILED
        article.translation_error = str(e)[:ERROR_MAX_CHARS]
        db.commit()
        return
    article.title_zh = data["title_zh"].strip()
    article.paragraphs_zh = data["paragraphs_zh"]
    category = (data.get("category") or "").strip().lower()
    article.category = category if category in CATEGORIES else DEFAULT_CATEGORY
    article.status = STATUS_PUBLISHED
    article.translation_error = None
    db.commit()


def _translate_with_retry(db: Session, payload: str, expected: int) -> dict:
    data = chat_json(db, SYSTEM_PROMPT, payload)
    if _valid(data, expected):
        return data
    correction = (
        SYSTEM_PROMPT
        + f"\nIMPORTANT: your previous answer had the wrong paragraph count. "
        f"paragraphs_zh must contain exactly {expected} elements."
    )
    data = chat_json(db, correction, payload)
    if _valid(data, expected):
        return data
    raise TranslationError(
        f"paragraph count mismatch: expected {expected}, "
        f"got {len(data.get('paragraphs_zh') or [])}"
    )


def _valid(data: dict, expected: int) -> bool:
    return (
        isinstance(data.get("title_zh"), str)
        and bool(data["title_zh"].strip())
        and isinstance(data.get("paragraphs_zh"), list)
        and len(data["paragraphs_zh"]) == expected
        and all(isinstance(p, str) for p in data["paragraphs_zh"])
    )


def run_translation_sweep(db: Session, batch_size: int = SWEEP_BATCH_SIZE) -> int:
    """Translate up to batch_size pending articles. Returns number processed."""
    articles = db.scalars(
        select(Article)
        .where(Article.status == STATUS_PENDING_TRANSLATION)
        .order_by(Article.id)
        .limit(batch_size)
    ).all()
    if not articles:
        return 0
    if not get_config(db, "ai_api_key"):
        logger.warning("AI API key not configured; %d article(s) pending", len(articles))
        return 0
    processed = 0
    for article in articles:
        translate_article(db, article)
        processed += 1
    return processed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_translator.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/translate/translator.py backend/tests/test_translator.py
git commit -m "feat(translate): paragraph-aligned translation with classify and sweep"
```

---

### Task 8: Pipeline orchestration

**Files:**
- Create: `backend/app/crawler/pipeline.py`
- Test: `backend/tests/test_pipeline.py`

- [ ] **Step 1: Write the failing tests — `backend/tests/test_pipeline.py`**

```python
import pytest

import app.crawler.pipeline as pl
from app.crawler.contracts import (
    CandidateArticle,
    DiscoveryError,
    ExtractedArticle,
    ExtractionFailed,
    FetchedPage,
)
from app.models import Article, Country, CrawlRun, Site


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    monkeypatch.setattr(pl, "ARTICLE_DELAY_SECONDS", 0)


@pytest.fixture()
def site(db_session):
    gh = Country(code="GH", name_en="Ghana", name_zh="加纳", flag_emoji="🇬🇭")
    s = Site(country=gh, name="MyJoyOnline", base_url="https://www.myjoyonline.com",
             language="en", discovery_method="rss", feed_url="https://x/feed")
    db_session.add(s)
    db_session.commit()
    return s


GOOD_EXTRACT = ExtractedArticle(
    title="A story", paragraphs=["One paragraph.", "Two paragraphs."],
    main_image_url="https://cdn/x.jpg",
)


def test_crawl_site_stores_new_articles(monkeypatch, db_session, site):
    monkeypatch.setattr(pl, "discover", lambda s, fetch_text: [
        CandidateArticle(url="https://x/a1"), CandidateArticle(url="https://x/a2"),
    ])
    monkeypatch.setattr(pl, "fetch_page_with_retry", lambda url: FetchedPage(url=url, html="<html>"))
    monkeypatch.setattr(pl, "extract", lambda page, s: GOOD_EXTRACT)

    run = pl.crawl_site(db_session, site)
    assert run.status == "success"
    assert run.articles_found == 2
    assert run.articles_new == 2
    assert db_session.query(Article).count() == 2
    stored = db_session.query(Article).first()
    assert stored.status == "pending_translation"
    assert stored.source_language == "en"
    assert site.last_crawl_status == "success: 2 new"
    assert site.last_crawl_at is not None


def test_crawl_site_dedupes_existing_urls(monkeypatch, db_session, site):
    db_session.add(Article(site_id=site.id, country_id=site.country_id,
                           source_url="https://x/a1", source_language="en",
                           title="old", paragraphs=["p"]))
    db_session.commit()
    monkeypatch.setattr(pl, "discover", lambda s, fetch_text: [
        CandidateArticle(url="https://x/a1"), CandidateArticle(url="https://x/a2"),
    ])
    monkeypatch.setattr(pl, "fetch_page_with_retry", lambda url: FetchedPage(url=url, html="<html>"))
    monkeypatch.setattr(pl, "extract", lambda page, s: GOOD_EXTRACT)

    run = pl.crawl_site(db_session, site)
    assert run.articles_found == 2
    assert run.articles_new == 1


def test_one_bad_article_does_not_abort_run(monkeypatch, db_session, site):
    monkeypatch.setattr(pl, "discover", lambda s, fetch_text: [
        CandidateArticle(url="https://x/bad"), CandidateArticle(url="https://x/good"),
    ])

    def fetch(url):
        if url.endswith("bad"):
            raise pl.FetchError("timeout twice")
        return FetchedPage(url=url, html="<html>")

    monkeypatch.setattr(pl, "fetch_page_with_retry", fetch)
    monkeypatch.setattr(pl, "extract", lambda page, s: GOOD_EXTRACT)

    run = pl.crawl_site(db_session, site)
    assert run.status == "success"
    assert run.articles_new == 1
    assert "https://x/bad" in run.error


def test_extraction_failure_falls_back_to_llm(monkeypatch, db_session, site):
    monkeypatch.setattr(pl, "discover", lambda s, fetch_text: [CandidateArticle(url="https://x/a1")])
    monkeypatch.setattr(pl, "fetch_page_with_retry", lambda url: FetchedPage(url=url, html="<html>"))

    def failing_extract(page, s):
        raise ExtractionFailed("thin page")

    monkeypatch.setattr(pl, "extract", failing_extract)
    monkeypatch.setattr(pl, "extract_with_llm", lambda db, html: GOOD_EXTRACT)

    run = pl.crawl_site(db_session, site)
    assert run.articles_new == 1


def test_discovery_error_fails_run(monkeypatch, db_session, site):
    def boom(s, fetch_text):
        raise DiscoveryError("feed 404")

    monkeypatch.setattr(pl, "discover", boom)
    run = pl.crawl_site(db_session, site)
    assert run.status == "failed"
    assert "feed 404" in run.error
    assert site.last_crawl_status.startswith("failed:")


def test_crawl_site_reuses_provided_run(monkeypatch, db_session, site):
    monkeypatch.setattr(pl, "discover", lambda s, fetch_text: [])
    pre = CrawlRun(site_id=site.id, status="running")
    db_session.add(pre)
    db_session.commit()
    run = pl.crawl_site(db_session, site, run=pre)
    assert run.id == pre.id
    assert db_session.query(CrawlRun).count() == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError` (no `app.crawler.pipeline`)

- [ ] **Step 3: Create `backend/app/crawler/pipeline.py`**

```python
import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crawler.contracts import DiscoveryError, ExtractionFailed, FetchError
from app.crawler.discovery import discover
from app.crawler.extractor import extract
from app.crawler.fetcher import fetch_page_with_retry, fetch_text
from app.crawler.llm_extractor import extract_with_llm
from app.models import STATUS_PENDING_TRANSLATION, Article, CrawlRun, Site
from app.timeutil import to_naive_utc, utcnow_naive

logger = logging.getLogger(__name__)

ARTICLE_DELAY_SECONDS = 3
ERROR_MAX_CHARS = 2000
STATUS_MAX_CHARS = 500


def crawl_site(db: Session, site: Site, run: CrawlRun | None = None) -> CrawlRun:
    """Run the full discover→fetch→extract→store pipeline for one site.

    Never raises: all failures end up on the CrawlRun / Site status fields.
    """
    if run is None:
        run = CrawlRun(site_id=site.id, status="running")
        db.add(run)
        db.commit()

    failures: list[str] = []
    new_count = 0
    try:
        candidates = discover(site, fetch_text=fetch_text)
        run.articles_found = len(candidates)
        fresh = [
            c
            for c in candidates
            if db.scalar(select(Article.id).where(Article.source_url == c.url)) is None
        ]
        for i, cand in enumerate(fresh):
            if i > 0 and ARTICLE_DELAY_SECONDS:
                time.sleep(ARTICLE_DELAY_SECONDS)
            try:
                page = fetch_page_with_retry(cand.url)
                try:
                    extracted = extract(page, site)
                except ExtractionFailed:
                    extracted = extract_with_llm(db, page.html)
                db.add(
                    Article(
                        site_id=site.id,
                        country_id=site.country_id,
                        source_url=cand.url,
                        source_language=site.language,
                        title=extracted.title,
                        paragraphs=extracted.paragraphs,
                        main_image_url=extracted.main_image_url,
                        published_at=to_naive_utc(
                            extracted.published_at or cand.published_at
                        ),
                        status=STATUS_PENDING_TRANSLATION,
                    )
                )
                db.commit()
                new_count += 1
            except Exception as e:  # per-article failure: skip, continue
                db.rollback()
                failures.append(f"{cand.url}: {e}")
                logger.warning("article failed for %s: %s", cand.url, e)
        run.status = "success"
        if failures:
            run.error = (
                f"{len(failures)} article(s) failed: " + "; ".join(failures)
            )[:ERROR_MAX_CHARS]
    except DiscoveryError as e:
        run.status = "failed"
        run.error = str(e)[:ERROR_MAX_CHARS]
    except Exception as e:  # unexpected: never propagate out of a crawl
        db.rollback()
        run.status = "failed"
        run.error = f"unexpected: {e}"[:ERROR_MAX_CHARS]
        logger.exception("unexpected crawl failure for site %s", site.name)

    run.articles_new = new_count
    run.finished_at = utcnow_naive()
    site.last_crawl_at = run.finished_at
    site.last_crawl_status = (
        f"success: {new_count} new"
        if run.status == "success"
        else f"failed: {run.error}"[:STATUS_MAX_CHARS]
    )
    db.commit()
    return run
```

Note: `FetchError` is imported for re-export to tests/callers (`pl.FetchError`), keep it
even though only the generic handler catches it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_pipeline.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/crawler/pipeline.py backend/tests/test_pipeline.py
git commit -m "feat(crawler): crawl_site pipeline with run bookkeeping and LLM fallback"
```

---

### Task 9: Scheduler + lifespan wiring

**Files:**
- Create: `backend/app/scheduler.py`
- Modify: `backend/app/config.py`, `backend/app/main.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_scheduler.py`

- [ ] **Step 1: Write the failing test — `backend/tests/test_scheduler.py`**

```python
from app.scheduler import build_scheduler


def test_build_scheduler_registers_all_jobs():
    sched = build_scheduler()
    jobs = {j.id: j for j in sched.get_jobs()}
    assert set(jobs) == {
        "crawl-tier-1",
        "crawl-tier-2",
        "crawl-tier-3",
        "translation-sweep",
    }
    for job in jobs.values():
        assert job.max_instances == 1
        assert job.coalesce is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_scheduler.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.scheduler'`

- [ ] **Step 3: Create `backend/app/scheduler.py`**

```python
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

logger = logging.getLogger(__name__)


def crawl_tier(tier: int) -> None:
    from app.crawler.pipeline import crawl_site
    from app.db import SessionLocal
    from app.models import Site

    with SessionLocal() as db:
        sites = db.scalars(
            select(Site).where(Site.tier == tier, Site.enabled.is_(True)).order_by(Site.id)
        ).all()
        logger.info("tier %d crawl: %d site(s)", tier, len(sites))
        for site in sites:
            try:
                crawl_site(db, site)
            except Exception:
                logger.exception("crawl_site escaped for %s", site.name)


def translation_job() -> None:
    from app.db import SessionLocal
    from app.translate.translator import run_translation_sweep

    with SessionLocal() as db:
        processed = run_translation_sweep(db)
        if processed:
            logger.info("translation sweep processed %d article(s)", processed)


def build_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler()
    common = {"max_instances": 1, "coalesce": True}
    sched.add_job(crawl_tier, "interval", hours=1, args=[1], id="crawl-tier-1", **common)
    sched.add_job(crawl_tier, "interval", hours=6, args=[2], id="crawl-tier-2", **common)
    sched.add_job(crawl_tier, "interval", days=1, args=[3], id="crawl-tier-3", **common)
    sched.add_job(translation_job, "interval", minutes=5, id="translation-sweep", **common)
    return sched
```

- [ ] **Step 4: Add setting to `backend/app/config.py`** (add field to `Settings`)

```python
    scheduler_enabled: bool = True
```

- [ ] **Step 5: Wire into `backend/app/main.py` lifespan** (replace the lifespan function)

```python
from app.config import settings
from app.scheduler import build_scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    scheduler = None
    if settings.scheduler_enabled:
        scheduler = build_scheduler()
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)
```

- [ ] **Step 6: Disable scheduler in tests — `backend/tests/conftest.py`** (extend the env block at the very top)

```python
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SCHEDULER_ENABLED"] = "false"
```

- [ ] **Step 7: Run the whole suite**

Run: `cd backend && uv run pytest tests/ -v`
Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add backend/app/scheduler.py backend/app/config.py backend/app/main.py backend/tests/
git commit -m "feat(scheduler): tiered crawl jobs and translation sweep in lifespan"
```

---

### Task 10: Admin crawl endpoints + test-translation

**Files:**
- Create: `backend/app/api/admin/crawl.py`
- Modify: `backend/app/api/admin/config.py`, `backend/app/main.py`
- Test: `backend/tests/test_admin_crawl.py`

- [ ] **Step 1: Write the failing tests — `backend/tests/test_admin_crawl.py`**

```python
import pytest

import app.api.admin.config as admin_config_mod
import app.api.admin.crawl as crawl_mod
from app.models import AdminUser, AppConfig, Country, CrawlRun, Site
from app.security import hash_password


@pytest.fixture()
def auth_headers(client, db_session):
    db_session.add(AdminUser(username="admin", password_hash=hash_password("pw")))
    db_session.commit()
    token = client.post(
        "/api/admin/auth/login", json={"username": "admin", "password": "pw"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def site(db_session):
    gh = Country(code="GH", name_en="Ghana", name_zh="加纳", flag_emoji="🇬🇭")
    s = Site(country=gh, name="MyJoyOnline", base_url="https://www.myjoyonline.com",
             language="en", discovery_method="rss", feed_url="https://x/feed")
    db_session.add(s)
    db_session.commit()
    return s


def test_crawl_runs_listing_and_auth(client, auth_headers, db_session, site):
    assert client.get("/api/admin/crawl-runs").status_code == 401
    db_session.add_all([
        CrawlRun(site_id=site.id, status="success", articles_found=5, articles_new=2),
        CrawlRun(site_id=site.id, status="failed", error="feed 404"),
    ])
    db_session.commit()
    r = client.get("/api/admin/crawl-runs", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["items"][0]["status"] == "failed"  # newest first
    assert body["items"][0]["site_name"] == "MyJoyOnline"
    assert client.get(
        f"/api/admin/crawl-runs?site_id={site.id + 99}", headers=auth_headers
    ).json()["total"] == 0


def test_trigger_crawl_202_then_409(client, auth_headers, db_session, site, monkeypatch):
    started = []
    monkeypatch.setattr(crawl_mod, "start_crawl_thread", lambda sid, rid: started.append((sid, rid)))

    r = client.post(f"/api/admin/sites/{site.id}/crawl", headers=auth_headers)
    assert r.status_code == 202
    run_id = r.json()["crawl_run_id"]
    assert started == [(site.id, run_id)]
    assert db_session.get(CrawlRun, run_id).status == "running"

    r2 = client.post(f"/api/admin/sites/{site.id}/crawl", headers=auth_headers)
    assert r2.status_code == 409

    r3 = client.post("/api/admin/sites/99999/crawl", headers=auth_headers)
    assert r3.status_code == 404


def test_test_translation_ok_and_error(client, auth_headers, db_session, monkeypatch):
    db_session.add(AppConfig(key="ai_api_key", value="sk-test"))
    db_session.commit()
    monkeypatch.setattr(
        admin_config_mod, "_translate_with_retry",
        lambda db, payload, expected: {"title_zh": "测试标题", "paragraphs_zh": ["测试段落。"], "category": "business"},
    )
    r = client.post("/api/admin/config/test-translation", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["title_zh"] == "测试标题"
    assert "latency_ms" in body

    def boom(db, payload, expected):
        raise RuntimeError("provider unreachable")

    monkeypatch.setattr(admin_config_mod, "_translate_with_retry", boom)
    r2 = client.post("/api/admin/config/test-translation", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["ok"] is False
    assert "provider unreachable" in r2.json()["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_admin_crawl.py -v`
Expected: FAIL — routes return 404 / import error

- [ ] **Step 3: Create `backend/app/api/admin/crawl.py`**

```python
import threading

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import CrawlRun, Site
from app.security import get_current_admin

router = APIRouter(dependencies=[Depends(get_current_admin)])


def start_crawl_thread(site_id: int, run_id: int) -> None:
    """Run one site crawl in a daemon thread with its own DB session."""

    def _work() -> None:
        from app.crawler.pipeline import crawl_site
        from app.db import SessionLocal

        with SessionLocal() as db:
            site = db.get(Site, site_id)
            run = db.get(CrawlRun, run_id)
            if site is not None and run is not None:
                crawl_site(db, site, run=run)

    threading.Thread(target=_work, daemon=True).start()


def _run_view(r: CrawlRun) -> dict:
    return {
        "id": r.id,
        "site_id": r.site_id,
        "site_name": r.site.name,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "status": r.status,
        "articles_found": r.articles_found,
        "articles_new": r.articles_new,
        "error": r.error,
    }


@router.get("/crawl-runs")
def list_crawl_runs(
    site_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = select(CrawlRun)
    if site_id:
        q = q.where(CrawlRun.site_id == site_id)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(
        q.order_by(CrawlRun.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [_run_view(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/sites/{site_id}/crawl", status_code=202)
def trigger_crawl(site_id: int, db: Session = Depends(get_db)):
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    already = db.scalar(
        select(CrawlRun.id).where(CrawlRun.site_id == site_id, CrawlRun.status == "running")
    )
    if already:
        raise HTTPException(status_code=409, detail="A crawl is already running for this site")
    run = CrawlRun(site_id=site_id, status="running")
    db.add(run)
    db.commit()
    start_crawl_thread(site_id, run.id)
    return {"crawl_run_id": run.id}
```

- [ ] **Step 4: Add test-translation to `backend/app/api/admin/config.py`** (append)

```python
import json
import time

from app.translate.translator import _translate_with_retry

SAMPLE_TITLE = "Ghana's economy shows steady growth"
SAMPLE_PARAGRAPHS = ["The Ghanaian economy expanded in the second quarter, driven by exports."]


@router.post("/test-translation")
def test_translation(db: Session = Depends(get_db)):
    payload = json.dumps(
        {"title": SAMPLE_TITLE, "paragraphs": SAMPLE_PARAGRAPHS}, ensure_ascii=False
    )
    start = time.monotonic()
    try:
        data = _translate_with_retry(db, payload, expected=1)
        return {
            "ok": True,
            "title_zh": data["title_zh"],
            "paragraph_zh": data["paragraphs_zh"][0],
            "latency_ms": round((time.monotonic() - start) * 1000),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:500]}
```

- [ ] **Step 5: Wire the crawl router in `backend/app/main.py`** (add lines)

```python
from app.api.admin import crawl as admin_crawl

app.include_router(admin_crawl.router, prefix="/api/admin", tags=["admin"])
```

- [ ] **Step 6: Run the whole suite**

Run: `cd backend && uv run pytest tests/ -v`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/ backend/tests/test_admin_crawl.py
git commit -m "feat(api): crawl-runs listing, crawl-now trigger, test-translation"
```

---

### Task 11: Live verification (manual, real sites)

**Files:** none created — this task validates and, if needed, corrects seeded site URLs.

- [ ] **Step 1: Install the headless browser**

Run: `cd backend && uv run playwright install chromium`
Expected: Chromium downloads (~150 MB). If this fails, the httpx degraded mode still works —
note it and continue.

- [ ] **Step 2: Start the server** (SQLite is fine; use MySQL if credentials are configured in `.env`)

```bash
cd backend
rm -f live.db
DATABASE_URL="sqlite:///./live.db" uv run python -m app.seed
DATABASE_URL="sqlite:///./live.db" SCHEDULER_ENABLED=false uv run uvicorn app.main:app --port 8300
```

- [ ] **Step 3: Trigger a crawl on one RSS site and one listing site**

```bash
TOKEN=$(curl -s -X POST http://localhost:8300/api/admin/auth/login -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
# find Punch (rss) and Seneweb (listing) ids from /api/admin/sites, then:
curl -s -X POST http://localhost:8300/api/admin/sites/<punch_id>/crawl -H "Authorization: Bearer $TOKEN"
# wait ~2 min (20 candidates × 3s politeness + fetch time), then:
curl -s "http://localhost:8300/api/admin/crawl-runs" -H "Authorization: Bearer $TOKEN"
```

Expected: run reaches `status: "success"` with `articles_new > 0`; articles visible via
`GET /api/admin/articles?status=pending_translation` with real titles and ≥2 paragraphs each.

- [ ] **Step 4: Fix any seeded URLs that 404**

If a run fails with a fetch/parse error, find the site's real RSS feed or a better listing
URL/selector in a browser, update via `PUT /api/admin/sites/{id}`, re-trigger, and then
mirror the correction into `backend/app/seed.py` and commit it.

- [ ] **Step 5: Configure a real AI key and verify translation end-to-end**

```bash
curl -s -X PUT http://localhost:8300/api/admin/config -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ai_base_url":"<real base url>","ai_api_key":"<real key>","ai_model":"<model>"}'
curl -s -X POST http://localhost:8300/api/admin/config/test-translation -H "Authorization: Bearer $TOKEN"
```

Expected: `{"ok": true, "title_zh": "...", ...}`. Then run one sweep manually:

```bash
DATABASE_URL="sqlite:///./live.db" uv run python -c "
from app.db import SessionLocal
from app.translate.translator import run_translation_sweep
with SessionLocal() as db:
    print(run_translation_sweep(db), 'articles translated')
"
```

Expected: articles flip to `published`; `GET /api/public/articles` shows them with `title_zh`,
and a detail response has aligned `paragraphs` / `paragraphs_zh`.

- [ ] **Step 6: Clean up and commit any seed corrections**

```bash
rm -f backend/live.db
git add backend/app/seed.py
git commit -m "fix(seed): correct site feed/listing URLs verified against live sites"
```

(Skip the commit if no URLs needed correction.)
