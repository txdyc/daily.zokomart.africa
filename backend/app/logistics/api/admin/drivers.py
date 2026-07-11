from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import require_roles
from app.logistics.models import (
    DRIVER_APPROVED,
    DRIVER_FROZEN,
    DRIVER_PENDING,
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
    driver.status = DRIVER_APPROVED if body.action == "approve" else "rejected"
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
