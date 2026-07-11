"""Shared helpers for logistics tests."""

from app.logistics.models import OtpCode
from app.models import AdminUser
from app.security import hash_password


def h5_login(client, db_session, phone: str = "0241234567") -> dict:
    """Request an OTP, read the code from the DB (mock SMS), log in.
    Returns Authorization headers for the H5 user."""
    resp = client.post("/api/lg/auth/request-otp", json={"phone": phone})
    assert resp.status_code == 200, resp.text
    code = (
        db_session.query(OtpCode)
        .filter_by(used=False)
        .order_by(OtpCode.id.desc())
        .first()
    )
    resp = client.post("/api/lg/auth/login", json={"phone": phone, "code": code.code})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def admin_headers(client, db_session, role: str = "admin", username: str = "boss") -> dict:
    """Create a staff account with the given role and return its auth headers."""
    if db_session.query(AdminUser).filter_by(username=username).one_or_none() is None:
        db_session.add(
            AdminUser(username=username, password_hash=hash_password("pw123456"), role=role)
        )
        db_session.commit()
    resp = client.post(
        "/api/admin/auth/login", json={"username": username, "password": "pw123456"}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _digits(phone: str) -> str:
    return "".join(ch for ch in phone if ch.isdigit())[-9:]


def approved_driver(client, db_session, phone: str = "0241234567"):
    """OTP-login, submit a driver profile (unique per phone), force-approve it.
    Returns (headers, driver_id)."""
    from app.logistics.models import DRIVER_APPROVED, Driver

    headers = h5_login(client, db_session, phone)
    d = _digits(phone)
    profile = {
        "full_name": f"Driver {d}", "gender": "male", "date_of_birth": "1990-05-01",
        "ghana_card_number": f"GHA-{d}-1",
        "ghana_card_front_id": "a1", "ghana_card_back_id": "a2",
        "licence_number": f"DVLA-{d}", "licence_class": "C",
        "licence_expiry": "2030-01-01", "licence_photo_id": "a3",
        "emergency_contact_name": "Ama", "emergency_contact_phone": "0209876543",
        "submit": True,
    }
    resp = client.put("/api/lg/driver/me", json=profile, headers=headers)
    assert resp.status_code == 200, resp.text
    driver = db_session.query(Driver).order_by(Driver.id.desc()).first()
    driver.status = DRIVER_APPROVED
    db_session.commit()
    return headers, driver.id


def approved_vehicle(client, db_session, headers, plate: str = "GR 1111-24") -> int:
    """Create a vehicle for the logged-in approved driver and force-approve it."""
    from app.logistics.models import VEHICLE_APPROVED, Vehicle

    body = {
        "plate_number": plate, "brand_model": "Kia K2700", "vehicle_type": "box_truck",
        "year": 2019, "vin": "", "cargo_length_m": 3.1, "cargo_width_m": 1.7,
        "cargo_height_m": 1.8, "max_load_kg": 2000, "max_volume_m3": 10.0,
        "photo_front_id": "p1", "photo_left_id": "p2", "photo_right_id": "p3",
        "photo_rear_id": "p4", "photo_interior_id": "p5", "reg_cert_id": "d1",
        "roadworthy_cert_id": "d2", "roadworthy_expiry": "2030-01-01",
        "insurance_cert_id": "d3", "insurance_expiry": "2030-01-01",
    }
    resp = client.post("/api/lg/vehicles", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    vid = resp.json()["id"]
    db_session.get(Vehicle, vid).status = VEHICLE_APPROVED
    db_session.commit()
    return vid


ROUTE = {
    "origin_region": "Greater Accra", "origin_town": "Accra",
    "dest_region": "Ashanti", "dest_town": "Kumasi",
    "via_towns": ["Nkawkaw"], "frequency": "daily", "weekdays": [],
    "once_date": None, "depart_time": "08:00", "est_duration_hours": 6,
    "cargo_types": ["general", "electronics"], "prohibited_notes": "",
    "rate_per_ton": 350.0, "rate_per_m3": 60.0, "min_charge": 80.0,
    "negotiable": False,
}


def approved_route(client, db_session, headers, vehicle_id: int, **overrides) -> int:
    """Publish a route for the logged-in approved driver and force-approve it."""
    from app.logistics.models import ROUTE_APPROVED, Route

    body = {**ROUTE, "default_vehicle_id": vehicle_id, **overrides}
    resp = client.post("/api/lg/routes", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    rid = resp.json()["id"]
    db_session.get(Route, rid).status = ROUTE_APPROVED
    db_session.commit()
    return rid


def make_trip(db_session, route_id: int, depart_date, vehicle_id: int | None = None):
    """Insert a Trip directly, capacity seeded from the vehicle. Returns trip id."""
    from app.logistics.models import Route, Trip, Vehicle

    route = db_session.get(Route, route_id)
    vid = vehicle_id or route.default_vehicle_id
    vehicle = db_session.get(Vehicle, vid)
    trip = Trip(
        route_id=route_id, vehicle_id=vid, depart_date=depart_date,
        depart_time=route.depart_time,
        total_load_kg=float(vehicle.max_load_kg), total_volume_m3=vehicle.max_volume_m3,
    )
    db_session.add(trip)
    db_session.commit()
    return trip.id
