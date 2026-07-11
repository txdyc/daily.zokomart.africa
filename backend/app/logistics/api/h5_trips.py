from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
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
