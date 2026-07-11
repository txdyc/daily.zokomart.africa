"""Order status machine (PRD §10.1). transition() is the ONLY way order.status
changes — it validates the edge, stamps the timestamp, and writes the operation log."""

from sqlalchemy.orm import Session

from app.logistics.models import (
    ORDER_AWAITING_PICKUP,
    ORDER_CANCELLED,
    ORDER_COMPLETED,
    ORDER_DELIVERED,
    ORDER_EXCEPTION,
    ORDER_IN_TRANSIT,
    ORDER_PRICE_CONFIRMED,
    ORDER_SUBMITTED,
    CustomerOrder,
    utcnow,
)
from app.logistics.ops import log_op

ALLOWED: dict[str, tuple[str, ...]] = {
    ORDER_SUBMITTED: (ORDER_PRICE_CONFIRMED, ORDER_CANCELLED, ORDER_EXCEPTION),
    ORDER_PRICE_CONFIRMED: (ORDER_AWAITING_PICKUP, ORDER_SUBMITTED,
                            ORDER_CANCELLED, ORDER_EXCEPTION),
    ORDER_AWAITING_PICKUP: (ORDER_IN_TRANSIT, ORDER_CANCELLED, ORDER_EXCEPTION),
    ORDER_IN_TRANSIT: (ORDER_DELIVERED, ORDER_EXCEPTION),
    ORDER_DELIVERED: (ORDER_COMPLETED, ORDER_EXCEPTION),
}

_STAMP = {
    ORDER_PRICE_CONFIRMED: "price_confirmed_at",
    ORDER_AWAITING_PICKUP: "accepted_at",
    ORDER_IN_TRANSIT: "departed_at",
    ORDER_DELIVERED: "delivered_at",
    ORDER_COMPLETED: "completed_at",
    ORDER_CANCELLED: "closed_at",
    ORDER_EXCEPTION: "closed_at",
}

# Capacity is held while the order is in one of these states.
RESERVED_STATUSES = (ORDER_PRICE_CONFIRMED, ORDER_AWAITING_PICKUP)


def transition(db: Session, order: CustomerOrder, new_status: str,
               actor: str, actor_type: str, detail: str = "") -> None:
    if new_status not in ALLOWED.get(order.status, ()):
        raise ValueError(f"Cannot go from {order.status} to {new_status}")
    order.status = new_status
    stamp = _STAMP.get(new_status)
    if stamp:
        setattr(order, stamp, utcnow())
    log_op(db, actor, actor_type, f"order_{new_status}", "order", order.id, detail)
