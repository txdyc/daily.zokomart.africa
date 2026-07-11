from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.logistics.auth import require_roles
from app.logistics.models import (
    ROUTE_APPROVED,
    ROUTE_PENDING,
    ROUTE_REJECTED,
    ROUTE_SUSPENDED,
    AuditRecord,
    Driver,
    Route,
    UserAccount,
)
from app.logistics.notify import notify
from app.logistics.schemas import FreezeIn, Paginated, ReviewIn, RouteOut
from app.logistics.trips_service import generate_trips
from app.models import AdminUser

router = APIRouter()

reviewer = require_roles("admin", "auditor")
administrator = require_roles("admin")


def _get(db: Session, route_id: int) -> Route:
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")
    return route


def _notify_driver(db: Session, route: Route, title: str, body: str) -> None:
    driver = db.get(Driver, route.driver_id)
    user = db.get(UserAccount, driver.user_id)
    notify(db, user, "route_review", title, body, sms=True)


@router.get("", response_model=Paginated)
def list_routes(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    _: AdminUser = Depends(reviewer),
    db: Session = Depends(get_db),
):
    q = db.query(Route)
    if status:
        q = q.filter(Route.status == status)
    total = q.count()
    rows = q.order_by(Route.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return Paginated(items=[RouteOut.model_validate(r).model_dump(mode="json") for r in rows],
                     total=total, page=page, page_size=page_size)


@router.post("/{route_id}/review", response_model=RouteOut)
def review_route(
    route_id: int,
    body: ReviewIn,
    staff: AdminUser = Depends(reviewer),
    db: Session = Depends(get_db),
):
    route = _get(db, route_id)
    if route.status != ROUTE_PENDING:
        raise HTTPException(status_code=409, detail="Route is not pending review")
    if body.action == "reject" and not body.reason.strip():
        raise HTTPException(status_code=400, detail="Rejection requires a reason")
    route.status = ROUTE_APPROVED if body.action == "approve" else ROUTE_REJECTED
    route.review_remark = body.reason
    db.add(AuditRecord(entity_type="route", entity_id=route.id,
                       action=body.action, reason=body.reason, actor=staff.username))
    db.commit()
    if body.action == "approve":
        generate_trips(db, route_id=route.id)
        _notify_driver(db, route, "Route approved",
                       f"{route.origin_town} → {route.dest_town} is now live.")
    else:
        _notify_driver(db, route, "Route rejected", body.reason)
    return route


@router.post("/{route_id}/suspend", response_model=RouteOut)
def suspend_route(
    route_id: int,
    body: FreezeIn,
    staff: AdminUser = Depends(administrator),
    db: Session = Depends(get_db),
):
    route = _get(db, route_id)
    if route.status != ROUTE_APPROVED:
        raise HTTPException(status_code=409, detail="Only approved routes can be suspended")
    route.status = ROUTE_SUSPENDED
    db.add(AuditRecord(entity_type="route", entity_id=route.id,
                       action="suspend", reason=body.reason, actor=staff.username))
    db.commit()
    _notify_driver(db, route, "Route suspended", body.reason)
    return route


@router.post("/{route_id}/resume", response_model=RouteOut)
def resume_route(
    route_id: int,
    staff: AdminUser = Depends(administrator),
    db: Session = Depends(get_db),
):
    route = _get(db, route_id)
    if route.status != ROUTE_SUSPENDED:
        raise HTTPException(status_code=409, detail="Route is not suspended")
    route.status = ROUTE_APPROVED
    db.add(AuditRecord(entity_type="route", entity_id=route.id,
                       action="resume", reason="", actor=staff.username))
    db.commit()
    return route
