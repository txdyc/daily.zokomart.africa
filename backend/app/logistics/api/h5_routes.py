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
