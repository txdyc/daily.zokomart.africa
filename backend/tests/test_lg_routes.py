from app.logistics.models import ROUTE_PENDING, Route


def test_route_defaults(db_session):
    route = Route(
        driver_id=1, origin_region="Greater Accra", origin_town="Accra",
        dest_region="Ashanti", dest_town="Kumasi", via_towns=[],
        frequency="daily", weekdays=[], once_date=None,
        depart_time="08:00", est_duration_hours=6, default_vehicle_id=1,
        cargo_types=["general"], rate_per_ton=350.0, rate_per_m3=None,
        min_charge=None, negotiable=False,
    )
    db_session.add(route)
    db_session.commit()
    assert route.status == ROUTE_PENDING
    assert route.prohibited_notes == ""


from tests.lg_helpers import ROUTE, approved_driver, approved_vehicle, h5_login


def _setup(client, db_session, phone="0241234567", plate="GR 1111-24"):
    headers, driver_id = approved_driver(client, db_session, phone)
    vid = approved_vehicle(client, db_session, headers, plate)
    return headers, driver_id, vid


def test_publish_route(client, db_session):
    headers, _, vid = _setup(client, db_session)
    resp = client.post("/api/lg/routes", json={**ROUTE, "default_vehicle_id": vid},
                       headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending_review"


def test_unapproved_driver_cannot_publish(client, db_session):
    headers = h5_login(client, db_session, "0555000222")
    resp = client.post("/api/lg/routes", json={**ROUTE, "default_vehicle_id": 1},
                       headers=headers)
    assert resp.status_code == 403


def test_weekly_requires_weekdays(client, db_session):
    headers, _, vid = _setup(client, db_session)
    resp = client.post(
        "/api/lg/routes",
        json={**ROUTE, "default_vehicle_id": vid, "frequency": "weekly", "weekdays": []},
        headers=headers,
    )
    assert resp.status_code == 422


def test_pricing_required_unless_negotiable(client, db_session):
    headers, _, vid = _setup(client, db_session)
    bad = {**ROUTE, "default_vehicle_id": vid,
           "rate_per_ton": None, "rate_per_m3": None, "negotiable": False}
    assert client.post("/api/lg/routes", json=bad, headers=headers).status_code == 422
    ok = {**bad, "negotiable": True}
    assert client.post("/api/lg/routes", json=ok, headers=headers).status_code == 200


def test_cannot_use_someone_elses_vehicle(client, db_session):
    _, _, other_vid = _setup(client, db_session, "0241111111", "GR 2222-24")
    headers, _, _ = _setup(client, db_session, "0242222222", "GR 3333-24")
    resp = client.post("/api/lg/routes", json={**ROUTE, "default_vehicle_id": other_vid},
                       headers=headers)
    assert resp.status_code == 403


def test_edit_and_driver_suspend_resume(client, db_session):
    from app.logistics.models import ROUTE_APPROVED, Route

    headers, _, vid = _setup(client, db_session)
    rid = client.post("/api/lg/routes", json={**ROUTE, "default_vehicle_id": vid},
                      headers=headers).json()["id"]
    # edit while pending is allowed and stays pending
    resp = client.put(f"/api/lg/routes/{rid}",
                      json={**ROUTE, "default_vehicle_id": vid, "origin_town": "Tema"},
                      headers=headers)
    assert resp.status_code == 200 and resp.json()["origin_town"] == "Tema"
    # suspend requires approved
    assert client.post(f"/api/lg/routes/{rid}/suspend", headers=headers).status_code == 409
    db_session.get(Route, rid).status = ROUTE_APPROVED
    db_session.commit()
    assert client.post(f"/api/lg/routes/{rid}/suspend",
                       headers=headers).json()["status"] == "suspended"
    assert client.post(f"/api/lg/routes/{rid}/resume",
                       headers=headers).json()["status"] == "approved"


def test_list_my_routes(client, db_session):
    headers, _, vid = _setup(client, db_session)
    client.post("/api/lg/routes", json={**ROUTE, "default_vehicle_id": vid}, headers=headers)
    resp = client.get("/api/lg/routes/mine", headers=headers)
    assert resp.status_code == 200 and len(resp.json()) == 1
