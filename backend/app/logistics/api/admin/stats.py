from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import require_roles
from app.logistics.models import (
    COMMISSION_PENDING,
    COMMISSION_SETTLED,
    ORDER_CANCELLED,
    ORDER_COMPLETED,
    ROUTE_APPROVED,
    CommissionRecord,
    CustomerOrder,
    Driver,
    Route,
    Trip,
    Vehicle,
)
from app.models import AdminUser

router = APIRouter()

any_staff = require_roles("admin", "auditor", "cs")


def _range_filter(q, column, start: date | None, end: date | None):
    if start:
        q = q.filter(column >= start)
    if end:
        q = q.filter(column <= end)
    return q


@router.get("/overview")
def overview(
    start: date | None = None,
    end: date | None = None,
    _: AdminUser = Depends(any_staff),
    db: Session = Depends(get_db),
):
    drivers = dict(db.query(Driver.status, func.count()).group_by(Driver.status).all())
    orders_q = _range_filter(db.query(CustomerOrder), CustomerOrder.created_at, start, end)
    orders = dict(
        _range_filter(db.query(CustomerOrder.status, func.count()),
                      CustomerOrder.created_at, start, end)
        .group_by(CustomerOrder.status).all()
    )
    total_orders = sum(orders.values())
    completed = orders.get(ORDER_COMPLETED, 0)
    cancelled = orders.get(ORDER_CANCELLED, 0)

    gmv = (_range_filter(
        db.query(func.coalesce(func.sum(CustomerOrder.freight_ghs), 0.0))
        .filter(CustomerOrder.status == ORDER_COMPLETED),
        CustomerOrder.created_at, start, end).scalar())
    pending = (db.query(func.coalesce(func.sum(CommissionRecord.amount_ghs), 0.0))
               .filter(CommissionRecord.status == COMMISSION_PENDING).scalar())
    settled = (db.query(func.coalesce(func.sum(CommissionRecord.amount_ghs), 0.0))
               .filter(CommissionRecord.status == COMMISSION_SETTLED).scalar())

    lanes = (
        _range_filter(
            db.query(Route.origin_town, Route.dest_town, func.count(CustomerOrder.id))
            .join(Trip, Trip.route_id == Route.id)
            .join(CustomerOrder, CustomerOrder.trip_id == Trip.id),
            CustomerOrder.created_at, start, end)
        .group_by(Route.origin_town, Route.dest_town)
        .order_by(func.count(CustomerOrder.id).desc()).limit(5).all()
    )

    past_trips = (db.query(Trip)
                  .filter(Trip.depart_date < date.today(), Trip.total_load_kg > 0).all())
    utilization = (
        round(sum((t.used_load_kg + t.manual_load_kg) / t.total_load_kg
                  for t in past_trips) / len(past_trips), 3)
        if past_trips else 0.0
    )

    return {
        "drivers": drivers,
        "vehicles": db.query(Vehicle).count(),
        "routes_active": db.query(Route).filter(Route.status == ROUTE_APPROVED).count(),
        "trips_upcoming": db.query(Trip).filter(Trip.depart_date >= date.today()).count(),
        "orders": orders,
        "orders_total": total_orders,
        "gmv_ghs": round(float(gmv), 2),
        "commission": {"pending_ghs": round(float(pending), 2),
                       "settled_ghs": round(float(settled), 2)},
        "top_lanes": [{"lane": f"{o} → {d}", "orders": n} for o, d, n in lanes],
        "completion_rate": round(completed / total_orders, 3) if total_orders else 0.0,
        "cancellation_rate": round(cancelled / total_orders, 3) if total_orders else 0.0,
        "capacity_utilization": utilization,
    }
