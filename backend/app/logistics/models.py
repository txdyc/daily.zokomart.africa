from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    """Naive UTC now — matches the column convention used by the news module."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UserAccount(Base):
    __tablename__ = "lg_user_account"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(16), unique=True)  # normalized +233XXXXXXXXX
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class OtpCode(Base):
    __tablename__ = "lg_otp_code"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(16), index=True)
    code: Mapped[str] = mapped_column(String(6))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SmsLog(Base):
    __tablename__ = "lg_sms_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(30))  # otp / audit_result / order / expiry ...
    body: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(10))  # sent | failed
    response: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Attachment(Base):
    __tablename__ = "lg_attachment"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # uuid4
    owner_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(50))
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


DRIVER_DRAFT = "draft"
DRIVER_PENDING = "pending_review"
DRIVER_APPROVED = "approved"
DRIVER_REJECTED = "rejected"
DRIVER_FROZEN = "frozen"
DRIVER_STATUSES = (DRIVER_DRAFT, DRIVER_PENDING, DRIVER_APPROVED, DRIVER_REJECTED, DRIVER_FROZEN)

AVAILABILITY_ACCEPTING = "accepting"
AVAILABILITY_PAUSED = "paused"


class Driver(Base):
    __tablename__ = "lg_driver"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("lg_user_account.id"), unique=True)
    full_name: Mapped[str] = mapped_column(String(100))
    gender: Mapped[str] = mapped_column(String(10))
    date_of_birth: Mapped[date] = mapped_column(Date)
    ghana_card_number: Mapped[str] = mapped_column(String(20), unique=True)
    ghana_card_front_id: Mapped[str] = mapped_column(String(36))
    ghana_card_back_id: Mapped[str] = mapped_column(String(36))
    licence_number: Mapped[str] = mapped_column(String(30))
    licence_class: Mapped[str] = mapped_column(String(5))
    licence_expiry: Mapped[date] = mapped_column(Date)
    licence_photo_id: Mapped[str] = mapped_column(String(36))
    emergency_contact_name: Mapped[str] = mapped_column(String(100))
    emergency_contact_phone: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(20), default=DRIVER_DRAFT)
    availability: Mapped[str] = mapped_column(String(10), default=AVAILABILITY_ACCEPTING)
    review_remark: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AuditRecord(Base):
    """Immutable review decisions. Never updated or deleted (PRD XIII)."""

    __tablename__ = "lg_audit_record"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20))  # driver | vehicle | route
    entity_id: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(20))  # approve | reject | freeze | unfreeze
    reason: Mapped[str] = mapped_column(Text, default="")
    actor: Mapped[str] = mapped_column(String(50))  # staff username
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Blacklist(Base):
    __tablename__ = "lg_blacklist"

    id: Mapped[int] = mapped_column(primary_key=True)
    value_type: Mapped[str] = mapped_column(String(20))  # phone | ghana_card | plate
    value: Mapped[str] = mapped_column(String(30), index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
