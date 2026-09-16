"""Verify the deployed public site, snapshot freshness, feeds and privacy mode."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

DEFAULT_SITE = "https://homerzhou6778-tech.github.io/ai-daily/"


def parse_time(value: str) -> datetime:
    """Accept only timezone-aware ISO timestamps, normalized to UTC."""
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamp has no timezone")
    return result.astimezone(timezone.utc)


def inspect_snapshot(news: dict, status: dict, *, now: datetime,
                     minimum_generated_at: str | None = None) -> dict:
    """Separate source degradation from an unusable or unsafe deployment."""
    issues: list[str] = []
    degraded: list[str] = []
    generated = parse_time(news["generated_at"])
    age_hours = (now - generated).total_seconds() / 3600
    if age_hours > 4:
        issues.append("snapshot_older_than_4_hours")
    if generated > now + timedelta(minutes=5):
        issues.append("snapshot_timestamp_in_future")
    if minimum_generated_at and generated < parse_time(minimum_generated_at):
        issues.append("new_deployment_not_visible_yet")
    if status.get("generated_at") != news["generated_at"]:
        issues.append("mixed_snapshot_versions")
    if status.get("profile") != "public-only":
        issues.append("unexpected_public_profile")
    for key in ("agentmail", "x_api", "socialdata", "tikhub"):
        if status.get(key, {}).get("enabled") is not False:
            issues.append(f"integration_not_explicitly_disabled:{key}")

    feeds = status.get("rss_opml", {}).get("feeds", [])
    if len(feeds) != 10 or len({feed.get("feed_url") for feed in feeds}) != 10:
        issues.append("unexpected_rss_inventory")
    healthy = 0
    for feed in feeds:
        if feed.get("ok") is True:
            healthy += 1
        else:
            degraded.append(str(feed.get("feed_title") or "RSS feed"))
    sites = {site["site_id"]: site for site in status.get("sites", [])}
    if set(sites) != {"official_ai", "followbuilders", "opmlrss"}:
        issues.append("unexpected_source_inventory")
    for key in ("official_ai", "followbuilders"):
        source = sites.get(key, {})
        if source.get("ok") is True:
            healthy += 1
        else:
            degraded.append(str(source.get("site_name") or key))
    if healthy < 6:
        issues.append("fewer_than_6_healthy_sources")

    items = news.get("items")
    if not isinstance(items, list) or news.get("total_items") != len(items):
        issues.append("invalid_news_item_count")
    else:
        for item in items:
            try:
                published = parse_time(item["published_at"])
                if not generated - timedelta(hours=24) <= published <= generated:
                    issues.append("item_outside_publication_window")
                    break
            except (KeyError, TypeError, ValueError):
                issues.append("item_without_valid_publication_date")
                break
    return {
        "state": "unhealthy" if issues else "degraded" if degraded else "healthy",
        "generated_at": news["generated_at"],
        "age_hours": round(age_hours, 2),
        "healthy_sources": healthy,
        "configured_sources": 12,
        "ai_items": news.get("total_items"),
        "failed_sources": sorted(degraded),
        "issues": issues,
    }


def fetch_public(site: str, path: str) -> bytes:
    """Read public bytes without supplying authentication or logging bodies."""
    request = Request(site + path, headers={"User-Agent": "AI-Daily-Health/1.0", "Cache-Control": "no-cache"})
    with urlopen(request, timeout=20) as response:
        body = response.read(4 * 1024 * 1024 + 1)
    if len(body) > 4 * 1024 * 1024:
        raise ValueError("Public response exceeds size limit")
    return body


def check_site(site: str, minimum_generated_at: str | None = None) -> dict:
    """Check the homepage, both JSON snapshots and generated RSS concurrently."""
    paths = ("", "data/latest-24h.json", "data/source-status.json", "data/feed.xml")
    with ThreadPoolExecutor(max_workers=4) as pool:
        bodies = dict(zip(paths, pool.map(lambda path: fetch_public(site, path), paths)))
    if b"<html" not in bodies[""][:1000].lower():
        raise ValueError("Homepage is not HTML")
    rss = ET.fromstring(bodies["data/feed.xml"])
    if rss.tag != "rss" or rss.find("channel") is None:
        raise ValueError("Invalid RSS document")
    return inspect_snapshot(
        json.loads(bodies["data/latest-24h.json"]),
        json.loads(bodies["data/source-status.json"]),
        now=datetime.now(timezone.utc), minimum_generated_at=minimum_generated_at,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default=DEFAULT_SITE)
    parser.add_argument("--minimum-generated-at")
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--retry-seconds", type=int, default=15)
    args = parser.parse_args()
    parsed = urlparse(args.site)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        parser.error("Use a public HTTPS site URL without credentials or query parameters")
    if not 1 <= args.attempts <= 6 or not 1 <= args.retry_seconds <= 30:
        parser.error("attempts must be 1..6 and retry-seconds must be 1..30")
    if args.minimum_generated_at:
        parse_time(args.minimum_generated_at)
    for attempt in range(args.attempts):
        try:
            report = check_site(args.site.rstrip("/") + "/", args.minimum_generated_at)
        except Exception as error:
            report = {"state": "unhealthy", "issues": [f"probe_failed:{type(error).__name__}"]}
        if report["state"] != "unhealthy" or attempt + 1 == args.attempts:
            break
        time.sleep(args.retry_seconds)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["state"] == "unhealthy" else 0


if __name__ == "__main__":
    raise SystemExit(main())
