# LTL Plan 1: Logistics Backend Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backend foundation for the ZokoDaily LTL Logistics module: phone+OTP user accounts, H5 JWT auth, staff roles, image uploads, driver certification, vehicle certification, admin review queues, blacklist, and the in-app/SMS notification plumbing.

**Architecture:** Logistics lives in a new `app/logistics/` package inside the existing ZokoDaily FastAPI app, with all tables prefixed `lg_` (except a new `role` column on the existing `admin_user`). H5 endpoints mount under `/api/lg/*` (user JWT, scope `"h5"`); staff endpoints under `/api/admin/lg/*` (existing admin JWT + new role checks). SMS goes through a provider abstraction (mock for dev/tests, Arkesel for prod) configured via the existing `app_config` table. Uploaded images are stored on disk under `settings.upload_dir` and served through an authenticated endpoint.

**Tech Stack:** Python 3.12 + uv, FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, PyJWT, httpx, pytest + TestClient. No new dependencies.

**Plan sequence:** LTL Plan 1 (this) → LTL Plan 2 backend marketplace (routes, trips + capacity, orders, commission, CS APIs, statistics, expiry sweep) → LTL Plan 3 H5 frontend (bottom tabs, logistics browsing/ordering, driver center) → LTL Plan 4 admin frontend (review queues, order workspace, commission ledger, dashboard). Plans 2–4 are separate documents written after this plan lands.

**Working directory:** all commands run from `backend/` unless stated otherwise.
**Spec:** `D:\GHANA\COMPANIES\daily.zokomart\Less-than-Truckload_prd.md` (V1.1) — this plan covers PRD §3.2, §4.3–4.4, §6, §7, §13 (audit for driver/vehicle), §14 (notification plumbing), §16 (duplicates, blacklist, operation trail via AuditRecord).

**Conventions to follow (from the existing codebase):**
- Models: SQLAlchemy 2.0 `Mapped`/`mapped_column`, one file per concern, registered via `app/models/__init__.py`.
- Naive-UTC timestamps via a `utcnow()` helper (matches `article.py`).
- Paginated responses use `{"items": [...], "total": n, "page": n, "page_size": n}`.
- Tests: `db_session` + `client` fixtures from `tests/conftest.py` (SQLite in-memory, `create_all`).

---

## File structure created by this plan

```
backend/app/
├── config.py                     # MODIFIED: upload/OTP settings
├── security.py                   # MODIFIED: get_current_admin rejects h5-scope tokens
├── seed.py                       # MODIFIED: lg_* config defaults
├── models/__init__.py            # MODIFIED: registers logistics models
└── logistics/
    ├── __init__.py
    ├── models.py                 # UserAccount, OtpCode, SmsLog, Attachment, Driver,
    │                             # AuditRecord, Blacklist, Vehicle, Notification (+status constants)
    ├── schemas.py                # all Pydantic schemas for this plan
    ├── auth.py                   # user JWT, get_current_user, get_principal, require_roles
    ├── otp.py                    # phone normalization + OTP issue/verify with limits
    ├── sms.py                    # send_sms via mock/Arkesel + SmsLog
    ├── storage.py                # save_upload validation + disk write
    ├── notify.py                 # notify() helper (in-app row + optional SMS)
    └── api/
        ├── __init__.py
        ├── h5_auth.py            # /api/lg/auth: request-otp, login, me
        ├── h5_uploads.py         # /api/lg/uploads: POST, GET /{id}
        ├── h5_driver.py          # /api/lg/driver: me, availability
        ├── h5_vehicles.py        # /api/lg/vehicles CRUD-ish
        ├── h5_notifications.py   # /api/lg/notifications
        └── admin/
            ├── __init__.py
            ├── staff.py          # /api/admin/lg/staff
            ├── drivers.py        # /api/admin/lg/drivers review queue
            ├── vehicles.py       # /api/admin/lg/vehicles review queue
            └── blacklist.py      # /api/admin/lg/blacklist

backend/tests/
├── lg_helpers.py                 # h5_login(), admin_headers() shared helpers
├── test_lg_models.py
├── test_lg_sms.py
├── test_lg_auth.py
├── test_lg_staff.py
├── test_lg_uploads.py
├── test_lg_driver.py
├── test_lg_admin_drivers.py
├── test_lg_vehicles.py
├── test_lg_admin_vehicles.py
└── test_lg_notifications.py
```

---

### Task 1: Package scaffold, settings, UserAccount + OtpCode models

**Files:**
- Create: `backend/app/logistics/__init__.py`, `backend/app/logistics/models.py`
- Modify: `backend/app/config.py`, `backend/app/models/__init__.py`
- Test: `backend/tests/test_lg_models.py`

- [ ] **Step 1: Create a work branch**

```bash
git checkout -b ltl-plan-1
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_lg_models.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.logistics'`

- [ ] **Step 4: Write the implementation**

Create `backend/app/logistics/__init__.py` (empty file).

Create `backend/app/logistics/models.py`:

```python
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
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
```

In `backend/app/models/__init__.py`, add this import at the top (after the existing imports):

```python
import app.logistics.models  # noqa: F401  (register lg_* tables on Base)
```

In `backend/app/config.py`, add these fields to `Settings` (after `scheduler_enabled`):

```python
    upload_dir: str = "uploads"
    otp_ttl_seconds: int = 300
    otp_resend_seconds: int = 60
    otp_hourly_limit: int = 5
    otp_max_attempts: int = 5
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_models.py -v` → 3 PASS
Run: `uv run pytest` → full suite PASS (nothing existing should break)

- [ ] **Step 6: Commit**

```bash
git add app/logistics app/models/__init__.py app/config.py tests/test_lg_models.py
git commit -m "feat(lg): logistics package scaffold, UserAccount + OtpCode models"
```

---

### Task 2: SMS service (mock + Arkesel) with SmsLog

**Files:**
- Create: `backend/app/logistics/sms.py`
- Modify: `backend/app/logistics/models.py`
- Test: `backend/tests/test_lg_sms.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_lg_sms.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_sms.py -v`
Expected: FAIL — `ImportError: cannot import name 'SmsLog'`

- [ ] **Step 3: Write the implementation**

Append to `backend/app/logistics/models.py` (note the new `Text` import — extend the existing import line):

```python
from sqlalchemy import Boolean, DateTime, Integer, String, Text  # updated import line


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
```

Create `backend/app/logistics/sms.py`:

```python
"""SMS provider abstraction. Provider chosen via app_config key lg_sms_provider:
"mock" (default: log only, always succeeds) or "arkesel" (https://developers.arkesel.com).
Never raises — failures are recorded in SmsLog and reported as False."""

import httpx
from sqlalchemy.orm import Session

from app.logistics.models import SmsLog
from app.services.config_service import get_config

ARKESEL_URL = "https://sms.arkesel.com/api/v2/sms/send"


def send_sms(db: Session, phone: str, body: str, kind: str = "generic") -> bool:
    provider = get_config(db, "lg_sms_provider", "mock")
    status, response = "sent", ""
    if provider == "arkesel":
        try:
            resp = httpx.post(
                ARKESEL_URL,
                headers={"api-key": get_config(db, "lg_sms_api_key", "")},
                json={
                    "sender": get_config(db, "lg_sms_sender_id", "ZokoDaily"),
                    "message": body,
                    "recipients": [phone],
                },
                timeout=15,
            )
            response = resp.text[:500]
            if resp.status_code >= 400:
                status = "failed"
        except Exception as exc:  # network errors must never break the caller
            status, response = "failed", str(exc)[:500]
    db.add(SmsLog(phone=phone, kind=kind, body=body, provider=provider,
                  status=status, response=response))
    db.commit()
    return status == "sent"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_sms.py -v` → 2 PASS

