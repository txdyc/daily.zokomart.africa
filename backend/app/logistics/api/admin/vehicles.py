from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import require_roles
from app.logistics.models import (
    VEHICLE_APPROVED,
    VEHICLE_PENDING,
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
    vehicle.status = VEHICLE_APPROVED if body.action == "approve" else "rejected"
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
