from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

STATUS_PENDING_TRANSLATION = "pending_translation"
STATUS_PUBLISHED = "published"
STATUS_TRANSLATION_FAILED = "translation_failed"
STATUS_HIDDEN = "hidden"
ARTICLE_STATUSES = (
    STATUS_PENDING_TRANSLATION,
    STATUS_PUBLISHED,
    STATUS_TRANSLATION_FAILED,
    STATUS_HIDDEN,
)

CATEGORIES = (
    "politics",
    "business",
    "sports",
    "entertainment",
    "society",
    "technology",
    "health",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Article(Base):
    __tablename__ = "article"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"))
    country_id: Mapped[int] = mapped_column(ForeignKey("country.id"))
    source_url: Mapped[str] = mapped_column(String(700), unique=True)
    source_language: Mapped[str] = mapped_column(String(2))  # "en" | "fr"
    title: Mapped[str] = mapped_column(String(500))
    title_zh: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str | None] = mapped_column(String(30), nullable=True)
    main_image_url: Mapped[str | None] = mapped_column(String(700), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    paragraphs: Mapped[list] = mapped_column(JSON)  # ordered source-language paragraphs
    paragraphs_zh: Mapped[list | None] = mapped_column(JSON, nullable=True)  # aligned ZH
    status: Mapped[str] = mapped_column(String(30), default=STATUS_PENDING_TRANSLATION)
    translation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_banner: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    site: Mapped["Site"] = relationship()  # noqa: F821
    country: Mapped["Country"] = relationship()  # noqa: F821
