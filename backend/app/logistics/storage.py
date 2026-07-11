import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.logistics.models import Attachment

ALLOWED = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_BYTES = 8 * 1024 * 1024


def _dir() -> Path:
    p = Path(settings.upload_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def file_path(att: Attachment) -> Path:
    return _dir() / f"{att.id}.{ALLOWED[att.content_type]}"


def save_upload(db: Session, file: UploadFile, owner_user_id: int) -> Attachment:
    if file.content_type not in ALLOWED:
        raise HTTPException(status_code=415, detail="Only JPEG/PNG/WebP images are accepted")
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 8 MB limit")
    att = Attachment(
        id=str(uuid.uuid4()),
        owner_user_id=owner_user_id,
        filename=file.filename or "upload",
        content_type=file.content_type,
        size=len(data),
    )
    file_path(att).write_bytes(data)
    db.add(att)
    db.commit()
    return att
