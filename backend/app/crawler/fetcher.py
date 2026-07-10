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


def fetch_text_rendered(url: str) -> str:
    """Browser-rendered HTML for JS-heavy listing pages (Crawl4AI first, httpx fallback)."""
    return fetch_page(url).html


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
