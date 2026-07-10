from datetime import datetime, timezone

import pytest

from app.models import Article, Country, Site


@pytest.fixture()
def sample_data(db_session):
    gh = Country(code="GH", name_en="Ghana", name_zh="加纳", flag_emoji="🇬🇭")
    sn = Country(code="SN", name_en="Senegal", name_zh="塞内加尔", flag_emoji="🇸🇳")
    site_gh = Site(country=gh, name="MyJoyOnline", base_url="https://www.myjoyonline.com",
                   language="en", discovery_method="rss")
    site_sn = Site(country=sn, name="Seneweb", base_url="https://www.seneweb.com",
                   language="fr", discovery_method="listing")
    articles = []
    for i in range(3):
        articles.append(Article(
            site=site_gh, country=gh, source_url=f"https://gh.example/{i}",
            source_language="en", title=f"Ghana story {i}", title_zh=f"加纳新闻 {i}",
            category="business", paragraphs=[f"Para {i}."], paragraphs_zh=[f"段落 {i}。"],
            status="published", is_banner=(i == 0),
            published_at=datetime(2026, 7, 1 + i, tzinfo=timezone.utc),
        ))
    articles.append(Article(
        site=site_sn, country=sn, source_url="https://sn.example/1",
        source_language="fr", title="Histoire du Sénégal", title_zh="塞内加尔新闻",
        category="politics", paragraphs=["Le paragraphe."], paragraphs_zh=["段落。"],
        status="published", published_at=datetime(2026, 7, 9, tzinfo=timezone.utc),
    ))
    articles.append(Article(
        site=site_gh, country=gh, source_url="https://gh.example/pending",
        source_language="en", title="Not translated yet", paragraphs=["x"],
        status="pending_translation",
    ))
    db_session.add_all(articles)
    db_session.commit()
    return articles


def test_list_returns_only_published_newest_first(client, sample_data):
    r = client.get("/api/public/articles")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 4
    assert [a["title"] for a in body["items"]][:2] == ["Histoire du Sénégal", "Ghana story 2"]
    assert body["items"][0]["country"]["flag_emoji"] == "🇸🇳"


def test_list_filters(client, sample_data):
    assert client.get("/api/public/articles?country=SN").json()["total"] == 1
    assert client.get("/api/public/articles?category=business").json()["total"] == 3
    assert client.get("/api/public/articles?search=加纳新闻 1").json()["total"] == 1
    assert client.get("/api/public/articles?page=1&page_size=2").json()["items"][1][
        "title"
    ] == "Ghana story 2"


def test_banner_returns_five_or_fewer_published(client, sample_data):
    r = client.get("/api/public/articles/banner")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 4  # 1 flagged + 3 fill, pending one excluded
    assert items[0]["title"] == "Ghana story 0"  # flagged first


def test_detail_full_payload_and_404s(client, sample_data):
    listing = client.get("/api/public/articles?country=SN").json()["items"]
    r = client.get(f"/api/public/articles/{listing[0]['id']}")
    assert r.status_code == 200
    d = r.json()
    assert d["paragraphs"] == ["Le paragraphe."]
    assert d["paragraphs_zh"] == ["段落。"]
    assert d["source_language"] == "fr"
    assert d["site"]["name"] == "Seneweb"

    assert client.get("/api/public/articles/999999").status_code == 404
    pending_id = sample_data[-1].id
    assert client.get(f"/api/public/articles/{pending_id}").status_code == 404
