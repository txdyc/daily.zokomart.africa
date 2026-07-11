from sqlalchemy.orm import Session

from app.logistics.models import Notification, UserAccount
from app.logistics.sms import send_sms


def notify(
    db: Session,
    user: UserAccount,
    kind: str,
    title: str,
    body: str = "",
    sms: bool = False,
) -> None:
    """In-app notification, optionally mirrored by SMS (critical events, PRD XIV)."""
    db.add(Notification(user_id=user.id, kind=kind, title=title, body=body))
    db.commit()
    if sms:
        send_sms(db, user.phone, f"ZokoDaily: {title}. {body}"[:160], kind=kind)
