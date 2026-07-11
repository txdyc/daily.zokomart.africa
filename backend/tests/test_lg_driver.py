from app.logistics.models import Blacklist, Driver
from tests.lg_helpers import h5_login

PROFILE = {
    "full_name": "Kwame Mensah",
    "gender": "male",
    "date_of_birth": "1990-05-01",
    "ghana_card_number": "GHA-123456789-0",
    "ghana_card_front_id": "a1",
    "ghana_card_back_id": "a2",
    "licence_number": "GH-DVLA-0001",
    "licence_class": "C",
    "licence_expiry": "2030-01-01",
    "licence_photo_id": "a3",
    "emergency_contact_name": "Ama",
    "emergency_contact_phone": "0209876543",
    "submit": True,
}


def test_get_me_before_submission_404(client, db_session):
    headers = h5_login(client, db_session)
    assert client.get("/api/lg/driver/me", headers=headers).status_code == 404


def test_submit_profile(client, db_session):
    headers = h5_login(client, db_session)
    resp = client.put("/api/lg/driver/me", json=PROFILE, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending_review"


def test_save_as_draft(client, db_session):
    headers = h5_login(client, db_session)
    resp = client.put("/api/lg/driver/me", json={**PROFILE, "submit": False}, headers=headers)
    assert resp.json()["status"] == "draft"


def test_under_18_rejected(client, db_session):
    headers = h5_login(client, db_session)
    resp = client.put(
        "/api/lg/driver/me", json={**PROFILE, "date_of_birth": "2015-01-01"}, headers=headers
    )
    assert resp.status_code == 400


def test_bad_ghana_card_format_rejected(client, db_session):
    headers = h5_login(client, db_session)
    resp = client.put(
        "/api/lg/driver/me", json={**PROFILE, "ghana_card_number": "GHA-123-4"}, headers=headers
    )
    assert resp.status_code == 422


def test_duplicate_ghana_card_conflict(client, db_session):
    h1 = h5_login(client, db_session, "0241111111")
    client.put("/api/lg/driver/me", json=PROFILE, headers=h1)
    h2 = h5_login(client, db_session, "0242222222")
    resp = client.put("/api/lg/driver/me", json=PROFILE, headers=h2)
    assert resp.status_code == 409


def test_blacklisted_card_forbidden(client, db_session):
    db_session.add(Blacklist(value_type="ghana_card", value="GHA-123456789-0",
                             reason="fraud", created_by="boss"))
    db_session.commit()
    headers = h5_login(client, db_session)
    resp = client.put("/api/lg/driver/me", json=PROFILE, headers=headers)
    assert resp.status_code == 403


def test_resubmit_only_from_draft_or_rejected(client, db_session):
    headers = h5_login(client, db_session)
    client.put("/api/lg/driver/me", json=PROFILE, headers=headers)  # -> pending_review
    resp = client.put("/api/lg/driver/me", json=PROFILE, headers=headers)
    assert resp.status_code == 409


def test_availability_requires_approval(client, db_session):
    headers = h5_login(client, db_session)
    client.put("/api/lg/driver/me", json=PROFILE, headers=headers)
    resp = client.patch(
        "/api/lg/driver/me/availability", json={"availability": "paused"}, headers=headers
    )
    assert resp.status_code == 409
    driver = db_session.query(Driver).one()
    driver.status = "approved"
    db_session.commit()
    resp = client.patch(
        "/api/lg/driver/me/availability", json={"availability": "paused"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["availability"] == "paused"
