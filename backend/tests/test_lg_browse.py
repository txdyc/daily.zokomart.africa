from datetime import date, timedelta

from app.logistics.models import Trip
from tests.lg_helpers import (
    approved_driver,
    approved_route,
    approved_vehicle,
    make_trip,
)

TOMORROW = date.today() + timedelta(days=1)


def _live_trip(client, db_session, phone="0241234567", plate="GR 1111-24"):
    headers, _ = approved_driver(client, db_session, phone)
    vid = approved_vehicle(client, db_session, headers, plate)
    rid = approved_route(client, db_session, headers, vid)
    tid = make_trip(db_session, rid, TOMORROW)
    return headers, rid, tid


def test_public_browse_no_auth(client, db_session):
    _live_trip(client, db_session)
    resp = client.get("/api/lg/trips")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    card = resp.json()["items"][0]
    assert card["origin_town"] == "Accra"
    assert card["remaining_load_kg"] == 2000.0
    assert card["remaining_volume_m3"] == 10.0
    assert "plate_number" not in card  # not disclosed publicly


def test_browse_filters(client, db_session):
    _live_trip(client, db_session)
    assert client.get("/api/lg/trips?dest_town=Kumasi").json()["total"] == 1
    assert client.get("/api/lg/trips?dest_town=Tamale").json()["total"] == 0
    assert client.get(f"/api/lg/trips?date={TOMORROW.isoformat()}").json()["total"] == 1


def test_suspended_route_hidden(client, db_session):
    from app.logistics.models import ROUTE_SUSPENDED, Route

    _, rid, _ = _live_trip(client, db_session)
    db_session.get(Route, rid).status = ROUTE_SUSPENDED
    db_session.commit()
    assert client.get("/api/lg/trips").json()["total"] == 0


def test_route_detail_with_upcoming_trips(client, db_session):
    _, rid, _ = _live_trip(client, db_session)
    resp = client.get(f"/api/lg/routes/{rid}")
    assert resp.status_code == 200
    assert resp.json()["vehicle"]["vehicle_type"] == "box_truck"
    assert len(resp.json()["upcoming_trips"]) == 1


def test_driver_one_off_trip_and_cancel(client, db_session):
    headers, rid, _ = _live_trip(client, db_session)
    extra = TOMORROW + timedelta(days=10)
    resp = client.post("/api/lg/trips",
                       json={"route_id": rid, "depart_date": extra.isoformat()},
                       headers=headers)
    assert resp.status_code == 200
    tid = resp.json()["id"]
    resp = client.post(f"/api/lg/trips/{tid}/cancel", headers=headers)
    assert resp.status_code == 200 and resp.json()["status"] == "cancelled"


def test_capacity_adjustment_floor(client, db_session):
    headers, _, tid = _live_trip(client, db_session)
    resp = client.post(
        f"/api/lg/trips/{tid}/capacity",
        json={"manual_load_kg": 500, "manual_volume_m3": 2, "reason": "own goods"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert client.get("/api/lg/trips").json()["items"][0]["remaining_load_kg"] == 1500.0
    resp = client.post(
        f"/api/lg/trips/{tid}/capacity",
        json={"manual_load_kg": 99999, "manual_volume_m3": 0, "reason": "x"},
        headers=headers,
    )
    assert resp.status_code == 409  # cannot exceed total
