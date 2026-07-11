# LTL Plan 2: Backend Marketplace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The marketplace core of the LTL module: routes, dated trips with an atomic capacity ledger, the full order status machine, commission snapshots and settlement ledger, CS workspace APIs, operational statistics, and the daily scheduler job (trip generation + document-expiry sweep).

**Architecture:** Everything extends the Plan 1 `app/logistics/` package: new models appended to `models.py`, business rules in small service modules (`capacity.py`, `orders.py`, `trips_service.py`, `sweep.py`, `ops.py`), H5 routers under `/api/lg/*` and staff routers under `/api/admin/lg/*`. A **Route** is a driver-owned reviewed template; a **Trip** is one dated departure with its own capacity ledger seeded from the vehicle; orders book against Trips. Capacity is reserved at CS price-confirmation (row-locked) and released on rejection/cancellation. Commission is snapshotted on the order at price-confirmation and becomes a `CommissionRecord` (payable) at completion.

**Tech Stack:** unchanged — FastAPI, SQLAlchemy 2.0 sync, Pydantic v2, pytest. No new dependencies.

**Money representation (V1 decision):** GHS amounts are stored as `Float` rounded to 2 decimals in code — these are reference records; no money moves through the platform in V1. When V2 adds online payment, migrate to integer pesewas.

**Plan sequence:** LTL Plan 1 (done) → **LTL Plan 2 (this)** → LTL Plan 3 H5 frontend → LTL Plan 4 admin frontend.

**Working directory:** all commands run from `backend/` unless stated otherwise.
**Spec:** `D:\GHANA\COMPANIES\daily.zokomart\Less-than-Truckload_prd.md` (V1.1) §5, §8–§12, §13 (route audit), §14 (order/expiry events), §15, §16 (OperationLog, expiry sweep).

**Plan 1 building blocks referenced throughout** (all exist on branch `ltl-plan-1`):
`app.logistics.models`: `UserAccount, Driver, Vehicle, AuditRecord, Blacklist, Notification, utcnow, DRIVER_APPROVED, AVAILABILITY_ACCEPTING, VEHICLE_APPROVED` · `app.logistics.auth`: `get_current_user, require_roles` · `app.logistics.notify`: `notify(db, user, kind, title, body="", sms=False)` · `app.logistics.schemas`: `Paginated, ReviewIn` · `app.services.config_service`: `get_config, set_config, mask_secret` · tests: `tests/lg_helpers.py` (`h5_login`, `admin_headers`).

---

## File structure created by this plan

```
backend/app/logistics/
├── models.py             # MODIFIED: + Route, Trip, CustomerOrder, CommissionRecord,
│                         #   CsRemark, OperationLog (+ status constants)
├── schemas.py            # MODIFIED: + all Plan 2 schemas
├── ops.py                # log_op() operation-log helper
├── capacity.py           # remaining / reserve / release with row locking
├── orders.py             # order status machine: ALLOWED transitions + transition()
├── trips_service.py      # generate_trips() rolling window
├── sweep.py              # expiry_sweep(): reminders + auto-suspend
└── api/
    ├── h5_routes.py      # /api/lg/routes  (public detail + driver manage)
    ├── h5_trips.py       # /api/lg/trips   (public browse + driver manage)
    ├── h5_orders.py      # /api/lg/orders  (shipper + driver actions)
    ├── h5_commissions.py # /api/lg/commissions/mine
    └── admin/
        ├── routes.py     # /api/admin/lg/routes review queue
        ├── orders.py     # /api/admin/lg/orders CS workspace
        ├── commissions.py# /api/admin/lg/commissions ledger
        ├── config.py     # /api/admin/lg/config
        └── stats.py      # /api/admin/lg/stats/overview

backend/app/scheduler.py  # MODIFIED: + lg_daily_job
backend/app/seed.py       # MODIFIED: + lg_commission_rate, lg_payment_instructions
backend/tests/
├── lg_helpers.py         # MODIFIED: + approved_driver, approved_vehicle, approved_route, make_trip
├── test_lg_routes.py
├── test_lg_admin_routes.py
├── test_lg_trips.py
├── test_lg_browse.py
├── test_lg_capacity.py
├── test_lg_orders_shipper.py
├── test_lg_orders_cs.py
├── test_lg_orders_driver.py
├── test_lg_orders_close.py
├── test_lg_commissions.py
├── test_lg_config.py
├── test_lg_stats.py
└── test_lg_sweep.py
```

**Status-machine reference (implemented in Task 6, used everywhere):**

```
submitted        → price_confirmed | cancelled | exception_closed
price_confirmed  → awaiting_pickup | submitted (driver reject) | cancelled | exception_closed
awaiting_pickup  → in_transit | cancelled | exception_closed
in_transit       → delivered | exception_closed
delivered        → completed | exception_closed
completed / cancelled / exception_closed = terminal
Capacity: reserved on → price_confirmed; released on reject/cancel/exception while in
(price_confirmed, awaiting_pickup).
```

---

### Task 1: Route model + shared test helpers

**Files:**
- Modify: `backend/app/logistics/models.py`, `backend/tests/lg_helpers.py`
- Test: `backend/tests/test_lg_routes.py` (model part)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/lg_helpers.py`:

```python
def _digits(phone: str) -> str:
    return "".join(ch for ch in phone if ch.isdigit())[-9:]


def approved_driver(client, db_session, phone: str = "0241234567"):
    """OTP-login, submit a driver profile (unique per phone), force-approve it.
    Returns (headers, driver_id)."""
    from app.logistics.models import DRIVER_APPROVED, Driver

    headers = h5_login(client, db_session, phone)
    d = _digits(phone)
    profile = {
        "full_name": f"Driver {d}", "gender": "male", "date_of_birth": "1990-05-01",
        "ghana_card_number": f"GHA-{d}-1",
        "ghana_card_front_id": "a1", "ghana_card_back_id": "a2",
        "licence_number": f"DVLA-{d}", "licence_class": "C",
        "licence_expiry": "2030-01-01", "licence_photo_id": "a3",
        "emergency_contact_name": "Ama", "emergency_contact_phone": "0209876543",
        "submit": True,
    }
    resp = client.put("/api/lg/driver/me", json=profile, headers=headers)
    assert resp.status_code == 200, resp.text
    driver = db_session.query(Driver).order_by(Driver.id.desc()).first()
    driver.status = DRIVER_APPROVED
    db_session.commit()
    return headers, driver.id


