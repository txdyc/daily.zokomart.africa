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
