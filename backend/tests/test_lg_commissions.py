from tests.lg_helpers import admin_headers
from tests.test_lg_orders_driver import _confirmed_order


def _completed_order(client, db_session):
    driver_h, shipper_h, oid, tid = _confirmed_order(client, db_session)
    cs = admin_headers(client, db_session, role="cs", username="susan")
    client.post(f"/api/lg/orders/{oid}/accept", headers=driver_h)
    client.post(f"/api/lg/orders/{oid}/depart", headers=driver_h)
    client.post(f"/api/lg/orders/{oid}/deliver", headers=driver_h)
    client.post(f"/api/admin/lg/orders/{oid}/complete", headers=cs)
    return driver_h, cs, oid


def test_driver_sees_own_ledger(client, db_session):
    driver_h, _, _ = _completed_order(client, db_session)
    resp = client.get("/api/lg/commissions/mine", headers=driver_h)
    assert resp.status_code == 200
    assert resp.json()["total_owed_ghs"] == 40.0
    assert resp.json()["items"][0]["status"] == "pending"


def test_settle_flow(client, db_session):
    _, cs, _ = _completed_order(client, db_session)
    resp = client.get("/api/admin/lg/commissions?status=pending", headers=cs)
    assert resp.json()["total"] == 1
    cid = resp.json()["items"][0]["id"]
    resp = client.post(f"/api/admin/lg/commissions/{cid}/settle",
                       json={"method": "momo", "reference": "MP123456"}, headers=cs)
    assert resp.status_code == 200 and resp.json()["status"] == "settled"
    # settling twice fails
    resp = client.post(f"/api/admin/lg/commissions/{cid}/settle",
                       json={"method": "momo", "reference": "MP123456"}, headers=cs)
    assert resp.status_code == 409


def test_waive_is_admin_only(client, db_session):
    _, cs, _ = _completed_order(client, db_session)
    cid = client.get("/api/admin/lg/commissions", headers=cs).json()["items"][0]["id"]
    resp = client.post(f"/api/admin/lg/commissions/{cid}/waive",
                       json={"reason": "goodwill"}, headers=cs)
    assert resp.status_code == 403
    boss = admin_headers(client, db_session, role="admin")
    resp = client.post(f"/api/admin/lg/commissions/{cid}/waive",
                       json={"reason": "goodwill"}, headers=boss)
    assert resp.status_code == 200 and resp.json()["status"] == "waived"
