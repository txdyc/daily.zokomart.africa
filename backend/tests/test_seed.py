from app.models import AdminUser, AppConfig, Country, Site
from app.seed import seed_all
from app.security import verify_password


def test_seed_creates_reference_data(db_session):
    seed_all(db_session)

    assert db_session.query(Country).count() == 4
    assert db_session.query(Site).count() == 10
    ghana = db_session.query(Country).filter_by(code="GH").one()
    assert ghana.name_zh == "加纳"
    assert db_session.query(Site).filter_by(country_id=ghana.id).count() == 3

    admin = db_session.query(AdminUser).filter_by(username="admin").one()
    assert verify_password("admin123", admin.password_hash)

    assert db_session.get(AppConfig, "ai_base_url").value == "https://api.openai.com/v1"
    assert db_session.get(AppConfig, "ai_api_key").value == ""
    assert db_session.get(AppConfig, "ai_model").value == "gpt-4o-mini"


def test_seed_is_idempotent(db_session):
    seed_all(db_session)
    seed_all(db_session)
    assert db_session.query(Country).count() == 4
    assert db_session.query(Site).count() == 10
    assert db_session.query(AdminUser).count() == 1
