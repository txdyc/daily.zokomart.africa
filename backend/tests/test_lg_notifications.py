from app.logistics.models import Notification, UserAccount
from tests.lg_helpers import h5_login


def _seed_notifications(db_session, phone="+233241234567", n=3):
    user = db_session.query(UserAccount).filter_by(phone=phone).one()
    for i in range(n):
        db_session.add(Notification(user_id=user.id, kind="order",
                                    title=f"Event {i}", body=""))
    db_session.commit()


def test_list_with_unread_count(client, db_session):
    headers = h5_login(client, db_session)
    _seed_notifications(db_session)
    resp = client.get("/api/lg/notifications", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["unread"] == 3
    assert data["items"][0]["title"] == "Event 2"  # newest first


def test_mark_read(client, db_session):
    headers = h5_login(client, db_session)
    _seed_notifications(db_session, n=1)
    nid = client.get("/api/lg/notifications", headers=headers).json()["items"][0]["id"]
    assert client.post(f"/api/lg/notifications/{nid}/read", headers=headers).status_code == 200
    assert client.get("/api/lg/notifications", headers=headers).json()["unread"] == 0


def test_cannot_read_others_notification(client, db_session):
    h1 = h5_login(client, db_session, "0241111111")
    _seed_notifications(db_session, "+233241111111", n=1)
    nid = client.get("/api/lg/notifications", headers=h1).json()["items"][0]["id"]
    h2 = h5_login(client, db_session, "0242222222")
    assert client.post(f"/api/lg/notifications/{nid}/read", headers=h2).status_code == 404
