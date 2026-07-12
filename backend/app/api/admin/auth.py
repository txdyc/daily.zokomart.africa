import logging
import time
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AdminUser
from app.schemas import LoginIn, TokenOut
from app.security import create_access_token, get_current_admin, verify_password

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Simple in-memory login rate limiter (per IP, sliding window) ──
# For multi-process deployments, replace with Redis-backed limiter.
_LOGIN_ATTEMPTS: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW_SECONDS = 60
_RATE_MAX_ATTEMPTS = 10


def _check_rate_limit(client_ip: str) -> None:
    now = time.monotonic()
    attempts = _LOGIN_ATTEMPTS[client_ip]
    # Prune entries outside the window
    cutoff = now - _RATE_WINDOW_SECONDS
    _LOGIN_ATTEMPTS[client_ip] = [t for t in attempts if t > cutoff]
    if len(_LOGIN_ATTEMPTS[client_ip]) >= _RATE_MAX_ATTEMPTS:
        logger.warning("Login rate limit exceeded for IP %s", client_ip)
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")
    _LOGIN_ATTEMPTS[client_ip].append(now)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)
    user = db.query(AdminUser).filter_by(username=body.username).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    logger.info("Admin login: user=%s ip=%s time=%s", user.username, client_ip,
                datetime.now(timezone.utc).isoformat())
    return TokenOut(access_token=create_access_token(user.username))


@router.get("/me")
def me(username: str = Depends(get_current_admin), db: Session = Depends(get_db)):
    user = db.query(AdminUser).filter_by(username=username).one_or_none()
    return {"username": username, "role": user.role if user else "admin"}
