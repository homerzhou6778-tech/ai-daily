"""Health checks must detect stale, mixed, private and partially failed snapshots."""
from datetime import datetime, timedelta, timezone

import pytest

from scripts.check_health import inspect_snapshot

NOW = datetime(2026, 9, 16, 4, 0, tzinfo=timezone.utc)


@pytest.fixture
def snapshot():
    timestamp = NOW.isoformat()
    news = {"generated_at": timestamp, "total_items": 0, "items": []}
    status = {
        "generated_at": timestamp, "profile": "public-only",
        "rss_opml": {"feeds": [{"feed_url": f"https://example.com/{i}", "feed_title": f"feed-{i}", "ok": True} for i in range(10)]},
        "sites": [{"site_id": key, "ok": True} for key in ("official_ai", "followbuilders", "opmlrss")],
        **{key: {"enabled": False} for key in ("agentmail", "x_api", "socialdata", "tikhub")},
    }
    return news, status


def test_healthy_quiet_day_is_valid(snapshot):
    result = inspect_snapshot(*snapshot, now=NOW)
    assert result["state"] == "healthy"
    assert result["healthy_sources"] == 12


def test_stale_and_old_deployment_are_detected(snapshot):
    result = inspect_snapshot(*snapshot, now=NOW+timedelta(hours=5), minimum_generated_at=(NOW+timedelta(minutes=1)).isoformat())
    assert result["state"] == "unhealthy"
    assert result["issues"] == ["snapshot_older_than_4_hours", "new_deployment_not_visible_yet"]


def test_partial_failure_is_degraded_not_total_outage(snapshot):
    snapshot[1]["rss_opml"]["feeds"][0]["ok"] = False
    result = inspect_snapshot(*snapshot, now=NOW)
    assert result["state"] == "degraded"
    assert result["healthy_sources"] == 11
    assert result["failed_sources"] == ["feed-0"]


@pytest.mark.parametrize("key", ["agentmail", "x_api", "socialdata", "tikhub"])
def test_private_or_paid_mode_is_not_healthy(snapshot, key):
    snapshot[1][key]["enabled"] = True
    result = inspect_snapshot(*snapshot, now=NOW)
    assert result["state"] == "unhealthy"
    assert f"integration_not_explicitly_disabled:{key}" in result["issues"]


def test_mixed_cdn_snapshots_are_rejected(snapshot):
    snapshot[1]["generated_at"] = (NOW-timedelta(hours=1)).isoformat()
    assert "mixed_snapshot_versions" in inspect_snapshot(*snapshot, now=NOW)["issues"]


def test_old_articles_cannot_appear_as_today(snapshot):
    snapshot[0]["items"] = [{"published_at": (NOW-timedelta(days=2)).isoformat()}]
    snapshot[0]["total_items"] = 1
    assert "item_outside_publication_window" in inspect_snapshot(*snapshot, now=NOW)["issues"]
