from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from app.migrate import ensure_schema


def _engine_without_role():
    """A SQLite engine (single shared connection) whose admin_user lacks `role`,
    emulating a news-only production MySQL before the Plan 5 column was added."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE admin_user "
                "(id INTEGER PRIMARY KEY, username VARCHAR(50), password_hash VARCHAR(100))"
            )
        )
    return engine


def test_adds_missing_role_column():
    engine = _engine_without_role()
    applied = ensure_schema(engine)
    assert applied == ["admin_user.role"]
    cols = {c["name"] for c in inspect(engine).get_columns("admin_user")}
    assert "role" in cols


def test_role_defaults_to_admin():
    engine = _engine_without_role()
    ensure_schema(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO admin_user (username, password_hash) VALUES ('u', 'h')"))
        role = conn.execute(text("SELECT role FROM admin_user WHERE username='u'")).scalar()
    assert role == "admin"


def test_idempotent_when_column_present():
    engine = _engine_without_role()
    ensure_schema(engine)          # first run adds it
    assert ensure_schema(engine) == []  # second run is a no-op


def test_noop_when_table_absent():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    assert ensure_schema(engine) == []
