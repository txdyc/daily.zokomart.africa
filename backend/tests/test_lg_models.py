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


from datetime import date

from app.logistics.models import (
    DRIVER_APPROVED,
    DRIVER_DRAFT,
    AuditRecord,
    Blacklist,
    Driver,
)


def _driver(user_id: int, card: str = "GHA-123456789-0") -> Driver:
    return Driver(
        user_id=user_id,
        full_name="Kwame Mensah",
        gender="male",
        date_of_birth=date(1990, 5, 1),
        ghana_card_number=card,
        ghana_card_front_id="a1", ghana_card_back_id="a2",
        licence_number="GH-DVLA-0001", licence_class="C",
        licence_expiry=date(2030, 1, 1), licence_photo_id="a3",
        emergency_contact_name="Ama", emergency_contact_phone="+233209876543",
    )


def test_driver_defaults(db_session):
    user = UserAccount(phone="+233241234567")
    db_session.add(user)
    db_session.flush()
    d = _driver(user.id)
    db_session.add(d)
    db_session.commit()
    assert d.status == DRIVER_DRAFT
    assert d.availability == "accepting"


def test_ghana_card_unique(db_session):
    u1 = UserAccount(phone="+233241111111")
    u2 = UserAccount(phone="+233242222222")
    db_session.add_all([u1, u2])
    db_session.flush()
    db_session.add(_driver(u1.id))
    db_session.commit()
    db_session.add(_driver(u2.id))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_audit_and_blacklist_roundtrip(db_session):
    db_session.add(AuditRecord(entity_type="driver", entity_id=1,
                               action="approve", reason="", actor="boss"))
    db_session.add(Blacklist(value_type="phone", value="+233200000000",
                             reason="fraud", created_by="boss"))
    db_session.commit()
    assert db_session.query(AuditRecord).count() == 1
    assert db_session.query(Blacklist).count() == 1
