from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import get_current_user
from app.logistics.models import Notification, UserAccount, utcnow

router = APIRouter()


@router.get("")
def list_notifications(
    page: int = 1,
    page_size: int = 20,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Notification).filter_by(user_id=user.id)
    total = q.count()
    unread = q.filter(Notification.read_at.is_(None)).count()
    rows = (
        q.order_by(Notification.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [
            {
                "id": n.id, "kind": n.kind, "title": n.title, "body": n.body,
                "read": n.read_at is not None,
                "created_at": n.created_at.isoformat(),
            }
            for n in rows
        ],
        "total": total,
        "unread": unread,
        "page": page,
        "page_size": page_size,
    }


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: int,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    if n.read_at is None:
        n.read_at = utcnow()
        db.commit()
    return {"ok": True}
