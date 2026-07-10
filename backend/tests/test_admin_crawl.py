import pytest

import app.api.admin.config as admin_config_mod
import app.api.admin.crawl as crawl_mod
from app.models import AdminUser, AppConfig, Country, CrawlRun, Site
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
def site(db_session):
    gh = Country(code="GH", name_en="Ghana", name_zh="加纳", flag_emoji="🇬🇭")
    s = Site(country=gh, name="MyJoyOnline", base_url="https://www.myjoyonline.com",
             language="en", discovery_method="rss", feed_url="https://x/feed")
    db_session.add(s)
    db_session.commit()
    return s


def test_crawl_runs_listing_and_auth(client, auth_headers, db_session, site):
    assert client.get("/api/admin/crawl-runs").status_code == 401
    db_session.add_all([
        CrawlRun(site_id=site.id, status="success", articles_found=5, articles_new=2),
        CrawlRun(site_id=site.id, status="failed", error="feed 404"),
    ])
    db_session.commit()
    r = client.get("/api/admin/crawl-runs", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["items"][0]["status"] == "failed"  # newest first
    assert body["items"][0]["site_name"] == "MyJoyOnline"
    assert client.get(
        f"/api/admin/crawl-runs?site_id={site.id + 99}", headers=auth_headers
    ).json()["total"] == 0


def test_trigger_crawl_202_then_409(client, auth_headers, db_session, site, monkeypatch):
    started = []
    monkeypatch.setattr(crawl_mod, "start_crawl_thread", lambda sid, rid: started.append((sid, rid)))

    r = client.post(f"/api/admin/sites/{site.id}/crawl", headers=auth_headers)
    assert r.status_code == 202
    run_id = r.json()["crawl_run_id"]
    assert started == [(site.id, run_id)]
    assert db_session.get(CrawlRun, run_id).status == "running"

    r2 = client.post(f"/api/admin/sites/{site.id}/crawl", headers=auth_headers)
    assert r2.status_code == 409

    r3 = client.post("/api/admin/sites/99999/crawl", headers=auth_headers)
    assert r3.status_code == 404


def test_test_translation_ok_and_error(client, auth_headers, db_session, monkeypatch):
    db_session.add(AppConfig(key="ai_api_key", value="sk-test"))
    db_session.commit()
    monkeypatch.setattr(
        admin_config_mod, "_translate_with_retry",
        lambda db, payload, expected: {"title_zh": "测试标题", "paragraphs_zh": ["测试段落。"], "category": "business"},
    )
    r = client.post("/api/admin/config/test-translation", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["title_zh"] == "测试标题"
    assert "latency_ms" in body

    def boom(db, payload, expected):
        raise RuntimeError("provider unreachable")

    monkeypatch.setattr(admin_config_mod, "_translate_with_retry", boom)
    r2 = client.post("/api/admin/config/test-translation", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["ok"] is False
    assert "provider unreachable" in r2.json()["error"]
