"""Idempotent additive migrations that `create_all` cannot perform.

`Base.metadata.create_all` creates missing tables but never alters existing ones, so a
column added to a model after its table already exists in production (e.g. admin_user.role,
added in LTL Plan 5) must be applied here. Run from the seed after create_all. Each change is
guarded by an inspector check, so fresh databases and repeated runs are safe no-ops.
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

# (table, column, DDL) — additive columns only. Add future one-liners here.
_ADDITIVE_COLUMNS: list[tuple[str, str, str]] = [
    (
        "admin_user",
        "role",
        "ALTER TABLE admin_user ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'admin'",
    ),
]


def ensure_schema(engine: Engine) -> list[str]:
    """Apply any missing additive columns. Returns the list of `table.column` changes made."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    applied: list[str] = []
    with engine.begin() as conn:
        for table, column, ddl in _ADDITIVE_COLUMNS:
            if table not in tables:
                continue  # create_all will build it fresh, already including the column
            columns = {c["name"] for c in inspector.get_columns(table)}
            if column in columns:
                continue
            conn.execute(text(ddl))
            applied.append(f"{table}.{column}")
    return applied
