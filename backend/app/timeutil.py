from datetime import datetime, timezone


def to_naive_utc(dt: datetime | None) -> datetime | None:
    """Normalize any datetime to naive UTC (MySQL DATETIME drops tzinfo silently)."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
