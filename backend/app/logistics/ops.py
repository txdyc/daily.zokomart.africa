from sqlalchemy.orm import Session

from app.logistics.models import OperationLog


def log_op(db: Session, actor: str, actor_type: str, action: str,
           entity_type: str, entity_id: int, detail: str = "") -> None:
    """Append-only operation trail (PRD §16). Caller commits."""
    db.add(OperationLog(actor=actor, actor_type=actor_type, action=action,
                        entity_type=entity_type, entity_id=entity_id, detail=detail))
