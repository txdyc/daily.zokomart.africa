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
