from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import require_roles
from app.models import AdminUser
from app.services.config_service import get_config, mask_secret, set_config

router = APIRouter(dependencies=[Depends(require_roles("admin"))])

DEFAULTS = {
    "lg_commission_rate": "0.08",
    "lg_payment_instructions": "",
    "lg_sms_provider": "mock",
    "lg_sms_sender_id": "ZokoDaily",
    "lg_sms_api_key": "",
}
SECRET_KEYS = {"lg_sms_api_key"}


@router.get("")
def get_lg_config(db: Session = Depends(get_db)):
    out = {}
    for key, default in DEFAULTS.items():
        value = get_config(db, key, default)
        out[key] = mask_secret(value) if key in SECRET_KEYS else value
    return out


@router.put("")
def put_lg_config(body: dict[str, str], db: Session = Depends(get_db)):
    unknown = set(body) - set(DEFAULTS)
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown keys: {sorted(unknown)}")
    if "lg_commission_rate" in body:
        try:
            rate = float(body["lg_commission_rate"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Commission rate must be a number")
        if not 0 <= rate <= 0.5:
            raise HTTPException(status_code=400, detail="Commission rate must be 0-0.5")
    if "lg_sms_provider" in body and body["lg_sms_provider"] not in ("mock", "arkesel"):
        raise HTTPException(status_code=400, detail="Provider must be mock or arkesel")
    for key, value in body.items():
        set_config(db, key, value)
    db.commit()
    return {"ok": True}
