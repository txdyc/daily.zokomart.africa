from datetime import date, timedelta

from app.logistics.models import CustomerOrder, Notification, Trip
from tests.lg_helpers import (
    admin_headers,
    approved_driver,
    approved_route,
    approved_vehicle,
    h5_login,
    make_trip,
)
from tests.test_lg_orders_shipper import ORDER


def _submitted_order(client, db_session):
    headers, _ = approved_driver(client, db_session)
    vid = approved_vehicle(client, db_session, headers)
    rid = approved_route(client, db_session, headers, vid)
    tid = make_trip(db_session, rid, date.today() + timedelta(days=1))
    shipper = h5_login(client, db_session, "0209999999")
    oid = client.post("/api/lg/orders", json={**ORDER, "trip_id": tid},
                      headers=shipper).json()["id"]
    return oid, tid, rid, shipper


def test_confirm_price_snapshots_commission_and_reserves(client, db_session):
    oid, tid, _, _ = _submitted_order(client, db_session)
    cs = admin_headers(client, db_session, role="cs", username="susan")
    resp = client.post(f"/api/admin/lg/orders/{oid}/confirm-price",
                       json={"freight_ghs": 500.0, "pickup_time": "Sat 08:00"},
                       headers=cs)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "price_confirmed"
    assert body["freight_ghs"] == 500.0
    assert body["commission_ghs"] == 40.0  # 8% default
    trip = db_session.get(Trip, tid)
    assert trip.used_load_kg == 200.0 and trip.used_volume_m3 == 1.5
    assert db_session.query(Notification).filter_by(kind="order").count() == 1  # driver SMS'd


def test_commission_override_needs_reason(client, db_session):
    oid, _, _, _ = _submitted_order(client, db_session)
    cs = admin_headers(client, db_session, role="cs", username="susan")
    resp = client.post(
        f"/api/admin/lg/orders/{oid}/confirm-price",
        json={"freight_ghs": 500.0, "pickup_time": "Sat", "commission_ghs": 10.0},
        headers=cs,
    )
    assert resp.status_code == 400
    resp = client.post(
        f"/api/admin/lg/orders/{oid}/confirm-price",
        json={"freight_ghs": 500.0, "pickup_time": "Sat",
              "commission_ghs": 10.0, "override_reason": "promo"},
        headers=cs,
    )
    assert resp.status_code == 200 and resp.json()["commission_ghs"] == 10.0


def test_reconfirm_replaces_reservation(client, db_session):
    oid, tid, _, _ = _submitted_order(client, db_session)
    cs = admin_headers(client, db_session, role="cs", username="susan")
    client.post(f"/api/admin/lg/orders/{oid}/confirm-price",
                json={"freight_ghs": 500.0, "pickup_time": "Sat"}, headers=cs)
    resp = client.post(f"/api/admin/lg/orders/{oid}/confirm-price",
                       json={"freight_ghs": 650.0, "pickup_time": "Sun"}, headers=cs)
    assert resp.status_code == 200 and resp.json()["freight_ghs"] == 650.0
    trip = db_session.get(Trip, tid)
    assert trip.used_load_kg == 200.0  # not double-reserved


def test_capacity_shortfall_blocks_confirmation(client, db_session):
    oid, tid, _, _ = _submitted_order(client, db_session)
    trip = db_session.get(Trip, tid)
    trip.used_load_kg = 1900.0  # only 100 kg left; order needs 200
    db_session.commit()
    cs = admin_headers(client, db_session, role="cs", username="susan")
    resp = client.post(f"/api/admin/lg/orders/{oid}/confirm-price",
                       json={"freight_ghs": 500.0, "pickup_time": "Sat"}, headers=cs)
    assert resp.status_code == 409
    assert "short" in resp.json()["detail"]


def test_auditor_cannot_work_orders(client, db_session):
    oid, _, _, _ = _submitted_order(client, db_session)
    aud = admin_headers(client, db_session, role="auditor", username="audrey")
    resp = client.post(f"/api/admin/lg/orders/{oid}/confirm-price",
                       json={"freight_ghs": 500.0, "pickup_time": "Sat"}, headers=aud)
    assert resp.status_code == 403


def test_reassign_in_submitted(client, db_session):
    oid, _, rid, _ = _submitted_order(client, db_session)
    tid2 = make_trip(db_session, rid, date.today() + timedelta(days=2))
    cs = admin_headers(client, db_session, role="cs", username="susan")
    resp = client.post(f"/api/admin/lg/orders/{oid}/reassign",
                       json={"trip_id": tid2}, headers=cs)
    assert resp.status_code == 200 and resp.json()["trip_id"] == tid2
    assert db_session.get(CustomerOrder, oid).trip_id == tid2
