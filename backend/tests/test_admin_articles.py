import pytest

from app.models import AdminUser, Article, Country, Site
from app.security import hash_password


@pytest.fixture()
def auth_headers(client, db_session):
    db_session.add(AdminUser(username="admin", password_hash=hash_password("pw")))
    db_session.commit()
    token = client.post(
        "/api/admin/auth/login", json={"username": "admin", "password": "pw"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def articles(db_session):
    gh = Country(code="GH", name_en="Ghana", name_zh="加纳", flag_emoji="🇬🇭")
    site = Site(country=gh, name="MyJoyOnline", base_url="https://www.myjoyonline.com",
                language="en", discovery_method="rss")
    rows = [
        Article(site=site, country=gh, source_url="https://x/1", source_language="en",
                title="Published one", paragraphs=["a"], paragraphs_zh=["甲"],
                status="published"),
        Article(site=site, country=gh, source_url="https://x/2", source_language="en",
                title="Failed one", paragraphs=["b"], status="translation_failed",
                translation_error="LLM timeout"),
    ]
    db_session.add_all(rows)
    db_session.commit()
    return rows


def test_list_shows_all_statuses_and_filters(client, auth_headers, articles):
    r = client.get("/api/admin/articles", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["total"] == 2

    r = client.get("/api/admin/articles?status=translation_failed", headers=auth_headers)
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["translation_error"] == "LLM timeout"


def test_update_article_fields(client, auth_headers, articles):
    aid = articles[0].id
    r = client.patch(
        f"/api/admin/articles/{aid}",
        json={"title_zh": "已编辑标题", "category": "business", "is_banner": True,
              "status": "hidden"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["title_zh"] == "已编辑标题"
    assert body["is_banner"] is True
    assert body["status"] == "hidden"


def test_update_rejects_bad_status(client, auth_headers, articles):
    r = client.patch(
        f"/api/admin/articles/{articles[0].id}",
        json={"status": "bogus"},
        headers=auth_headers,
    )
    assert r.status_code == 422


def test_retranslate_resets_status(client, auth_headers, articles):
    aid = articles[1].id
    r = client.post(f"/api/admin/articles/{aid}/retranslate", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "pending_translation"
    assert r.json()["translation_error"] is None


def test_delete_article(client, auth_headers, articles):
    aid = articles[0].id
    assert client.delete(f"/api/admin/articles/{aid}", headers=auth_headers).status_code == 204
    assert client.get("/api/admin/articles", headers=auth_headers).json()["total"] == 1
