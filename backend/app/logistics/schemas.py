from pydantic import BaseModel, field_validator
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
