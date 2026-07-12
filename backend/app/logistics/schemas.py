from pydantic import BaseModel, field_validator, model_validator
from typing import Literal
import re
from datetime import date

from app.logistics.otp import normalize_phone


class PhoneIn(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def _normalize(cls, v: str) -> str:
        return normalize_phone(v)  # ValueError -> 422


class OtpLoginIn(PhoneIn):
    code: str


class UserTokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    phone: str


class StaffIn(BaseModel):
    username: str
    password: str
    role: Literal["admin", "auditor", "cs"]

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("Password must contain both letters and digits")
        return v

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters")
        return v


class StaffOut(BaseModel):
    id: int
    username: str
    role: str


GHANA_CARD_RE = re.compile(r"^GHA-\d{9}-\d$")


class DriverIn(BaseModel):
    full_name: str
    gender: Literal["male", "female"]
    date_of_birth: date
    ghana_card_number: str
    ghana_card_front_id: str
    ghana_card_back_id: str
    licence_number: str
    licence_class: Literal["B", "C", "D", "E", "F"]
    licence_expiry: date
    licence_photo_id: str
    emergency_contact_name: str
    emergency_contact_phone: str
    submit: bool = True

    @field_validator("ghana_card_number")
    @classmethod
    def _card_format(cls, v: str) -> str:
        v = v.strip().upper()
        if not GHANA_CARD_RE.fullmatch(v):
            raise ValueError("Ghana Card number must match GHA-XXXXXXXXX-X")
        return v

    @field_validator("emergency_contact_phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)


class DriverOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    full_name: str
    gender: str
    date_of_birth: date
    ghana_card_number: str
    ghana_card_front_id: str
    ghana_card_back_id: str
    licence_number: str
    licence_class: str
    licence_expiry: date
    licence_photo_id: str
    emergency_contact_name: str
    emergency_contact_phone: str
    status: str
    availability: str
    review_remark: str


class AvailabilityIn(BaseModel):
    availability: Literal["accepting", "paused"]


class ReviewIn(BaseModel):
    action: Literal["approve", "reject"]
    reason: str = ""


class FreezeIn(BaseModel):
    reason: str


class DriverAdminOut(DriverOut):
    user_id: int
    phone: str = ""  # filled by the endpoint


class Paginated(BaseModel):
    items: list
    total: int
    page: int
    page_size: int


class VehicleIn(BaseModel):
    plate_number: str
    brand_model: str
    vehicle_type: str
    year: int
    vin: str = ""
    cargo_length_m: float
    cargo_width_m: float
    cargo_height_m: float
    max_load_kg: int
    max_volume_m3: float
    photo_front_id: str
    photo_left_id: str
    photo_right_id: str
    photo_rear_id: str
    photo_interior_id: str
    reg_cert_id: str
    roadworthy_cert_id: str
    roadworthy_expiry: date
    insurance_cert_id: str
    insurance_expiry: date

    @field_validator("plate_number")
    @classmethod
    def _plate(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("Plate number required")
        return v


class VehicleOut(VehicleIn):
    model_config = {"from_attributes": True}

    id: int
    driver_id: int
    status: str
    review_remark: str


class BlacklistIn(BaseModel):
    value_type: Literal["phone", "ghana_card", "plate"]
    value: str
    reason: str = ""


class BlacklistOut(BlacklistIn):
    model_config = {"from_attributes": True}

    id: int
    created_by: str


class RouteIn(BaseModel):
    origin_region: str
    origin_town: str
    dest_region: str
    dest_town: str
    via_towns: list[str] = []
    frequency: Literal["daily", "weekly", "once"]
    weekdays: list[int] = []
    once_date: date | None = None
    depart_time: str
    est_duration_hours: int
    default_vehicle_id: int
    cargo_types: list[str]
    prohibited_notes: str = ""
    rate_per_ton: float | None = None
    rate_per_m3: float | None = None
    min_charge: float | None = None
    negotiable: bool = False

    @field_validator("depart_time")
    @classmethod
    def _time(cls, v: str) -> str:
        h, _, m = v.partition(":")
        if not (h.isdigit() and m.isdigit() and 0 <= int(h) <= 23 and 0 <= int(m) <= 59):
            raise ValueError("depart_time must be HH:MM")
        return f"{int(h):02d}:{int(m):02d}"

    @model_validator(mode="after")
    def _rules(self):
        if self.frequency == "weekly" and not self.weekdays:
            raise ValueError("weekly routes need weekdays")
        if any(d < 0 or d > 6 for d in self.weekdays):
            raise ValueError("weekdays are 0 (Mon) to 6 (Sun)")
        if self.frequency == "once" and self.once_date is None:
            raise ValueError("one-time routes need once_date")
        if not self.negotiable and self.rate_per_ton is None and self.rate_per_m3 is None:
            raise ValueError("set rate_per_ton or rate_per_m3, or mark negotiable")
        return self


class RouteOut(RouteIn):
    model_config = {"from_attributes": True}

    id: int
    driver_id: int
    status: str
    review_remark: str


class TripCreateIn(BaseModel):
    route_id: int
    depart_date: date
    vehicle_id: int | None = None  # defaults to the route's default vehicle


class CapacityAdjustIn(BaseModel):
    manual_load_kg: float
    manual_volume_m3: float
    reason: str

    @model_validator(mode="after")
    def _non_negative(self):
        if self.manual_load_kg < 0 or self.manual_volume_m3 < 0:
            raise ValueError("adjustments cannot be negative")
        return self


class TripOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    route_id: int
    vehicle_id: int
    depart_date: date
    depart_time: str
    status: str
    total_load_kg: float
    total_volume_m3: float
    used_load_kg: float
    used_volume_m3: float
    manual_load_kg: float
    manual_volume_m3: float


class OrderIn(BaseModel):
    trip_id: int
    contact_name: str
    contact_phone: str
    pickup_region: str
    pickup_town: str
    pickup_details: str
    delivery_region: str
    delivery_town: str
    delivery_details: str
    consignee_name: str
    consignee_phone: str
    cargo_name: str
    cargo_category: str
    packaging: Literal["carton", "pallet", "bag", "drum", "loose", "other"]
    pieces: int
    weight_kg: float
    volume_m3: float
    fragile: bool = False
    needs_loading: bool = False
    needs_pickup: bool = False
    pickup_window: str
    remarks: str = ""
    photo_ids: list[str] = []

    @field_validator("contact_phone", "consignee_phone")
    @classmethod
    def _phones(cls, v: str) -> str:
        return normalize_phone(v)

    @model_validator(mode="after")
    def _positive(self):
        if self.pieces <= 0 or self.weight_kg <= 0 or self.volume_m3 <= 0:
            raise ValueError("pieces, weight and volume must be positive")
        if len(self.photo_ids) > 6:
            raise ValueError("at most 6 photos")
        return self


class CancelIn(BaseModel):
    reason: str


class ConfirmPriceIn(BaseModel):
    freight_ghs: float
    pickup_time: str
    commission_ghs: float | None = None  # manual override
    override_reason: str = ""

    @model_validator(mode="after")
    def _check(self):
        if self.freight_ghs <= 0:
            raise ValueError("freight must be positive")
        return self


class ReassignIn(BaseModel):
    trip_id: int


class RemarkIn(BaseModel):
    body: str


class SettleIn(BaseModel):
    method: Literal["momo", "bank", "cash"]
    reference: str = ""


class CommissionOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    order_id: int
    driver_id: int
    freight_ghs: float
    rate: float
    amount_ghs: float
    status: str
    method: str
    reference: str
    note: str
    settled_by: str
