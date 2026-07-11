from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import require_roles
from app.logistics.capacity import CapacityError, release, reserve
from app.logistics.models import (
    ORDER_PRICE_CONFIRMED,
    ORDER_SUBMITTED,
    TRIP_SCHEDULED,
    CsRemark,
    CustomerOrder,
    Driver,
    Route,
    Trip,
    UserAccount,
)
from app.logistics.notify import notify
from app.logistics.orders import RESERVED_STATUSES, transition
from app.logistics.api.h5_orders import order_out
from app.logistics.schemas import ConfirmPriceIn, Paginated, ReassignIn, RemarkIn
from app.models import AdminUser
from app.services.config_service import get_config

router = APIRouter()

cs_staff = require_roles("admin", "cs")


def _get_order(db: Session, order_id: int) -> CustomerOrder:
    order = db.get(CustomerOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def _driver_user(db: Session, order: CustomerOrder) -> tuple[Driver, UserAccount]:
    trip = db.get(Trip, order.trip_id)
    route = db.get(Route, trip.route_id)
    driver = db.get(Driver, route.driver_id)
    return driver, db.get(UserAccount, driver.user_id)


@router.get("", response_model=Paginated)
def list_orders(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    _: AdminUser = Depends(cs_staff),
    db: Session = Depends(get_db),
):
    q = db.query(CustomerOrder)
    if status:
        q = q.filter(CustomerOrder.status == status)
    total = q.count()
    order_col = CustomerOrder.id if status == ORDER_SUBMITTED else CustomerOrder.id.desc()
    rows = q.order_by(order_col).offset((page - 1) * page_size).limit(page_size).all()
    return Paginated(items=[order_out(db, o, "staff") for o in rows],
                     total=total, page=page, page_size=page_size)


@router.get("/{order_id}")
def order_detail(
    order_id: int,
    _: AdminUser = Depends(cs_staff),
    db: Session = Depends(get_db),
):
    order = _get_order(db, order_id)
    data = order_out(db, order, "staff")
    data["remarks"] = [
        {"author": r.author, "body": r.body, "created_at": r.created_at.isoformat()}
        for r in db.query(CsRemark).filter_by(order_id=order.id).order_by(CsRemark.id)
    ]
    data["reject_count"] = order.reject_count
    return data


@router.post("/{order_id}/confirm-price")
def confirm_price(
    order_id: int,
    body: ConfirmPriceIn,
    staff: AdminUser = Depends(cs_staff),
    db: Session = Depends(get_db),
):
    order = _get_order(db, order_id)
    if order.status not in (ORDER_SUBMITTED, ORDER_PRICE_CONFIRMED):
        raise HTTPException(status_code=409, detail=f"Order is {order.status}")
    if body.commission_ghs is not None and not body.override_reason.strip():
        raise HTTPException(status_code=400, detail="Commission override requires a reason")

    if order.status == ORDER_PRICE_CONFIRMED:  # re-confirm: replace the reservation
        release(db, order.trip_id, order.weight_kg, order.volume_m3)
    try:
        reserve(db, order.trip_id, order.weight_kg, order.volume_m3)
    except CapacityError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=e.detail)

    rate = float(get_config(db, "lg_commission_rate", "0.08"))
    order.freight_ghs = round(body.freight_ghs, 2)
    order.commission_rate = rate
    order.commission_ghs = (round(body.commission_ghs, 2) if body.commission_ghs is not None
                            else round(body.freight_ghs * rate, 2))
    order.pickup_time = body.pickup_time
    if order.status == ORDER_SUBMITTED:
        transition(db, order, ORDER_PRICE_CONFIRMED, actor=staff.username,
                   actor_type="staff", detail=body.override_reason)
    db.commit()
    _, user = _driver_user(db, order)
    notify(db, user, "order", "New order needs acceptance",
           f"Order #{order.id}: {order.cargo_name}, {order.weight_kg} kg, "
           f"GHS {order.freight_ghs}. Open ZokoDaily to accept.", sms=True)
    return order_out(db, order, "staff")


@router.post("/{order_id}/reassign")
def reassign(
    order_id: int,
    body: ReassignIn,
    staff: AdminUser = Depends(cs_staff),
    db: Session = Depends(get_db),
):
    order = _get_order(db, order_id)
    if order.status != ORDER_SUBMITTED:
        raise HTTPException(status_code=409, detail="Only submitted orders can be reassigned")
    trip = db.get(Trip, body.trip_id)
    if (trip is None or trip.status != TRIP_SCHEDULED
            or trip.depart_date < date.today()):
        raise HTTPException(status_code=409, detail="Target trip is not open")
    order.trip_id = trip.id
    from app.logistics.ops import log_op

    log_op(db, staff.username, "staff", "order_reassign", "order", order.id,
           f"trip -> {trip.id}")
    db.commit()
    return order_out(db, order, "staff")


@router.post("/{order_id}/remarks")
def add_remark(
    order_id: int,
    body: RemarkIn,
    staff: AdminUser = Depends(cs_staff),
    db: Session = Depends(get_db),
):
    order = _get_order(db, order_id)
    db.add(CsRemark(order_id=order.id, author=staff.username, body=body.body))
    db.commit()
    return {"ok": True}
