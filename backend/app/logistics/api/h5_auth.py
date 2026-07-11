from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics import otp
from app.logistics.auth import create_user_token, get_current_user
from app.logistics.models import UserAccount
from app.logistics.schemas import OtpLoginIn, PhoneIn, UserTokenOut

router = APIRouter()


@router.post("/request-otp")
def request_otp(body: PhoneIn, db: Session = Depends(get_db)):
    try:
        otp.request_code(db, body.phone)
    except otp.OtpError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    return {"ok": True}


@router.post("/login", response_model=UserTokenOut)
def login(body: OtpLoginIn, db: Session = Depends(get_db)):
    if not otp.verify_code(db, body.phone, body.code):
        raise HTTPException(status_code=401, detail="Invalid or expired code")
    user = db.query(UserAccount).filter_by(phone=body.phone).one_or_none()
    if user is None:
        user = UserAccount(phone=body.phone)
        db.add(user)
        db.commit()
    return UserTokenOut(access_token=create_user_token(user.id), user_id=user.id, phone=user.phone)


@router.get("/me")
def me(user: UserAccount = Depends(get_current_user)):
    return {"id": user.id, "phone": user.phone}