def approved_vehicle(client, db_session, headers, plate: str = "GR 1111-24") -> int:
    """Create a vehicle for the logged-in approved driver and force-approve it."""
    from app.logistics.models import VEHICLE_APPROVED, Vehicle

    body = {
        "plate_number": plate, "brand_model": "Kia K2700", "vehicle_type": "box_truck",
        "year": 2019, "vin": "", "cargo_length_m": 3.1, "cargo_width_m": 1.7,
        "cargo_height_m": 1.8, "max_load_kg": 2000, "max_volume_m3": 10.0,
        "photo_front_id": "p1", "photo_left_id": "p2", "photo_right_id": "p3",
        "photo_rear_id": "p4", "photo_interior_id": "p5", "reg_cert_id": "d1",
        "roadworthy_cert_id": "d2", "roadworthy_expiry": "2030-01-01",
        "insurance_cert_id": "d3", "insurance_expiry": "2030-01-01",
    }
    resp = client.post("/api/lg/vehicles", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    vid = resp.json()["id"]
    db_session.get(Vehicle, vid).status = VEHICLE_APPROVED
    db_session.commit()
    return vid


ROUTE = {
    "origin_region": "Greater Accra", "origin_town": "Accra",
    "dest_region": "Ashanti", "dest_town": "Kumasi",
    "via_towns": ["Nkawkaw"], "frequency": "daily", "weekdays": [],
    "once_date": None, "depart_time": "08:00", "est_duration_hours": 6,
    "cargo_types": ["general", "electronics"], "prohibited_notes": "",
    "rate_per_ton": 350.0, "rate_per_m3": 60.0, "min_charge": 80.0,
    "negotiable": False,
    # default_vehicle_id filled by caller
}


def approved_route(client, db_session, headers, vehicle_id: int, **overrides) -> int:
    """Publish a route for the logged-in approved driver and force-approve it."""
    from app.logistics.models import ROUTE_APPROVED, Route

    body = {**ROUTE, "default_vehicle_id": vehicle_id, **overrides}
    resp = client.post("/api/lg/routes", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    rid = resp.json()["id"]
    db_session.get(Route, rid).status = ROUTE_APPROVED
    db_session.commit()
    return rid


def make_trip(db_session, route_id: int, depart_date, vehicle_id: int | None = None):
    """Insert a Trip directly, capacity seeded from the vehicle. Returns trip id."""
    from app.logistics.models import Route, Trip, Vehicle

    route = db_session.get(Route, route_id)
    vid = vehicle_id or route.default_vehicle_id
    vehicle = db_session.get(Vehicle, vid)
    trip = Trip(
        route_id=route_id, vehicle_id=vid, depart_date=depart_date,
        depart_time=route.depart_time,
        total_load_kg=float(vehicle.max_load_kg), total_volume_m3=vehicle.max_volume_m3,
    )
    db_session.add(trip)
    db_session.commit()
    return trip.id
```

Create `backend/tests/test_lg_routes.py` (model tests first; endpoint tests arrive in Step 4 of this task via the API):

```python
from app.logistics.models import ROUTE_PENDING, Route


def test_route_defaults(db_session):
    route = Route(
        driver_id=1, origin_region="Greater Accra", origin_town="Accra",
        dest_region="Ashanti", dest_town="Kumasi", via_towns=[],
        frequency="daily", weekdays=[], once_date=None,
        depart_time="08:00", est_duration_hours=6, default_vehicle_id=1,
        cargo_types=["general"], rate_per_ton=350.0, rate_per_m3=None,
        min_charge=None, negotiable=False,
    )
    db_session.add(route)
    db_session.commit()
    assert route.status == ROUTE_PENDING
    assert route.prohibited_notes == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_routes.py -v`
Expected: FAIL — `ImportError: cannot import name 'ROUTE_PENDING'`

- [ ] **Step 3: Write the implementation**

Append to `backend/app/logistics/models.py` (extend the sqlalchemy import line with `JSON`):

```python
from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_routes.py -v` → PASS
Run: `uv run pytest` → full suite PASS

- [ ] **Step 5: Commit**

```bash
git add app/logistics/models.py tests/lg_helpers.py tests/test_lg_routes.py
git commit -m "feat(lg): Route model and marketplace test helpers"
```

---

### Task 2: H5 route publish/manage endpoints

**Files:**
- Create: `backend/app/logistics/api/h5_routes.py`
- Modify: `backend/app/logistics/schemas.py`, `backend/app/main.py`
- Test: `backend/tests/test_lg_routes.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_lg_routes.py`:

```python
from tests.lg_helpers import ROUTE, approved_driver, approved_vehicle, h5_login


def _setup(client, db_session, phone="0241234567", plate="GR 1111-24"):
    headers, driver_id = approved_driver(client, db_session, phone)
    vid = approved_vehicle(client, db_session, headers, plate)
    return headers, driver_id, vid


def test_publish_route(client, db_session):
    headers, _, vid = _setup(client, db_session)
    resp = client.post("/api/lg/routes", json={**ROUTE, "default_vehicle_id": vid},
                       headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending_review"


def test_unapproved_driver_cannot_publish(client, db_session):
    headers = h5_login(client, db_session, "0555000222")
    resp = client.post("/api/lg/routes", json={**ROUTE, "default_vehicle_id": 1},
                       headers=headers)
    assert resp.status_code == 403


def test_weekly_requires_weekdays(client, db_session):
    headers, _, vid = _setup(client, db_session)
    resp = client.post(
        "/api/lg/routes",
        json={**ROUTE, "default_vehicle_id": vid, "frequency": "weekly", "weekdays": []},
        headers=headers,
    )
    assert resp.status_code == 422


def test_pricing_required_unless_negotiable(client, db_session):
    headers, _, vid = _setup(client, db_session)
    bad = {**ROUTE, "default_vehicle_id": vid,
           "rate_per_ton": None, "rate_per_m3": None, "negotiable": False}
    assert client.post("/api/lg/routes", json=bad, headers=headers).status_code == 422
    ok = {**bad, "negotiable": True}
    assert client.post("/api/lg/routes", json=ok, headers=headers).status_code == 200


def test_cannot_use_someone_elses_vehicle(client, db_session):
    _, _, other_vid = _setup(client, db_session, "0241111111", "GR 2222-24")
    headers, _, _ = _setup(client, db_session, "0242222222", "GR 3333-24")
    resp = client.post("/api/lg/routes", json={**ROUTE, "default_vehicle_id": other_vid},
                       headers=headers)
    assert resp.status_code == 403


def test_edit_and_driver_suspend_resume(client, db_session):
    from app.logistics.models import ROUTE_APPROVED, Route

    headers, _, vid = _setup(client, db_session)
    rid = client.post("/api/lg/routes", json={**ROUTE, "default_vehicle_id": vid},
                      headers=headers).json()["id"]
    # edit while pending is allowed and stays pending
    resp = client.put(f"/api/lg/routes/{rid}",
                      json={**ROUTE, "default_vehicle_id": vid, "origin_town": "Tema"},
                      headers=headers)
    assert resp.status_code == 200 and resp.json()["origin_town"] == "Tema"
    # suspend requires approved
    assert client.post(f"/api/lg/routes/{rid}/suspend", headers=headers).status_code == 409
    db_session.get(Route, rid).status = ROUTE_APPROVED
    db_session.commit()
    assert client.post(f"/api/lg/routes/{rid}/suspend",
                       headers=headers).json()["status"] == "suspended"
    assert client.post(f"/api/lg/routes/{rid}/resume",
                       headers=headers).json()["status"] == "approved"


def test_list_my_routes(client, db_session):
    headers, _, vid = _setup(client, db_session)
    client.post("/api/lg/routes", json={**ROUTE, "default_vehicle_id": vid}, headers=headers)
    resp = client.get("/api/lg/routes/mine", headers=headers)
    assert resp.status_code == 200 and len(resp.json()) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_routes.py -v`
Expected: new tests FAIL with 404 (routes not registered)

- [ ] **Step 3: Write the implementation**

Append to `backend/app/logistics/schemas.py` (`model_validator` joins the existing pydantic import):

```python
from pydantic import BaseModel, field_validator, model_validator


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
```

Create `backend/app/logistics/api/h5_routes.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import get_current_user
from app.logistics.models import (
    DRIVER_APPROVED,
    ROUTE_APPROVED,
    ROUTE_PENDING,
    ROUTE_REJECTED,
    ROUTE_SUSPENDED,
    VEHICLE_APPROVED,
    Driver,
    Route,
    UserAccount,
    Vehicle,
)
from app.logistics.schemas import RouteIn, RouteOut

router = APIRouter()


def _my_approved_driver(db: Session, user: UserAccount) -> Driver:
    driver = db.query(Driver).filter_by(user_id=user.id).one_or_none()
    if driver is None or driver.status != DRIVER_APPROVED:
        raise HTTPException(status_code=403, detail="Driver certification required")
    return driver


def _check_vehicle(db: Session, driver: Driver, vehicle_id: int) -> Vehicle:
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None or vehicle.driver_id != driver.id:
        raise HTTPException(status_code=403, detail="Not your vehicle")
    if vehicle.status != VEHICLE_APPROVED:
        raise HTTPException(status_code=409, detail="Vehicle is not approved")
    return vehicle


def _my_route(db: Session, user: UserAccount, route_id: int) -> tuple[Driver, Route]:
    driver = _my_approved_driver(db, user)
    route = db.get(Route, route_id)
    if route is None or route.driver_id != driver.id:
        raise HTTPException(status_code=404, detail="Route not found")
    return driver, route


@router.get("/mine", response_model=list[RouteOut])
def my_routes(user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)):
    driver = db.query(Driver).filter_by(user_id=user.id).one_or_none()
    if driver is None:
        return []
    return db.query(Route).filter_by(driver_id=driver.id).order_by(Route.id.desc()).all()


@router.post("", response_model=RouteOut)
def publish_route(
    body: RouteIn,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    driver = _my_approved_driver(db, user)
    _check_vehicle(db, driver, body.default_vehicle_id)
    route = Route(driver_id=driver.id, **body.model_dump())
    db.add(route)
    db.commit()
    return route


@router.put("/{route_id}", response_model=RouteOut)
def update_route(
    route_id: int,
    body: RouteIn,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    driver, route = _my_route(db, user, route_id)
    if route.status not in (ROUTE_PENDING, ROUTE_REJECTED):
        raise HTTPException(status_code=409, detail=f"Route is {route.status}; cannot edit")
    _check_vehicle(db, driver, body.default_vehicle_id)
    for field, value in body.model_dump().items():
        setattr(route, field, value)
    route.status = ROUTE_PENDING
    route.review_remark = ""
    db.commit()
    return route


@router.post("/{route_id}/suspend", response_model=RouteOut)
def suspend_route(
    route_id: int,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _, route = _my_route(db, user, route_id)
    if route.status != ROUTE_APPROVED:
        raise HTTPException(status_code=409, detail="Only approved routes can be suspended")
    route.status = ROUTE_SUSPENDED
    db.commit()
    return route


@router.post("/{route_id}/resume", response_model=RouteOut)
def resume_route(
    route_id: int,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _, route = _my_route(db, user, route_id)
    if route.status != ROUTE_SUSPENDED:
        raise HTTPException(status_code=409, detail="Route is not suspended")
    route.status = ROUTE_APPROVED
    db.commit()
    return route
```

Modify `backend/app/main.py` — extend the logistics imports and registrations:

```python
from app.logistics.api import h5_auth, h5_driver, h5_notifications, h5_routes, h5_uploads, h5_vehicles

app.include_router(h5_routes.router, prefix="/api/lg/routes", tags=["lg-h5"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_routes.py -v` → all PASS

- [ ] **Step 5: Commit**

```bash
git add app/logistics tests/test_lg_routes.py app/main.py
git commit -m "feat(lg): H5 route publish, edit, suspend/resume"
```

---

### Task 3: Trip model + generation service

**Files:**
- Create: `backend/app/logistics/trips_service.py`
- Modify: `backend/app/logistics/models.py`
- Test: `backend/tests/test_lg_trips.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_lg_trips.py`:

```python
from datetime import date, timedelta

from app.logistics.models import Trip
from app.logistics.trips_service import generate_trips
from tests.lg_helpers import approved_driver, approved_route, approved_vehicle

TODAY = date(2026, 7, 13)  # a Monday


def _route(client, db_session, **overrides):
    headers, _ = approved_driver(client, db_session)
    vid = approved_vehicle(client, db_session, headers)
    rid = approved_route(client, db_session, headers, vid, **overrides)
    return headers, vid, rid


def test_daily_route_generates_seven_trips(client, db_session):
    _, vid, rid = _route(client, db_session)
    created = generate_trips(db_session, days_ahead=7, today=TODAY)
    assert created == 7
    trips = db_session.query(Trip).filter_by(route_id=rid).all()
    assert len(trips) == 7
    assert trips[0].total_load_kg == 2000.0  # seeded from the vehicle
    assert trips[0].used_load_kg == 0.0


def test_generation_is_idempotent(client, db_session):
    _route(client, db_session)
    generate_trips(db_session, days_ahead=7, today=TODAY)
    assert generate_trips(db_session, days_ahead=7, today=TODAY) == 0


def test_weekly_route_generates_matching_days(client, db_session):
    _, _, rid = _route(client, db_session,
                       frequency="weekly", weekdays=[0, 3])  # Mon + Thu
    created = generate_trips(db_session, days_ahead=7, today=TODAY)
    dates = [t.depart_date for t in db_session.query(Trip).filter_by(route_id=rid).all()]
    assert created == 2
    assert dates == [TODAY, TODAY + timedelta(days=3)]


def test_once_route_generates_single_trip(client, db_session):
    target = TODAY + timedelta(days=2)
    _, _, rid = _route(client, db_session, frequency="once",
                       once_date=target.isoformat())
    created = generate_trips(db_session, days_ahead=7, today=TODAY)
    assert created == 1
    assert db_session.query(Trip).filter_by(route_id=rid).one().depart_date == target


def test_paused_driver_gets_no_trips(client, db_session):
    from app.logistics.models import AVAILABILITY_PAUSED, Driver

    _, _, _ = _route(client, db_session)
    db_session.query(Driver).one().availability = AVAILABILITY_PAUSED
    db_session.commit()
    assert generate_trips(db_session, days_ahead=7, today=TODAY) == 0


def test_expired_insurance_blocks_generation(client, db_session):
    from app.logistics.models import Vehicle

    _, vid, _ = _route(client, db_session)
    db_session.get(Vehicle, vid).insurance_expiry = TODAY - timedelta(days=1)
    db_session.commit()
    assert generate_trips(db_session, days_ahead=7, today=TODAY) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_trips.py -v`
Expected: FAIL — `ImportError: cannot import name 'Trip'`

- [ ] **Step 3: Write the implementation**

Append to `backend/app/logistics/models.py` (extend the sqlalchemy import line with `UniqueConstraint`):

```python
from sqlalchemy import UniqueConstraint  # merge into the existing import line

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
```

Create `backend/app/logistics/trips_service.py`:

```python
"""Rolling trip generation (PRD §8.1): 7 days ahead, only for routes whose driver
is approved+accepting and whose vehicle is approved with unexpired documents."""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.logistics.models import (
    AVAILABILITY_ACCEPTING,
    DRIVER_APPROVED,
    ROUTE_APPROVED,
    VEHICLE_APPROVED,
    Driver,
    Route,
    Trip,
    Vehicle,
)


def _eligible(driver: Driver | None, vehicle: Vehicle | None, today: date) -> bool:
    return (
        driver is not None
        and driver.status == DRIVER_APPROVED
        and driver.availability == AVAILABILITY_ACCEPTING
        and vehicle is not None
        and vehicle.status == VEHICLE_APPROVED
        and vehicle.roadworthy_expiry >= today
        and vehicle.insurance_expiry >= today
    )


def _wants(route: Route, d: date) -> bool:
    if route.frequency == "daily":
        return True
    if route.frequency == "weekly":
        return d.weekday() in (route.weekdays or [])
    return route.once_date == d  # "once"


def generate_trips(db: Session, days_ahead: int = 7, today: date | None = None,
                   route_id: int | None = None) -> int:
    today = today or date.today()
    q = db.query(Route).filter(Route.status == ROUTE_APPROVED)
    if route_id is not None:
        q = q.filter(Route.id == route_id)
    created = 0
    for route in q.all():
        driver = db.get(Driver, route.driver_id)
        vehicle = db.get(Vehicle, route.default_vehicle_id)
        if not _eligible(driver, vehicle, today):
            continue
        for offset in range(days_ahead):
            d = today + timedelta(days=offset)
            if not _wants(route, d):
                continue
            if db.query(Trip).filter_by(route_id=route.id, depart_date=d).first():
                continue
            db.add(Trip(
                route_id=route.id, vehicle_id=vehicle.id, depart_date=d,
                depart_time=route.depart_time,
                total_load_kg=float(vehicle.max_load_kg),
                total_volume_m3=vehicle.max_volume_m3,
            ))
            created += 1
    db.commit()
    return created
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_trips.py -v` → 6 PASS

- [ ] **Step 5: Commit**

```bash
git add app/logistics tests/test_lg_trips.py
git commit -m "feat(lg): Trip model with capacity ledger and rolling generation"
```

---

### Task 4: Admin route review (generates trips on approval)

**Files:**
- Create: `backend/app/logistics/api/admin/routes.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_lg_admin_routes.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_lg_admin_routes.py`:

```python
from app.logistics.models import AuditRecord, Notification, Route, Trip
from tests.lg_helpers import ROUTE, admin_headers, approved_driver, approved_vehicle


def _pending_route(client, db_session):
    headers, _ = approved_driver(client, db_session)
    vid = approved_vehicle(client, db_session, headers)
    rid = client.post("/api/lg/routes", json={**ROUTE, "default_vehicle_id": vid},
                      headers=headers).json()["id"]
    return rid


def test_review_queue_and_approve_generates_trips(client, db_session):
    rid = _pending_route(client, db_session)
    staff = admin_headers(client, db_session, role="auditor", username="audrey")
    resp = client.get("/api/admin/lg/routes?status=pending_review", headers=staff)
    assert resp.json()["total"] == 1
    resp = client.post(f"/api/admin/lg/routes/{rid}/review",
                       json={"action": "approve", "reason": ""}, headers=staff)
    assert resp.status_code == 200 and resp.json()["status"] == "approved"
    assert db_session.query(AuditRecord).filter_by(entity_type="route").count() == 1
    assert db_session.query(Notification).filter_by(kind="route_review").count() == 1
    assert db_session.query(Trip).filter_by(route_id=rid).count() > 0  # trips generated


def test_reject_requires_reason(client, db_session):
    rid = _pending_route(client, db_session)
    staff = admin_headers(client, db_session, role="auditor", username="audrey")
    resp = client.post(f"/api/admin/lg/routes/{rid}/review",
                       json={"action": "reject", "reason": ""}, headers=staff)
    assert resp.status_code == 400


def test_cs_cannot_review_routes(client, db_session):
    rid = _pending_route(client, db_session)
    staff = admin_headers(client, db_session, role="cs", username="susan")
    resp = client.post(f"/api/admin/lg/routes/{rid}/review",
                       json={"action": "approve", "reason": ""}, headers=staff)
    assert resp.status_code == 403


def test_admin_suspend_and_resume(client, db_session):
    rid = _pending_route(client, db_session)
    boss = admin_headers(client, db_session, role="admin")
    client.post(f"/api/admin/lg/routes/{rid}/review",
                json={"action": "approve", "reason": ""}, headers=boss)
    resp = client.post(f"/api/admin/lg/routes/{rid}/suspend",
                       json={"reason": "pricing complaint"}, headers=boss)
    assert resp.json()["status"] == "suspended"
    resp = client.post(f"/api/admin/lg/routes/{rid}/resume", headers=boss)
    assert resp.json()["status"] == "approved"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_admin_routes.py -v`
Expected: FAIL — 404 on `/api/admin/lg/routes`

- [ ] **Step 3: Write the implementation**

Create `backend/app/logistics/api/admin/routes.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import require_roles
from app.logistics.models import (
    ROUTE_APPROVED,
    ROUTE_PENDING,
    ROUTE_REJECTED,
    ROUTE_SUSPENDED,
    AuditRecord,
    Driver,
    Route,
    UserAccount,
)
from app.logistics.notify import notify
from app.logistics.schemas import FreezeIn, Paginated, ReviewIn, RouteOut
from app.logistics.trips_service import generate_trips
from app.models import AdminUser

router = APIRouter()

reviewer = require_roles("admin", "auditor")
administrator = require_roles("admin")


def _get(db: Session, route_id: int) -> Route:
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")
    return route


def _notify_driver(db: Session, route: Route, title: str, body: str) -> None:
    driver = db.get(Driver, route.driver_id)
    user = db.get(UserAccount, driver.user_id)
    notify(db, user, "route_review", title, body, sms=True)


@router.get("", response_model=Paginated)
def list_routes(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    _: AdminUser = Depends(reviewer),
    db: Session = Depends(get_db),
):
    q = db.query(Route)
    if status:
        q = q.filter(Route.status == status)
    total = q.count()
    rows = q.order_by(Route.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return Paginated(items=[RouteOut.model_validate(r).model_dump(mode="json") for r in rows],
                     total=total, page=page, page_size=page_size)


@router.post("/{route_id}/review", response_model=RouteOut)
def review_route(
    route_id: int,
    body: ReviewIn,
    staff: AdminUser = Depends(reviewer),
    db: Session = Depends(get_db),
):
    route = _get(db, route_id)
    if route.status != ROUTE_PENDING:
        raise HTTPException(status_code=409, detail="Route is not pending review")
    if body.action == "reject" and not body.reason.strip():
        raise HTTPException(status_code=400, detail="Rejection requires a reason")
    route.status = ROUTE_APPROVED if body.action == "approve" else ROUTE_REJECTED
    route.review_remark = body.reason
    db.add(AuditRecord(entity_type="route", entity_id=route.id,
                       action=body.action, reason=body.reason, actor=staff.username))
    db.commit()
    if body.action == "approve":
        generate_trips(db, route_id=route.id)
        _notify_driver(db, route, "Route approved",
                       f"{route.origin_town} → {route.dest_town} is now live.")
    else:
        _notify_driver(db, route, "Route rejected", body.reason)
    return route


@router.post("/{route_id}/suspend", response_model=RouteOut)
def suspend_route(
    route_id: int,
    body: FreezeIn,
    staff: AdminUser = Depends(administrator),
    db: Session = Depends(get_db),
):
    route = _get(db, route_id)
    if route.status != ROUTE_APPROVED:
        raise HTTPException(status_code=409, detail="Only approved routes can be suspended")
    route.status = ROUTE_SUSPENDED
    db.add(AuditRecord(entity_type="route", entity_id=route.id,
                       action="suspend", reason=body.reason, actor=staff.username))
    db.commit()
    _notify_driver(db, route, "Route suspended", body.reason)
    return route


@router.post("/{route_id}/resume", response_model=RouteOut)
def resume_route(
    route_id: int,
    staff: AdminUser = Depends(administrator),
    db: Session = Depends(get_db),
):
    route = _get(db, route_id)
    if route.status != ROUTE_SUSPENDED:
        raise HTTPException(status_code=409, detail="Route is not suspended")
    route.status = ROUTE_APPROVED
    db.add(AuditRecord(entity_type="route", entity_id=route.id,
                       action="resume", reason="", actor=staff.username))
    db.commit()
    return route
```

Modify `backend/app/main.py`:

```python
from app.logistics.api.admin import routes as lg_admin_routes

app.include_router(lg_admin_routes.router, prefix="/api/admin/lg/routes", tags=["lg-admin"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_admin_routes.py -v` → 4 PASS

- [ ] **Step 5: Commit**

```bash
git add app/logistics tests/test_lg_admin_routes.py app/main.py
git commit -m "feat(lg): admin route review with trip generation on approval"
```

---

### Task 5: Public trip browse + driver trip management

**Files:**
- Create: `backend/app/logistics/api/h5_trips.py`, `backend/app/logistics/ops.py`
- Modify: `backend/app/logistics/schemas.py`, `backend/app/main.py`
- Test: `backend/tests/test_lg_browse.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_lg_browse.py`:

```python
from datetime import date, timedelta

from app.logistics.models import Trip
from tests.lg_helpers import (
    approved_driver,
    approved_route,
    approved_vehicle,
    make_trip,
)

TOMORROW = date.today() + timedelta(days=1)


def _live_trip(client, db_session, phone="0241234567", plate="GR 1111-24"):
    headers, _ = approved_driver(client, db_session, phone)
    vid = approved_vehicle(client, db_session, headers, plate)
    rid = approved_route(client, db_session, headers, vid)
    tid = make_trip(db_session, rid, TOMORROW)
    return headers, rid, tid


def test_public_browse_no_auth(client, db_session):
    _live_trip(client, db_session)
    resp = client.get("/api/lg/trips")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    card = resp.json()["items"][0]
    assert card["origin_town"] == "Accra"
    assert card["remaining_load_kg"] == 2000.0
    assert card["remaining_volume_m3"] == 10.0
    assert "plate_number" not in card  # not disclosed publicly


def test_browse_filters(client, db_session):
    _live_trip(client, db_session)
    assert client.get("/api/lg/trips?dest_town=Kumasi").json()["total"] == 1
    assert client.get("/api/lg/trips?dest_town=Tamale").json()["total"] == 0
    assert client.get(f"/api/lg/trips?date={TOMORROW.isoformat()}").json()["total"] == 1


def test_suspended_route_hidden(client, db_session):
    from app.logistics.models import ROUTE_SUSPENDED, Route

    _, rid, _ = _live_trip(client, db_session)
    db_session.get(Route, rid).status = ROUTE_SUSPENDED
    db_session.commit()
    assert client.get("/api/lg/trips").json()["total"] == 0


def test_route_detail_with_upcoming_trips(client, db_session):
    _, rid, _ = _live_trip(client, db_session)
    resp = client.get(f"/api/lg/routes/{rid}")
    assert resp.status_code == 200
    assert resp.json()["vehicle"]["vehicle_type"] == "box_truck"
    assert len(resp.json()["upcoming_trips"]) == 1


def test_driver_one_off_trip_and_cancel(client, db_session):
    headers, rid, _ = _live_trip(client, db_session)
    extra = TOMORROW + timedelta(days=10)
    resp = client.post("/api/lg/trips",
                       json={"route_id": rid, "depart_date": extra.isoformat()},
                       headers=headers)
    assert resp.status_code == 200
    tid = resp.json()["id"]
    resp = client.post(f"/api/lg/trips/{tid}/cancel", headers=headers)
    assert resp.status_code == 200 and resp.json()["status"] == "cancelled"


def test_capacity_adjustment_floor(client, db_session):
    headers, _, tid = _live_trip(client, db_session)
    resp = client.post(
        f"/api/lg/trips/{tid}/capacity",
        json={"manual_load_kg": 500, "manual_volume_m3": 2, "reason": "own goods"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert client.get("/api/lg/trips").json()["items"][0]["remaining_load_kg"] == 1500.0
    resp = client.post(
        f"/api/lg/trips/{tid}/capacity",
        json={"manual_load_kg": 99999, "manual_volume_m3": 0, "reason": "x"},
        headers=headers,
    )
    assert resp.status_code == 409  # cannot exceed total
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_browse.py -v`
Expected: FAIL — 404 on `/api/lg/trips`

- [ ] **Step 3: Write the implementation**

Create `backend/app/logistics/ops.py`:

```python
from sqlalchemy.orm import Session

from app.logistics.models import OperationLog


def log_op(db: Session, actor: str, actor_type: str, action: str,
           entity_type: str, entity_id: int, detail: str = "") -> None:
    """Append-only operation trail (PRD §16). Caller commits."""
    db.add(OperationLog(actor=actor, actor_type=actor_type, action=action,
                        entity_type=entity_type, entity_id=entity_id, detail=detail))
```

Append to `backend/app/logistics/models.py`:

```python
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
```

Append to `backend/app/logistics/schemas.py`:

```python
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
```

Create `backend/app/logistics/api/h5_trips.py`:

```python
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import get_current_user
from app.logistics.capacity import remaining_load, remaining_volume
from app.logistics.models import (
    AVAILABILITY_ACCEPTING,
    DRIVER_APPROVED,
    ORDER_ACTIVE_STATUSES,
    ROUTE_APPROVED,
    TRIP_CANCELLED,
    TRIP_SCHEDULED,
    CustomerOrder,
    Driver,
    Route,
    Trip,
    UserAccount,
    Vehicle,
)
from app.logistics.ops import log_op
from app.logistics.schemas import CapacityAdjustIn, TripCreateIn, TripOut

router = APIRouter()


def _browse_query(db: Session, today: date):
    return (
        db.query(Trip, Route, Vehicle)
        .join(Route, Trip.route_id == Route.id)
        .join(Vehicle, Trip.vehicle_id == Vehicle.id)
        .join(Driver, Route.driver_id == Driver.id)
        .filter(
            Trip.status == TRIP_SCHEDULED,
            Trip.depart_date >= today,
            Route.status == ROUTE_APPROVED,
            Driver.status == DRIVER_APPROVED,
            Driver.availability == AVAILABILITY_ACCEPTING,
        )
    )


def _card(trip: Trip, route: Route, vehicle: Vehicle) -> dict:
    return {
        "trip_id": trip.id,
        "route_id": route.id,
        "depart_date": trip.depart_date.isoformat(),
        "depart_time": trip.depart_time,
        "origin_region": route.origin_region, "origin_town": route.origin_town,
        "dest_region": route.dest_region, "dest_town": route.dest_town,
        "via_towns": route.via_towns,
        "est_duration_hours": route.est_duration_hours,
        "vehicle_type": vehicle.vehicle_type, "brand_model": vehicle.brand_model,
        "remaining_load_kg": remaining_load(trip),
        "remaining_volume_m3": remaining_volume(trip),
        "rate_per_ton": route.rate_per_ton, "rate_per_m3": route.rate_per_m3,
        "min_charge": route.min_charge, "negotiable": route.negotiable,
        "cargo_types": route.cargo_types,
    }


@router.get("")
def browse_trips(
    origin_town: str | None = None,
    dest_town: str | None = None,
    origin_region: str | None = None,
    dest_region: str | None = None,
    date_: date | None = Query(default=None, alias="date"),
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    q = _browse_query(db, date.today())
    if origin_town:
        q = q.filter(Route.origin_town.ilike(f"%{origin_town}%"))
    if dest_town:
        q = q.filter(Route.dest_town.ilike(f"%{dest_town}%"))
    if origin_region:
        q = q.filter(Route.origin_region == origin_region)
    if dest_region:
        q = q.filter(Route.dest_region == dest_region)
    if date_:
        q = q.filter(Trip.depart_date == date_)
    total = q.count()
    rows = (q.order_by(Trip.depart_date, Trip.id)
             .offset((page - 1) * page_size).limit(page_size).all())
    return {"items": [_card(t, r, v) for t, r, v in rows],
            "total": total, "page": page, "page_size": page_size}


@router.get("/mine", response_model=list[TripOut])
def my_trips(user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)):
    driver = db.query(Driver).filter_by(user_id=user.id).one_or_none()
    if driver is None:
        return []
    return (
        db.query(Trip).join(Route, Trip.route_id == Route.id)
        .filter(Route.driver_id == driver.id, Trip.depart_date >= date.today())
        .order_by(Trip.depart_date).all()
    )


def _my_trip(db: Session, user: UserAccount, trip_id: int) -> Trip:
    driver = db.query(Driver).filter_by(user_id=user.id).one_or_none()
    trip = db.get(Trip, trip_id)
    if driver is None or trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    route = db.get(Route, trip.route_id)
    if route.driver_id != driver.id:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.post("", response_model=TripOut)
def create_trip(
    body: TripCreateIn,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    driver = db.query(Driver).filter_by(user_id=user.id).one_or_none()
    route = db.get(Route, body.route_id)
    if driver is None or route is None or route.driver_id != driver.id:
        raise HTTPException(status_code=404, detail="Route not found")
    if route.status != ROUTE_APPROVED:
        raise HTTPException(status_code=409, detail="Route is not approved")
    if body.depart_date < date.today():
        raise HTTPException(status_code=400, detail="Departure date is in the past")
    if db.query(Trip).filter_by(route_id=route.id, depart_date=body.depart_date).first():
        raise HTTPException(status_code=409, detail="Trip already exists for that date")
    vehicle = db.get(Vehicle, body.vehicle_id or route.default_vehicle_id)
    if vehicle is None or vehicle.driver_id != driver.id or vehicle.status != "approved":
        raise HTTPException(status_code=409, detail="Vehicle unavailable")
    trip = Trip(route_id=route.id, vehicle_id=vehicle.id, depart_date=body.depart_date,
                depart_time=route.depart_time,
                total_load_kg=float(vehicle.max_load_kg),
                total_volume_m3=vehicle.max_volume_m3)
    db.add(trip)
    log_op(db, user.phone, "driver", "trip_create", "trip", 0, str(body.depart_date))
    db.commit()
    return trip


@router.post("/{trip_id}/cancel", response_model=TripOut)
def cancel_trip(
    trip_id: int,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    trip = _my_trip(db, user, trip_id)
    if trip.status != TRIP_SCHEDULED:
        raise HTTPException(status_code=409, detail="Trip is not scheduled")
    active = (db.query(CustomerOrder)
              .filter(CustomerOrder.trip_id == trip.id,
                      CustomerOrder.status.in_(ORDER_ACTIVE_STATUSES)).count())
    if active:
        raise HTTPException(status_code=409,
                            detail="Trip has active orders; contact customer service")
    trip.status = TRIP_CANCELLED
    log_op(db, user.phone, "driver", "trip_cancel", "trip", trip.id)
    db.commit()
    return trip


@router.post("/{trip_id}/capacity", response_model=TripOut)
def adjust_capacity(
    trip_id: int,
    body: CapacityAdjustIn,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    trip = _my_trip(db, user, trip_id)
    if (trip.used_load_kg + body.manual_load_kg > trip.total_load_kg
            or trip.used_volume_m3 + body.manual_volume_m3 > trip.total_volume_m3):
        raise HTTPException(status_code=409, detail="Adjustment exceeds vehicle capacity")
    trip.manual_load_kg = body.manual_load_kg
    trip.manual_volume_m3 = body.manual_volume_m3
    log_op(db, user.phone, "driver", "trip_capacity_adjust", "trip", trip.id, body.reason)
    db.commit()
    return trip
```

Add the missing `Query` import at the top of `h5_trips.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Query
```

Append the public route-detail endpoint to `backend/app/logistics/api/h5_routes.py`
(**after** `/mine` so `/mine` matches first; FastAPI matches in declaration order):

```python
@router.get("/{route_id}")
def route_detail(route_id: int, db: Session = Depends(get_db)):
    from datetime import date as _date

    from app.logistics.capacity import remaining_load, remaining_volume
    from app.logistics.models import ROUTE_APPROVED, TRIP_SCHEDULED, Trip

    route = db.get(Route, route_id)
    if route is None or route.status != ROUTE_APPROVED:
        raise HTTPException(status_code=404, detail="Route not found")
    vehicle = db.get(Vehicle, route.default_vehicle_id)
    trips = (
        db.query(Trip)
        .filter(Trip.route_id == route.id, Trip.status == TRIP_SCHEDULED,
                Trip.depart_date >= _date.today())
        .order_by(Trip.depart_date).limit(14).all()
    )
    data = RouteOut.model_validate(route).model_dump(mode="json")
    data["vehicle"] = {
        "vehicle_type": vehicle.vehicle_type, "brand_model": vehicle.brand_model,
        "max_load_kg": vehicle.max_load_kg, "max_volume_m3": vehicle.max_volume_m3,
        "cargo_length_m": vehicle.cargo_length_m, "cargo_width_m": vehicle.cargo_width_m,
        "cargo_height_m": vehicle.cargo_height_m,
    }
    data["upcoming_trips"] = [
        {"trip_id": t.id, "depart_date": t.depart_date.isoformat(),
         "depart_time": t.depart_time,
         "remaining_load_kg": remaining_load(t), "remaining_volume_m3": remaining_volume(t)}
        for t in trips
    ]
    return data
```

Create a **stub** of `backend/app/logistics/capacity.py` now (reserve/release arrive in Task 6 — only the two pure helpers are needed here):

```python
from app.logistics.models import Trip


def remaining_load(trip: Trip) -> float:
    return round(trip.total_load_kg - trip.used_load_kg - trip.manual_load_kg, 2)


def remaining_volume(trip: Trip) -> float:
    return round(trip.total_volume_m3 - trip.used_volume_m3 - trip.manual_volume_m3, 2)
```

`h5_trips.py` imports `CustomerOrder` and `ORDER_ACTIVE_STATUSES`, which arrive in Task 6. To keep this task green on its own, append the constant and a minimal `CustomerOrder` **now** as part of this task — Task 6 then extends the model test coverage. Append to `backend/app/logistics/models.py`:

```python
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
```

Modify `backend/app/main.py`:

```python
from app.logistics.api import (
    h5_auth, h5_driver, h5_notifications, h5_routes, h5_trips, h5_uploads, h5_vehicles,
)

app.include_router(h5_trips.router, prefix="/api/lg/trips", tags=["lg-h5"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_browse.py -v` → 6 PASS
Run: `uv run pytest` → full suite PASS

- [ ] **Step 5: Commit**

```bash
git add app/logistics tests/test_lg_browse.py app/main.py
git commit -m "feat(lg): public trip browse, route detail, driver trip management"
```

---

### Task 6: Capacity reserve/release + order status machine

**Files:**
- Modify: `backend/app/logistics/capacity.py`
- Create: `backend/app/logistics/orders.py`
- Modify: `backend/app/logistics/models.py` (CommissionRecord, CsRemark)
- Test: `backend/tests/test_lg_capacity.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_lg_capacity.py`:

```python
from datetime import date, timedelta

import pytest

from app.logistics.capacity import CapacityError, release, reserve
from app.logistics.models import Trip
from app.logistics.orders import ALLOWED, transition
from tests.lg_helpers import approved_driver, approved_route, approved_vehicle, make_trip


def _trip(client, db_session):
    headers, _ = approved_driver(client, db_session)
    vid = approved_vehicle(client, db_session, headers)
    rid = approved_route(client, db_session, headers, vid)
    tid = make_trip(db_session, rid, date.today() + timedelta(days=1))
    return db_session.get(Trip, tid)


def test_reserve_and_release(client, db_session):
    trip = _trip(client, db_session)
    reserve(db_session, trip.id, 800.0, 4.0)
    db_session.commit()
    assert trip.used_load_kg == 800.0 and trip.used_volume_m3 == 4.0
    release(db_session, trip.id, 800.0, 4.0)
    db_session.commit()
    assert trip.used_load_kg == 0.0 and trip.used_volume_m3 == 0.0


def test_overbooking_blocked(client, db_session):
    trip = _trip(client, db_session)
    reserve(db_session, trip.id, 1500.0, 5.0)
    db_session.commit()
    with pytest.raises(CapacityError):
        reserve(db_session, trip.id, 600.0, 1.0)  # 1500+600 > 2000 kg


def test_release_never_goes_negative(client, db_session):
    trip = _trip(client, db_session)
    release(db_session, trip.id, 999.0, 9.0)
    db_session.commit()
    assert trip.used_load_kg == 0.0 and trip.used_volume_m3 == 0.0


def test_transition_machine(db_session):
    from app.logistics.models import CustomerOrder

    order = CustomerOrder(
        shipper_user_id=1, trip_id=1, contact_name="A", contact_phone="+233241234567",
        pickup_region="GA", pickup_town="Accra", pickup_details="x",
        delivery_region="AS", delivery_town="Kumasi", delivery_details="y",
        consignee_name="B", consignee_phone="+233209876543",
        cargo_name="TVs", cargo_category="electronics", packaging="carton",
        pieces=10, weight_kg=200.0, volume_m3=1.5, pickup_window="morning",
    )
    db_session.add(order)
    db_session.commit()
    transition(db_session, order, "price_confirmed", actor="susan", actor_type="staff")
    db_session.commit()
    assert order.status == "price_confirmed" and order.price_confirmed_at is not None
    with pytest.raises(ValueError):
        transition(db_session, order, "delivered", actor="x", actor_type="staff")
    assert set(ALLOWED["delivered"]) == {"completed", "exception_closed"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_capacity.py -v`
Expected: FAIL — `ImportError: cannot import name 'CapacityError'`

- [ ] **Step 3: Write the implementation**

Replace `backend/app/logistics/capacity.py` with the full version:

```python
"""Trip capacity ledger (PRD §8.4). reserve()/release() lock the trip row
(SELECT ... FOR UPDATE on MySQL; harmless no-op on SQLite) so concurrent CS
confirmations cannot overbook. Callers commit."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.logistics.models import Trip


class CapacityError(Exception):
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


def remaining_load(trip: Trip) -> float:
    return round(trip.total_load_kg - trip.used_load_kg - trip.manual_load_kg, 2)


def remaining_volume(trip: Trip) -> float:
    return round(trip.total_volume_m3 - trip.used_volume_m3 - trip.manual_volume_m3, 2)


def reserve(db: Session, trip_id: int, weight_kg: float, volume_m3: float) -> Trip:
    trip = db.execute(
        select(Trip).where(Trip.id == trip_id).with_for_update()
    ).scalar_one()
    short = []
    if remaining_load(trip) < weight_kg:
        short.append(f"load short by {round(weight_kg - remaining_load(trip), 2)} kg")
    if remaining_volume(trip) < volume_m3:
        short.append(f"volume short by {round(volume_m3 - remaining_volume(trip), 2)} m³")
    if short:
        raise CapacityError("Insufficient capacity: " + ", ".join(short))
    trip.used_load_kg = round(trip.used_load_kg + weight_kg, 2)
    trip.used_volume_m3 = round(trip.used_volume_m3 + volume_m3, 2)
    return trip


def release(db: Session, trip_id: int, weight_kg: float, volume_m3: float) -> Trip:
    trip = db.execute(
        select(Trip).where(Trip.id == trip_id).with_for_update()
    ).scalar_one()
    trip.used_load_kg = max(0.0, round(trip.used_load_kg - weight_kg, 2))
    trip.used_volume_m3 = max(0.0, round(trip.used_volume_m3 - volume_m3, 2))
    return trip
```

Create `backend/app/logistics/orders.py`:

```python
"""Order status machine (PRD §10.1). transition() is the ONLY way order.status
changes — it validates the edge, stamps the timestamp, and writes the operation log."""

from sqlalchemy.orm import Session

from app.logistics.models import (
    ORDER_AWAITING_PICKUP,
    ORDER_CANCELLED,
    ORDER_COMPLETED,
    ORDER_DELIVERED,
    ORDER_EXCEPTION,
    ORDER_IN_TRANSIT,
    ORDER_PRICE_CONFIRMED,
    ORDER_SUBMITTED,
    CustomerOrder,
    utcnow,
)
from app.logistics.ops import log_op

ALLOWED: dict[str, tuple[str, ...]] = {
    ORDER_SUBMITTED: (ORDER_PRICE_CONFIRMED, ORDER_CANCELLED, ORDER_EXCEPTION),
    ORDER_PRICE_CONFIRMED: (ORDER_AWAITING_PICKUP, ORDER_SUBMITTED,
                            ORDER_CANCELLED, ORDER_EXCEPTION),
    ORDER_AWAITING_PICKUP: (ORDER_IN_TRANSIT, ORDER_CANCELLED, ORDER_EXCEPTION),
    ORDER_IN_TRANSIT: (ORDER_DELIVERED, ORDER_EXCEPTION),
    ORDER_DELIVERED: (ORDER_COMPLETED, ORDER_EXCEPTION),
}

_STAMP = {
    ORDER_PRICE_CONFIRMED: "price_confirmed_at",
    ORDER_AWAITING_PICKUP: "accepted_at",
    ORDER_IN_TRANSIT: "departed_at",
    ORDER_DELIVERED: "delivered_at",
    ORDER_COMPLETED: "completed_at",
    ORDER_CANCELLED: "closed_at",
    ORDER_EXCEPTION: "closed_at",
}

# Capacity is held while the order is in one of these states.
RESERVED_STATUSES = (ORDER_PRICE_CONFIRMED, ORDER_AWAITING_PICKUP)


def transition(db: Session, order: CustomerOrder, new_status: str,
               actor: str, actor_type: str, detail: str = "") -> None:
    if new_status not in ALLOWED.get(order.status, ()):
        raise ValueError(f"Cannot go from {order.status} to {new_status}")
    order.status = new_status
    stamp = _STAMP.get(new_status)
    if stamp:
        setattr(order, stamp, utcnow())
    log_op(db, actor, actor_type, f"order_{new_status}", "order", order.id, detail)
```

Append to `backend/app/logistics/models.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_capacity.py -v` → 4 PASS
Run: `uv run pytest` → full suite PASS

- [ ] **Step 5: Commit**

```bash
git add app/logistics tests/test_lg_capacity.py
git commit -m "feat(lg): capacity reserve/release with locking, order status machine"
```

---

### Task 7: Shipper order endpoints (submit / mine / detail / cancel)

**Files:**
- Create: `backend/app/logistics/api/h5_orders.py`
- Modify: `backend/app/logistics/schemas.py`, `backend/app/main.py`
- Test: `backend/tests/test_lg_orders_shipper.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_lg_orders_shipper.py`:

```python
from datetime import date, timedelta

from tests.lg_helpers import (
    approved_driver,
    approved_route,
    approved_vehicle,
    h5_login,
    make_trip,
)

ORDER = {
    "contact_name": "Efua", "contact_phone": "0201112223",
    "pickup_region": "Greater Accra", "pickup_town": "Accra",
    "pickup_details": "12 Ring Road", "delivery_region": "Ashanti",
    "delivery_town": "Kumasi", "delivery_details": "Adum market",
    "consignee_name": "Yaw", "consignee_phone": "0261112223",
    "cargo_name": "TV sets", "cargo_category": "electronics",
    "packaging": "carton", "pieces": 10, "weight_kg": 200.0, "volume_m3": 1.5,
    "fragile": True, "needs_loading": True, "needs_pickup": False,
    "pickup_window": "tomorrow morning", "remarks": "", "photo_ids": [],
}


def _live_trip(client, db_session):
    headers, _ = approved_driver(client, db_session)
    vid = approved_vehicle(client, db_session, headers)
    rid = approved_route(client, db_session, headers, vid)
    return make_trip(db_session, rid, date.today() + timedelta(days=1))


def test_submit_order(client, db_session):
    tid = _live_trip(client, db_session)
    shipper = h5_login(client, db_session, "0209999999")
    resp = client.post("/api/lg/orders", json={**ORDER, "trip_id": tid}, headers=shipper)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "submitted"
    assert body["driver"] is None  # contact not disclosed before acceptance


def test_anonymous_cannot_order(client, db_session):
    tid = _live_trip(client, db_session)
    assert client.post("/api/lg/orders", json={**ORDER, "trip_id": tid}).status_code == 401


def test_oversize_order_blocked(client, db_session):
    tid = _live_trip(client, db_session)
    shipper = h5_login(client, db_session, "0209999999")
    resp = client.post("/api/lg/orders",
                       json={**ORDER, "trip_id": tid, "weight_kg": 5000.0},
                       headers=shipper)
    assert resp.status_code == 409


def test_order_on_past_or_cancelled_trip_blocked(client, db_session):
    from app.logistics.models import TRIP_CANCELLED, Trip

    tid = _live_trip(client, db_session)
    db_session.get(Trip, tid).status = TRIP_CANCELLED
    db_session.commit()
    shipper = h5_login(client, db_session, "0209999999")
    resp = client.post("/api/lg/orders", json={**ORDER, "trip_id": tid}, headers=shipper)
    assert resp.status_code == 409


def test_my_orders_and_detail_access(client, db_session):
    tid = _live_trip(client, db_session)
    shipper = h5_login(client, db_session, "0209999999")
    oid = client.post("/api/lg/orders", json={**ORDER, "trip_id": tid},
                      headers=shipper).json()["id"]
    assert client.get("/api/lg/orders/mine", headers=shipper).json()["total"] == 1
    assert client.get(f"/api/lg/orders/{oid}", headers=shipper).status_code == 200
    stranger = h5_login(client, db_session, "0208888888")
    assert client.get(f"/api/lg/orders/{oid}", headers=stranger).status_code == 404


def test_shipper_cancel_only_early(client, db_session):
    from app.logistics.models import CustomerOrder

    tid = _live_trip(client, db_session)
    shipper = h5_login(client, db_session, "0209999999")
    oid = client.post("/api/lg/orders", json={**ORDER, "trip_id": tid},
                      headers=shipper).json()["id"]
    resp = client.post(f"/api/lg/orders/{oid}/cancel",
                       json={"reason": "changed my mind"}, headers=shipper)
    assert resp.status_code == 200 and resp.json()["status"] == "cancelled"
    # a second order pushed to awaiting_pickup can no longer be cancelled by the shipper
    oid2 = client.post("/api/lg/orders", json={**ORDER, "trip_id": tid},
                       headers=shipper).json()["id"]
    db_session.get(CustomerOrder, oid2).status = "awaiting_pickup"
    db_session.commit()
    resp = client.post(f"/api/lg/orders/{oid2}/cancel",
                       json={"reason": "too late"}, headers=shipper)
    assert resp.status_code == 409
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_orders_shipper.py -v`
Expected: FAIL — 404 on `/api/lg/orders`

- [ ] **Step 3: Write the implementation**

Append to `backend/app/logistics/schemas.py`:

```python
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
```

Create `backend/app/logistics/api/h5_orders.py`:

```python
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import get_current_user
from app.logistics.capacity import remaining_load, remaining_volume
from app.logistics.models import (
    AVAILABILITY_ACCEPTING,
    DRIVER_APPROVED,
    ORDER_AWAITING_PICKUP,
    ORDER_CANCELLED,
    ORDER_COMPLETED,
    ORDER_DELIVERED,
    ORDER_IN_TRANSIT,
    ORDER_PRICE_CONFIRMED,
    ORDER_SUBMITTED,
    ROUTE_APPROVED,
    TRIP_SCHEDULED,
    CustomerOrder,
    Driver,
    Route,
    Trip,
    UserAccount,
    Vehicle,
)
from app.logistics.orders import RESERVED_STATUSES, transition
from app.logistics.capacity import release
from app.logistics.schemas import CancelIn, OrderIn

router = APIRouter()

CONTACT_VISIBLE = (ORDER_AWAITING_PICKUP, ORDER_IN_TRANSIT, ORDER_DELIVERED, ORDER_COMPLETED)


def order_out(db: Session, order: CustomerOrder, viewer: str) -> dict:
    """viewer: "shipper" | "driver" | "staff". Contact details cross the fence only
    from awaiting_pickup onward (PRD §10 contact disclosure)."""
    trip = db.get(Trip, order.trip_id)
    route = db.get(Route, trip.route_id)
    vehicle = db.get(Vehicle, trip.vehicle_id)
    driver = db.get(Driver, route.driver_id)
    disclosed = order.status in CONTACT_VISIBLE or viewer == "staff"
    data = {
        "id": order.id, "status": order.status, "trip_id": order.trip_id,
        "depart_date": trip.depart_date.isoformat(), "depart_time": trip.depart_time,
        "origin_town": route.origin_town, "dest_town": route.dest_town,
        "cargo_name": order.cargo_name, "cargo_category": order.cargo_category,
        "packaging": order.packaging, "pieces": order.pieces,
        "weight_kg": order.weight_kg, "volume_m3": order.volume_m3,
        "fragile": order.fragile, "needs_loading": order.needs_loading,
        "needs_pickup": order.needs_pickup, "pickup_window": order.pickup_window,
        "remarks": order.remarks, "photo_ids": order.photo_ids,
        "freight_ghs": order.freight_ghs, "commission_ghs": order.commission_ghs,
        "pickup_time": order.pickup_time, "cancel_reason": order.cancel_reason,
        "created_at": order.created_at.isoformat(),
        "pickup_town": order.pickup_town, "delivery_town": order.delivery_town,
        "driver": None, "shipper": None,
    }
    if viewer in ("shipper", "staff"):
        data["driver"] = {
            "full_name": driver.full_name,
            "plate_number": vehicle.plate_number,
            "phone": db.get(UserAccount, driver.user_id).phone,
        } if disclosed else None
    if viewer in ("driver", "staff"):
        data["shipper"] = {
            "contact_name": order.contact_name, "contact_phone": order.contact_phone,
            "pickup_details": order.pickup_details,
            "delivery_details": order.delivery_details,
            "consignee_name": order.consignee_name,
            "consignee_phone": order.consignee_phone,
        } if disclosed else None
    return data


@router.post("")
def submit_order(
    body: OrderIn,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    trip = db.get(Trip, body.trip_id)
    if trip is None or trip.status != TRIP_SCHEDULED or trip.depart_date < date.today():
        raise HTTPException(status_code=409, detail="Trip is not open for booking")
    route = db.get(Route, trip.route_id)
    driver = db.get(Driver, route.driver_id)
    if (route.status != ROUTE_APPROVED or driver.status != DRIVER_APPROVED
            or driver.availability != AVAILABILITY_ACCEPTING):
        raise HTTPException(status_code=409, detail="Trip is not open for booking")
    if remaining_load(trip) < body.weight_kg or remaining_volume(trip) < body.volume_m3:
        raise HTTPException(status_code=409, detail="Not enough remaining capacity")
    order = CustomerOrder(shipper_user_id=user.id, **body.model_dump())
    db.add(order)
    db.commit()
    return order_out(db, order, "shipper")


@router.get("/mine")
def my_orders(
    page: int = 1,
    page_size: int = 20,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(CustomerOrder).filter_by(shipper_user_id=user.id)
    total = q.count()
    rows = (q.order_by(CustomerOrder.id.desc())
             .offset((page - 1) * page_size).limit(page_size).all())
    return {"items": [order_out(db, o, "shipper") for o in rows],
            "total": total, "page": page, "page_size": page_size}


def _visible_order(db: Session, user: UserAccount, order_id: int) -> tuple[CustomerOrder, str]:
    order = db.get(CustomerOrder, order_id)
    if order is not None and order.shipper_user_id == user.id:
        return order, "shipper"
    if order is not None:
        driver = db.query(Driver).filter_by(user_id=user.id).one_or_none()
        if driver is not None:
            trip = db.get(Trip, order.trip_id)
            route = db.get(Route, trip.route_id)
            if route.driver_id == driver.id:
                return order, "driver"
    raise HTTPException(status_code=404, detail="Order not found")


@router.get("/{order_id}")
def order_detail(
    order_id: int,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order, viewer = _visible_order(db, user, order_id)
    return order_out(db, order, viewer)


@router.post("/{order_id}/cancel")
def cancel_order(
    order_id: int,
    body: CancelIn,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order, viewer = _visible_order(db, user, order_id)
    if viewer != "shipper":
        raise HTTPException(status_code=403, detail="Only the shipper can cancel here")
    if order.status not in (ORDER_SUBMITTED, ORDER_PRICE_CONFIRMED):
        raise HTTPException(status_code=409,
                            detail="Too late to cancel; contact customer service")
    if order.status in RESERVED_STATUSES:
        release(db, order.trip_id, order.weight_kg, order.volume_m3)
    order.cancel_reason = body.reason
    transition(db, order, ORDER_CANCELLED, actor=user.phone, actor_type="shipper",
               detail=body.reason)
    db.commit()
    return order_out(db, order, "shipper")
```

Modify `backend/app/main.py`:

```python
from app.logistics.api import (
    h5_auth, h5_driver, h5_notifications, h5_orders, h5_routes, h5_trips,
    h5_uploads, h5_vehicles,
)

app.include_router(h5_orders.router, prefix="/api/lg/orders", tags=["lg-h5"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_orders_shipper.py -v` → 6 PASS

- [ ] **Step 5: Commit**

```bash
git add app/logistics tests/test_lg_orders_shipper.py app/main.py
git commit -m "feat(lg): shipper order submit, list, detail, early cancel"
```

---

### Task 8: CS confirm-price (commission snapshot + reservation) and reassign

**Files:**
- Create: `backend/app/logistics/api/admin/orders.py`
- Modify: `backend/app/logistics/schemas.py`, `backend/app/main.py`
- Test: `backend/tests/test_lg_orders_cs.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_lg_orders_cs.py`:

```python
from datetime import date, timedelta

from app.logistics.models import CustomerOrder, Notification, Trip
from tests.lg_helpers import (
    admin_headers,
    approved_driver,
    approved_route,
    approved_vehicle,
    h5_login,
    make_trip,
)
from tests.test_lg_orders_shipper import ORDER


def _submitted_order(client, db_session):
    headers, _ = approved_driver(client, db_session)
    vid = approved_vehicle(client, db_session, headers)
    rid = approved_route(client, db_session, headers, vid)
    tid = make_trip(db_session, rid, date.today() + timedelta(days=1))
    shipper = h5_login(client, db_session, "0209999999")
    oid = client.post("/api/lg/orders", json={**ORDER, "trip_id": tid},
                      headers=shipper).json()["id"]
    return oid, tid, rid, shipper


def test_confirm_price_snapshots_commission_and_reserves(client, db_session):
    oid, tid, _, _ = _submitted_order(client, db_session)
    cs = admin_headers(client, db_session, role="cs", username="susan")
    resp = client.post(f"/api/admin/lg/orders/{oid}/confirm-price",
                       json={"freight_ghs": 500.0, "pickup_time": "Sat 08:00"},
                       headers=cs)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "price_confirmed"
    assert body["freight_ghs"] == 500.0
    assert body["commission_ghs"] == 40.0  # 8% default
    trip = db_session.get(Trip, tid)
    assert trip.used_load_kg == 200.0 and trip.used_volume_m3 == 1.5
    assert db_session.query(Notification).filter_by(kind="order").count() == 1  # driver SMS'd


def test_commission_override_needs_reason(client, db_session):
    oid, _, _, _ = _submitted_order(client, db_session)
    cs = admin_headers(client, db_session, role="cs", username="susan")
    resp = client.post(
        f"/api/admin/lg/orders/{oid}/confirm-price",
        json={"freight_ghs": 500.0, "pickup_time": "Sat", "commission_ghs": 10.0},
        headers=cs,
    )
    assert resp.status_code == 400
    resp = client.post(
        f"/api/admin/lg/orders/{oid}/confirm-price",
        json={"freight_ghs": 500.0, "pickup_time": "Sat",
              "commission_ghs": 10.0, "override_reason": "promo"},
        headers=cs,
    )
    assert resp.status_code == 200 and resp.json()["commission_ghs"] == 10.0


def test_reconfirm_replaces_reservation(client, db_session):
    oid, tid, _, _ = _submitted_order(client, db_session)
    cs = admin_headers(client, db_session, role="cs", username="susan")
    client.post(f"/api/admin/lg/orders/{oid}/confirm-price",
                json={"freight_ghs": 500.0, "pickup_time": "Sat"}, headers=cs)
    resp = client.post(f"/api/admin/lg/orders/{oid}/confirm-price",
                       json={"freight_ghs": 650.0, "pickup_time": "Sun"}, headers=cs)
    assert resp.status_code == 200 and resp.json()["freight_ghs"] == 650.0
    trip = db_session.get(Trip, tid)
    assert trip.used_load_kg == 200.0  # not double-reserved


def test_capacity_shortfall_blocks_confirmation(client, db_session):
    oid, tid, _, _ = _submitted_order(client, db_session)
    trip = db_session.get(Trip, tid)
    trip.used_load_kg = 1900.0  # only 100 kg left; order needs 200
    db_session.commit()
    cs = admin_headers(client, db_session, role="cs", username="susan")
    resp = client.post(f"/api/admin/lg/orders/{oid}/confirm-price",
                       json={"freight_ghs": 500.0, "pickup_time": "Sat"}, headers=cs)
    assert resp.status_code == 409
    assert "short" in resp.json()["detail"]


def test_auditor_cannot_work_orders(client, db_session):
    oid, _, _, _ = _submitted_order(client, db_session)
    aud = admin_headers(client, db_session, role="auditor", username="audrey")
    resp = client.post(f"/api/admin/lg/orders/{oid}/confirm-price",
                       json={"freight_ghs": 500.0, "pickup_time": "Sat"}, headers=aud)
    assert resp.status_code == 403


def test_reassign_in_submitted(client, db_session):
    oid, _, rid, _ = _submitted_order(client, db_session)
    tid2 = make_trip(db_session, rid, date.today() + timedelta(days=2))
    cs = admin_headers(client, db_session, role="cs", username="susan")
    resp = client.post(f"/api/admin/lg/orders/{oid}/reassign",
                       json={"trip_id": tid2}, headers=cs)
    assert resp.status_code == 200 and resp.json()["trip_id"] == tid2
    assert db_session.get(CustomerOrder, oid).trip_id == tid2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_orders_cs.py -v`
Expected: FAIL — 404 on `/api/admin/lg/orders/...`

- [ ] **Step 3: Write the implementation**

Append to `backend/app/logistics/schemas.py`:

```python
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
```

Create `backend/app/logistics/api/admin/orders.py`:

```python
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import require_roles
from app.logistics.capacity import CapacityError, release, reserve
from app.logistics.models import (
    ORDER_PRICE_CONFIRMED,
    ORDER_SUBMITTED,
    TRIP_SCHEDULED,
    CsRemark,
    CustomerOrder,
    Driver,
    Route,
    Trip,
    UserAccount,
)
from app.logistics.notify import notify
from app.logistics.orders import RESERVED_STATUSES, transition
from app.logistics.api.h5_orders import order_out
from app.logistics.schemas import ConfirmPriceIn, Paginated, ReassignIn, RemarkIn
from app.models import AdminUser
from app.services.config_service import get_config

router = APIRouter()

cs_staff = require_roles("admin", "cs")


def _get_order(db: Session, order_id: int) -> CustomerOrder:
    order = db.get(CustomerOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def _driver_user(db: Session, order: CustomerOrder) -> tuple[Driver, UserAccount]:
    trip = db.get(Trip, order.trip_id)
    route = db.get(Route, trip.route_id)
    driver = db.get(Driver, route.driver_id)
    return driver, db.get(UserAccount, driver.user_id)


@router.get("", response_model=Paginated)
def list_orders(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    _: AdminUser = Depends(cs_staff),
    db: Session = Depends(get_db),
):
    q = db.query(CustomerOrder)
    if status:
        q = q.filter(CustomerOrder.status == status)
    total = q.count()
    order_col = CustomerOrder.id if status == ORDER_SUBMITTED else CustomerOrder.id.desc()
    rows = q.order_by(order_col).offset((page - 1) * page_size).limit(page_size).all()
    return Paginated(items=[order_out(db, o, "staff") for o in rows],
                     total=total, page=page, page_size=page_size)


@router.get("/{order_id}")
def order_detail(
    order_id: int,
    _: AdminUser = Depends(cs_staff),
    db: Session = Depends(get_db),
):
    order = _get_order(db, order_id)
    data = order_out(db, order, "staff")
    data["remarks"] = [
        {"author": r.author, "body": r.body, "created_at": r.created_at.isoformat()}
        for r in db.query(CsRemark).filter_by(order_id=order.id).order_by(CsRemark.id)
    ]
    data["reject_count"] = order.reject_count
    return data


@router.post("/{order_id}/confirm-price")
def confirm_price(
    order_id: int,
    body: ConfirmPriceIn,
    staff: AdminUser = Depends(cs_staff),
    db: Session = Depends(get_db),
):
    order = _get_order(db, order_id)
    if order.status not in (ORDER_SUBMITTED, ORDER_PRICE_CONFIRMED):
        raise HTTPException(status_code=409, detail=f"Order is {order.status}")
    if body.commission_ghs is not None and not body.override_reason.strip():
        raise HTTPException(status_code=400, detail="Commission override requires a reason")

    if order.status == ORDER_PRICE_CONFIRMED:  # re-confirm: replace the reservation
        release(db, order.trip_id, order.weight_kg, order.volume_m3)
    try:
        reserve(db, order.trip_id, order.weight_kg, order.volume_m3)
    except CapacityError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=e.detail)

    rate = float(get_config(db, "lg_commission_rate", "0.08"))
    order.freight_ghs = round(body.freight_ghs, 2)
    order.commission_rate = rate
    order.commission_ghs = (round(body.commission_ghs, 2) if body.commission_ghs is not None
                            else round(body.freight_ghs * rate, 2))
    order.pickup_time = body.pickup_time
    if order.status == ORDER_SUBMITTED:
        transition(db, order, ORDER_PRICE_CONFIRMED, actor=staff.username,
                   actor_type="staff", detail=body.override_reason)
    db.commit()
    _, user = _driver_user(db, order)
    notify(db, user, "order", "New order needs acceptance",
           f"Order #{order.id}: {order.cargo_name}, {order.weight_kg} kg, "
           f"GHS {order.freight_ghs}. Open ZokoDaily to accept.", sms=True)
    return order_out(db, order, "staff")


@router.post("/{order_id}/reassign")
def reassign(
    order_id: int,
    body: ReassignIn,
    staff: AdminUser = Depends(cs_staff),
    db: Session = Depends(get_db),
):
    order = _get_order(db, order_id)
    if order.status != ORDER_SUBMITTED:
        raise HTTPException(status_code=409, detail="Only submitted orders can be reassigned")
    trip = db.get(Trip, body.trip_id)
    if (trip is None or trip.status != TRIP_SCHEDULED
            or trip.depart_date < date.today()):
        raise HTTPException(status_code=409, detail="Target trip is not open")
    order.trip_id = trip.id
    from app.logistics.ops import log_op

    log_op(db, staff.username, "staff", "order_reassign", "order", order.id,
           f"trip -> {trip.id}")
    db.commit()
    return order_out(db, order, "staff")


@router.post("/{order_id}/remarks")
def add_remark(
    order_id: int,
    body: RemarkIn,
    staff: AdminUser = Depends(cs_staff),
    db: Session = Depends(get_db),
):
    order = _get_order(db, order_id)
    db.add(CsRemark(order_id=order.id, author=staff.username, body=body.body))
    db.commit()
    return {"ok": True}
```

Modify `backend/app/main.py`:

```python
from app.logistics.api.admin import orders as lg_admin_orders

app.include_router(lg_admin_orders.router, prefix="/api/admin/lg/orders", tags=["lg-admin"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_orders_cs.py -v` → 6 PASS

- [ ] **Step 5: Commit**

```bash
git add app/logistics tests/test_lg_orders_cs.py app/main.py
git commit -m "feat(lg): CS price confirmation with commission snapshot and capacity reservation"
```

---

### Task 9: Driver order actions (accept / reject / depart / deliver)

**Files:**
- Modify: `backend/app/logistics/api/h5_orders.py`
- Test: `backend/tests/test_lg_orders_driver.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_lg_orders_driver.py`:

```python
from datetime import date, timedelta

from app.logistics.models import CustomerOrder, Notification, Trip
from tests.lg_helpers import (
    admin_headers,
    approved_driver,
    approved_route,
    approved_vehicle,
    h5_login,
    make_trip,
)
from tests.test_lg_orders_shipper import ORDER


def _confirmed_order(client, db_session):
    driver_h, _ = approved_driver(client, db_session)
    vid = approved_vehicle(client, db_session, driver_h)
    rid = approved_route(client, db_session, driver_h, vid)
    tid = make_trip(db_session, rid, date.today() + timedelta(days=1))
    shipper_h = h5_login(client, db_session, "0209999999")
    oid = client.post("/api/lg/orders", json={**ORDER, "trip_id": tid},
                      headers=shipper_h).json()["id"]
    cs = admin_headers(client, db_session, role="cs", username="susan")
    client.post(f"/api/admin/lg/orders/{oid}/confirm-price",
                json={"freight_ghs": 500.0, "pickup_time": "Sat 08:00"}, headers=cs)
    return driver_h, shipper_h, oid, tid


def test_assigned_list_and_accept_flow(client, db_session):
    driver_h, shipper_h, oid, _ = _confirmed_order(client, db_session)
    resp = client.get("/api/lg/orders/assigned", headers=driver_h)
    assert resp.json()["total"] == 1
    # shipper contact hidden before acceptance
    assert resp.json()["items"][0]["shipper"] is None
    resp = client.post(f"/api/lg/orders/{oid}/accept", headers=driver_h)
    assert resp.status_code == 200 and resp.json()["status"] == "awaiting_pickup"
    assert resp.json()["shipper"]["contact_phone"] == "+233201112223"  # now disclosed
    # shipper now sees the driver too
    detail = client.get(f"/api/lg/orders/{oid}", headers=shipper_h).json()
    assert detail["driver"]["plate_number"] == "GR 1111-24"
    # shipper got an SMS-level notification
    assert db_session.query(Notification).filter_by(kind="order_accepted").count() == 1


def test_reject_releases_capacity_and_returns_to_submitted(client, db_session):
    driver_h, _, oid, tid = _confirmed_order(client, db_session)
    resp = client.post(f"/api/lg/orders/{oid}/reject",
                       json={"reason": "truck issue"}, headers=driver_h)
    assert resp.status_code == 200 and resp.json()["status"] == "submitted"
    trip = db_session.get(Trip, tid)
    assert trip.used_load_kg == 0.0 and trip.used_volume_m3 == 0.0
    assert db_session.get(CustomerOrder, oid).reject_count == 1


def test_depart_and_deliver(client, db_session):
    driver_h, _, oid, _ = _confirmed_order(client, db_session)
    client.post(f"/api/lg/orders/{oid}/accept", headers=driver_h)
    resp = client.post(f"/api/lg/orders/{oid}/depart", headers=driver_h)
    assert resp.json()["status"] == "in_transit"
    resp = client.post(f"/api/lg/orders/{oid}/deliver", headers=driver_h)
    assert resp.json()["status"] == "delivered"
    # transitions in wrong order are rejected
    assert client.post(f"/api/lg/orders/{oid}/depart",
                       headers=driver_h).status_code == 409


def test_only_the_trips_driver_can_act(client, db_session):
    _, _, oid, _ = _confirmed_order(client, db_session)
    intruder_h, _ = approved_driver(client, db_session, "0242222222")
    assert client.post(f"/api/lg/orders/{oid}/accept",
                       headers=intruder_h).status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_orders_driver.py -v`
Expected: FAIL — 404 on `/api/lg/orders/assigned`

- [ ] **Step 3: Write the implementation**

Append to `backend/app/logistics/api/h5_orders.py` (extend the existing imports with
`ORDER_SUBMITTED` — already imported — plus `notify`, `reserve` is not needed here):

```python
from app.logistics.notify import notify


def _my_driver_order(db: Session, user: UserAccount, order_id: int) -> CustomerOrder:
    order = db.get(CustomerOrder, order_id)
    driver = db.query(Driver).filter_by(user_id=user.id).one_or_none()
    if order is None or driver is None:
        raise HTTPException(status_code=404, detail="Order not found")
    trip = db.get(Trip, order.trip_id)
    route = db.get(Route, trip.route_id)
    if route.driver_id != driver.id:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def _shipper_user(db: Session, order: CustomerOrder) -> UserAccount:
    return db.get(UserAccount, order.shipper_user_id)


@router.get("/assigned")
def assigned_orders(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    driver = db.query(Driver).filter_by(user_id=user.id).one_or_none()
    if driver is None:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    q = (db.query(CustomerOrder)
         .join(Trip, CustomerOrder.trip_id == Trip.id)
         .join(Route, Trip.route_id == Route.id)
         .filter(Route.driver_id == driver.id))
    if status:
        q = q.filter(CustomerOrder.status == status)
    total = q.count()
    rows = (q.order_by(CustomerOrder.id.desc())
             .offset((page - 1) * page_size).limit(page_size).all())
    return {"items": [order_out(db, o, "driver") for o in rows],
            "total": total, "page": page, "page_size": page_size}


@router.post("/{order_id}/accept")
def accept_order(
    order_id: int,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _my_driver_order(db, user, order_id)
    if order.status != ORDER_PRICE_CONFIRMED:
        raise HTTPException(status_code=409, detail=f"Order is {order.status}")
    transition(db, order, ORDER_AWAITING_PICKUP, actor=user.phone, actor_type="driver")
    db.commit()
    notify(db, _shipper_user(db, order), "order_accepted", "Driver accepted your order",
           f"Order #{order.id} will be picked up: {order.pickup_time}.", sms=True)
    return order_out(db, order, "driver")


@router.post("/{order_id}/reject")
def reject_order(
    order_id: int,
    body: CancelIn,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _my_driver_order(db, user, order_id)
    if order.status != ORDER_PRICE_CONFIRMED:
        raise HTTPException(status_code=409, detail=f"Order is {order.status}")
    release(db, order.trip_id, order.weight_kg, order.volume_m3)
    order.reject_count += 1
    transition(db, order, ORDER_SUBMITTED, actor=user.phone, actor_type="driver",
               detail=body.reason)
    db.commit()
    return order_out(db, order, "driver")


@router.post("/{order_id}/depart")
def depart(
    order_id: int,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _my_driver_order(db, user, order_id)
    if order.status != ORDER_AWAITING_PICKUP:
        raise HTTPException(status_code=409, detail=f"Order is {order.status}")
    transition(db, order, ORDER_IN_TRANSIT, actor=user.phone, actor_type="driver")
    db.commit()
    notify(db, _shipper_user(db, order), "order", "Your cargo is in transit",
           f"Order #{order.id} departed.")
    return order_out(db, order, "driver")


@router.post("/{order_id}/deliver")
def deliver(
    order_id: int,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _my_driver_order(db, user, order_id)
    if order.status != ORDER_IN_TRANSIT:
        raise HTTPException(status_code=409, detail=f"Order is {order.status}")
    transition(db, order, ORDER_DELIVERED, actor=user.phone, actor_type="driver")
    db.commit()
    notify(db, _shipper_user(db, order), "order", "Cargo delivered",
           f"Order #{order.id} was delivered. Customer service will confirm completion.")
    return order_out(db, order, "driver")
```

**Route-ordering note:** `/assigned` must be declared **before** the existing `/{order_id}`
GET route in the file, or FastAPI will try to parse "assigned" as an int. Move the
`assigned_orders` function above `order_detail` when appending.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_orders_driver.py tests/test_lg_orders_shipper.py -v` → all PASS

- [ ] **Step 5: Commit**

```bash
git add app/logistics tests/test_lg_orders_driver.py
git commit -m "feat(lg): driver accept/reject/depart/deliver with contact disclosure"
```

---

### Task 10: CS close-out — cancel, exception-close, complete (creates CommissionRecord)

**Files:**
- Modify: `backend/app/logistics/api/admin/orders.py`
- Test: `backend/tests/test_lg_orders_close.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_lg_orders_close.py`:

```python
from app.logistics.models import CommissionRecord, Notification, Trip
from tests.lg_helpers import admin_headers
from tests.test_lg_orders_driver import _confirmed_order


def test_cs_cancel_releases_capacity_and_notifies_both(client, db_session):
    _, _, oid, tid = _confirmed_order(client, db_session)
    cs = admin_headers(client, db_session, role="cs", username="susan")
    resp = client.post(f"/api/admin/lg/orders/{oid}/cancel",
                       json={"reason": "shipper unreachable"}, headers=cs)
    assert resp.status_code == 200 and resp.json()["status"] == "cancelled"
    trip = db_session.get(Trip, tid)
    assert trip.used_load_kg == 0.0
    assert db_session.query(Notification).filter_by(kind="order_closed").count() == 2


def test_complete_creates_pending_commission(client, db_session):
    driver_h, _, oid, _ = _confirmed_order(client, db_session)
    cs = admin_headers(client, db_session, role="cs", username="susan")
    client.post(f"/api/lg/orders/{oid}/accept", headers=driver_h)
    client.post(f"/api/lg/orders/{oid}/depart", headers=driver_h)
    client.post(f"/api/lg/orders/{oid}/deliver", headers=driver_h)
    resp = client.post(f"/api/admin/lg/orders/{oid}/complete", headers=cs)
    assert resp.status_code == 200 and resp.json()["status"] == "completed"
    rec = db_session.query(CommissionRecord).one()
    assert rec.amount_ghs == 40.0 and rec.status == "pending"
    # completing twice is blocked
    assert client.post(f"/api/admin/lg/orders/{oid}/complete",
                       headers=cs).status_code == 409


def test_complete_requires_delivered(client, db_session):
    _, _, oid, _ = _confirmed_order(client, db_session)
    cs = admin_headers(client, db_session, role="cs", username="susan")
    assert client.post(f"/api/admin/lg/orders/{oid}/complete",
                       headers=cs).status_code == 409


def test_exception_close_in_transit_keeps_capacity(client, db_session):
    driver_h, _, oid, tid = _confirmed_order(client, db_session)
    cs = admin_headers(client, db_session, role="cs", username="susan")
    client.post(f"/api/lg/orders/{oid}/accept", headers=driver_h)
    client.post(f"/api/lg/orders/{oid}/depart", headers=driver_h)
    resp = client.post(f"/api/admin/lg/orders/{oid}/exception-close",
                       json={"reason": "cargo damaged in transit"}, headers=cs)
    assert resp.status_code == 200 and resp.json()["status"] == "exception_closed"
    assert db_session.get(Trip, tid).used_load_kg == 200.0  # consumed, not released
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_orders_close.py -v`
Expected: FAIL — 404 on `/api/admin/lg/orders/{id}/cancel`

- [ ] **Step 3: Write the implementation**

Append to `backend/app/logistics/api/admin/orders.py` (extend the models import with
`ORDER_CANCELLED, ORDER_COMPLETED, ORDER_DELIVERED, ORDER_EXCEPTION, CommissionRecord`
and the schemas import with `CancelIn`):

```python
def _close(db: Session, order: CustomerOrder, new_status: str, staff: AdminUser,
           reason: str) -> None:
    if order.status in RESERVED_STATUSES:
        release(db, order.trip_id, order.weight_kg, order.volume_m3)
    order.cancel_reason = reason
    transition(db, order, new_status, actor=staff.username, actor_type="staff",
               detail=reason)
    db.commit()
    driver, driver_user = _driver_user(db, order)
    shipper_user = db.get(UserAccount, order.shipper_user_id)
    label = "cancelled" if new_status == ORDER_CANCELLED else "closed (exception)"
    for target in (driver_user, shipper_user):
        notify(db, target, "order_closed", f"Order #{order.id} {label}", reason, sms=True)


@router.post("/{order_id}/cancel")
def cs_cancel(
    order_id: int,
    body: CancelIn,
    staff: AdminUser = Depends(cs_staff),
    db: Session = Depends(get_db),
):
    order = _get_order(db, order_id)
    if ORDER_CANCELLED not in __import__("app.logistics.orders",
                                         fromlist=["ALLOWED"]).ALLOWED.get(order.status, ()):
        raise HTTPException(status_code=409, detail=f"Cannot cancel a {order.status} order")
    _close(db, order, ORDER_CANCELLED, staff, body.reason)
    return order_out(db, order, "staff")


@router.post("/{order_id}/exception-close")
def exception_close(
    order_id: int,
    body: CancelIn,
    staff: AdminUser = Depends(cs_staff),
    db: Session = Depends(get_db),
):
    order = _get_order(db, order_id)
    if order.status in (ORDER_COMPLETED, ORDER_CANCELLED, ORDER_EXCEPTION):
        raise HTTPException(status_code=409, detail="Order is already closed")
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="Resolution note required")
    _close(db, order, ORDER_EXCEPTION, staff, body.reason)
    return order_out(db, order, "staff")


@router.post("/{order_id}/complete")
def complete_order(
    order_id: int,
    staff: AdminUser = Depends(cs_staff),
    db: Session = Depends(get_db),
):
    order = _get_order(db, order_id)
    if order.status != ORDER_DELIVERED:
        raise HTTPException(status_code=409, detail=f"Order is {order.status}")
    driver, driver_user = _driver_user(db, order)
    transition(db, order, ORDER_COMPLETED, actor=staff.username, actor_type="staff")
    db.add(CommissionRecord(
        order_id=order.id, driver_id=driver.id,
        freight_ghs=order.freight_ghs, rate=order.commission_rate,
        amount_ghs=order.commission_ghs,
    ))
    db.commit()
    shipper_user = db.get(UserAccount, order.shipper_user_id)
    notify(db, shipper_user, "order", f"Order #{order.id} completed",
           "Thank you for using ZokoDaily Logistics.")
    notify(db, driver_user, "commission", "Commission payable",
           f"GHS {order.commission_ghs} is due for order #{order.id}. "
           "See My Commissions for payment details.", sms=True)
    return order_out(db, order, "staff")
```

Replace the awkward `__import__` line in `cs_cancel` with a top-of-file import instead
(cleaner — do it this way):

```python
from app.logistics.orders import ALLOWED, RESERVED_STATUSES, transition
```

and in `cs_cancel`:

```python
    if ORDER_CANCELLED not in ALLOWED.get(order.status, ()):
        raise HTTPException(status_code=409, detail=f"Cannot cancel a {order.status} order")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_orders_close.py -v` → 4 PASS
Run: `uv run pytest` → full suite PASS

- [ ] **Step 5: Commit**

```bash
git add app/logistics tests/test_lg_orders_close.py
git commit -m "feat(lg): CS cancel/exception-close/complete with commission record"
```

---

### Task 11: Commission ledger endpoints + logistics config API

**Files:**
- Create: `backend/app/logistics/api/h5_commissions.py`, `backend/app/logistics/api/admin/commissions.py`, `backend/app/logistics/api/admin/config.py`
- Modify: `backend/app/logistics/schemas.py`, `backend/app/main.py`, `backend/app/seed.py`
- Test: `backend/tests/test_lg_commissions.py`, `backend/tests/test_lg_config.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_lg_commissions.py`:

```python
from tests.lg_helpers import admin_headers
from tests.test_lg_orders_driver import _confirmed_order


def _completed_order(client, db_session):
    driver_h, shipper_h, oid, tid = _confirmed_order(client, db_session)
    cs = admin_headers(client, db_session, role="cs", username="susan")
    client.post(f"/api/lg/orders/{oid}/accept", headers=driver_h)
    client.post(f"/api/lg/orders/{oid}/depart", headers=driver_h)
    client.post(f"/api/lg/orders/{oid}/deliver", headers=driver_h)
    client.post(f"/api/admin/lg/orders/{oid}/complete", headers=cs)
    return driver_h, cs, oid


def test_driver_sees_own_ledger(client, db_session):
    driver_h, _, _ = _completed_order(client, db_session)
    resp = client.get("/api/lg/commissions/mine", headers=driver_h)
    assert resp.status_code == 200
    assert resp.json()["total_owed_ghs"] == 40.0
    assert resp.json()["items"][0]["status"] == "pending"


def test_settle_flow(client, db_session):
    _, cs, _ = _completed_order(client, db_session)
    resp = client.get("/api/admin/lg/commissions?status=pending", headers=cs)
    assert resp.json()["total"] == 1
    cid = resp.json()["items"][0]["id"]
    resp = client.post(f"/api/admin/lg/commissions/{cid}/settle",
                       json={"method": "momo", "reference": "MP123456"}, headers=cs)
    assert resp.status_code == 200 and resp.json()["status"] == "settled"
    # settling twice fails
    resp = client.post(f"/api/admin/lg/commissions/{cid}/settle",
                       json={"method": "momo", "reference": "MP123456"}, headers=cs)
    assert resp.status_code == 409


def test_waive_is_admin_only(client, db_session):
    _, cs, _ = _completed_order(client, db_session)
    cid = client.get("/api/admin/lg/commissions", headers=cs).json()["items"][0]["id"]
    resp = client.post(f"/api/admin/lg/commissions/{cid}/waive",
                       json={"reason": "goodwill"}, headers=cs)
    assert resp.status_code == 403
    boss = admin_headers(client, db_session, role="admin")
    resp = client.post(f"/api/admin/lg/commissions/{cid}/waive",
                       json={"reason": "goodwill"}, headers=boss)
    assert resp.status_code == 200 and resp.json()["status"] == "waived"
```

Create `backend/tests/test_lg_config.py`:

```python
from tests.lg_helpers import admin_headers


def test_get_config_masks_sms_key(client, db_session):
    boss = admin_headers(client, db_session, role="admin")
    client.put("/api/admin/lg/config",
               json={"lg_sms_api_key": "secret-key-12345"}, headers=boss)
    resp = client.get("/api/admin/lg/config", headers=boss)
    assert resp.status_code == 200
    assert resp.json()["lg_sms_api_key"] == "****2345"
    assert resp.json()["lg_commission_rate"] == "0.08"  # default


def test_put_validates_rate(client, db_session):
    boss = admin_headers(client, db_session, role="admin")
    resp = client.put("/api/admin/lg/config",
                      json={"lg_commission_rate": "1.5"}, headers=boss)
    assert resp.status_code == 400
    resp = client.put("/api/admin/lg/config",
                      json={"lg_commission_rate": "0.10"}, headers=boss)
    assert resp.status_code == 200


def test_unknown_keys_rejected(client, db_session):
    boss = admin_headers(client, db_session, role="admin")
    resp = client.put("/api/admin/lg/config", json={"ai_api_key": "x"}, headers=boss)
    assert resp.status_code == 400


def test_config_is_admin_only(client, db_session):
    cs = admin_headers(client, db_session, role="cs", username="susan")
    assert client.get("/api/admin/lg/config", headers=cs).status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_lg_commissions.py tests/test_lg_config.py -v`
Expected: FAIL — 404s on both routers

- [ ] **Step 3: Write the implementation**

Append to `backend/app/logistics/schemas.py`:

```python
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
```

Create `backend/app/logistics/api/h5_commissions.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import get_current_user
from app.logistics.models import COMMISSION_PENDING, CommissionRecord, Driver, UserAccount
from app.logistics.schemas import CommissionOut
from app.services.config_service import get_config

router = APIRouter()


@router.get("/mine")
def my_commissions(
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    driver = db.query(Driver).filter_by(user_id=user.id).one_or_none()
    if driver is None:
        return {"items": [], "total_owed_ghs": 0.0, "payment_instructions": ""}
    rows = (db.query(CommissionRecord).filter_by(driver_id=driver.id)
            .order_by(CommissionRecord.id.desc()).all())
    owed = (db.query(func.coalesce(func.sum(CommissionRecord.amount_ghs), 0.0))
            .filter_by(driver_id=driver.id, status=COMMISSION_PENDING).scalar())
    return {
        "items": [CommissionOut.model_validate(r).model_dump() for r in rows],
        "total_owed_ghs": round(float(owed), 2),
        "payment_instructions": get_config(db, "lg_payment_instructions", ""),
    }
```

Create `backend/app/logistics/api/admin/commissions.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import require_roles
from app.logistics.models import (
    COMMISSION_PENDING,
    COMMISSION_SETTLED,
    COMMISSION_WAIVED,
    CommissionRecord,
    utcnow,
)
from app.logistics.ops import log_op
from app.logistics.schemas import CommissionOut, FreezeIn, Paginated, SettleIn
from app.models import AdminUser

router = APIRouter()

cs_staff = require_roles("admin", "cs")


def _get(db: Session, commission_id: int) -> CommissionRecord:
    rec = db.get(CommissionRecord, commission_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Commission record not found")
    return rec


@router.get("", response_model=Paginated)
def list_commissions(
    status: str | None = None,
    driver_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    _: AdminUser = Depends(cs_staff),
    db: Session = Depends(get_db),
):
    q = db.query(CommissionRecord)
    if status:
        q = q.filter(CommissionRecord.status == status)
    if driver_id:
        q = q.filter(CommissionRecord.driver_id == driver_id)
    total = q.count()
    rows = (q.order_by(CommissionRecord.id.desc())
             .offset((page - 1) * page_size).limit(page_size).all())
    return Paginated(items=[CommissionOut.model_validate(r).model_dump() for r in rows],
                     total=total, page=page, page_size=page_size)


@router.post("/{commission_id}/settle", response_model=CommissionOut)
def settle(
    commission_id: int,
    body: SettleIn,
    staff: AdminUser = Depends(cs_staff),
    db: Session = Depends(get_db),
):
    rec = _get(db, commission_id)
    if rec.status != COMMISSION_PENDING:
        raise HTTPException(status_code=409, detail=f"Record is {rec.status}")
    rec.status = COMMISSION_SETTLED
    rec.method = body.method
    rec.reference = body.reference
    rec.settled_by = staff.username
    rec.settled_at = utcnow()
    log_op(db, staff.username, "staff", "commission_settle", "commission", rec.id,
           f"{body.method} {body.reference}")
    db.commit()
    return rec


@router.post("/{commission_id}/waive", response_model=CommissionOut)
def waive(
    commission_id: int,
    body: FreezeIn,
    staff: AdminUser = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    rec = _get(db, commission_id)
    if rec.status != COMMISSION_PENDING:
        raise HTTPException(status_code=409, detail=f"Record is {rec.status}")
    rec.status = COMMISSION_WAIVED
    rec.note = body.reason
    log_op(db, staff.username, "staff", "commission_waive", "commission", rec.id, body.reason)
    db.commit()
    return rec
```

Create `backend/app/logistics/api/admin/config.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import require_roles
from app.models import AdminUser
from app.services.config_service import get_config, mask_secret, set_config

router = APIRouter(dependencies=[Depends(require_roles("admin"))])

DEFAULTS = {
    "lg_commission_rate": "0.08",
    "lg_payment_instructions": "",
    "lg_sms_provider": "mock",
    "lg_sms_sender_id": "ZokoDaily",
    "lg_sms_api_key": "",
}
SECRET_KEYS = {"lg_sms_api_key"}


@router.get("")
def get_lg_config(db: Session = Depends(get_db)):
    out = {}
    for key, default in DEFAULTS.items():
        value = get_config(db, key, default)
        out[key] = mask_secret(value) if key in SECRET_KEYS else value
    return out


@router.put("")
def put_lg_config(body: dict[str, str], db: Session = Depends(get_db)):
    unknown = set(body) - set(DEFAULTS)
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown keys: {sorted(unknown)}")
    if "lg_commission_rate" in body:
        try:
            rate = float(body["lg_commission_rate"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Commission rate must be a number")
        if not 0 <= rate <= 0.5:
            raise HTTPException(status_code=400, detail="Commission rate must be 0–0.5")
    if "lg_sms_provider" in body and body["lg_sms_provider"] not in ("mock", "arkesel"):
        raise HTTPException(status_code=400, detail="Provider must be mock or arkesel")
    for key, value in body.items():
        set_config(db, key, value)
    db.commit()
    return {"ok": True}
```

Modify `backend/app/main.py`:

```python
from app.logistics.api import (
    h5_auth, h5_commissions, h5_driver, h5_notifications, h5_orders, h5_routes,
    h5_trips, h5_uploads, h5_vehicles,
)
from app.logistics.api.admin import commissions as lg_admin_commissions
from app.logistics.api.admin import config as lg_admin_config

app.include_router(h5_commissions.router, prefix="/api/lg/commissions", tags=["lg-h5"])
app.include_router(lg_admin_commissions.router,
                   prefix="/api/admin/lg/commissions", tags=["lg-admin"])
app.include_router(lg_admin_config.router, prefix="/api/admin/lg/config", tags=["lg-admin"])
```

Modify `backend/app/seed.py` — extend `CONFIG_DEFAULTS`:

```python
    "lg_commission_rate": "0.08",
    "lg_payment_instructions": "",
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_commissions.py tests/test_lg_config.py -v` → 7 PASS

- [ ] **Step 5: Commit**

```bash
git add app/logistics tests/test_lg_commissions.py tests/test_lg_config.py app/main.py app/seed.py
git commit -m "feat(lg): commission ledger (settle/waive/driver view) and lg config API"
```

---

### Task 12: Statistics overview endpoint

**Files:**
- Create: `backend/app/logistics/api/admin/stats.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_lg_stats.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_lg_stats.py`:

```python
from tests.lg_helpers import admin_headers
from tests.test_lg_commissions import _completed_order


def test_overview_counts_and_money(client, db_session):
    _completed_order(client, db_session)
    staff = admin_headers(client, db_session, role="admin")
    resp = client.get("/api/admin/lg/stats/overview", headers=staff)
    assert resp.status_code == 200
    data = resp.json()
    assert data["drivers"]["approved"] == 1
    assert data["vehicles"] == 1
    assert data["routes_active"] == 1
    assert data["orders"]["completed"] == 1
    assert data["gmv_ghs"] == 500.0
    assert data["commission"]["pending_ghs"] == 40.0
    assert data["top_lanes"][0] == {"lane": "Accra → Kumasi", "orders": 1}
    assert data["completion_rate"] == 1.0


def test_all_staff_roles_can_read_stats(client, db_session):
    for role, name in (("auditor", "audrey"), ("cs", "susan")):
        staff = admin_headers(client, db_session, role=role, username=name)
        assert client.get("/api/admin/lg/stats/overview", headers=staff).status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_stats.py -v`
Expected: FAIL — 404 on `/api/admin/lg/stats/overview`

- [ ] **Step 3: Write the implementation**

Create `backend/app/logistics/api/admin/stats.py`:

```python
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import require_roles
from app.logistics.models import (
    COMMISSION_PENDING,
    COMMISSION_SETTLED,
    ORDER_CANCELLED,
    ORDER_COMPLETED,
    ROUTE_APPROVED,
    CommissionRecord,
    CustomerOrder,
    Driver,
    Route,
    Trip,
    Vehicle,
)
from app.models import AdminUser

router = APIRouter()

any_staff = require_roles("admin", "auditor", "cs")


def _range_filter(q, column, start: date | None, end: date | None):
    if start:
        q = q.filter(column >= start)
    if end:
        q = q.filter(column <= end)
    return q


@router.get("/overview")
def overview(
    start: date | None = None,
    end: date | None = None,
    _: AdminUser = Depends(any_staff),
    db: Session = Depends(get_db),
):
    drivers = dict(db.query(Driver.status, func.count()).group_by(Driver.status).all())
    orders_q = _range_filter(db.query(CustomerOrder), CustomerOrder.created_at, start, end)
    orders = dict(
        _range_filter(db.query(CustomerOrder.status, func.count()),
                      CustomerOrder.created_at, start, end)
        .group_by(CustomerOrder.status).all()
    )
    total_orders = sum(orders.values())
    completed = orders.get(ORDER_COMPLETED, 0)
    cancelled = orders.get(ORDER_CANCELLED, 0)

    gmv = (_range_filter(
        db.query(func.coalesce(func.sum(CustomerOrder.freight_ghs), 0.0))
        .filter(CustomerOrder.status == ORDER_COMPLETED),
        CustomerOrder.created_at, start, end).scalar())
    pending = (db.query(func.coalesce(func.sum(CommissionRecord.amount_ghs), 0.0))
               .filter(CommissionRecord.status == COMMISSION_PENDING).scalar())
    settled = (db.query(func.coalesce(func.sum(CommissionRecord.amount_ghs), 0.0))
               .filter(CommissionRecord.status == COMMISSION_SETTLED).scalar())

    lanes = (
        _range_filter(
            db.query(Route.origin_town, Route.dest_town, func.count(CustomerOrder.id))
            .join(Trip, Trip.route_id == Route.id)
            .join(CustomerOrder, CustomerOrder.trip_id == Trip.id),
            CustomerOrder.created_at, start, end)
        .group_by(Route.origin_town, Route.dest_town)
        .order_by(func.count(CustomerOrder.id).desc()).limit(5).all()
    )

    past_trips = (db.query(Trip)
                  .filter(Trip.depart_date < date.today(), Trip.total_load_kg > 0).all())
    utilization = (
        round(sum((t.used_load_kg + t.manual_load_kg) / t.total_load_kg
                  for t in past_trips) / len(past_trips), 3)
        if past_trips else 0.0
    )

    return {
        "drivers": drivers,
        "vehicles": db.query(Vehicle).count(),
        "routes_active": db.query(Route).filter(Route.status == ROUTE_APPROVED).count(),
        "trips_upcoming": db.query(Trip).filter(Trip.depart_date >= date.today()).count(),
        "orders": orders,
        "orders_total": total_orders,
        "gmv_ghs": round(float(gmv), 2),
        "commission": {"pending_ghs": round(float(pending), 2),
                       "settled_ghs": round(float(settled), 2)},
        "top_lanes": [{"lane": f"{o} → {d}", "orders": n} for o, d, n in lanes],
        "completion_rate": round(completed / total_orders, 3) if total_orders else 0.0,
        "cancellation_rate": round(cancelled / total_orders, 3) if total_orders else 0.0,
        "capacity_utilization": utilization,
    }
```

Modify `backend/app/main.py`:

```python
from app.logistics.api.admin import stats as lg_admin_stats

app.include_router(lg_admin_stats.router, prefix="/api/admin/lg/stats", tags=["lg-admin"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lg_stats.py -v` → 2 PASS

- [ ] **Step 5: Commit**

```bash
git add app/logistics tests/test_lg_stats.py app/main.py
git commit -m "feat(lg): operational statistics overview"
```

---

### Task 13: Expiry sweep + daily scheduler job + final verification

**Files:**
- Create: `backend/app/logistics/sweep.py`
- Modify: `backend/app/scheduler.py`
- Test: `backend/tests/test_lg_sweep.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_lg_sweep.py`:

```python
from datetime import date, timedelta

from app.logistics.models import Notification, Route, Vehicle
from app.logistics.sweep import expiry_sweep
from tests.lg_helpers import approved_driver, approved_route, approved_vehicle

TODAY = date(2026, 7, 13)


def _setup(client, db_session, insurance_expiry):
    headers, _ = approved_driver(client, db_session)
    vid = approved_vehicle(client, db_session, headers)
    vehicle = db_session.get(Vehicle, vid)
    vehicle.insurance_expiry = insurance_expiry
    db_session.commit()
    rid = approved_route(client, db_session, headers, vid)
    return vid, rid


def test_reminder_at_30_and_7_days(client, db_session):
    _setup(client, db_session, TODAY + timedelta(days=30))
    expiry_sweep(db_session, today=TODAY)
    notes = db_session.query(Notification).filter_by(kind="expiry").all()
    assert len(notes) == 1
    assert "insurance" in notes[0].title.lower()


def test_no_reminder_at_other_offsets(client, db_session):
    _setup(client, db_session, TODAY + timedelta(days=15))
    expiry_sweep(db_session, today=TODAY)
    assert db_session.query(Notification).filter_by(kind="expiry").count() == 0


def test_expired_docs_suspend_routes(client, db_session):
    _, rid = _setup(client, db_session, TODAY - timedelta(days=1))
    expiry_sweep(db_session, today=TODAY)
    assert db_session.get(Route, rid).status == "suspended"
    assert "expired" in db_session.get(Route, rid).review_remark
    # sweep is idempotent — running again adds no duplicate notifications
    before = db_session.query(Notification).count()
    expiry_sweep(db_session, today=TODAY)
    assert db_session.query(Notification).count() == before
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lg_sweep.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.logistics.sweep'`

- [ ] **Step 3: Write the implementation**

Create `backend/app/logistics/sweep.py`:

```python
"""Daily document-expiry sweep (PRD §7.3, §14, §16):
- reminders to drivers at exactly 30 and 7 days before licence/roadworthy/insurance expiry
- auto-suspend approved routes whose vehicle has an expired document."""

from datetime import date

from sqlalchemy.orm import Session

from app.logistics.models import (
    DRIVER_APPROVED,
    ROUTE_APPROVED,
    ROUTE_SUSPENDED,
    VEHICLE_APPROVED,
    Driver,
    Route,
    UserAccount,
    Vehicle,
)
from app.logistics.notify import notify

REMIND_AT = (30, 7)


def _remind(db: Session, user: UserAccount, doc: str, expiry: date, today: date) -> None:
    days = (expiry - today).days
    if days in REMIND_AT:
        notify(db, user, "expiry", f"Your {doc} expires soon",
               f"Expiry date: {expiry.isoformat()} ({days} days left). "
               "Renew and update your documents to keep your routes live.", sms=True)


def expiry_sweep(db: Session, today: date | None = None) -> None:
    today = today or date.today()

    for driver in db.query(Driver).filter(Driver.status == DRIVER_APPROVED).all():
        user = db.get(UserAccount, driver.user_id)
        _remind(db, user, "driver's licence", driver.licence_expiry, today)

    for vehicle in db.query(Vehicle).filter(Vehicle.status == VEHICLE_APPROVED).all():
        driver = db.get(Driver, vehicle.driver_id)
        user = db.get(UserAccount, driver.user_id)
        _remind(db, user, "roadworthiness certificate", vehicle.roadworthy_expiry, today)
        _remind(db, user, "vehicle insurance", vehicle.insurance_expiry, today)

        if vehicle.roadworthy_expiry < today or vehicle.insurance_expiry < today:
            routes = (db.query(Route)
                      .filter(Route.default_vehicle_id == vehicle.id,
                              Route.status == ROUTE_APPROVED).all())
            for route in routes:
                route.status = ROUTE_SUSPENDED
                route.review_remark = "Auto-suspended: vehicle documents expired"
                db.commit()
                notify(db, user, "expiry",
                       f"Route {route.origin_town} → {route.dest_town} suspended",
                       "Vehicle documents have expired. Renew them and ask support "
                       "to resume the route.", sms=True)
```

Modify `backend/app/scheduler.py` — add the daily logistics job (same lazy-import style
as the existing jobs) and register it in `build_scheduler`:

```python
def lg_daily_job() -> None:
    from app.db import SessionLocal
    from app.logistics.sweep import expiry_sweep
    from app.logistics.trips_service import generate_trips

    with SessionLocal() as db:
        created = generate_trips(db)
        expiry_sweep(db)
        if created:
            logger.info("lg daily: generated %d trip(s)", created)
```

and inside `build_scheduler()`, after the existing `add_job` lines:

```python
    sched.add_job(lg_daily_job, "cron", hour=1, minute=0, id="lg-daily", **common)
```

- [ ] **Step 4: Run tests, then the full suite**

Run: `uv run pytest tests/test_lg_sweep.py -v` → 3 PASS
Run: `uv run pytest` → **full suite PASS** (expect ~175 tests)

- [ ] **Step 5: Verify seed + live boot**

```bash
rm -f verify.db
DATABASE_URL="sqlite:///./verify.db" uv run python -m app.seed
DATABASE_URL="sqlite:///./verify.db" SCHEDULER_ENABLED=false timeout 10 uv run uvicorn app.main:app --port 8010 &
sleep 4 && curl -s http://127.0.0.1:8010/api/lg/trips | head -c 200
rm -f verify.db
```

Expected: seed completes; `{"items":[],"total":0,...}` from the browse endpoint.

- [ ] **Step 6: Commit**

```bash
git add app/logistics app/scheduler.py tests/test_lg_sweep.py
git commit -m "feat(lg): expiry sweep and daily trip-generation scheduler job"
```

---

## What this plan deliberately defers

| Deferred item | Where it lands |
| --- | --- |
| All H5 pages (browse UI, order form, driver center, commission view) | LTL Plan 3 |
| All admin pages (queues, order workspace, ledger, dashboard) + deployment updates | LTL Plan 4 |
| Anomaly flags (repeat rejections, overdue-commission auto-freeze) beyond `reject_count` tracking | LTL Plan 4 (admin dashboard surfacing) or V2 |
| Tiered pricing, per-driver commission rates, online payment | V2 roadmap |

## Deployment checklist (PR description)

1. New `lg_*` tables auto-created by `create_all` at startup; no ALTERs needed for this plan.
2. Scheduler gains the `lg-daily` cron job (01:00) — still exactly ONE backend replica.
3. Set `lg_payment_instructions` (MoMo number / bank details shown to drivers) via
   `PUT /api/admin/lg/config` before go-live; adjust `lg_commission_rate` if 8% isn't final.
