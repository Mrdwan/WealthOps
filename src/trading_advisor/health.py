"""System health check: heartbeat freshness monitoring."""

import datetime

from trading_advisor.storage.base import StorageBackend

_MAX_AGE_HOURS: float = 14.0


def check_health(
    storage: StorageBackend,
    *,
    max_age_hours: float = _MAX_AGE_HOURS,
) -> tuple[bool, str]:
    """Check heartbeat freshness.

    Reads the ``state/heartbeat`` JSON from storage and verifies the
    timestamp is within *max_age_hours* of the current time.

    Args:
        storage: Backend to read heartbeat state from.
        max_age_hours: Maximum acceptable heartbeat age in hours.

    Returns:
        Tuple of ``(ok, message)`` where *ok* is ``True`` when the
        heartbeat is fresh and ``False`` when stale or missing.
    """
    if not storage.exists("state/heartbeat"):
        return False, "No heartbeat found"
    heartbeat = storage.read_json("state/heartbeat")
    ts = datetime.datetime.fromisoformat(str(heartbeat["timestamp"]))
    now = datetime.datetime.now(tz=datetime.UTC)
    age_hours = (now - ts).total_seconds() / 3600
    if age_hours > max_age_hours:
        return False, f"STALE -- last heartbeat {age_hours:.1f}h ago (threshold: {max_age_hours}h)"
    return True, f"OK -- last heartbeat {age_hours:.1f}h ago"
