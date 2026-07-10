import pytest

from app.models import AdminUser
from app.security import hash_password


@pytest.fixture()
def auth_headers(client, db_session):
    db_session.add(AdminUser(username="admin", password_hash=hash_password("pw")))
    db_session.commit()
    token = client.post(
        "/api/admin/auth/login", json={"username": "admin", "password": "pw"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_endpoints_require_auth(client):
    assert client.get("/api/admin/countries").status_code == 401
    assert client.get("/api/admin/sites").status_code == 401


def test_country_crud(client, auth_headers):
    r = client.post(
        "/api/admin/countries",
        json={"code": "BJ", "name_en": "Benin", "name_zh": "贝宁", "flag_emoji": "🇧🇯", "tier": 2},
        headers=auth_headers,
    )
    assert r.status_code == 201
    cid = r.json()["id"]

    assert len(client.get("/api/admin/countries", headers=auth_headers).json()) == 1

    r = client.put(
        f"/api/admin/countries/{cid}",
        json={"code": "BJ", "name_en": "Benin", "name_zh": "贝宁", "flag_emoji": "🇧🇯",
              "tier": 2, "enabled": False},
        headers=auth_headers,
    )
    assert r.json()["enabled"] is False

    assert client.delete(f"/api/admin/countries/{cid}", headers=auth_headers).status_code == 204
    assert client.get("/api/admin/countries", headers=auth_headers).json() == []


def test_site_crud(client, auth_headers):
    cid = client.post(
        "/api/admin/countries",
        json={"code": "TG", "name_en": "Togo", "name_zh": "多哥", "flag_emoji": "🇹🇬", "tier": 2},
        headers=auth_headers,
    ).json()["id"]

    r = client.post(
        "/api/admin/sites",
        json={"country_id": cid, "name": "Togo First", "base_url": "https://www.togofirst.com",
              "language": "fr", "discovery_method": "rss",
              "feed_url": "https://www.togofirst.com/fr/rss", "tier": 2},
        headers=auth_headers,
    )
    assert r.status_code == 201
    sid = r.json()["id"]

    r = client.put(
        f"/api/admin/sites/{sid}",
        json={"country_id": cid, "name": "Togo First", "base_url": "https://www.togofirst.com",
              "language": "fr", "discovery_method": "rss",
              "feed_url": "https://www.togofirst.com/fr/rss", "tier": 2, "enabled": False},
        headers=auth_headers,
    )
    assert r.json()["enabled"] is False

    sites = client.get("/api/admin/sites", headers=auth_headers).json()
    assert len(sites) == 1 and sites[0]["country"]["code"] == "TG"

    assert client.delete(f"/api/admin/sites/{sid}", headers=auth_headers).status_code == 204
