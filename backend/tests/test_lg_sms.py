import httpx

from app.logistics.models import SmsLog
from app.logistics.sms import send_sms
from app.services.config_service import set_config


def test_mock_provider_logs_and_reports_sent(db_session):
    ok = send_sms(db_session, "+233241234567", "Your code is 123456", kind="otp")
    assert ok is True
    log = db_session.query(SmsLog).one()
    assert log.provider == "mock"
    assert log.status == "sent"
    assert log.kind == "otp"


def test_arkesel_failure_is_swallowed(db_session, monkeypatch):
    set_config(db_session, "lg_sms_provider", "arkesel")
    db_session.commit()

    def boom(*args, **kwargs):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(httpx, "post", boom)
    ok = send_sms(db_session, "+233241234567", "hello", kind="generic")
    assert ok is False
    log = db_session.query(SmsLog).one()
    assert log.status == "failed"
    assert "no network" in log.response
