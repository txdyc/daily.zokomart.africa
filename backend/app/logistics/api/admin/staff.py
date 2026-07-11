from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import require_roles
from app.logistics.schemas import StaffIn, StaffOut
from app.models import AdminUser
from app.security import hash_password

router = APIRouter(dependencies=[Depends(require_roles("admin"))])


@router.get("", response_model=list[StaffOut])
def list_staff(db: Session = Depends(get_db)):
    return db.query(AdminUser).order_by(AdminUser.id).all()


@router.post("", response_model=StaffOut)
def create_staff(body: StaffIn, db: Session = Depends(get_db)):
    if db.query(AdminUser).filter_by(username=body.username).one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Username already exists")
    user = AdminUser(username=body.username,
                     password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.commit()
    return user
