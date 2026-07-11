from pydantic import BaseModel, field_validator
from typing import Literal

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
