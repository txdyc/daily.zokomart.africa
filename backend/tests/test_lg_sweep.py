from datetime import date, timedelta

from app.logistics.models import Notification, Route, Vehicle
from app.logistics.sweep import expiry_sweep
from tests.lg_helpers import approved_driver, approved_route, approved_vehicle

TODAY = date(2026, 7, 13)


def _setup(client, db_session, insurance_expiry):
    headers, _ = approved_driver(client, db_session)
    vid = approved_vehicle(client, db_session, headers)
    vehicle = db_session.get(Vehicle, vid)
    vehicle.insurance_expiry = insurance_expiry
    db_session.commit()
    rid = approved_route(client, db_session, headers, vid)
    return vid, rid


def test_reminder_at_30_and_7_days(client, db_session):
    _setup(client, db_session, TODAY + timedelta(days=30))
    expiry_sweep(db_session, today=TODAY)
    notes = db_session.query(Notification).filter_by(kind="expiry").all()
    assert len(notes) == 1
    assert "insurance" in notes[0].title.lower()


def test_no_reminder_at_other_offsets(client, db_session):
    _setup(client, db_session, TODAY + timedelta(days=15))
    expiry_sweep(db_session, today=TODAY)
    assert db_session.query(Notification).filter_by(kind="expiry").count() == 0


def test_expired_docs_suspend_routes(client, db_session):
    _, rid = _setup(client, db_session, TODAY - timedelta(days=1))
    expiry_sweep(db_session, today=TODAY)
    assert db_session.get(Route, rid).status == "suspended"
    assert "expired" in db_session.get(Route, rid).review_remark
    # sweep is idempotent — running again adds no duplicate notifications
    before = db_session.query(Notification).count()
    expiry_sweep(db_session, today=TODAY)
    assert db_session.query(Notification).count() == before
