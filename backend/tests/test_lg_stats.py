from tests.lg_helpers import admin_headers
from tests.test_lg_commissions import _completed_order


def test_overview_counts_and_money(client, db_session):
    _completed_order(client, db_session)
    staff = admin_headers(client, db_session, role="admin")
    resp = client.get("/api/admin/lg/stats/overview", headers=staff)
    assert resp.status_code == 200
    data = resp.json()
    assert data["drivers"]["approved"] == 1
    assert data["vehicles"] == 1
    assert data["routes_active"] == 1
    assert data["orders"]["completed"] == 1
    assert data["gmv_ghs"] == 500.0
    assert data["commission"]["pending_ghs"] == 40.0
    assert data["top_lanes"][0] == {"lane": "Accra → Kumasi", "orders": 1}
    assert data["completion_rate"] == 1.0


def test_all_staff_roles_can_read_stats(client, db_session):
    for role, name in (("auditor", "audrey"), ("cs", "susan")):
        staff = admin_headers(client, db_session, role=role, username=name)
        assert client.get("/api/admin/lg/stats/overview", headers=staff).status_code == 200
