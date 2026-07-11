from datetime import date, timedelta

from tests.lg_helpers import (
    approved_driver,
    approved_route,
    approved_vehicle,
    h5_login,
    make_trip,
)

ORDER = {
    "contact_name": "Efua", "contact_phone": "0201112223",
    "pickup_region": "Greater Accra", "pickup_town": "Accra",
    "pickup_details": "12 Ring Road", "delivery_region": "Ashanti",
    "delivery_town": "Kumasi", "delivery_details": "Adum market",
    "consignee_name": "Yaw", "consignee_phone": "0261112223",
    "cargo_name": "TV sets", "cargo_category": "electronics",
    "packaging": "carton", "pieces": 10, "weight_kg": 200.0, "volume_m3": 1.5,
    "fragile": True, "needs_loading": True, "needs_pickup": False,
    "pickup_window": "tomorrow morning", "remarks": "", "photo_ids": [],
}


def _live_trip(client, db_session):
    headers, _ = approved_driver(client, db_session)
    vid = approved_vehicle(client, db_session, headers)
    rid = approved_route(client, db_session, headers, vid)
    return make_trip(db_session, rid, date.today() + timedelta(days=1))


def test_submit_order(client, db_session):
    tid = _live_trip(client, db_session)
    shipper = h5_login(client, db_session, "0209999999")
    resp = client.post("/api/lg/orders", json={**ORDER, "trip_id": tid}, headers=shipper)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "submitted"
    assert body["driver"] is None  # contact not disclosed before acceptance


def test_anonymous_cannot_order(client, db_session):
    tid = _live_trip(client, db_session)
    assert client.post("/api/lg/orders", json={**ORDER, "trip_id": tid}).status_code == 401


def test_oversize_order_blocked(client, db_session):
    tid = _live_trip(client, db_session)
    shipper = h5_login(client, db_session, "0209999999")
    resp = client.post("/api/lg/orders",
                       json={**ORDER, "trip_id": tid, "weight_kg": 5000.0},
                       headers=shipper)
    assert resp.status_code == 409


def test_order_on_past_or_cancelled_trip_blocked(client, db_session):
    from app.logistics.models import TRIP_CANCELLED, Trip

    tid = _live_trip(client, db_session)
    db_session.get(Trip, tid).status = TRIP_CANCELLED
    db_session.commit()
    shipper = h5_login(client, db_session, "0209999999")
    resp = client.post("/api/lg/orders", json={**ORDER, "trip_id": tid}, headers=shipper)
    assert resp.status_code == 409


def test_my_orders_and_detail_access(client, db_session):
    tid = _live_trip(client, db_session)
    shipper = h5_login(client, db_session, "0209999999")
    oid = client.post("/api/lg/orders", json={**ORDER, "trip_id": tid},
                      headers=shipper).json()["id"]
    assert client.get("/api/lg/orders/mine", headers=shipper).json()["total"] == 1
    assert client.get(f"/api/lg/orders/{oid}", headers=shipper).status_code == 200
    stranger = h5_login(client, db_session, "0208888888")
    assert client.get(f"/api/lg/orders/{oid}", headers=stranger).status_code == 404


def test_shipper_cancel_only_early(client, db_session):
    from app.logistics.models import CustomerOrder

    tid = _live_trip(client, db_session)
    shipper = h5_login(client, db_session, "0209999999")
    oid = client.post("/api/lg/orders", json={**ORDER, "trip_id": tid},
                      headers=shipper).json()["id"]
    resp = client.post(f"/api/lg/orders/{oid}/cancel",
                       json={"reason": "changed my mind"}, headers=shipper)
    assert resp.status_code == 200 and resp.json()["status"] == "cancelled"
    # a second order pushed to awaiting_pickup can no longer be cancelled by the shipper
    oid2 = client.post("/api/lg/orders", json={**ORDER, "trip_id": tid},
                       headers=shipper).json()["id"]
    db_session.get(CustomerOrder, oid2).status = "awaiting_pickup"
    db_session.commit()
    resp = client.post(f"/api/lg/orders/{oid2}/cancel",
                       json={"reason": "too late"}, headers=shipper)
    assert resp.status_code == 409
