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
