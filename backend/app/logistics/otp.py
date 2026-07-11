import random
import re
from datetime import timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.logistics.models import OtpCode, utcnow
from app.logistics.sms import send_sms

_LOCAL = re.compile(r"^0\d{9}$")
_INTL = re.compile(r"^\+?233\d{9}$")


class OtpError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


def normalize_phone(raw: str) -> str:
    """Normalize a Ghana mobile number to +233XXXXXXXXX or raise ValueError."""
    value = raw.strip().replace(" ", "")
    if _LOCAL.fullmatch(value):
        return "+233" + value[1:]
    if _INTL.fullmatch(value):
        return "+233" + value[-9:]
    raise ValueError("Not a valid Ghana mobile number")


def request_code(db: Session, phone: str) -> None:
    now = utcnow()
    recent = (
        db.query(OtpCode)
        .filter(OtpCode.phone == phone)
        .order_by(OtpCode.id.desc())
        .first()
    )
    if recent and (now - recent.created_at).total_seconds() < settings.otp_resend_seconds:
        raise OtpError(429, "Please wait before requesting another code")
    hour_ago = now - timedelta(hours=1)
    sent_this_hour = (
        db.query(OtpCode)
        .filter(OtpCode.phone == phone, OtpCode.created_at >= hour_ago)
        .count()
    )
    if sent_this_hour >= settings.otp_hourly_limit:
        raise OtpError(429, "Too many codes requested; try again later")

    code = f"{random.randint(0, 999999):06d}"
    db.add(OtpCode(phone=phone, code=code,
                   expires_at=now + timedelta(seconds=settings.otp_ttl_seconds)))
    db.commit()
    send_sms(db, phone, f"Your ZokoDaily verification code is {code}", kind="otp")


def verify_code(db: Session, phone: str, code: str) -> bool:
    row = (
        db.query(OtpCode)
        .filter(OtpCode.phone == phone, OtpCode.used.is_(False))
        .order_by(OtpCode.id.desc())
        .first()
    )
    if row is None or row.expires_at < utcnow() or row.attempts >= settings.otp_max_attempts:
        return False
    row.attempts += 1
    if row.code != code:
        db.commit()
        return False
    row.used = True
    db.commit()
    return True
