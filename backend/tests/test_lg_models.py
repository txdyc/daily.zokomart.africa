import pytest
from sqlalchemy.exc import IntegrityError

from app.logistics.models import OtpCode, UserAccount


def test_user_account_roundtrip(db_session):
    user = UserAccount(phone="+233241234567")
    db_session.add(user)
    db_session.commit()
    assert user.id is not None
    assert user.created_at is not None


def test_phone_is_unique(db_session):
    db_session.add(UserAccount(phone="+233241234567"))
    db_session.commit()
    db_session.add(UserAccount(phone="+233241234567"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_otp_code_defaults(db_session):
    from app.logistics.models import utcnow

    code = OtpCode(phone="+233241234567", code="123456", expires_at=utcnow())
    db_session.add(code)
    db_session.commit()
    assert code.attempts == 0
    assert code.used is False
