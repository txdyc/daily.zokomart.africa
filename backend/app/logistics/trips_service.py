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
