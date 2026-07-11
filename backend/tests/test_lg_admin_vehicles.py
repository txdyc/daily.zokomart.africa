from app.logistics.models import AuditRecord, Notification, Vehicle
from tests.lg_helpers import admin_headers
from tests.test_lg_vehicles import VEHICLE, _approved_driver_headers


def _submitted_vehicle(client, db_session) -> Vehicle:
    headers = _approved_driver_headers(client, db_session)
    client.post("/api/lg/vehicles", json=VEHICLE, headers=headers)
    return db_session.query(Vehicle).one()


def test_review_approve(client, db_session):
    vehicle = _submitted_vehicle(client, db_session)
    staff = admin_headers(client, db_session, role="auditor", username="audrey")
    resp = client.post(
        f"/api/admin/lg/vehicles/{vehicle.id}/review",
        json={"action": "approve", "reason": ""},
        headers=staff,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert db_session.query(AuditRecord).filter_by(entity_type="vehicle").count() == 1
    assert db_session.query(Notification).filter_by(kind="vehicle_review").count() == 1


def test_reject_requires_reason(client, db_session):
    vehicle = _submitted_vehicle(client, db_session)
    staff = admin_headers(client, db_session, role="auditor", username="audrey")
    resp = client.post(
        f"/api/admin/lg/vehicles/{vehicle.id}/review",
        json={"action": "reject", "reason": ""},
        headers=staff,
    )
    assert resp.status_code == 400


def test_blacklist_crud(client, db_session):
    boss = admin_headers(client, db_session, role="admin")
    resp = client.post(
        "/api/admin/lg/blacklist",
        json={"value_type": "plate", "value": "GR 9999-24", "reason": "stolen"},
        headers=boss,
    )
    assert resp.status_code == 200
    entry_id = resp.json()["id"]
    resp = client.get("/api/admin/lg/blacklist", headers=boss)
    assert resp.json()[0]["value"] == "GR 9999-24"
    assert client.delete(f"/api/admin/lg/blacklist/{entry_id}", headers=boss).status_code == 200
    assert client.get("/api/admin/lg/blacklist", headers=boss).json() == []


def test_auditor_cannot_manage_blacklist(client, db_session):
    staff = admin_headers(client, db_session, role="auditor", username="audrey")
    resp = client.get("/api/admin/lg/blacklist", headers=staff)
    assert resp.status_code == 403
