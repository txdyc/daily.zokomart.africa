from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CountryIn(BaseModel):
    code: str
    name_en: str
    name_zh: str
    flag_emoji: str
    tier: int = 1
    enabled: bool = True


class CountryOut(CountryIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class SiteIn(BaseModel):
    country_id: int
    name: str
    base_url: str
    language: str
    discovery_method: str
    feed_url: str | None = None
    listing_url: str | None = None
    listing_selector: str | None = None
    title_selector: str | None = None
    body_selector: str | None = None
    image_selector: str | None = None
    date_selector: str | None = None
    tier: int = 1
    enabled: bool = True


class SiteOut(SiteIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    last_crawl_at: datetime | None = None
    last_crawl_status: str | None = None
    country: CountryOut | None = None


class ArticleUpdate(BaseModel):
    title: str | None = None
    title_zh: str | None = None
    category: str | None = None
    main_image_url: str | None = None
    paragraphs: list[str] | None = None
    paragraphs_zh: list[str] | None = None
    is_banner: bool | None = None
    status: Literal[
        "pending_translation", "published", "translation_failed", "hidden"
    ] | None = None
