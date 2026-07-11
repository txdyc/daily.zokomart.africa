from datetime import date, timedelta

import pytest

from app.logistics.capacity import CapacityError, release, reserve
from app.logistics.models import Trip
from app.logistics.orders import ALLOWED, transition
from tests.lg_helpers import approved_driver, approved_route, approved_vehicle, make_trip


def _trip(client, db_session):
    headers, _ = approved_driver(client, db_session)
    vid = approved_vehicle(client, db_session, headers)
    rid = approved_route(client, db_session, headers, vid)
    tid = make_trip(db_session, rid, date.today() + timedelta(days=1))
    return db_session.get(Trip, tid)


def test_reserve_and_release(client, db_session):
    trip = _trip(client, db_session)
    reserve(db_session, trip.id, 800.0, 4.0)
    db_session.commit()
    assert trip.used_load_kg == 800.0 and trip.used_volume_m3 == 4.0
    release(db_session, trip.id, 800.0, 4.0)
    db_session.commit()
    assert trip.used_load_kg == 0.0 and trip.used_volume_m3 == 0.0


def test_overbooking_blocked(client, db_session):
    trip = _trip(client, db_session)
    reserve(db_session, trip.id, 1500.0, 5.0)
    db_session.commit()
    with pytest.raises(CapacityError):
        reserve(db_session, trip.id, 600.0, 1.0)  # 1500+600 > 2000 kg


def test_release_never_goes_negative(client, db_session):
    trip = _trip(client, db_session)
    release(db_session, trip.id, 999.0, 9.0)
    db_session.commit()
    assert trip.used_load_kg == 0.0 and trip.used_volume_m3 == 0.0


def test_transition_machine(db_session):
    from app.logistics.models import CustomerOrder

    order = CustomerOrder(
        shipper_user_id=1, trip_id=1, contact_name="A", contact_phone="+233241234567",
        pickup_region="GA", pickup_town="Accra", pickup_details="x",
        delivery_region="AS", delivery_town="Kumasi", delivery_details="y",
        consignee_name="B", consignee_phone="+233209876543",
        cargo_name="TVs", cargo_category="electronics", packaging="carton",
        pieces=10, weight_kg=200.0, volume_m3=1.5, pickup_window="morning",
    )
    db_session.add(order)
    db_session.commit()
    transition(db_session, order, "price_confirmed", actor="susan", actor_type="staff")
    db_session.commit()
    assert order.status == "price_confirmed" and order.price_confirmed_at is not None
    with pytest.raises(ValueError):
        transition(db_session, order, "delivered", actor="x", actor_type="staff")
    assert set(ALLOWED["delivered"]) == {"completed", "exception_closed"}
