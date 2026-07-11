from app.logistics.models import OtpCode, SmsLog, UserAccount
from tests.lg_helpers import h5_login


def test_request_otp_creates_code_and_sms(client, db_session):
    resp = client.post("/api/lg/auth/request-otp", json={"phone": "0241234567"})
    assert resp.status_code == 200
    code = db_session.query(OtpCode).one()
    assert code.phone == "+233241234567"
    assert len(code.code) == 6
    assert db_session.query(SmsLog).filter_by(kind="otp").count() == 1


def test_request_otp_rejects_bad_phone(client):
    resp = client.post("/api/lg/auth/request-otp", json={"phone": "12345"})
    assert resp.status_code == 422


def test_resend_cooldown(client):
    client.post("/api/lg/auth/request-otp", json={"phone": "0241234567"})
    resp = client.post("/api/lg/auth/request-otp", json={"phone": "0241234567"})
    assert resp.status_code == 429


def test_login_wrong_code_rejected(client, db_session):
    client.post("/api/lg/auth/request-otp", json={"phone": "0241234567"})
    resp = client.post("/api/lg/auth/login", json={"phone": "0241234567", "code": "000000"})
    assert resp.status_code == 401


def test_login_creates_account_and_token_works(client, db_session):
    headers = h5_login(client, db_session, "0241234567")
    assert db_session.query(UserAccount).filter_by(phone="+233241234567").count() == 1
    resp = client.get("/api/lg/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["phone"] == "+233241234567"


def test_otp_is_single_use(client, db_session):
    client.post("/api/lg/auth/request-otp", json={"phone": "0241234567"})
    code = db_session.query(OtpCode).one()
    ok = client.post("/api/lg/auth/login", json={"phone": "0241234567", "code": code.code})
    assert ok.status_code == 200
    again = client.post("/api/lg/auth/login", json={"phone": "0241234567", "code": code.code})
    assert again.status_code == 401


def test_h5_token_rejected_on_admin_api(client, db_session):
    headers = h5_login(client, db_session)
    resp = client.get("/api/admin/countries", headers=headers)
    assert resp.status_code == 401
