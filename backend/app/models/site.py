from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Site(Base):
    __tablename__ = "site"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("country.id"))
    name: Mapped[str] = mapped_column(String(100))
    base_url: Mapped[str] = mapped_column(String(500))
    language: Mapped[str] = mapped_column(String(2))  # "en" | "fr"
    discovery_method: Mapped[str] = mapped_column(String(10))  # "rss" | "listing"
    feed_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    listing_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    listing_selector: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # optional per-site extraction overrides (CSS selectors)
    title_selector: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body_selector: Mapped[str | None] = mapped_column(String(200), nullable=True)
    image_selector: Mapped[str | None] = mapped_column(String(200), nullable=True)
    date_selector: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tier: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_crawl_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_crawl_status: Mapped[str | None] = mapped_column(String(500), nullable=True)

    country: Mapped["Country"] = relationship()  # noqa: F821
