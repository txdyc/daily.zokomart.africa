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
