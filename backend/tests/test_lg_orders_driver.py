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


def _confirmed_order(client, db_session):
    driver_h, _ = approved_driver(client, db_session)
    vid = approved_vehicle(client, db_session, driver_h)
    rid = approved_route(client, db_session, driver_h, vid)
    tid = make_trip(db_session, rid, date.today() + timedelta(days=1))
    shipper_h = h5_login(client, db_session, "0209999999")
    oid = client.post("/api/lg/orders", json={**ORDER, "trip_id": tid},
                      headers=shipper_h).json()["id"]
    cs = admin_headers(client, db_session, role="cs", username="susan")
    client.post(f"/api/admin/lg/orders/{oid}/confirm-price",
                json={"freight_ghs": 500.0, "pickup_time": "Sat 08:00"}, headers=cs)
    return driver_h, shipper_h, oid, tid


def test_assigned_list_and_accept_flow(client, db_session):
    driver_h, shipper_h, oid, _ = _confirmed_order(client, db_session)
    resp = client.get("/api/lg/orders/assigned", headers=driver_h)
    assert resp.json()["total"] == 1
    # shipper contact hidden before acceptance
    assert resp.json()["items"][0]["shipper"] is None
    resp = client.post(f"/api/lg/orders/{oid}/accept", headers=driver_h)
    assert resp.status_code == 200 and resp.json()["status"] == "awaiting_pickup"
    assert resp.json()["shipper"]["contact_phone"] == "+233201112223"  # now disclosed
    # shipper now sees the driver too
    detail = client.get(f"/api/lg/orders/{oid}", headers=shipper_h).json()
    assert detail["driver"]["plate_number"] == "GR 1111-24"
    # shipper got an SMS-level notification
    assert db_session.query(Notification).filter_by(kind="order_accepted").count() == 1


def test_reject_releases_capacity_and_returns_to_submitted(client, db_session):
    driver_h, _, oid, tid = _confirmed_order(client, db_session)
    resp = client.post(f"/api/lg/orders/{oid}/reject",
                       json={"reason": "truck issue"}, headers=driver_h)
    assert resp.status_code == 200 and resp.json()["status"] == "submitted"
    trip = db_session.get(Trip, tid)
    assert trip.used_load_kg == 0.0 and trip.used_volume_m3 == 0.0
    assert db_session.get(CustomerOrder, oid).reject_count == 1


def test_depart_and_deliver(client, db_session):
    driver_h, _, oid, _ = _confirmed_order(client, db_session)
    client.post(f"/api/lg/orders/{oid}/accept", headers=driver_h)
    resp = client.post(f"/api/lg/orders/{oid}/depart", headers=driver_h)
    assert resp.json()["status"] == "in_transit"
    resp = client.post(f"/api/lg/orders/{oid}/deliver", headers=driver_h)
    assert resp.json()["status"] == "delivered"
    # transitions in wrong order are rejected
    assert client.post(f"/api/lg/orders/{oid}/depart",
                       headers=driver_h).status_code == 409


def test_only_the_trips_driver_can_act(client, db_session):
    _, _, oid, _ = _confirmed_order(client, db_session)
    intruder_h, _ = approved_driver(client, db_session, "0242222222")
    assert client.post(f"/api/lg/orders/{oid}/accept",
                       headers=intruder_h).status_code == 404
