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
