from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AdminUser
from app.schemas import LoginIn, TokenOut
from app.security import create_access_token, get_current_admin, verify_password

router = APIRouter()


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(AdminUser).filter_by(username=body.username).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return TokenOut(access_token=create_access_token(user.username))


@router.get("/me")
def me(username: str = Depends(get_current_admin), db: Session = Depends(get_db)):
    user = db.query(AdminUser).filter_by(username=username).one_or_none()
    return {"username": username, "role": user.role if user else "admin"}
