"""Idempotent seed data: countries, Tier-1 sites, default admin, AI config defaults.

Run manually with:  uv run python -m app.seed
"""

from sqlalchemy.orm import Session

from app.models import AdminUser, AppConfig, Country, Site
from app.security import hash_password

COUNTRIES = [
    # (code, name_en, name_zh, flag, tier)
    ("NG", "Nigeria", "尼日利亚", "🇳🇬", 1),
    ("GH", "Ghana", "加纳", "🇬🇭", 1),
    ("SN", "Senegal", "塞内加尔", "🇸🇳", 1),
    ("CI", "Côte d'Ivoire", "科特迪瓦", "🇨🇮", 1),
]

SITES = [
    # (country_code, name, base_url, language, discovery, feed_url, listing_url,
    #  listing_selector, body_selector)
    ("NG", "Premium Times", "https://www.premiumtimesng.com", "en", "rss",
     "https://www.premiumtimesng.com/feed", None, None, None),
    ("NG", "Punch", "https://punchng.com", "en", "rss",
     "https://punchng.com/feed/", None, None, None),
    ("NG", "Channels TV", "https://www.channelstv.com", "en", "rss",
     "https://www.channelstv.com/feed/", None, None, ".post-content"),
    ("GH", "GhanaWeb", "https://www.ghanaweb.com", "en", "listing",
     None, "https://www.ghanaweb.com/GhanaHomePage/NewsArchive/",
     ".left_artl_list a", ".article-content-area"),
    ("GH", "MyJoyOnline", "https://www.myjoyonline.com", "en", "rss",
     "https://www.myjoyonline.com/feed/", None, None, ".article-body"),
    ("GH", "Graphic Online", "https://www.graphic.com.gh", "en", "listing",
     None, "https://www.graphic.com.gh/news.html", None, None),
    ("SN", "Seneweb", "https://www.seneweb.com", "fr", "listing",
     None, "https://www.seneweb.com/news/",
     "a[href*='_n_']", ".category-post__post-content"),
    ("SN", "Dakaractu", "https://www.dakaractu.com", "fr", "rss",
     "https://www.dakaractu.com/xml/syndication.rss", None, None, None),
    ("CI", "Abidjan.net", "https://news.abidjan.net", "fr", "listing",
     None, "https://news.abidjan.net/",
     "a[href*='/articles/']", ".article-content"),
    ("CI", "Koaci", "https://www.koaci.com", "fr", "listing",
     None, "https://www.koaci.com/",
     "a[href*='/article/']", ".KText1"),
]

CONFIG_DEFAULTS = {
    "ai_base_url": "https://api.openai.com/v1",
    "ai_api_key": "",
    "ai_model": "gpt-4o-mini",
}

DEFAULT_ADMIN = ("admin", "admin123")  # change the password after first login


def seed_all(db: Session) -> None:
    countries: dict[str, Country] = {}
    for code, name_en, name_zh, flag, tier in COUNTRIES:
        country = db.query(Country).filter_by(code=code).one_or_none()
        if country is None:
            country = Country(
                code=code, name_en=name_en, name_zh=name_zh, flag_emoji=flag, tier=tier
            )
            db.add(country)
        countries[code] = country
    db.flush()

    for code, name, base_url, language, discovery, feed_url, listing_url, listing_selector, body_selector in SITES:
        if db.query(Site).filter_by(base_url=base_url).one_or_none() is None:
            db.add(
                Site(
                    country_id=countries[code].id,
                    name=name,
                    base_url=base_url,
                    language=language,
                    discovery_method=discovery,
                    feed_url=feed_url,
                    listing_url=listing_url,
                    listing_selector=listing_selector,
                    body_selector=body_selector,
                    tier=1,
                )
            )

    username, password = DEFAULT_ADMIN
    if db.query(AdminUser).filter_by(username=username).one_or_none() is None:
        db.add(AdminUser(username=username, password_hash=hash_password(password)))

    for key, value in CONFIG_DEFAULTS.items():
        if db.get(AppConfig, key) is None:
            db.add(AppConfig(key=key, value=value))

    db.commit()


if __name__ == "__main__":
    import app.models  # noqa: F401

    from app.db import Base, SessionLocal, engine

    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed_all(session)
    print("Seed complete.")
