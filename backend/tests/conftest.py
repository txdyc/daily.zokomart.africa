import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SCHEDULER_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import app.models  # noqa: F401  (register all tables on Base)

    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    session = TestingSession()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def _reset_login_rate_limiter():
    """Clear the in-memory login rate limiter before and after each test.

    All TestClient requests come from the same IP ("testclient"). Tests call
    the login endpoint repeatedly via admin_headers(), which would otherwise
    exceed the 10-attempt/60s limit and cause spurious 429 failures.
    """
    try:
        from app.api.admin.auth import _LOGIN_ATTEMPTS
        _LOGIN_ATTEMPTS.clear()
    except ImportError:
        pass
    yield
    try:
        from app.api.admin.auth import _LOGIN_ATTEMPTS
        _LOGIN_ATTEMPTS.clear()
    except ImportError:
        pass


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
