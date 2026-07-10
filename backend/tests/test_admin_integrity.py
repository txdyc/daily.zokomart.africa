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
def ghana(db_session):
    country = Country(code="GH", name_en="Ghana", name_zh="加纳", flag_emoji="🇬🇭")
    db_session.add(country)
    db_session.commit()
    return country


@pytest.fixture()
def joy(db_session, ghana):
    site = Site(country_id=ghana.id, name="MyJoyOnline",
                base_url="https://www.myjoyonline.com", language="en",
                discovery_method="rss", feed_url="https://www.myjoyonline.com/feed/")
    db_session.add(site)
    db_session.commit()
    return site


def test_delete_country_with_sites_409(client, auth_headers, ghana, joy):
    r = client.delete(f"/api/admin/countries/{ghana.id}", headers=auth_headers)
    assert r.status_code == 409


def test_delete_site_with_articles_409(client, auth_headers, db_session, ghana, joy):
    db_session.add(Article(site_id=joy.id, country_id=ghana.id,
                           source_url="https://x/1", source_language="en",
                           title="t", paragraphs=["p"]))
    db_session.commit()
    r = client.delete(f"/api/admin/sites/{joy.id}", headers=auth_headers)
    assert r.status_code == 409


def test_delete_country_without_children_ok(client, auth_headers, ghana):
    r = client.delete(f"/api/admin/countries/{ghana.id}", headers=auth_headers)
    assert r.status_code == 204


def test_duplicate_country_code_409(client, auth_headers, ghana):
    r = client.post(
        "/api/admin/countries",
        json={"code": "GH", "name_en": "Ghana2", "name_zh": "加纳2", "flag_emoji": "🇬🇭"},
        headers=auth_headers,
    )
    assert r.status_code == 409


def test_duplicate_site_base_url_409(client, auth_headers, ghana, joy):
    r = client.post(
        "/api/admin/sites",
        json={"country_id": ghana.id, "name": "Copy",
              "base_url": "https://www.myjoyonline.com", "language": "en",
              "discovery_method": "rss"},
        headers=auth_headers,
    )
    assert r.status_code == 409


def test_site_with_unknown_country_422(client, auth_headers):
    r = client.post(
        "/api/admin/sites",
        json={"country_id": 9999, "name": "Ghost", "base_url": "https://ghost.example",
              "language": "en", "discovery_method": "rss"},
        headers=auth_headers,
    )
    assert r.status_code == 422
