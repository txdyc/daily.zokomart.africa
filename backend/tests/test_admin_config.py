import pytest

from app.models import AdminUser, AppConfig
from app.security import hash_password


@pytest.fixture()
def auth_headers(client, db_session):
    db_session.add(AdminUser(username="admin", password_hash=hash_password("pw")))
    db_session.add_all([
        AppConfig(key="ai_base_url", value="https://api.openai.com/v1"),
        AppConfig(key="ai_api_key", value=""),
        AppConfig(key="ai_model", value="gpt-4o-mini"),
    ])
    db_session.commit()
    token = client.post(
        "/api/admin/auth/login", json={"username": "admin", "password": "pw"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_get_config_masks_api_key(client, auth_headers, db_session):
    db_session.get(AppConfig, "ai_api_key").value = "sk-verysecret1234"
    db_session.commit()
    r = client.get("/api/admin/config", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["ai_base_url"] == "https://api.openai.com/v1"
    assert body["ai_model"] == "gpt-4o-mini"
    assert body["ai_api_key_masked"] == "****1234"
    assert "ai_api_key" not in body


def test_get_config_empty_key_masked_as_empty(client, auth_headers):
    r = client.get("/api/admin/config", headers=auth_headers)
    assert r.json()["ai_api_key_masked"] == ""


def test_update_config(client, auth_headers, db_session):
    r = client.put(
        "/api/admin/config",
        json={"ai_base_url": "https://my-proxy.example/v1", "ai_api_key": "sk-newkey9999",
              "ai_model": "deepseek-chat"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["ai_api_key_masked"] == "****9999"
    assert db_session.get(AppConfig, "ai_api_key").value == "sk-newkey9999"


def test_update_without_key_keeps_existing(client, auth_headers, db_session):
    db_session.get(AppConfig, "ai_api_key").value = "sk-keepme0000"
    db_session.commit()
    r = client.put(
        "/api/admin/config",
        json={"ai_model": "gpt-4o"},
        headers=auth_headers,
    )
    assert r.json()["ai_api_key_masked"] == "****0000"
    assert db_session.get(AppConfig, "ai_api_key").value == "sk-keepme0000"
