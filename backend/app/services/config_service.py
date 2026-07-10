from sqlalchemy.orm import Session

from app.models import AppConfig


def get_config(db: Session, key: str, default: str = "") -> str:
    row = db.get(AppConfig, key)
    return row.value if row is not None else default


def set_config(db: Session, key: str, value: str) -> None:
    row = db.get(AppConfig, key)
    if row is None:
        db.add(AppConfig(key=key, value=value))
    else:
        row.value = value


def mask_secret(value: str) -> str:
    if not value:
        return ""
    return "****" + value[-4:]
