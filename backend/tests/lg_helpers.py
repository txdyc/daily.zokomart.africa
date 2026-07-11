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
