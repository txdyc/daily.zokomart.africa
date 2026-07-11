from app.logistics.models import ROUTE_PENDING, Route


def test_route_defaults(db_session):
    route = Route(
        driver_id=1, origin_region="Greater Accra", origin_town="Accra",
        dest_region="Ashanti", dest_town="Kumasi", via_towns=[],
        frequency="daily", weekdays=[], once_date=None,
        depart_time="08:00", est_duration_hours=6, default_vehicle_id=1,
        cargo_types=["general"], rate_per_ton=350.0, rate_per_m3=None,
        min_charge=None, negotiable=False,
    )
    db_session.add(route)
    db_session.commit()
    assert route.status == ROUTE_PENDING
    assert route.prohibited_notes == ""
