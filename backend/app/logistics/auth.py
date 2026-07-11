from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.logistics.models import UserAccount
from app.models import AdminUser
from app.security import ALGORITHM, get_current_admin

_bearer = HTTPBearer(auto_error=False)


def create_user_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "scope": "h5",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def _decode(credentials: HTTPAuthorizationCredentials | None) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> UserAccount:
    """FastAPI dependency: the authenticated H5 user account, or 401."""
    payload = _decode(credentials)
    if payload.get("scope") != "h5":
        raise HTTPException(status_code=401, detail="Not an H5 user token")
    user = db.get(UserAccount, int(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="Account not found")
    return user


def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> tuple[str, object]:
    """Accepts either token type. Returns ("user", UserAccount) or ("admin", username)."""
    payload = _decode(credentials)
    if payload.get("scope") == "h5":
        user = db.get(UserAccount, int(payload["sub"]))
        if user is None:
            raise HTTPException(status_code=401, detail="Account not found")
        return ("user", user)
    return ("admin", payload["sub"])


def require_roles(*roles: str):
    """Dependency factory: staff member whose role is in `roles`, else 403."""

    def dep(
        username: str = Depends(get_current_admin),
        db: Session = Depends(get_db),
    ) -> AdminUser:
        user = db.query(AdminUser).filter_by(username=username).one_or_none()
        if user is None or user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user

    return dep
