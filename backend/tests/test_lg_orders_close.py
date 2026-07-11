from app.logistics.models import CommissionRecord, Notification, Trip
from tests.lg_helpers import admin_headers
from tests.test_lg_orders_driver import _confirmed_order


def test_cs_cancel_releases_capacity_and_notifies_both(client, db_session):
    _, _, oid, tid = _confirmed_order(client, db_session)
    cs = admin_headers(client, db_session, role="cs", username="susan")
    resp = client.post(f"/api/admin/lg/orders/{oid}/cancel",
                       json={"reason": "shipper unreachable"}, headers=cs)
    assert resp.status_code == 200 and resp.json()["status"] == "cancelled"
    trip = db_session.get(Trip, tid)
    assert trip.used_load_kg == 0.0
    assert db_session.query(Notification).filter_by(kind="order_closed").count() == 2


def test_complete_creates_pending_commission(client, db_session):
    driver_h, _, oid, _ = _confirmed_order(client, db_session)
    cs = admin_headers(client, db_session, role="cs", username="susan")
    client.post(f"/api/lg/orders/{oid}/accept", headers=driver_h)
    client.post(f"/api/lg/orders/{oid}/depart", headers=driver_h)
    client.post(f"/api/lg/orders/{oid}/deliver", headers=driver_h)
    resp = client.post(f"/api/admin/lg/orders/{oid}/complete", headers=cs)
    assert resp.status_code == 200 and resp.json()["status"] == "completed"
    rec = db_session.query(CommissionRecord).one()
    assert rec.amount_ghs == 40.0 and rec.status == "pending"
    # completing twice is blocked
    assert client.post(f"/api/admin/lg/orders/{oid}/complete",
                       headers=cs).status_code == 409


def test_complete_requires_delivered(client, db_session):
    _, _, oid, _ = _confirmed_order(client, db_session)
    cs = admin_headers(client, db_session, role="cs", username="susan")
    assert client.post(f"/api/admin/lg/orders/{oid}/complete",
                       headers=cs).status_code == 409


def test_exception_close_in_transit_keeps_capacity(client, db_session):
    driver_h, _, oid, tid = _confirmed_order(client, db_session)
    cs = admin_headers(client, db_session, role="cs", username="susan")
    client.post(f"/api/lg/orders/{oid}/accept", headers=driver_h)
    client.post(f"/api/lg/orders/{oid}/depart", headers=driver_h)
    resp = client.post(f"/api/admin/lg/orders/{oid}/exception-close",
                       json={"reason": "cargo damaged in transit"}, headers=cs)
    assert resp.status_code == 200 and resp.json()["status"] == "exception_closed"
    assert db_session.get(Trip, tid).used_load_kg == 200.0  # consumed, not released
