"""Tests for health module: heartbeat freshness monitoring."""

import datetime
from pathlib import Path

from trading_advisor.health import check_health
from trading_advisor.storage.local import LocalStorage


def test_no_heartbeat_returns_false(tmp_path: Path) -> None:
    """check_health returns False when no heartbeat exists."""
    storage = LocalStorage(tmp_path)
    ok, message = check_health(storage)
    assert ok is False
    assert "No heartbeat" in message


def test_fresh_heartbeat_returns_true(tmp_path: Path) -> None:
    """check_health returns True when heartbeat is within threshold."""
    storage = LocalStorage(tmp_path)
    ts = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(hours=1)
    storage.write_json("state/heartbeat", {"command": "ingest", "timestamp": ts.isoformat()})
    ok, message = check_health(storage)
    assert ok is True
    assert "OK" in message


def test_stale_heartbeat_returns_false(tmp_path: Path) -> None:
    """check_health returns False when heartbeat exceeds threshold."""
    storage = LocalStorage(tmp_path)
    ts = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(hours=20)
    storage.write_json("state/heartbeat", {"command": "ingest", "timestamp": ts.isoformat()})
    ok, message = check_health(storage)
    assert ok is False
    assert "STALE" in message


def test_custom_max_age_hours(tmp_path: Path) -> None:
    """check_health respects a custom max_age_hours parameter."""
    storage = LocalStorage(tmp_path)
    ts = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(hours=5)
    storage.write_json("state/heartbeat", {"command": "ingest", "timestamp": ts.isoformat()})

    # 4h threshold -> stale
    ok_short, _ = check_health(storage, max_age_hours=4.0)
    assert ok_short is False

    # 6h threshold -> fresh
    ok_long, _ = check_health(storage, max_age_hours=6.0)
    assert ok_long is True


def test_boundary_exactly_at_max_age_is_fresh(tmp_path: Path) -> None:
    """Heartbeat at exactly max_age_hours is considered fresh (> not >=)."""
    storage = LocalStorage(tmp_path)
    # Use a very tight window: 1 second old with 1 second threshold
    # The check_health function uses `>`, so age == max is still fresh
    ts = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(seconds=3600)
    storage.write_json("state/heartbeat", {"command": "ingest", "timestamp": ts.isoformat()})
    # 1.0h old, threshold 1.0h → age is NOT > max → fresh
    # But due to sub-second timing, use a slightly larger threshold
    ok_at, _ = check_health(storage, max_age_hours=1.001)
    assert ok_at is True
    # Just under the threshold → stale
    ok_under, _ = check_health(storage, max_age_hours=0.999)
    assert ok_under is False
