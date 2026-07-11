from app.logistics.models import AuditRecord, Driver, Notification, SmsLog
from tests.lg_helpers import admin_headers, h5_login
from tests.test_lg_driver import PROFILE


def _submit_driver(client, db_session, phone="0241234567"):
    headers = h5_login(client, db_session, phone)
    client.put("/api/lg/driver/me", json=PROFILE, headers=headers)
    return db_session.query(Driver).order_by(Driver.id.desc()).first()


def test_queue_lists_pending(client, db_session):
    _submit_driver(client, db_session)
    staff = admin_headers(client, db_session, role="auditor", username="audrey")
    resp = client.get("/api/admin/lg/drivers?status=pending_review", headers=staff)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_approve_creates_audit_and_notification(client, db_session):
    driver = _submit_driver(client, db_session)
    staff = admin_headers(client, db_session, role="auditor", username="audrey")
    resp = client.post(
        f"/api/admin/lg/drivers/{driver.id}/review",
        json={"action": "approve", "reason": ""},
        headers=staff,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    audit = db_session.query(AuditRecord).filter_by(entity_type="driver").one()
    assert audit.action == "approve" and audit.actor == "audrey"
    assert db_session.query(Notification).filter_by(kind="driver_review").count() == 1
    assert db_session.query(SmsLog).filter_by(kind="driver_review").count() == 1


def test_reject_requires_reason(client, db_session):
    driver = _submit_driver(client, db_session)
    staff = admin_headers(client, db_session, role="auditor", username="audrey")
    resp = client.post(
        f"/api/admin/lg/drivers/{driver.id}/review",
        json={"action": "reject", "reason": ""},
        headers=staff,
    )
    assert resp.status_code == 400


def test_cs_role_cannot_review(client, db_session):
    driver = _submit_driver(client, db_session)
    staff = admin_headers(client, db_session, role="cs", username="susan")
    resp = client.post(
        f"/api/admin/lg/drivers/{driver.id}/review",
        json={"action": "approve", "reason": ""},
        headers=staff,
    )
    assert resp.status_code == 403


def test_freeze_and_unfreeze(client, db_session):
    driver = _submit_driver(client, db_session)
    boss = admin_headers(client, db_session, role="admin")
    client.post(f"/api/admin/lg/drivers/{driver.id}/review",
                json={"action": "approve", "reason": ""}, headers=boss)
    resp = client.post(f"/api/admin/lg/drivers/{driver.id}/freeze",
                       json={"reason": "unpaid commission"}, headers=boss)
    assert resp.json()["status"] == "frozen"
    resp = client.post(f"/api/admin/lg/drivers/{driver.id}/unfreeze", headers=boss)
    assert resp.json()["status"] == "approved"
