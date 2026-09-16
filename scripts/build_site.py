"""Stage only the static site and approved public JSON files for GitHub Pages."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

PUBLIC_DATA = (
    "latest-24h.json", "latest-24h-all.json", "source-status.json",
    "daily-brief.json", "stories-merged.json", "waytoagi-7d.json",
    "service-status.json", "feed.xml",
)


def stage_site(root: Path, destination: Path) -> None:
    """Create a fresh deployment directory; exclude raw archives and email files."""
    root = root.resolve()
    destination = destination.resolve()
    if destination.exists():
        raise ValueError("Deployment output must be a new directory")
    latest = json.loads((root / "data/latest-24h.json").read_text("utf-8"))
    status = json.loads((root / "data/source-status.json").read_text("utf-8"))
    if status.get("profile") != "public-only":
        raise ValueError("Only the public-only profile may be published")
    if not latest.get("generated_at") or not isinstance(latest.get("items"), list):
        raise ValueError("Invalid public snapshot")
    for key in ("agentmail", "x_api", "socialdata", "tikhub"):
        if status.get(key, {}).get("enabled"):
            raise ValueError("Only the public-only profile may be published")
    for filename in PUBLIC_DATA:
        if not (root / "data" / filename).is_file():
            raise ValueError(f"Missing public output: {filename}")
    destination.mkdir(parents=True)
    for name in ("index.html", "site.webmanifest"):
        shutil.copy2(root / name, destination / name)
    for name in ("assets", "classic"):
        shutil.copytree(root / name, destination / name)
    (destination / "data").mkdir()
    for name in PUBLIC_DATA:
        shutil.copy2(root / "data" / name, destination / "data" / name)
    # Legacy UI requests this optional file even when persona scoring is off.
    (destination / "data/top3-personas.json").write_text(
        json.dumps({"generated_at": latest["generated_at"], "items": []}), "utf-8"
    )
    (destination / ".nojekyll").touch()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="_site")
    args = parser.parse_args()
    stage_site(Path(__file__).resolve().parents[1], Path(args.output))
