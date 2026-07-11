from app.logistics.models import AuditRecord, Notification, Route, Trip
from tests.lg_helpers import ROUTE, admin_headers, approved_driver, approved_vehicle


def _pending_route(client, db_session):
    headers, _ = approved_driver(client, db_session)
    vid = approved_vehicle(client, db_session, headers)
    rid = client.post("/api/lg/routes", json={**ROUTE, "default_vehicle_id": vid},
                      headers=headers).json()["id"]
    return rid


def test_review_queue_and_approve_generates_trips(client, db_session):
    rid = _pending_route(client, db_session)
    staff = admin_headers(client, db_session, role="auditor", username="audrey")
    resp = client.get("/api/admin/lg/routes?status=pending_review", headers=staff)
    assert resp.json()["total"] == 1
    resp = client.post(f"/api/admin/lg/routes/{rid}/review",
                       json={"action": "approve", "reason": ""}, headers=staff)
    assert resp.status_code == 200 and resp.json()["status"] == "approved"
    assert db_session.query(AuditRecord).filter_by(entity_type="route").count() == 1
    assert db_session.query(Notification).filter_by(kind="route_review").count() == 1
    assert db_session.query(Trip).filter_by(route_id=rid).count() > 0  # trips generated


def test_reject_requires_reason(client, db_session):
    rid = _pending_route(client, db_session)
    staff = admin_headers(client, db_session, role="auditor", username="audrey")
    resp = client.post(f"/api/admin/lg/routes/{rid}/review",
                       json={"action": "reject", "reason": ""}, headers=staff)
    assert resp.status_code == 400


def test_cs_cannot_review_routes(client, db_session):
    rid = _pending_route(client, db_session)
    staff = admin_headers(client, db_session, role="cs", username="susan")
    resp = client.post(f"/api/admin/lg/routes/{rid}/review",
                       json={"action": "approve", "reason": ""}, headers=staff)
    assert resp.status_code == 403


def test_admin_suspend_and_resume(client, db_session):
    rid = _pending_route(client, db_session)
    boss = admin_headers(client, db_session, role="admin")
    client.post(f"/api/admin/lg/routes/{rid}/review",
                json={"action": "approve", "reason": ""}, headers=boss)
    resp = client.post(f"/api/admin/lg/routes/{rid}/suspend",
                       json={"reason": "pricing complaint"}, headers=boss)
    assert resp.json()["status"] == "suspended"
    resp = client.post(f"/api/admin/lg/routes/{rid}/resume", headers=boss)
    assert resp.json()["status"] == "approved"
