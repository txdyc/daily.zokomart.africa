from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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


class Notification(Base):
    __tablename__ = "lg_notification"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("lg_user_account.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # driver_review / vehicle_review / order / expiry
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


VEHICLE_PENDING = "pending_review"
VEHICLE_APPROVED = "approved"
VEHICLE_REJECTED = "rejected"
VEHICLE_DEACTIVATED = "deactivated"
VEHICLE_STATUSES = (VEHICLE_PENDING, VEHICLE_APPROVED, VEHICLE_REJECTED, VEHICLE_DEACTIVATED)


class Vehicle(Base):
    __tablename__ = "lg_vehicle"

    id: Mapped[int] = mapped_column(primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("lg_driver.id"), index=True)
    plate_number: Mapped[str] = mapped_column(String(20), unique=True)
    brand_model: Mapped[str] = mapped_column(String(100))
    vehicle_type: Mapped[str] = mapped_column(String(30))
    year: Mapped[int] = mapped_column(Integer)
    vin: Mapped[str] = mapped_column(String(30), default="")
    cargo_length_m: Mapped[float] = mapped_column(Float)
    cargo_width_m: Mapped[float] = mapped_column(Float)
    cargo_height_m: Mapped[float] = mapped_column(Float)
    max_load_kg: Mapped[int] = mapped_column(Integer)
    max_volume_m3: Mapped[float] = mapped_column(Float)
    photo_front_id: Mapped[str] = mapped_column(String(36))
    photo_left_id: Mapped[str] = mapped_column(String(36))
    photo_right_id: Mapped[str] = mapped_column(String(36))
    photo_rear_id: Mapped[str] = mapped_column(String(36))
    photo_interior_id: Mapped[str] = mapped_column(String(36))
    reg_cert_id: Mapped[str] = mapped_column(String(36))
    roadworthy_cert_id: Mapped[str] = mapped_column(String(36))
    roadworthy_expiry: Mapped[date] = mapped_column(Date)
    insurance_cert_id: Mapped[str] = mapped_column(String(36))
    insurance_expiry: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default=VEHICLE_PENDING)
    review_remark: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


ROUTE_PENDING = "pending_review"
ROUTE_APPROVED = "approved"
ROUTE_REJECTED = "rejected"
ROUTE_SUSPENDED = "suspended"
ROUTE_STATUSES = (ROUTE_PENDING, ROUTE_APPROVED, ROUTE_REJECTED, ROUTE_SUSPENDED)


class Route(Base):
    """Driver-owned reusable template (PRD §8.1). Orders never book a Route directly."""

    __tablename__ = "lg_route"

    id: Mapped[int] = mapped_column(primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("lg_driver.id"), index=True)
    origin_region: Mapped[str] = mapped_column(String(50))
    origin_town: Mapped[str] = mapped_column(String(80))
    dest_region: Mapped[str] = mapped_column(String(50))
    dest_town: Mapped[str] = mapped_column(String(80))
    via_towns: Mapped[list] = mapped_column(JSON, default=list)
    frequency: Mapped[str] = mapped_column(String(10))  # daily | weekly | once
    weekdays: Mapped[list] = mapped_column(JSON, default=list)  # 0=Mon..6=Sun, weekly only
    once_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # once only
    depart_time: Mapped[str] = mapped_column(String(5))  # "08:00"
    est_duration_hours: Mapped[int] = mapped_column(Integer)
    default_vehicle_id: Mapped[int] = mapped_column(ForeignKey("lg_vehicle.id"))
    cargo_types: Mapped[list] = mapped_column(JSON, default=list)
    prohibited_notes: Mapped[str] = mapped_column(Text, default="")
    rate_per_ton: Mapped[float | None] = mapped_column(Float, nullable=True)  # GHS
    rate_per_m3: Mapped[float | None] = mapped_column(Float, nullable=True)  # GHS
    min_charge: Mapped[float | None] = mapped_column(Float, nullable=True)  # GHS
    negotiable: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default=ROUTE_PENDING)
    review_remark: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


TRIP_SCHEDULED = "scheduled"
TRIP_CANCELLED = "cancelled"


