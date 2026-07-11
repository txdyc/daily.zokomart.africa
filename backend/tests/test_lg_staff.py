from tests.lg_helpers import admin_headers

STAFF_ROLES = ("admin", "auditor", "cs")


def test_admin_creates_auditor(client, db_session):
    headers = admin_headers(client, db_session, role="admin")
    resp = client.post(
        "/api/admin/lg/staff",
        json={"username": "audrey", "password": "secret123", "role": "auditor"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "auditor"


def test_invalid_role_rejected(client, db_session):
    headers = admin_headers(client, db_session, role="admin")
    resp = client.post(
        "/api/admin/lg/staff",
        json={"username": "x", "password": "secret123", "role": "superuser"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_non_admin_cannot_manage_staff(client, db_session):
    headers = admin_headers(client, db_session, role="cs", username="susan")
    resp = client.get("/api/admin/lg/staff", headers=headers)
    assert resp.status_code == 403


def test_list_staff(client, db_session):
    headers = admin_headers(client, db_session, role="admin")
    resp = client.get("/api/admin/lg/staff", headers=headers)
    assert resp.status_code == 200
    assert any(u["username"] == "boss" for u in resp.json())
