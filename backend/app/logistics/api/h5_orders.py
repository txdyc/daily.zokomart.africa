from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import get_current_user
from app.logistics.capacity import remaining_load, remaining_volume, release
from app.logistics.models import (
    AVAILABILITY_ACCEPTING,
    DRIVER_APPROVED,
    ORDER_AWAITING_PICKUP,
    ORDER_CANCELLED,
    ORDER_COMPLETED,
    ORDER_DELIVERED,
    ORDER_IN_TRANSIT,
    ORDER_PRICE_CONFIRMED,
    ORDER_SUBMITTED,
    ROUTE_APPROVED,
    TRIP_SCHEDULED,
    CustomerOrder,
    Driver,
    Route,
    Trip,
    UserAccount,
    Vehicle,
)
from app.logistics.orders import RESERVED_STATUSES, transition
from app.logistics.schemas import CancelIn, OrderIn
from app.logistics.notify import notify

router = APIRouter()

CONTACT_VISIBLE = (ORDER_AWAITING_PICKUP, ORDER_IN_TRANSIT, ORDER_DELIVERED, ORDER_COMPLETED)


def order_out(db: Session, order: CustomerOrder, viewer: str) -> dict:
    """viewer: "shipper" | "driver" | "staff". Contact details cross the fence only
    from awaiting_pickup onward (PRD §10 contact disclosure)."""
    trip = db.get(Trip, order.trip_id)
    route = db.get(Route, trip.route_id)
    vehicle = db.get(Vehicle, trip.vehicle_id)
    driver = db.get(Driver, route.driver_id)
    disclosed = order.status in CONTACT_VISIBLE or viewer == "staff"
    data = {
        "id": order.id, "status": order.status, "trip_id": order.trip_id,
        "depart_date": trip.depart_date.isoformat(), "depart_time": trip.depart_time,
        "origin_town": route.origin_town, "dest_town": route.dest_town,
        "cargo_name": order.cargo_name, "cargo_category": order.cargo_category,
        "packaging": order.packaging, "pieces": order.pieces,
        "weight_kg": order.weight_kg, "volume_m3": order.volume_m3,
        "fragile": order.fragile, "needs_loading": order.needs_loading,
        "needs_pickup": order.needs_pickup, "pickup_window": order.pickup_window,
        "remarks": order.remarks, "photo_ids": order.photo_ids,
        "freight_ghs": order.freight_ghs, "commission_ghs": order.commission_ghs,
        "pickup_time": order.pickup_time, "cancel_reason": order.cancel_reason,
        "created_at": order.created_at.isoformat(),
        "pickup_town": order.pickup_town, "delivery_town": order.delivery_town,
        "driver": None, "shipper": None,
    }
    if viewer in ("shipper", "staff"):
        data["driver"] = {
            "full_name": driver.full_name,
            "plate_number": vehicle.plate_number,
            "phone": db.get(UserAccount, driver.user_id).phone,
        } if disclosed else None
    if viewer in ("driver", "staff"):
        data["shipper"] = {
            "contact_name": order.contact_name, "contact_phone": order.contact_phone,
            "pickup_details": order.pickup_details,
            "delivery_details": order.delivery_details,
            "consignee_name": order.consignee_name,
            "consignee_phone": order.consignee_phone,
        } if disclosed else None
    return data


