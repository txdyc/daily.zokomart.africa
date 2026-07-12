from app.models import AdminUser
from app.security import hash_password


def _create_admin(db_session, username="admin", password="secret123"):
    db_session.add(AdminUser(username=username, password_hash=hash_password(password)))
    db_session.commit()


def _login(client, username="admin", password="secret123"):
    return client.post(
        "/api/admin/auth/login", json={"username": username, "password": password}
    )


def test_login_success_returns_token(client, db_session):
    _create_admin(db_session)
    r = _login(client)
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_wrong_password_401(client, db_session):
    _create_admin(db_session)
    r = _login(client, password="wrong")
    assert r.status_code == 401


def test_me_requires_token(client, db_session):
    _create_admin(db_session)
    assert client.get("/api/admin/auth/me").status_code == 401
    assert (
        client.get(
            "/api/admin/auth/me", headers={"Authorization": "Bearer not-a-token"}
        ).status_code
        == 401
    )

    token = _login(client).json()["access_token"]
    r = client.get("/api/admin/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"username": "admin", "role": "admin"}


def test_me_returns_staff_role(client, db_session):
    db_session.add(AdminUser(
        username="cs1", password_hash=hash_password("pw"), role="cs",
    ))
    db_session.commit()
    token = _login(client, username="cs1", password="pw").json()["access_token"]
    r = client.get("/api/admin/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"username": "cs1", "role": "cs"}
