from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import require_roles
from app.logistics.models import Blacklist
from app.logistics.schemas import BlacklistIn, BlacklistOut
from app.models import AdminUser

router = APIRouter()


@router.get("", response_model=list[BlacklistOut])
def list_entries(staff: AdminUser = Depends(require_roles("admin")),
                 db: Session = Depends(get_db)):
    return db.query(Blacklist).order_by(Blacklist.id.desc()).all()


@router.post("", response_model=BlacklistOut)
def add_entry(body: BlacklistIn,
              staff: AdminUser = Depends(require_roles("admin")),
              db: Session = Depends(get_db)):
    entry = Blacklist(**body.model_dump(), created_by=staff.username)
    db.add(entry)
    db.commit()
    return entry


@router.delete("/{entry_id}")
def remove_entry(entry_id: int,
                 staff: AdminUser = Depends(require_roles("admin")),
                 db: Session = Depends(get_db)):
    entry = db.get(Blacklist, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()
    return {"ok": True}