@router.post("")
def submit_order(
    body: OrderIn,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    trip = db.get(Trip, body.trip_id)
    if trip is None or trip.status != TRIP_SCHEDULED or trip.depart_date < date.today():
        raise HTTPException(status_code=409, detail="Trip is not open for booking")
    route = db.get(Route, trip.route_id)
    driver = db.get(Driver, route.driver_id)
    if (route.status != ROUTE_APPROVED or driver.status != DRIVER_APPROVED
            or driver.availability != AVAILABILITY_ACCEPTING):
        raise HTTPException(status_code=409, detail="Trip is not open for booking")
    if remaining_load(trip) < body.weight_kg or remaining_volume(trip) < body.volume_m3:
        raise HTTPException(status_code=409, detail="Not enough remaining capacity")
    order = CustomerOrder(shipper_user_id=user.id, **body.model_dump())
    db.add(order)
    db.commit()
    return order_out(db, order, "shipper")


@router.get("/mine")
def my_orders(
    page: int = 1,
    page_size: int = 20,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(CustomerOrder).filter_by(shipper_user_id=user.id)
    total = q.count()
    rows = (q.order_by(CustomerOrder.id.desc())
             .offset((page - 1) * page_size).limit(page_size).all())
    return {"items": [order_out(db, o, "shipper") for o in rows],
            "total": total, "page": page, "page_size": page_size}


def _my_driver_order(db: Session, user: UserAccount, order_id: int) -> CustomerOrder:
    order = db.get(CustomerOrder, order_id)
    driver = db.query(Driver).filter_by(user_id=user.id).one_or_none()
    if order is None or driver is None:
        raise HTTPException(status_code=404, detail="Order not found")
    trip = db.get(Trip, order.trip_id)
    route = db.get(Route, trip.route_id)
    if route.driver_id != driver.id:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def _shipper_user(db: Session, order: CustomerOrder) -> UserAccount:
    return db.get(UserAccount, order.shipper_user_id)


@router.get("/assigned")
def assigned_orders(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    driver = db.query(Driver).filter_by(user_id=user.id).one_or_none()
    if driver is None:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    q = (db.query(CustomerOrder)
         .join(Trip, CustomerOrder.trip_id == Trip.id)
         .join(Route, Trip.route_id == Route.id)
         .filter(Route.driver_id == driver.id))
    if status:
        q = q.filter(CustomerOrder.status == status)
    total = q.count()
    rows = (q.order_by(CustomerOrder.id.desc())
             .offset((page - 1) * page_size).limit(page_size).all())
    return {"items": [order_out(db, o, "driver") for o in rows],
            "total": total, "page": page, "page_size": page_size}


@router.post("/{order_id}/accept")
def accept_order(
    order_id: int,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _my_driver_order(db, user, order_id)
    if order.status != ORDER_PRICE_CONFIRMED:
        raise HTTPException(status_code=409, detail=f"Order is {order.status}")
    transition(db, order, ORDER_AWAITING_PICKUP, actor=user.phone, actor_type="driver")
    db.commit()
    notify(db, _shipper_user(db, order), "order_accepted", "Driver accepted your order",
           f"Order #{order.id} will be picked up: {order.pickup_time}.", sms=True)
    return order_out(db, order, "driver")


@router.post("/{order_id}/reject")
def reject_order(
    order_id: int,
    body: CancelIn,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _my_driver_order(db, user, order_id)
    if order.status != ORDER_PRICE_CONFIRMED:
        raise HTTPException(status_code=409, detail=f"Order is {order.status}")
    release(db, order.trip_id, order.weight_kg, order.volume_m3)
    order.reject_count += 1
    transition(db, order, ORDER_SUBMITTED, actor=user.phone, actor_type="driver",
               detail=body.reason)
    db.commit()
    return order_out(db, order, "driver")


@router.post("/{order_id}/depart")
def depart(
    order_id: int,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _my_driver_order(db, user, order_id)
    if order.status != ORDER_AWAITING_PICKUP:
        raise HTTPException(status_code=409, detail=f"Order is {order.status}")
    transition(db, order, ORDER_IN_TRANSIT, actor=user.phone, actor_type="driver")
    db.commit()
    notify(db, _shipper_user(db, order), "order", "Your cargo is in transit",
           f"Order #{order.id} departed.")
    return order_out(db, order, "driver")


@router.post("/{order_id}/deliver")
def deliver(
    order_id: int,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _my_driver_order(db, user, order_id)
    if order.status != ORDER_IN_TRANSIT:
        raise HTTPException(status_code=409, detail=f"Order is {order.status}")
    transition(db, order, ORDER_DELIVERED, actor=user.phone, actor_type="driver")
    db.commit()
    notify(db, _shipper_user(db, order), "order", "Cargo delivered",
           f"Order #{order.id} was delivered. Customer service will confirm completion.")
    return order_out(db, order, "driver")


def _visible_order(db: Session, user: UserAccount, order_id: int) -> tuple[CustomerOrder, str]:
    order = db.get(CustomerOrder, order_id)
    if order is not None and order.shipper_user_id == user.id:
        return order, "shipper"
    if order is not None:
        driver = db.query(Driver).filter_by(user_id=user.id).one_or_none()
        if driver is not None:
            trip = db.get(Trip, order.trip_id)
            route = db.get(Route, trip.route_id)
            if route.driver_id == driver.id:
                return order, "driver"
    raise HTTPException(status_code=404, detail="Order not found")


@router.get("/{order_id}")
def order_detail(
    order_id: int,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order, viewer = _visible_order(db, user, order_id)
    return order_out(db, order, viewer)


@router.post("/{order_id}/cancel")
def cancel_order(
    order_id: int,
    body: CancelIn,
    user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order, viewer = _visible_order(db, user, order_id)
    if viewer != "shipper":
        raise HTTPException(status_code=403, detail="Only the shipper can cancel here")
    if order.status not in (ORDER_SUBMITTED, ORDER_PRICE_CONFIRMED):
        raise HTTPException(status_code=409,
                            detail="Too late to cancel; contact customer service")
    if order.status in RESERVED_STATUSES:
        release(db, order.trip_id, order.weight_kg, order.volume_m3)
    order.cancel_reason = body.reason
    transition(db, order, ORDER_CANCELLED, actor=user.phone, actor_type="shipper",
               detail=body.reason)
    db.commit()
    return order_out(db, order, "shipper")