class Trip(Base):
    """One dated departure of a Route, with its own capacity ledger (PRD §8.4)."""

    __tablename__ = "lg_trip"
    __table_args__ = (UniqueConstraint("route_id", "depart_date", name="uq_trip_route_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("lg_route.id"), index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("lg_vehicle.id"))
    depart_date: Mapped[date] = mapped_column(Date, index=True)
    depart_time: Mapped[str] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(String(20), default=TRIP_SCHEDULED)
    total_load_kg: Mapped[float] = mapped_column(Float)
    total_volume_m3: Mapped[float] = mapped_column(Float)
    used_load_kg: Mapped[float] = mapped_column(Float, default=0.0)  # order reservations
    used_volume_m3: Mapped[float] = mapped_column(Float, default=0.0)
    manual_load_kg: Mapped[float] = mapped_column(Float, default=0.0)  # off-platform cargo
    manual_volume_m3: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class OperationLog(Base):
    __tablename__ = "lg_operation_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(50))  # username or phone
    actor_type: Mapped[str] = mapped_column(String(10))  # staff | driver | shipper | system
    action: Mapped[str] = mapped_column(String(40))
    entity_type: Mapped[str] = mapped_column(String(20))
    entity_id: Mapped[int] = mapped_column(Integer)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


ORDER_SUBMITTED = "submitted"
ORDER_PRICE_CONFIRMED = "price_confirmed"
ORDER_AWAITING_PICKUP = "awaiting_pickup"
ORDER_IN_TRANSIT = "in_transit"
ORDER_DELIVERED = "delivered"
ORDER_COMPLETED = "completed"
ORDER_CANCELLED = "cancelled"
ORDER_EXCEPTION = "exception_closed"
ORDER_STATUSES = (ORDER_SUBMITTED, ORDER_PRICE_CONFIRMED, ORDER_AWAITING_PICKUP,
                  ORDER_IN_TRANSIT, ORDER_DELIVERED, ORDER_COMPLETED,
                  ORDER_CANCELLED, ORDER_EXCEPTION)
ORDER_ACTIVE_STATUSES = (ORDER_PRICE_CONFIRMED, ORDER_AWAITING_PICKUP,
                         ORDER_IN_TRANSIT, ORDER_DELIVERED)


class CustomerOrder(Base):
    """Shipper order against a specific Trip (PRD §9, §10)."""

    __tablename__ = "lg_customer_order"

    id: Mapped[int] = mapped_column(primary_key=True)
    shipper_user_id: Mapped[int] = mapped_column(ForeignKey("lg_user_account.id"), index=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("lg_trip.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default=ORDER_SUBMITTED, index=True)
    contact_name: Mapped[str] = mapped_column(String(100))
    contact_phone: Mapped[str] = mapped_column(String(16))
    pickup_region: Mapped[str] = mapped_column(String(50))
    pickup_town: Mapped[str] = mapped_column(String(80))
    pickup_details: Mapped[str] = mapped_column(String(300))
    delivery_region: Mapped[str] = mapped_column(String(50))
    delivery_town: Mapped[str] = mapped_column(String(80))
    delivery_details: Mapped[str] = mapped_column(String(300))
    consignee_name: Mapped[str] = mapped_column(String(100))
    consignee_phone: Mapped[str] = mapped_column(String(16))
    cargo_name: Mapped[str] = mapped_column(String(200))
    cargo_category: Mapped[str] = mapped_column(String(50))
    packaging: Mapped[str] = mapped_column(String(20))
    pieces: Mapped[int] = mapped_column(Integer)
    weight_kg: Mapped[float] = mapped_column(Float)
    volume_m3: Mapped[float] = mapped_column(Float)
    fragile: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_loading: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_pickup: Mapped[bool] = mapped_column(Boolean, default=False)
    pickup_window: Mapped[str] = mapped_column(String(100))
    remarks: Mapped[str] = mapped_column(Text, default="")
    photo_ids: Mapped[list] = mapped_column(JSON, default=list)
    freight_ghs: Mapped[float | None] = mapped_column(Float, nullable=True)
    commission_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    commission_ghs: Mapped[float | None] = mapped_column(Float, nullable=True)
    pickup_time: Mapped[str] = mapped_column(String(100), default="")
    cancel_reason: Mapped[str] = mapped_column(Text, default="")
    reject_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    price_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    departed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


COMMISSION_PENDING = "pending"
COMMISSION_SETTLED = "settled"
COMMISSION_WAIVED = "waived"


class CommissionRecord(Base):
    """Payable commission, created when an order completes (PRD §11)."""

    __tablename__ = "lg_commission_record"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("lg_customer_order.id"), unique=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("lg_driver.id"), index=True)
    freight_ghs: Mapped[float] = mapped_column(Float)
    rate: Mapped[float] = mapped_column(Float)
    amount_ghs: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(10), default=COMMISSION_PENDING, index=True)
    method: Mapped[str] = mapped_column(String(20), default="")  # momo | bank | cash
    reference: Mapped[str] = mapped_column(String(100), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    settled_by: Mapped[str] = mapped_column(String(50), default="")
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CsRemark(Base):
    __tablename__ = "lg_cs_remark"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("lg_customer_order.id"), index=True)
    author: Mapped[str] = mapped_column(String(50))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
