from datetime import datetime, timezone

from app.models import AdminUser, AppConfig, Article, Country, CrawlRun, Site


def test_article_roundtrip_with_relationships(db_session):
    country = Country(code="GH", name_en="Ghana", name_zh="加纳", flag_emoji="🇬🇭")
    site = Site(
        country=country,
        name="MyJoyOnline",
        base_url="https://www.myjoyonline.com",
        language="en",
        discovery_method="rss",
        feed_url="https://www.myjoyonline.com/feed/",
        tier=1,
    )
    article = Article(
        site=site,
        country=country,
        source_url="https://www.myjoyonline.com/some-story/",
        source_language="en",
        title="Hello Ghana",
        paragraphs=["First paragraph.", "Second paragraph."],
        published_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
    )
    db_session.add(article)
    db_session.commit()

    got = db_session.get(Article, article.id)
    assert got.paragraphs == ["First paragraph.", "Second paragraph."]
    assert got.paragraphs_zh is None
    assert got.status == "pending_translation"
    assert got.is_banner is False
    assert got.site.country.code == "GH"


def test_other_tables_roundtrip(db_session):
    country = Country(code="NG", name_en="Nigeria", name_zh="尼日利亚", flag_emoji="🇳🇬")
    site = Site(
        country=country,
        name="Punch",
        base_url="https://punchng.com",
        language="en",
        discovery_method="rss",
        feed_url="https://punchng.com/feed/",
    )
    run = CrawlRun(site=site, status="running")
    user = AdminUser(username="admin", password_hash="x")
    cfg = AppConfig(key="ai_model", value="gpt-4o-mini")
    db_session.add_all([run, user, cfg])
    db_session.commit()

    assert db_session.get(CrawlRun, run.id).site.name == "Punch"
    assert db_session.get(AppConfig, "ai_model").value == "gpt-4o-mini"
    assert db_session.get(AdminUser, user.id).username == "admin"
