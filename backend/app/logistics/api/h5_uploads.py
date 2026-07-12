import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import get_current_user, get_principal
from app.logistics.models import Attachment, UserAccount
from app.logistics.storage import file_path, save_upload

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("")
def upload(
    file: UploadFile,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    att = save_upload(db, file, owner_user_id=user.id)
    return {"id": att.id, "url": f"/api/lg/uploads/{att.id}"}


@router.get("/{att_id}")
def download(
    att_id: str,
    principal: tuple = Depends(get_principal),
    db: Session = Depends(get_db),
):
    att = db.get(Attachment, att_id)
    if att is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    kind, who = principal
    if kind == "user" and who.id != att.owner_user_id:
        logger.warning("Unauthorized attachment access: att_id=%s user_id=%s owner=%s",
                       att_id, who.id, att.owner_user_id)
        raise HTTPException(status_code=403, detail="Not your attachment")
    # Log all attachment access for audit (especially admin access to user documents)
    accessor = who.id if kind == "user" else f"admin:{who}"
    logger.info("Attachment download: att_id=%s accessor=%s owner=%s",
                att_id, accessor, att.owner_user_id)
    return FileResponse(file_path(att), media_type=att.content_type)