- [ ] **Step 5: Commit**

```bash
git add app/logistics/models.py app/logistics/sms.py tests/test_lg_sms.py
git commit -m "feat(lg): SMS service with mock/Arkesel providers and SmsLog"
```

---

### Task 3: OTP service, user JWT, and H5 auth endpoints

**Files:**
- Create: `backend/app/logistics/otp.py`, `backend/app/logistics/auth.py`, `backend/app/logistics/schemas.py`, `backend/app/logistics/api/__init__.py`, `backend/app/logistics/api/h5_auth.py`, `backend/tests/lg_helpers.py`
- Modify: `backend/app/security.py`, `backend/app/main.py`
- Test: `backend/tests/test_lg_auth.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/lg_helpers.py`:

```python
"""Shared helpers for logistics tests."""

from app.logistics.models import OtpCode
from app.models import AdminUser
from app.security import hash_password


def h5_login(client, db_session, phone: str = "0241234567") -> dict:
    """Request an OTP, read the code from the DB (mock SMS), log in.
    Returns Authorization headers for the H5 user."""
    resp = client.post("/api/lg/auth/request-otp", json={"phone": phone})
    assert resp.status_code == 200, resp.text
    code = (
        db_session.query(OtpCode)
        .filter_by(used=False)
        .order_by(OtpCode.id.desc())
        .first()
    )
    resp = client.post("/api/lg/auth/login", json={"phone": phone, "code": code.code})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def admin_headers(client, db_session, role: str = "admin", username: str = "boss") -> dict:
    """Create a staff account with the given role and return its auth headers."""
    if db_session.query(AdminUser).filter_by(username=username).one_or_none() is None:
        db_session.add(
            AdminUser(username=username, password_hash=hash_password("pw123456"), role=role)
        )
        db_session.commit()
    resp = client.post(
        "/api/admin/auth/login", json={"username": username, "password": "pw123456"}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}
```

