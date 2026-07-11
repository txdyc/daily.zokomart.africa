from app.logistics.models import Driver, Vehicle
from tests.lg_helpers import h5_login
from tests.test_lg_driver import PROFILE

VEHICLE = {
    "plate_number": "GR 1234-24",
    "brand_model": "Kia K2700",
    "vehicle_type": "box_truck",
    "year": 2019,
    "vin": "",
    "cargo_length_m": 3.1, "cargo_width_m": 1.7, "cargo_height_m": 1.8,
    "max_load_kg": 1900, "max_volume_m3": 9.4,
    "photo_front_id": "p1", "photo_left_id": "p2", "photo_right_id": "p3",
    "photo_rear_id": "p4", "photo_interior_id": "p5",
    "reg_cert_id": "d1",
    "roadworthy_cert_id": "d2", "roadworthy_expiry": "2027-01-01",
    "insurance_cert_id": "d3", "insurance_expiry": "2026-12-01",
}


def _approved_driver_headers(client, db_session, phone="0241234567"):
    headers = h5_login(client, db_session, phone)
    # unique ghana card per driver to avoid unique-constraint conflicts
    suffix = phone[-1]
    profile = {**PROFILE, "ghana_card_number": f"GHA-12345678{suffix}-{suffix}"}
    client.put("/api/lg/driver/me", json=profile, headers=headers)
    driver = db_session.query(Driver).order_by(Driver.id.desc()).first()
    driver.status = "approved"
    db_session.commit()
    return headers


def test_unapproved_driver_cannot_add_vehicle(client, db_session):
    headers = h5_login(client, db_session)
    resp = client.post("/api/lg/vehicles", json=VEHICLE, headers=headers)
    assert resp.status_code == 403


def test_create_vehicle(client, db_session):
    headers = _approved_driver_headers(client, db_session)
    resp = client.post("/api/lg/vehicles", json=VEHICLE, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending_review"


def test_duplicate_plate_conflict(client, db_session):
    h1 = _approved_driver_headers(client, db_session, "0241111111")
    client.post("/api/lg/vehicles", json=VEHICLE, headers=h1)
    h2 = _approved_driver_headers(client, db_session, "0242222222")
    resp = client.post(
        "/api/lg/vehicles",
        json={**VEHICLE, "plate_number": "GR 1234-24"},
        headers=h2,
    )
    assert resp.status_code == 409


def test_list_my_vehicles(client, db_session):
    headers = _approved_driver_headers(client, db_session)
    client.post("/api/lg/vehicles", json=VEHICLE, headers=headers)
    resp = client.get("/api/lg/vehicles", headers=headers)
    assert len(resp.json()) == 1


def test_deactivate_and_reactivate(client, db_session):
    headers = _approved_driver_headers(client, db_session)
    vid = client.post("/api/lg/vehicles", json=VEHICLE, headers=headers).json()["id"]
    vehicle = db_session.get(Vehicle, vid)
    vehicle.status = "approved"
    db_session.commit()
    resp = client.post(f"/api/lg/vehicles/{vid}/deactivate", headers=headers)
    assert resp.json()["status"] == "deactivated"
    resp = client.post(f"/api/lg/vehicles/{vid}/reactivate", headers=headers)
    assert resp.json()["status"] == "approved"
