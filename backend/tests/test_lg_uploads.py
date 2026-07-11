import io

import pytest

from app.config import settings
from tests.lg_helpers import admin_headers, h5_login

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


@pytest.fixture(autouse=True)
def tmp_upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))


def _upload(client, headers):
    return client.post(
        "/api/lg/uploads",
        files={"file": ("ghana_card.png", io.BytesIO(PNG), "image/png")},
        headers=headers,
    )


def test_upload_and_owner_download(client, db_session):
    headers = h5_login(client, db_session)
    resp = _upload(client, headers)
    assert resp.status_code == 200
    att_id = resp.json()["id"]
    assert resp.json()["url"] == f"/api/lg/uploads/{att_id}"
    got = client.get(f"/api/lg/uploads/{att_id}", headers=headers)
    assert got.status_code == 200
    assert got.content == PNG


def test_other_user_cannot_download(client, db_session):
    owner = h5_login(client, db_session, "0241234567")
    att_id = _upload(client, owner).json()["id"]
    other = h5_login(client, db_session, "0209876543")
    assert client.get(f"/api/lg/uploads/{att_id}", headers=other).status_code == 403


def test_admin_can_download(client, db_session):
    owner = h5_login(client, db_session)
    att_id = _upload(client, owner).json()["id"]
    staff = admin_headers(client, db_session, role="auditor", username="audrey")
    assert client.get(f"/api/lg/uploads/{att_id}", headers=staff).status_code == 200


def test_bad_content_type_rejected(client, db_session):
    headers = h5_login(client, db_session)
    resp = client.post(
        "/api/lg/uploads",
        files={"file": ("x.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 415


def test_anonymous_upload_rejected(client):
    resp = client.post(
        "/api/lg/uploads", files={"file": ("x.png", io.BytesIO(PNG), "image/png")}
    )
    assert resp.status_code == 401