(Note: `AdminUser.role` does not exist yet — it arrives in Task 4. Task 3's tests only use `h5_login`.)

Create `backend/tests/test_lg_auth.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_auth.py -v`
Expected: FAIL — 404s on `/api/lg/auth/*` (routes not registered)

- [ ] **Step 3: Write the implementation**

Create `backend/app/logistics/otp.py`:

```python
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
```

Create `backend/app/logistics/auth.py`:

```python
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.logistics.models import UserAccount
from app.security import ALGORITHM

_bearer = HTTPBearer(auto_error=False)


def create_user_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "scope": "h5",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def _decode(credentials: HTTPAuthorizationCredentials | None) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> UserAccount:
    """FastAPI dependency: the authenticated H5 user account, or 401."""
    payload = _decode(credentials)
    if payload.get("scope") != "h5":
        raise HTTPException(status_code=401, detail="Not an H5 user token")
    user = db.get(UserAccount, int(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="Account not found")
    return user


def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> tuple[str, object]:
    """Accepts either token type. Returns ("user", UserAccount) or ("admin", username)."""
    payload = _decode(credentials)
    if payload.get("scope") == "h5":
        user = db.get(UserAccount, int(payload["sub"]))
        if user is None:
            raise HTTPException(status_code=401, detail="Account not found")
        return ("user", user)
    return ("admin", payload["sub"])
```

(A `require_roles` staff-role dependency is appended to this module in Task 4, once `AdminUser.role` exists.)

Modify `backend/app/security.py` — in `get_current_admin`, reject H5 tokens. After the `jwt.decode` try/except block, before `return payload["sub"]`, insert:

```python
    if payload.get("scope") == "h5":
        raise HTTPException(status_code=401, detail="Not an admin token")
```

Create `backend/app/logistics/schemas.py`:

```python
from pydantic import BaseModel, field_validator

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
```

Create `backend/app/logistics/api/__init__.py` (empty file).

Create `backend/app/logistics/api/h5_auth.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics import otp
from app.logistics.auth import create_user_token, get_current_user
from app.logistics.models import UserAccount
from app.logistics.schemas import OtpLoginIn, PhoneIn, UserTokenOut

router = APIRouter()


@router.post("/request-otp")
def request_otp(body: PhoneIn, db: Session = Depends(get_db)):
    try:
        otp.request_code(db, body.phone)
    except otp.OtpError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    return {"ok": True}


@router.post("/login", response_model=UserTokenOut)
def login(body: OtpLoginIn, db: Session = Depends(get_db)):
    if not otp.verify_code(db, body.phone, body.code):
        raise HTTPException(status_code=401, detail="Invalid or expired code")
    user = db.query(UserAccount).filter_by(phone=body.phone).one_or_none()
    if user is None:
        user = UserAccount(phone=body.phone)
        db.add(user)
        db.commit()
    return UserTokenOut(access_token=create_user_token(user.id), user_id=user.id, phone=user.phone)


@router.get("/me")
def me(user: UserAccount = Depends(get_current_user)):
    return {"id": user.id, "phone": user.phone}
```

Modify `backend/app/main.py` — add the import and router registration (after the existing `admin_crawl` lines):

```python
from app.logistics.api import h5_auth

app.include_router(h5_auth.router, prefix="/api/lg/auth", tags=["lg-h5"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_auth.py -v` → 7 PASS
Run: `uv run pytest` → full suite PASS (`test_auth.py` must still pass — admin tokens have no `scope` claim and are unaffected)

- [ ] **Step 5: Commit**

```bash
git add app/logistics app/security.py app/main.py tests/lg_helpers.py tests/test_lg_auth.py
git commit -m "feat(lg): phone+OTP auth, H5 user JWT with scope isolation"
```

---

### Task 4: Staff roles on AdminUser + staff management API

**Files:**
- Modify: `backend/app/models/admin_user.py`, `backend/app/logistics/auth.py`, `backend/app/logistics/schemas.py`, `backend/app/main.py`
- Create: `backend/app/logistics/api/admin/__init__.py`, `backend/app/logistics/api/admin/staff.py`
- Test: `backend/tests/test_lg_staff.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_lg_staff.py`:

```python
from tests.lg_helpers import admin_headers

STAFF_ROLES = ("admin", "auditor", "cs")


def test_admin_creates_auditor(client, db_session):
    headers = admin_headers(client, db_session, role="admin")
    resp = client.post(
        "/api/admin/lg/staff",
        json={"username": "audrey", "password": "secret123", "role": "auditor"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "auditor"


def test_invalid_role_rejected(client, db_session):
    headers = admin_headers(client, db_session, role="admin")
    resp = client.post(
        "/api/admin/lg/staff",
        json={"username": "x", "password": "secret123", "role": "superuser"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_non_admin_cannot_manage_staff(client, db_session):
    headers = admin_headers(client, db_session, role="cs", username="susan")
    resp = client.get("/api/admin/lg/staff", headers=headers)
    assert resp.status_code == 403


def test_list_staff(client, db_session):
    headers = admin_headers(client, db_session, role="admin")
    resp = client.get("/api/admin/lg/staff", headers=headers)
    assert resp.status_code == 200
    assert any(u["username"] == "boss" for u in resp.json())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_staff.py -v`
Expected: FAIL — `TypeError: 'role' is an invalid keyword argument for AdminUser` (from `admin_headers`)

- [ ] **Step 3: Write the implementation**

Modify `backend/app/models/admin_user.py` — add the role column:

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

STAFF_ROLES = ("admin", "auditor", "cs")


class AdminUser(Base):
    __tablename__ = "admin_user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="admin", server_default="admin")
```

Append to `backend/app/logistics/auth.py` (and add two imports: `from app.models import AdminUser` and `from app.security import get_current_admin` — merge the latter into the existing `from app.security import ALGORITHM` line):

```python
def require_roles(*roles: str):
    """Dependency factory: staff member whose role is in `roles`, else 403."""

    def dep(
        username: str = Depends(get_current_admin),
        db: Session = Depends(get_db),
    ) -> AdminUser:
        user = db.query(AdminUser).filter_by(username=username).one_or_none()
        if user is None or user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user

    return dep
```

Append to `backend/app/logistics/schemas.py`:

```python
from typing import Literal


class StaffIn(BaseModel):
    username: str
    password: str
    role: Literal["admin", "auditor", "cs"]


class StaffOut(BaseModel):
    id: int
    username: str
    role: str
```

Create `backend/app/logistics/api/admin/__init__.py` (empty file).

Create `backend/app/logistics/api/admin/staff.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import require_roles
from app.logistics.schemas import StaffIn, StaffOut
from app.models import AdminUser
from app.security import hash_password

router = APIRouter(dependencies=[Depends(require_roles("admin"))])


@router.get("", response_model=list[StaffOut])
def list_staff(db: Session = Depends(get_db)):
    return db.query(AdminUser).order_by(AdminUser.id).all()


@router.post("", response_model=StaffOut)
def create_staff(body: StaffIn, db: Session = Depends(get_db)):
    if db.query(AdminUser).filter_by(username=body.username).one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Username already exists")
    user = AdminUser(username=body.username,
                     password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.commit()
    return user
```

Modify `backend/app/main.py` — extend the logistics imports/registrations:

```python
from app.logistics.api.admin import staff as lg_admin_staff

app.include_router(lg_admin_staff.router, prefix="/api/admin/lg/staff", tags=["lg-admin"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_staff.py tests/test_auth.py -v` → all PASS
Run: `uv run pytest` → full suite PASS

- [ ] **Step 5: Commit**

```bash
git add app/models/admin_user.py app/logistics tests/test_lg_staff.py app/main.py
git commit -m "feat(lg): staff roles (admin/auditor/cs) and staff management API"
```

**Deployment note (record in the PR description):** existing MySQL deployments need
`ALTER TABLE admin_user ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'admin';`
(`create_all` does not add columns to existing tables). SQLite test DBs are recreated fresh.

---

### Task 5: Attachments — upload and authenticated retrieval

**Files:**
- Create: `backend/app/logistics/storage.py`, `backend/app/logistics/api/h5_uploads.py`
- Modify: `backend/app/logistics/models.py`, `backend/app/main.py`
- Test: `backend/tests/test_lg_uploads.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_lg_uploads.py`:

```python
import io

import pytest

from app.config import settings
from tests.lg_helpers import admin_headers, h5_login

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


@pytest.fixture(autouse=True)
def tmp_upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))


def _upload(client, headers):
    return client.post(
        "/api/lg/uploads",
        files={"file": ("ghana_card.png", io.BytesIO(PNG), "image/png")},
        headers=headers,
    )


def test_upload_and_owner_download(client, db_session):
    headers = h5_login(client, db_session)
    resp = _upload(client, headers)
    assert resp.status_code == 200
    att_id = resp.json()["id"]
    assert resp.json()["url"] == f"/api/lg/uploads/{att_id}"
    got = client.get(f"/api/lg/uploads/{att_id}", headers=headers)
    assert got.status_code == 200
    assert got.content == PNG


def test_other_user_cannot_download(client, db_session):
    owner = h5_login(client, db_session, "0241234567")
    att_id = _upload(client, owner).json()["id"]
    other = h5_login(client, db_session, "0209876543")
    assert client.get(f"/api/lg/uploads/{att_id}", headers=other).status_code == 403


def test_admin_can_download(client, db_session):
    owner = h5_login(client, db_session)
    att_id = _upload(client, owner).json()["id"]
    staff = admin_headers(client, db_session, role="auditor", username="audrey")
    assert client.get(f"/api/lg/uploads/{att_id}", headers=staff).status_code == 200


def test_bad_content_type_rejected(client, db_session):
    headers = h5_login(client, db_session)
    resp = client.post(
        "/api/lg/uploads",
        files={"file": ("x.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 415


def test_anonymous_upload_rejected(client):
    resp = client.post(
        "/api/lg/uploads", files={"file": ("x.png", io.BytesIO(PNG), "image/png")}
    )
    assert resp.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_uploads.py -v`
Expected: FAIL — 404 on `/api/lg/uploads`

- [ ] **Step 3: Write the implementation**

Append to `backend/app/logistics/models.py`:

```python
class Attachment(Base):
    __tablename__ = "lg_attachment"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # uuid4
    owner_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(50))
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
```

Create `backend/app/logistics/storage.py`:

```python
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.logistics.models import Attachment

ALLOWED = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_BYTES = 8 * 1024 * 1024


def _dir() -> Path:
    p = Path(settings.upload_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def file_path(att: Attachment) -> Path:
    return _dir() / f"{att.id}.{ALLOWED[att.content_type]}"


def save_upload(db: Session, file: UploadFile, owner_user_id: int) -> Attachment:
    if file.content_type not in ALLOWED:
        raise HTTPException(status_code=415, detail="Only JPEG/PNG/WebP images are accepted")
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 8 MB limit")
    att = Attachment(
        id=str(uuid.uuid4()),
        owner_user_id=owner_user_id,
        filename=file.filename or "upload",
        content_type=file.content_type,
        size=len(data),
    )
    file_path(att).write_bytes(data)
    db.add(att)
    db.commit()
    return att
```

Create `backend/app/logistics/api/h5_uploads.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import get_current_user, get_principal
from app.logistics.models import Attachment, UserAccount
from app.logistics.storage import file_path, save_upload

router = APIRouter()


@router.post("")
def upload(
    file: UploadFile,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    att = save_upload(db, file, owner_user_id=user.id)
    return {"id": att.id, "url": f"/api/lg/uploads/{att.id}"}


@router.get("/{att_id}")
def download(
    att_id: str,
    principal: tuple = Depends(get_principal),
    db: Session = Depends(get_db),
):
    att = db.get(Attachment, att_id)
    if att is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    kind, who = principal
    if kind == "user" and who.id != att.owner_user_id:
        raise HTTPException(status_code=403, detail="Not your attachment")
    return FileResponse(file_path(att), media_type=att.content_type)
```

Modify `backend/app/main.py`:

```python
from app.logistics.api import h5_auth, h5_uploads

app.include_router(h5_uploads.router, prefix="/api/lg/uploads", tags=["lg-h5"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_uploads.py -v` → 5 PASS

- [ ] **Step 5: Commit**

```bash
git add app/logistics tests/test_lg_uploads.py app/main.py
git commit -m "feat(lg): image uploads with owner/admin-gated retrieval"
```

---

### Task 6: Driver, AuditRecord, and Blacklist models

**Files:**
- Modify: `backend/app/logistics/models.py`
- Test: `backend/tests/test_lg_models.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_lg_models.py`:

```python
from datetime import date

from app.logistics.models import (
    DRIVER_APPROVED,
    DRIVER_DRAFT,
    AuditRecord,
    Blacklist,
    Driver,
    UserAccount,
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
    import pytest
    from sqlalchemy.exc import IntegrityError

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'DRIVER_APPROVED'`

- [ ] **Step 3: Write the implementation**

Append to `backend/app/logistics/models.py` (extend the sqlalchemy import line with `Date`):

```python
from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text  # updated import line
from sqlalchemy import ForeignKey  # add
from datetime import date  # add to the datetime import line

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_models.py -v` → all PASS

- [ ] **Step 5: Commit**

```bash
git add app/logistics/models.py tests/test_lg_models.py
git commit -m "feat(lg): Driver, AuditRecord, Blacklist models"
```

---

### Task 7: H5 driver certification endpoints

**Files:**
- Create: `backend/app/logistics/api/h5_driver.py`
- Modify: `backend/app/logistics/schemas.py`, `backend/app/main.py`
- Test: `backend/tests/test_lg_driver.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_lg_driver.py`:

```python
from app.logistics.models import Blacklist, Driver
from tests.lg_helpers import h5_login

PROFILE = {
    "full_name": "Kwame Mensah",
    "gender": "male",
    "date_of_birth": "1990-05-01",
    "ghana_card_number": "GHA-123456789-0",
    "ghana_card_front_id": "a1",
    "ghana_card_back_id": "a2",
    "licence_number": "GH-DVLA-0001",
    "licence_class": "C",
    "licence_expiry": "2030-01-01",
    "licence_photo_id": "a3",
    "emergency_contact_name": "Ama",
    "emergency_contact_phone": "0209876543",
    "submit": True,
}


def test_get_me_before_submission_404(client, db_session):
    headers = h5_login(client, db_session)
    assert client.get("/api/lg/driver/me", headers=headers).status_code == 404


def test_submit_profile(client, db_session):
    headers = h5_login(client, db_session)
    resp = client.put("/api/lg/driver/me", json=PROFILE, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending_review"


def test_save_as_draft(client, db_session):
    headers = h5_login(client, db_session)
    resp = client.put("/api/lg/driver/me", json={**PROFILE, "submit": False}, headers=headers)
    assert resp.json()["status"] == "draft"


def test_under_18_rejected(client, db_session):
    headers = h5_login(client, db_session)
    resp = client.put(
        "/api/lg/driver/me", json={**PROFILE, "date_of_birth": "2015-01-01"}, headers=headers
    )
    assert resp.status_code == 400


def test_bad_ghana_card_format_rejected(client, db_session):
    headers = h5_login(client, db_session)
    resp = client.put(
        "/api/lg/driver/me", json={**PROFILE, "ghana_card_number": "GHA-123-4"}, headers=headers
    )
    assert resp.status_code == 422


def test_duplicate_ghana_card_conflict(client, db_session):
    h1 = h5_login(client, db_session, "0241111111")
    client.put("/api/lg/driver/me", json=PROFILE, headers=h1)
    h2 = h5_login(client, db_session, "0242222222")
    resp = client.put("/api/lg/driver/me", json=PROFILE, headers=h2)
    assert resp.status_code == 409


def test_blacklisted_card_forbidden(client, db_session):
    db_session.add(Blacklist(value_type="ghana_card", value="GHA-123456789-0",
                             reason="fraud", created_by="boss"))
    db_session.commit()
    headers = h5_login(client, db_session)
    resp = client.put("/api/lg/driver/me", json=PROFILE, headers=headers)
    assert resp.status_code == 403


def test_resubmit_only_from_draft_or_rejected(client, db_session):
    headers = h5_login(client, db_session)
    client.put("/api/lg/driver/me", json=PROFILE, headers=headers)  # -> pending_review
    resp = client.put("/api/lg/driver/me", json=PROFILE, headers=headers)
    assert resp.status_code == 409


def test_availability_requires_approval(client, db_session):
    headers = h5_login(client, db_session)
    client.put("/api/lg/driver/me", json=PROFILE, headers=headers)
    resp = client.patch(
        "/api/lg/driver/me/availability", json={"availability": "paused"}, headers=headers
    )
    assert resp.status_code == 409
    driver = db_session.query(Driver).one()
    driver.status = "approved"
    db_session.commit()
    resp = client.patch(
        "/api/lg/driver/me/availability", json={"availability": "paused"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["availability"] == "paused"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_driver.py -v`
Expected: FAIL — 404 on `/api/lg/driver/me` for every test (routes missing)

- [ ] **Step 3: Write the implementation**

Append to `backend/app/logistics/schemas.py`:

```python
import re
from datetime import date
from typing import Literal

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
```

Create `backend/app/logistics/api/h5_driver.py`:

```python
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import get_current_user
from app.logistics.models import (
    DRIVER_APPROVED,
    DRIVER_DRAFT,
    DRIVER_PENDING,
    DRIVER_REJECTED,
    Blacklist,
    Driver,
    UserAccount,
)
from app.logistics.schemas import AvailabilityIn, DriverIn, DriverOut

router = APIRouter()

EDITABLE = (DRIVER_DRAFT, DRIVER_REJECTED)


def _blacklisted(db: Session, value_type: str, value: str) -> bool:
    return (
        db.query(Blacklist).filter_by(value_type=value_type, value=value).first() is not None
    )


@router.get("/me", response_model=DriverOut)
def my_profile(user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)):
    driver = db.query(Driver).filter_by(user_id=user.id).one_or_none()
    if driver is None:
        raise HTTPException(status_code=404, detail="No driver profile yet")
    return driver


@router.put("/me", response_model=DriverOut)
def upsert_profile(
    body: DriverIn,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = date.today()
    age = (today - body.date_of_birth).days // 365
    if age < 18:
        raise HTTPException(status_code=400, detail="Driver must be at least 18")
    if _blacklisted(db, "phone", user.phone) or _blacklisted(
        db, "ghana_card", body.ghana_card_number
    ):
        raise HTTPException(status_code=403, detail="Certification not permitted")
    dup = (
        db.query(Driver)
        .filter(Driver.ghana_card_number == body.ghana_card_number, Driver.user_id != user.id)
        .first()
    )
    if dup is not None:
        raise HTTPException(status_code=409, detail="Ghana Card already registered")

    driver = db.query(Driver).filter_by(user_id=user.id).one_or_none()
    if driver is not None and driver.status not in EDITABLE:
        raise HTTPException(status_code=409, detail=f"Profile is {driver.status}; cannot edit")
    if driver is None:
        driver = Driver(user_id=user.id)
        db.add(driver)
    for field in DriverIn.model_fields:
        if field != "submit":
            setattr(driver, field, getattr(body, field))
    driver.status = DRIVER_PENDING if body.submit else DRIVER_DRAFT
    db.commit()
    return driver


@router.patch("/me/availability", response_model=DriverOut)
def set_availability(
    body: AvailabilityIn,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    driver = db.query(Driver).filter_by(user_id=user.id).one_or_none()
    if driver is None or driver.status != DRIVER_APPROVED:
        raise HTTPException(status_code=409, detail="Driver is not approved")
    driver.availability = body.availability
    db.commit()
    return driver
```

Modify `backend/app/main.py`:

```python
from app.logistics.api import h5_auth, h5_driver, h5_uploads

app.include_router(h5_driver.router, prefix="/api/lg/driver", tags=["lg-h5"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_driver.py -v` → 9 PASS

- [ ] **Step 5: Commit**

```bash
git add app/logistics tests/test_lg_driver.py app/main.py
git commit -m "feat(lg): H5 driver certification submit/resubmit + availability"
```

---

### Task 8: Notification model + notify helper + admin driver review

**Files:**
- Create: `backend/app/logistics/notify.py`, `backend/app/logistics/api/admin/drivers.py`
- Modify: `backend/app/logistics/models.py`, `backend/app/logistics/schemas.py`, `backend/app/main.py`
- Test: `backend/tests/test_lg_admin_drivers.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_lg_admin_drivers.py`:

```python
from app.logistics.models import AuditRecord, Driver, Notification, SmsLog
from tests.lg_helpers import admin_headers, h5_login
from tests.test_lg_driver import PROFILE


def _submit_driver(client, db_session, phone="0241234567"):
    headers = h5_login(client, db_session, phone)
    client.put("/api/lg/driver/me", json=PROFILE, headers=headers)
    return db_session.query(Driver).order_by(Driver.id.desc()).first()


def test_queue_lists_pending(client, db_session):
    _submit_driver(client, db_session)
    staff = admin_headers(client, db_session, role="auditor", username="audrey")
    resp = client.get("/api/admin/lg/drivers?status=pending_review", headers=staff)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_approve_creates_audit_and_notification(client, db_session):
    driver = _submit_driver(client, db_session)
    staff = admin_headers(client, db_session, role="auditor", username="audrey")
    resp = client.post(
        f"/api/admin/lg/drivers/{driver.id}/review",
        json={"action": "approve", "reason": ""},
        headers=staff,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    audit = db_session.query(AuditRecord).filter_by(entity_type="driver").one()
    assert audit.action == "approve" and audit.actor == "audrey"
    assert db_session.query(Notification).filter_by(kind="driver_review").count() == 1
    assert db_session.query(SmsLog).filter_by(kind="driver_review").count() == 1


def test_reject_requires_reason(client, db_session):
    driver = _submit_driver(client, db_session)
    staff = admin_headers(client, db_session, role="auditor", username="audrey")
    resp = client.post(
        f"/api/admin/lg/drivers/{driver.id}/review",
        json={"action": "reject", "reason": ""},
        headers=staff,
    )
    assert resp.status_code == 400


def test_cs_role_cannot_review(client, db_session):
    driver = _submit_driver(client, db_session)
    staff = admin_headers(client, db_session, role="cs", username="susan")
    resp = client.post(
        f"/api/admin/lg/drivers/{driver.id}/review",
        json={"action": "approve", "reason": ""},
        headers=staff,
    )
    assert resp.status_code == 403


def test_freeze_and_unfreeze(client, db_session):
    driver = _submit_driver(client, db_session)
    boss = admin_headers(client, db_session, role="admin")
    client.post(f"/api/admin/lg/drivers/{driver.id}/review",
                json={"action": "approve", "reason": ""}, headers=boss)
    resp = client.post(f"/api/admin/lg/drivers/{driver.id}/freeze",
                       json={"reason": "unpaid commission"}, headers=boss)
    assert resp.json()["status"] == "frozen"
    resp = client.post(f"/api/admin/lg/drivers/{driver.id}/unfreeze", headers=boss)
    assert resp.json()["status"] == "approved"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_admin_drivers.py -v`
Expected: FAIL — `ImportError: cannot import name 'Notification'`

- [ ] **Step 3: Write the implementation**

Append to `backend/app/logistics/models.py`:

```python
class Notification(Base):
    __tablename__ = "lg_notification"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("lg_user_account.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # driver_review / vehicle_review / order / expiry
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
```

Create `backend/app/logistics/notify.py`:

```python
from sqlalchemy.orm import Session

from app.logistics.models import Notification, UserAccount
from app.logistics.sms import send_sms


def notify(
    db: Session,
    user: UserAccount,
    kind: str,
    title: str,
    body: str = "",
    sms: bool = False,
) -> None:
    """In-app notification, optionally mirrored by SMS (critical events, PRD XIV)."""
    db.add(Notification(user_id=user.id, kind=kind, title=title, body=body))
    db.commit()
    if sms:
        send_sms(db, user.phone, f"ZokoDaily: {title}. {body}"[:160], kind=kind)
```

Append to `backend/app/logistics/schemas.py`:

```python
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
```

Create `backend/app/logistics/api/admin/drivers.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import require_roles
from app.logistics.models import (
    DRIVER_APPROVED,
    DRIVER_FROZEN,
    DRIVER_PENDING,
    DRIVER_REJECTED,
    AuditRecord,
    Driver,
    UserAccount,
)
from app.logistics.notify import notify
from app.logistics.schemas import DriverAdminOut, FreezeIn, Paginated, ReviewIn
from app.models import AdminUser

router = APIRouter()

reviewer = require_roles("admin", "auditor")
administrator = require_roles("admin")


def _out(db: Session, driver: Driver) -> DriverAdminOut:
    user = db.get(UserAccount, driver.user_id)
    data = DriverAdminOut.model_validate(driver)
    data.user_id = driver.user_id
    data.phone = user.phone if user else ""
    return data


def _get_driver(db: Session, driver_id: int) -> Driver:
    driver = db.get(Driver, driver_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver


@router.get("", response_model=Paginated)
def list_drivers(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    _: AdminUser = Depends(reviewer),
    db: Session = Depends(get_db),
):
    q = db.query(Driver)
    if status:
        q = q.filter(Driver.status == status)
    total = q.count()
    rows = q.order_by(Driver.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return Paginated(items=[_out(db, d).model_dump() for d in rows],
                     total=total, page=page, page_size=page_size)


@router.get("/{driver_id}", response_model=DriverAdminOut)
def get_driver(driver_id: int, _: AdminUser = Depends(reviewer), db: Session = Depends(get_db)):
    return _out(db, _get_driver(db, driver_id))


@router.post("/{driver_id}/review", response_model=DriverAdminOut)
def review_driver(
    driver_id: int,
    body: ReviewIn,
    staff: AdminUser = Depends(reviewer),
    db: Session = Depends(get_db),
):
    driver = _get_driver(db, driver_id)
    if driver.status != DRIVER_PENDING:
        raise HTTPException(status_code=409, detail="Driver is not pending review")
    if body.action == "reject" and not body.reason.strip():
        raise HTTPException(status_code=400, detail="Rejection requires a reason")
    driver.status = DRIVER_APPROVED if body.action == "approve" else DRIVER_REJECTED
    driver.review_remark = body.reason
    db.add(AuditRecord(entity_type="driver", entity_id=driver.id,
                       action=body.action, reason=body.reason, actor=staff.username))
    db.commit()
    user = db.get(UserAccount, driver.user_id)
    if body.action == "approve":
        notify(db, user, "driver_review", "Driver certification approved",
               "You can now add vehicles and publish routes.", sms=True)
    else:
        notify(db, user, "driver_review", "Driver certification rejected",
               body.reason, sms=True)
    return _out(db, driver)


@router.post("/{driver_id}/freeze", response_model=DriverAdminOut)
def freeze_driver(
    driver_id: int,
    body: FreezeIn,
    staff: AdminUser = Depends(administrator),
    db: Session = Depends(get_db),
):
    driver = _get_driver(db, driver_id)
    if driver.status != DRIVER_APPROVED:
        raise HTTPException(status_code=409, detail="Only approved drivers can be frozen")
    driver.status = DRIVER_FROZEN
    db.add(AuditRecord(entity_type="driver", entity_id=driver.id,
                       action="freeze", reason=body.reason, actor=staff.username))
    db.commit()
    return _out(db, driver)


@router.post("/{driver_id}/unfreeze", response_model=DriverAdminOut)
def unfreeze_driver(
    driver_id: int,
    staff: AdminUser = Depends(administrator),
    db: Session = Depends(get_db),
):
    driver = _get_driver(db, driver_id)
    if driver.status != DRIVER_FROZEN:
        raise HTTPException(status_code=409, detail="Driver is not frozen")
    driver.status = DRIVER_APPROVED
    db.add(AuditRecord(entity_type="driver", entity_id=driver.id,
                       action="unfreeze", reason="", actor=staff.username))
    db.commit()
    return _out(db, driver)
```

Modify `backend/app/main.py`:

```python
from app.logistics.api.admin import drivers as lg_admin_drivers
from app.logistics.api.admin import staff as lg_admin_staff

app.include_router(lg_admin_drivers.router, prefix="/api/admin/lg/drivers", tags=["lg-admin"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_admin_drivers.py -v` → 5 PASS
Run: `uv run pytest` → full suite PASS

- [ ] **Step 5: Commit**

```bash
git add app/logistics tests/test_lg_admin_drivers.py app/main.py
git commit -m "feat(lg): admin driver review queue with audit records and notifications"
```

---

### Task 9: Vehicle model + H5 vehicle endpoints

**Files:**
- Create: `backend/app/logistics/api/h5_vehicles.py`
- Modify: `backend/app/logistics/models.py`, `backend/app/logistics/schemas.py`, `backend/app/main.py`
- Test: `backend/tests/test_lg_vehicles.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_lg_vehicles.py`:

```python
from app.logistics.models import Driver, Vehicle
from tests.lg_helpers import h5_login
from tests.test_lg_driver import PROFILE

VEHICLE = {
    "plate_number": "GR 1234-24",
    "brand_model": "Kia K2700",
    "vehicle_type": "box_truck",
    "year": 2019,
    "vin": "",
    "cargo_length_m": 3.1, "cargo_width_m": 1.7, "cargo_height_m": 1.8,
    "max_load_kg": 1900, "max_volume_m3": 9.4,
    "photo_front_id": "p1", "photo_left_id": "p2", "photo_right_id": "p3",
    "photo_rear_id": "p4", "photo_interior_id": "p5",
    "reg_cert_id": "d1",
    "roadworthy_cert_id": "d2", "roadworthy_expiry": "2027-01-01",
    "insurance_cert_id": "d3", "insurance_expiry": "2026-12-01",
}


def _approved_driver_headers(client, db_session, phone="0241234567"):
    headers = h5_login(client, db_session, phone)
    client.put("/api/lg/driver/me", json=PROFILE, headers=headers)
    driver = db_session.query(Driver).order_by(Driver.id.desc()).first()
    driver.status = "approved"
    db_session.commit()
    return headers


def test_unapproved_driver_cannot_add_vehicle(client, db_session):
    headers = h5_login(client, db_session)
    resp = client.post("/api/lg/vehicles", json=VEHICLE, headers=headers)
    assert resp.status_code == 403


def test_create_vehicle(client, db_session):
    headers = _approved_driver_headers(client, db_session)
    resp = client.post("/api/lg/vehicles", json=VEHICLE, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending_review"


def test_duplicate_plate_conflict(client, db_session):
    h1 = _approved_driver_headers(client, db_session, "0241111111")
    client.post("/api/lg/vehicles", json=VEHICLE, headers=h1)
    h2 = _approved_driver_headers(client, db_session, "0242222222")
    resp = client.post(
        "/api/lg/vehicles",
        json={**VEHICLE, "plate_number": "GR 1234-24"},
        headers=h2,
    )
    assert resp.status_code == 409


def test_list_my_vehicles(client, db_session):
    headers = _approved_driver_headers(client, db_session)
    client.post("/api/lg/vehicles", json=VEHICLE, headers=headers)
    resp = client.get("/api/lg/vehicles", headers=headers)
    assert len(resp.json()) == 1


def test_deactivate_and_reactivate(client, db_session):
    headers = _approved_driver_headers(client, db_session)
    vid = client.post("/api/lg/vehicles", json=VEHICLE, headers=headers).json()["id"]
    vehicle = db_session.get(Vehicle, vid)
    vehicle.status = "approved"
    db_session.commit()
    resp = client.post(f"/api/lg/vehicles/{vid}/deactivate", headers=headers)
    assert resp.json()["status"] == "deactivated"
    resp = client.post(f"/api/lg/vehicles/{vid}/reactivate", headers=headers)
    assert resp.json()["status"] == "approved"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_vehicles.py -v`
Expected: FAIL — `ImportError: cannot import name 'Vehicle'`

- [ ] **Step 3: Write the implementation**

Append to `backend/app/logistics/models.py` (extend the sqlalchemy import line with `Float`):

```python
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text

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
```

**Note (PRD §XVI deviation):** the PRD lists a `DriverVehicle` join entity for future multi-driver vehicles; V1 uses a direct `driver_id` FK (one owner). Revisit in V2 if vehicles gain multiple drivers.

Append to `backend/app/logistics/schemas.py`:

```python
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
```

Create `backend/app/logistics/api/h5_vehicles.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import get_current_user
from app.logistics.models import (
    DRIVER_APPROVED,
    VEHICLE_APPROVED,
    VEHICLE_DEACTIVATED,
    VEHICLE_PENDING,
    VEHICLE_REJECTED,
    Blacklist,
    Driver,
    UserAccount,
    Vehicle,
)
from app.logistics.schemas import VehicleIn, VehicleOut

router = APIRouter()


def _my_approved_driver(db: Session, user: UserAccount) -> Driver:
    driver = db.query(Driver).filter_by(user_id=user.id).one_or_none()
    if driver is None or driver.status != DRIVER_APPROVED:
        raise HTTPException(status_code=403, detail="Driver certification required")
    return driver


def _my_vehicle(db: Session, user: UserAccount, vehicle_id: int) -> Vehicle:
    driver = _my_approved_driver(db, user)
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None or vehicle.driver_id != driver.id:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


@router.get("", response_model=list[VehicleOut])
def my_vehicles(user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)):
    driver = db.query(Driver).filter_by(user_id=user.id).one_or_none()
    if driver is None:
        return []
    return db.query(Vehicle).filter_by(driver_id=driver.id).order_by(Vehicle.id).all()


@router.post("", response_model=VehicleOut)
def create_vehicle(
    body: VehicleIn,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    driver = _my_approved_driver(db, user)
    if db.query(Blacklist).filter_by(value_type="plate", value=body.plate_number).first():
        raise HTTPException(status_code=403, detail="Vehicle not permitted")
    if db.query(Vehicle).filter_by(plate_number=body.plate_number).first():
        raise HTTPException(status_code=409, detail="Plate number already registered")
    vehicle = Vehicle(driver_id=driver.id, **body.model_dump())
    db.add(vehicle)
    db.commit()
    return vehicle


@router.put("/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(
    vehicle_id: int,
    body: VehicleIn,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = _my_vehicle(db, user, vehicle_id)
    if vehicle.status not in (VEHICLE_PENDING, VEHICLE_REJECTED):
        raise HTTPException(status_code=409, detail=f"Vehicle is {vehicle.status}; cannot edit")
    dup = (
        db.query(Vehicle)
        .filter(Vehicle.plate_number == body.plate_number, Vehicle.id != vehicle.id)
        .first()
    )
    if dup is not None:
        raise HTTPException(status_code=409, detail="Plate number already registered")
    for field, value in body.model_dump().items():
        setattr(vehicle, field, value)
    vehicle.status = VEHICLE_PENDING
    vehicle.review_remark = ""
    db.commit()
    return vehicle


@router.post("/{vehicle_id}/deactivate", response_model=VehicleOut)
def deactivate(
    vehicle_id: int,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = _my_vehicle(db, user, vehicle_id)
    if vehicle.status != VEHICLE_APPROVED:
        raise HTTPException(status_code=409, detail="Only approved vehicles can be deactivated")
    vehicle.status = VEHICLE_DEACTIVATED
    db.commit()
    return vehicle


@router.post("/{vehicle_id}/reactivate", response_model=VehicleOut)
def reactivate(
    vehicle_id: int,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = _my_vehicle(db, user, vehicle_id)
    if vehicle.status != VEHICLE_DEACTIVATED:
        raise HTTPException(status_code=409, detail="Vehicle is not deactivated")
    vehicle.status = VEHICLE_APPROVED
    db.commit()
    return vehicle
```

Modify `backend/app/main.py`:

```python
from app.logistics.api import h5_auth, h5_driver, h5_uploads, h5_vehicles

app.include_router(h5_vehicles.router, prefix="/api/lg/vehicles", tags=["lg-h5"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_vehicles.py -v` → 5 PASS

- [ ] **Step 5: Commit**

```bash
git add app/logistics tests/test_lg_vehicles.py app/main.py
git commit -m "feat(lg): vehicle model and H5 vehicle management endpoints"
```

---

### Task 10: Admin vehicle review + blacklist management API

**Files:**
- Create: `backend/app/logistics/api/admin/vehicles.py`, `backend/app/logistics/api/admin/blacklist.py`
- Modify: `backend/app/logistics/schemas.py`, `backend/app/main.py`
- Test: `backend/tests/test_lg_admin_vehicles.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_lg_admin_vehicles.py`:

```python
from app.logistics.models import AuditRecord, Notification, Vehicle
from tests.lg_helpers import admin_headers
from tests.test_lg_vehicles import VEHICLE, _approved_driver_headers


def _submitted_vehicle(client, db_session) -> Vehicle:
    headers = _approved_driver_headers(client, db_session)
    client.post("/api/lg/vehicles", json=VEHICLE, headers=headers)
    return db_session.query(Vehicle).one()


def test_review_approve(client, db_session):
    vehicle = _submitted_vehicle(client, db_session)
    staff = admin_headers(client, db_session, role="auditor", username="audrey")
    resp = client.post(
        f"/api/admin/lg/vehicles/{vehicle.id}/review",
        json={"action": "approve", "reason": ""},
        headers=staff,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert db_session.query(AuditRecord).filter_by(entity_type="vehicle").count() == 1
    assert db_session.query(Notification).filter_by(kind="vehicle_review").count() == 1


def test_reject_requires_reason(client, db_session):
    vehicle = _submitted_vehicle(client, db_session)
    staff = admin_headers(client, db_session, role="auditor", username="audrey")
    resp = client.post(
        f"/api/admin/lg/vehicles/{vehicle.id}/review",
        json={"action": "reject", "reason": ""},
        headers=staff,
    )
    assert resp.status_code == 400


def test_blacklist_crud(client, db_session):
    boss = admin_headers(client, db_session, role="admin")
    resp = client.post(
        "/api/admin/lg/blacklist",
        json={"value_type": "plate", "value": "GR 9999-24", "reason": "stolen"},
        headers=boss,
    )
    assert resp.status_code == 200
    entry_id = resp.json()["id"]
    resp = client.get("/api/admin/lg/blacklist", headers=boss)
    assert resp.json()[0]["value"] == "GR 9999-24"
    assert client.delete(f"/api/admin/lg/blacklist/{entry_id}", headers=boss).status_code == 200
    assert client.get("/api/admin/lg/blacklist", headers=boss).json() == []


def test_auditor_cannot_manage_blacklist(client, db_session):
    staff = admin_headers(client, db_session, role="auditor", username="audrey")
    resp = client.get("/api/admin/lg/blacklist", headers=staff)
    assert resp.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_admin_vehicles.py -v`
Expected: FAIL — 404 on `/api/admin/lg/vehicles/.../review`

- [ ] **Step 3: Write the implementation**

Append to `backend/app/logistics/schemas.py`:

```python
class BlacklistIn(BaseModel):
    value_type: Literal["phone", "ghana_card", "plate"]
    value: str
    reason: str = ""


class BlacklistOut(BlacklistIn):
    model_config = {"from_attributes": True}

    id: int
    created_by: str
```

Create `backend/app/logistics/api/admin/vehicles.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import require_roles
from app.logistics.models import (
    VEHICLE_APPROVED,
    VEHICLE_PENDING,
    VEHICLE_REJECTED,
    AuditRecord,
    Driver,
    UserAccount,
    Vehicle,
)
from app.logistics.notify import notify
from app.logistics.schemas import Paginated, ReviewIn, VehicleOut
from app.models import AdminUser

router = APIRouter()

reviewer = require_roles("admin", "auditor")


@router.get("", response_model=Paginated)
def list_vehicles(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    _: AdminUser = Depends(reviewer),
    db: Session = Depends(get_db),
):
    q = db.query(Vehicle)
    if status:
        q = q.filter(Vehicle.status == status)
    total = q.count()
    rows = q.order_by(Vehicle.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return Paginated(items=[VehicleOut.model_validate(v).model_dump(mode="json") for v in rows],
                     total=total, page=page, page_size=page_size)


@router.post("/{vehicle_id}/review", response_model=VehicleOut)
def review_vehicle(
    vehicle_id: int,
    body: ReviewIn,
    staff: AdminUser = Depends(reviewer),
    db: Session = Depends(get_db),
):
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if vehicle.status != VEHICLE_PENDING:
        raise HTTPException(status_code=409, detail="Vehicle is not pending review")
    if body.action == "reject" and not body.reason.strip():
        raise HTTPException(status_code=400, detail="Rejection requires a reason")
    vehicle.status = VEHICLE_APPROVED if body.action == "approve" else VEHICLE_REJECTED
    vehicle.review_remark = body.reason
    db.add(AuditRecord(entity_type="vehicle", entity_id=vehicle.id,
                       action=body.action, reason=body.reason, actor=staff.username))
    db.commit()
    driver = db.get(Driver, vehicle.driver_id)
    user = db.get(UserAccount, driver.user_id)
    title = (f"Vehicle {vehicle.plate_number} approved" if body.action == "approve"
             else f"Vehicle {vehicle.plate_number} rejected")
    notify(db, user, "vehicle_review", title, body.reason, sms=True)
    return vehicle
```

Create `backend/app/logistics/api/admin/blacklist.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import require_roles
from app.logistics.models import Blacklist
from app.logistics.schemas import BlacklistIn, BlacklistOut
from app.models import AdminUser

router = APIRouter()


@router.get("", response_model=list[BlacklistOut])
def list_entries(staff: AdminUser = Depends(require_roles("admin")),
                 db: Session = Depends(get_db)):
    return db.query(Blacklist).order_by(Blacklist.id.desc()).all()


@router.post("", response_model=BlacklistOut)
def add_entry(body: BlacklistIn,
              staff: AdminUser = Depends(require_roles("admin")),
              db: Session = Depends(get_db)):
    entry = Blacklist(**body.model_dump(), created_by=staff.username)
    db.add(entry)
    db.commit()
    return entry


@router.delete("/{entry_id}")
def remove_entry(entry_id: int,
                 staff: AdminUser = Depends(require_roles("admin")),
                 db: Session = Depends(get_db)):
    entry = db.get(Blacklist, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()
    return {"ok": True}
```

Modify `backend/app/main.py`:

```python
from app.logistics.api.admin import blacklist as lg_admin_blacklist
from app.logistics.api.admin import vehicles as lg_admin_vehicles

app.include_router(lg_admin_vehicles.router, prefix="/api/admin/lg/vehicles", tags=["lg-admin"])
app.include_router(lg_admin_blacklist.router, prefix="/api/admin/lg/blacklist", tags=["lg-admin"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_admin_vehicles.py -v` → 4 PASS

- [ ] **Step 5: Commit**

```bash
git add app/logistics tests/test_lg_admin_vehicles.py app/main.py
git commit -m "feat(lg): admin vehicle review and blacklist management"
```

---

### Task 11: H5 notification center endpoints

**Files:**
- Create: `backend/app/logistics/api/h5_notifications.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_lg_notifications.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_lg_notifications.py`:

```python
from app.logistics.models import Notification, UserAccount
from tests.lg_helpers import h5_login


def _seed_notifications(db_session, phone="+233241234567", n=3):
    user = db_session.query(UserAccount).filter_by(phone=phone).one()
    for i in range(n):
        db_session.add(Notification(user_id=user.id, kind="order",
                                    title=f"Event {i}", body=""))
    db_session.commit()


def test_list_with_unread_count(client, db_session):
    headers = h5_login(client, db_session)
    _seed_notifications(db_session)
    resp = client.get("/api/lg/notifications", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["unread"] == 3
    assert data["items"][0]["title"] == "Event 2"  # newest first


def test_mark_read(client, db_session):
    headers = h5_login(client, db_session)
    _seed_notifications(db_session, n=1)
    nid = client.get("/api/lg/notifications", headers=headers).json()["items"][0]["id"]
    assert client.post(f"/api/lg/notifications/{nid}/read", headers=headers).status_code == 200
    assert client.get("/api/lg/notifications", headers=headers).json()["unread"] == 0


def test_cannot_read_others_notification(client, db_session):
    h1 = h5_login(client, db_session, "0241111111")
    _seed_notifications(db_session, "+233241111111", n=1)
    nid = client.get("/api/lg/notifications", headers=h1).json()["items"][0]["id"]
    h2 = h5_login(client, db_session, "0242222222")
    assert client.post(f"/api/lg/notifications/{nid}/read", headers=h2).status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_notifications.py -v`
Expected: FAIL — 404 on `/api/lg/notifications`

- [ ] **Step 3: Write the implementation**

Create `backend/app/logistics/api/h5_notifications.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import get_current_user
from app.logistics.models import Notification, UserAccount, utcnow

router = APIRouter()


@router.get("")
def list_notifications(
    page: int = 1,
    page_size: int = 20,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Notification).filter_by(user_id=user.id)
    total = q.count()
    unread = q.filter(Notification.read_at.is_(None)).count()
    rows = (
        q.order_by(Notification.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [
            {
                "id": n.id, "kind": n.kind, "title": n.title, "body": n.body,
                "read": n.read_at is not None,
                "created_at": n.created_at.isoformat(),
            }
            for n in rows
        ],
        "total": total,
        "unread": unread,
        "page": page,
        "page_size": page_size,
    }


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: int,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    if n.read_at is None:
        n.read_at = utcnow()
        db.commit()
    return {"ok": True}
```

Modify `backend/app/main.py`:

```python
from app.logistics.api import h5_auth, h5_driver, h5_notifications, h5_uploads, h5_vehicles

app.include_router(h5_notifications.router, prefix="/api/lg/notifications", tags=["lg-h5"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_notifications.py -v` → 3 PASS

- [ ] **Step 5: Commit**

```bash
git add app/logistics tests/test_lg_notifications.py app/main.py
git commit -m "feat(lg): H5 notification center endpoints"
```

---

### Task 12: Seed defaults, env example, final verification

**Files:**
- Modify: `backend/app/seed.py`, `backend/.env.example`

- [ ] **Step 1: Extend the seed config defaults**

In `backend/app/seed.py`, extend `CONFIG_DEFAULTS`:

```python
CONFIG_DEFAULTS = {
    "ai_base_url": "https://api.openai.com/v1",
    "ai_api_key": "",
    "ai_model": "gpt-4o-mini",
    "lg_sms_provider": "mock",
    "lg_sms_api_key": "",
    "lg_sms_sender_id": "ZokoDaily",
}
```

- [ ] **Step 2: Extend `.env.example`**

Append to `backend/.env.example`:

```
# Logistics module
UPLOAD_DIR=uploads
```

- [ ] **Step 3: Verify seed still works and run the full suite**

```bash
rm -f verify.db
DATABASE_URL="sqlite:///./verify.db" uv run python -m app.seed
uv run pytest
rm -f verify.db
```

Expected: `Seed complete.` and full suite PASS.

- [ ] **Step 4: Commit and summarize deployment steps**

```bash
git add app/seed.py .env.example
git commit -m "feat(lg): seed SMS config defaults, env example"
```

Deployment checklist for this plan (goes in the PR description; docker-compose changes land in LTL Plan 4 when the frontends ship):

1. `ALTER TABLE admin_user ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'admin';` on production MySQL.
2. New `lg_*` tables are created automatically by `create_all` at startup.
3. Mount a persistent volume for `UPLOAD_DIR` on the backend container.
4. Set `lg_sms_provider=arkesel` + API key via the admin config API when going live; leave `mock` until then.

---

## What this plan deliberately defers

| Deferred item | Where it lands |
| --- | --- |
| Routes, Trips, capacity ledger, orders, commission, CS APIs, statistics, document-expiry sweep | LTL Plan 2 |
| `OperationLog` (general staff action trail beyond review AuditRecords — needed once CS mutates orders) | LTL Plan 2 |
| All H5 pages (tabs, browse, order, driver center) | LTL Plan 3 |
| All admin pages, docker-compose upload volume, nginx config | LTL Plan 4 |
| `DriverVehicle` join table (multi-driver vehicles), signed URLs for object storage | V2 roadmap |
