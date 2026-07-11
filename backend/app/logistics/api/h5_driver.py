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
