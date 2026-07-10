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
