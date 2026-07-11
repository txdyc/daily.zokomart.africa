from datetime import date, timedelta

from app.logistics.models import Trip
from app.logistics.trips_service import generate_trips
from tests.lg_helpers import approved_driver, approved_route, approved_vehicle

TODAY = date(2026, 7, 13)  # a Monday


def _route(client, db_session, **overrides):
    headers, _ = approved_driver(client, db_session)
    vid = approved_vehicle(client, db_session, headers)
    rid = approved_route(client, db_session, headers, vid, **overrides)
    return headers, vid, rid


def test_daily_route_generates_seven_trips(client, db_session):
    _, vid, rid = _route(client, db_session)
    created = generate_trips(db_session, days_ahead=7, today=TODAY)
    assert created == 7
    trips = db_session.query(Trip).filter_by(route_id=rid).all()
    assert len(trips) == 7
    assert trips[0].total_load_kg == 2000.0  # seeded from the vehicle
    assert trips[0].used_load_kg == 0.0


def test_generation_is_idempotent(client, db_session):
    _route(client, db_session)
    generate_trips(db_session, days_ahead=7, today=TODAY)
    assert generate_trips(db_session, days_ahead=7, today=TODAY) == 0


def test_weekly_route_generates_matching_days(client, db_session):
    _, _, rid = _route(client, db_session,
                       frequency="weekly", weekdays=[0, 3])  # Mon + Thu
    created = generate_trips(db_session, days_ahead=7, today=TODAY)
    dates = [t.depart_date for t in db_session.query(Trip).filter_by(route_id=rid).all()]
    assert created == 2
    assert dates == [TODAY, TODAY + timedelta(days=3)]


def test_once_route_generates_single_trip(client, db_session):
    target = TODAY + timedelta(days=2)
    _, _, rid = _route(client, db_session, frequency="once",
                       once_date=target.isoformat())
    created = generate_trips(db_session, days_ahead=7, today=TODAY)
    assert created == 1
    assert db_session.query(Trip).filter_by(route_id=rid).one().depart_date == target


def test_paused_driver_gets_no_trips(client, db_session):
    from app.logistics.models import AVAILABILITY_PAUSED, Driver

    _, _, _ = _route(client, db_session)
    db_session.query(Driver).one().availability = AVAILABILITY_PAUSED
    db_session.commit()
    assert generate_trips(db_session, days_ahead=7, today=TODAY) == 0


def test_expired_insurance_blocks_generation(client, db_session):
    from app.logistics.models import Vehicle

    _, vid, _ = _route(client, db_session)
    db_session.get(Vehicle, vid).insurance_expiry = TODAY - timedelta(days=1)
    db_session.commit()
    assert generate_trips(db_session, days_ahead=7, today=TODAY) == 0
