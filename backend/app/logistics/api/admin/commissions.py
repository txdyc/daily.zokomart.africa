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
    """Get a commission record with a row-level lock to prevent concurrent settlement."""
    rec = (
        db.query(CommissionRecord)
        .filter_by(id=commission_id)
        .with_for_update()
        .one_or_none()
    )
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
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
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
