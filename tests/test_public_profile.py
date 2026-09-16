"""Verify the deployed profile cannot enter private or paid integrations."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import update_news as radar
from scripts.build_site import PUBLIC_DATA, stage_site

NOW = datetime(2026, 9, 16, 3, 0, tzinfo=timezone.utc)


def forbidden(*args, **kwargs):
    raise AssertionError("An excluded integration was called")


def install_public_fixture(monkeypatch, tmp_path, healthy=10):
    monkeypatch.setattr(radar, "utc_now", lambda: NOW)
    monkeypatch.setattr(sys, "argv", ["update_news", "--public-only", "--output-dir", str(tmp_path)])
    for name in (
        "maybe_fetch_agentmail_digest", "maybe_fetch_x_api_updates",
        "maybe_fetch_socialdata_updates", "maybe_fetch_tikhub_updates",
        "fetch_waytoagi_recent_7d", "fetch_service_status",
        "add_title_enhancements", "add_recommend_reasons", "translate_to_zh_cn",
        "translate_to_zh_deepseek",
    ):
        monkeypatch.setattr(radar, name, forbidden)
    for key in ("EMAIL_DIGEST_ENABLED", "X_API_ENABLED", "SOCIALDATA_ENABLED", "TIKHUB_ENABLED"):
        monkeypatch.setenv(key, "1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic-test-value")
    monkeypatch.setattr(radar, "collect_all", lambda session, now, *, public_only: ([], []))
    items = [radar.RawItem(
        site_id="opmlrss", site_name="OPML RSS", source="OpenAI News",
        title="OpenAI releases a new Codex model", url="https://openai.com/index/test-model/",
        published_at=NOW-timedelta(hours=1), meta={},
    ), radar.RawItem(
        site_id="opmlrss", site_name="OPML RSS", source="OpenAI News",
        title="OpenAI future publication", url="https://openai.com/index/future/",
        published_at=NOW+timedelta(days=1), meta={},
    )]
    def feeds(now, path, max_feeds=0, *, strict=False):
        assert path.name == "follow.example.opml"
        assert strict
        return items, {"site_id": "opmlrss", "site_name": "OPML RSS", "ok": healthy > 0, "item_count": 2}, [
            {"ok": i < healthy, "feed_url": f"https://example.com/{i}", "item_count": 1}
            for i in range(10)
        ]
    monkeypatch.setattr(radar, "fetch_opml_rss", feeds)


def test_public_mode_ignores_private_environment_and_future_news(monkeypatch, tmp_path):
    install_public_fixture(monkeypatch, tmp_path)
    (tmp_path / "archive.json").write_text(json.dumps({"items": [{
        "id": "old-private", "site_id": "agentmail", "source": "Private inbox",
        "title": "Private OpenAI newsletter", "url": "https://example.com/private",
        "published_at": NOW.isoformat(), "last_seen_at": NOW.isoformat(),
    }]}), "utf-8")
    assert radar.main() == 0
    status = json.loads((tmp_path / "source-status.json").read_text("utf-8"))
    assert all(not status[key]["enabled"] for key in ("agentmail", "x_api", "socialdata", "tikhub"))
    assert not (tmp_path / "email-digest.json").exists()
    latest = json.loads((tmp_path / "latest-24h.json").read_text("utf-8"))
    assert len(latest["items"]) == 1
    assert latest["items"][0]["url"] == "https://openai.com/index/test-model"
    assert "old-private" not in (tmp_path / "archive.json").read_text("utf-8")


def test_broad_outage_does_not_replace_good_snapshot(monkeypatch, tmp_path):
    install_public_fixture(monkeypatch, tmp_path, healthy=2)
    previous = tmp_path / "latest-24h.json"
    previous.write_text('{"previous":true}', "utf-8")
    with pytest.raises(RuntimeError, match="keeping the previous deployment"):
        radar.main()
    assert previous.read_text("utf-8") == '{"previous":true}'


def test_public_mode_rejects_private_opml(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["update", "--public-only", "--rss-opml", "private.opml"])
    with pytest.raises(SystemExit):
        radar.main()


def test_public_collector_only_calls_selected_adapters(monkeypatch):
    for name in ("fetch_official_ai_updates", "fetch_ai_breakfast", "fetch_curated_ai_media", "fetch_aihot"):
        monkeypatch.setattr(radar, name, forbidden)
    called = []
    monkeypatch.setattr(radar, "fetch_anthropic_public", lambda *args: called.append("anthropic") or [])
    monkeypatch.setattr(radar, "fetch_follow_builders", lambda *args: called.append("builders") or [])
    _, statuses = radar.collect_all(None, NOW, public_only=True)
    assert called == ["anthropic", "builders"]
    assert len(statuses) == 2


def test_html_error_page_is_not_a_healthy_feed(monkeypatch, tmp_path):
    opml = tmp_path / "example.opml"
    opml.write_text('<opml><body><outline title="Demo" xmlUrl="https://example.com/rss" /></body></opml>', "utf-8")
    response = SimpleNamespace(content=b"<html><body>Access denied</body></html>", raise_for_status=lambda: None)
    monkeypatch.setattr(radar.requests, "get", lambda *args, **kwargs: response)
    _, summary, feeds = radar.fetch_opml_rss(NOW, opml, strict=True)
    assert not summary["ok"]
    assert not feeds[0]["ok"]


def test_deployment_allowlist_excludes_private_files(tmp_path):
    root = tmp_path / "project"
    (root / "data").mkdir(parents=True)
    for name in PUBLIC_DATA:
        (root / "data" / name).write_text("{}", "utf-8")
    (root / "data/latest-24h.json").write_text(json.dumps({"generated_at": NOW.isoformat(), "items": []}), "utf-8")
    (root / "data/source-status.json").write_text('{"profile":"public-only"}', "utf-8")
    (root / "data/email-digest.json").write_text("synthetic private fixture", "utf-8")
    (root / "data/archive.json").write_text("not a published file", "utf-8")
    (root / ".env").write_text("synthetic fixture", "utf-8")
    for name in ("index.html", "site.webmanifest"):
        (root / name).write_text("", "utf-8")
    for name in ("assets", "classic"):
        (root / name).mkdir()
    destination = tmp_path / "published"
    stage_site(root, destination)
    assert not (destination / ".env").exists()
    assert not (destination / "data/email-digest.json").exists()
    assert not (destination / "data/archive.json").exists()
    (root / "data/source-status.json").write_text('{"profile":"public-only","agentmail":{"enabled":true}}', "utf-8")
    with pytest.raises(ValueError, match="public-only"):
        stage_site(root, tmp_path / "refused")
