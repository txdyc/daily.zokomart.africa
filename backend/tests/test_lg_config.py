from tests.lg_helpers import admin_headers


def test_get_config_masks_sms_key(client, db_session):
    boss = admin_headers(client, db_session, role="admin")
    client.put("/api/admin/lg/config",
               json={"lg_sms_api_key": "secret-key-12345"}, headers=boss)
    resp = client.get("/api/admin/lg/config", headers=boss)
    assert resp.status_code == 200
    assert resp.json()["lg_sms_api_key"] == "****2345"
    assert resp.json()["lg_commission_rate"] == "0.08"  # default


def test_put_validates_rate(client, db_session):
    boss = admin_headers(client, db_session, role="admin")
    resp = client.put("/api/admin/lg/config",
                      json={"lg_commission_rate": "1.5"}, headers=boss)
    assert resp.status_code == 400
    resp = client.put("/api/admin/lg/config",
                      json={"lg_commission_rate": "0.10"}, headers=boss)
    assert resp.status_code == 200


def test_unknown_keys_rejected(client, db_session):
    boss = admin_headers(client, db_session, role="admin")
    resp = client.put("/api/admin/lg/config", json={"ai_api_key": "x"}, headers=boss)
    assert resp.status_code == 400


def test_config_is_admin_only(client, db_session):
    cs = admin_headers(client, db_session, role="cs", username="susan")
    assert client.get("/api/admin/lg/config", headers=cs).status_code == 403
