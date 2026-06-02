#!/usr/bin/env python3
"""Tech-radar digest generator.

Builds a weekly "what's new in our stack" report by comparing the versions we
pin in requirements*.txt against the latest releases on PyPI, then writes a
Markdown digest to stdout (or --output). The GitHub Actions workflow
.github/workflows/tech-radar.yml posts/updates this digest as a GitHub Issue.

Stdlib only -- no third-party dependencies, no API keys. PyPI's public JSON
API is used for version/release-date lookups.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

# Core stack we actively want to track. Anything pinned but not listed here is
# still reported under "Other pinned packages" so nothing silently drifts.
WATCHLIST = [
    "pandas",
    "numpy",
    "scikit-learn",
    "xgboost",
    "scipy",
    "requests",
    "pyyaml",
    "matplotlib",
    "streamlit",
    "black",
    "ruff",
    "isort",
    "mypy",
    "pytest",
    "bandit",
    "pre-commit",
]

# Captures: name, operator (== >= ~= >), version. Floors (>=, ~=) and exact
# pins (==) are both reported -- a floor lagging far behind latest is exactly
# the kind of "are we keeping up?" signal this digest is meant to surface.
PIN_RE = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(==|>=|~=|>)\s*([0-9][^\s;#,]*)"
)
USER_AGENT = "nfl-betting-system-tech-radar/1.0 (+https://github.com/eagle605/nfl-betting-system)"


def read_pins(*filenames: str) -> Dict[str, Tuple[str, str]]:
    """Parse `name<op>version` constraints into {name: (operator, version)}."""
    pins: Dict[str, Tuple[str, str]] = {}
    for name in filenames:
        path = REPO_ROOT / name
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            match = PIN_RE.match(line)
            if match:
                pins[match.group(1).lower()] = (match.group(2), match.group(3))
    return pins


def fetch_pypi(package: str) -> Optional[Tuple[str, Optional[str]]]:
    """Return (latest_version, iso_release_date) for a package, or None."""
    url = f"https://pypi.org/pypi/{package}/json"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        print(f"  ! could not fetch {package}: {exc}", file=sys.stderr)
        return None

    version = data.get("info", {}).get("version")
    if not version:
        return None

    release_date: Optional[str] = None
    files = data.get("releases", {}).get(version) or []
    for file_info in files:
        uploaded = file_info.get("upload_time_iso_8601") or file_info.get("upload_time")
        if uploaded:
            release_date = uploaded[:10]
            break
    return version, release_date


def parse_version(version: str) -> Tuple[int, ...]:
    parts: List[int] = []
    for chunk in version.split(".")[:3]:
        digits = re.match(r"\d+", chunk)
        parts.append(int(digits.group()) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def bump_kind(pinned: str, latest: str) -> str:
    """Classify the gap between pinned and latest as major/minor/patch/none."""
    p, l = parse_version(pinned), parse_version(latest)
    if l <= p:
        return "none"
    if l[0] != p[0]:
        return "major"
    if l[1] != p[1]:
        return "minor"
    return "patch"


BADGE = {
    "major": "🔴 major",
    "minor": "🟡 minor",
    "patch": "🟢 patch",
    "none": "✅ current",
}


def status_cell(operator: str, kind: str) -> str:
    """A floor (>=, ~=) being behind latest is expected, not a failure; an exact
    pin (==) being behind is an actionable upgrade."""
    if kind == "none":
        return BADGE["none"]
    if operator == "==":
        return BADGE[kind]
    return f"ℹ️ {kind} behind floor"


def build_report(pins: Dict[str, Tuple[str, str]]) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    watched_rows: List[str] = []
    other_rows: List[str] = []
    outdated = {"major": 0, "minor": 0, "patch": 0}

    watch_set = {w.lower() for w in WATCHLIST}
    # Watched packages first (in declared order), then any remaining pins.
    ordered = [w.lower() for w in WATCHLIST if w.lower() in pins]
    ordered += sorted(name for name in pins if name not in watch_set)

    for name in ordered:
        operator, version = pins[name]
        constraint = f"{operator}{version}"
        result = fetch_pypi(name)
        if result is None:
            row = f"| `{name}` | {constraint} | _lookup failed_ | — | — |"
        else:
            latest, released = result
            kind = bump_kind(version, latest)
            # Only exact (==) pins behind latest count as actionable upgrades.
            if kind != "none" and operator == "==":
                outdated[kind] += 1
            row = (
                f"| `{name}` | {constraint} | {latest} | "
                f"{released or '—'} | {status_cell(operator, kind)} |"
            )
        if name in watch_set:
            watched_rows.append(row)
        else:
            other_rows.append(row)

    header = (
        "| Package | Constraint | Latest | Released | Status |\n"
        "| --- | --- | --- | --- | --- |\n"
    )
    lines = [
        f"## 📡 Tech Radar — {today}",
        "",
        "Weekly snapshot of our pinned stack vs. the latest releases on PyPI. "
        "Dependabot opens the actual upgrade PRs; this digest is the at-a-glance view.",
        "",
        f"**Exact (`==`) pins behind latest:** 🔴 {outdated['major']} major · "
        f"🟡 {outdated['minor']} minor · 🟢 {outdated['patch']} patch  "
        f"_(floors shown with ℹ️ are informational)_",
        "",
        "### Core stack",
        "",
        (
            header + "\n".join(watched_rows)
            if watched_rows
            else "_No watched packages pinned._"
        ),
    ]
    if other_rows:
        lines += [
            "",
            "### Other pinned packages",
            "",
            header + "\n".join(other_rows),
        ]
    lines += [
        "",
        "---",
        "_Generated by `scripts/tech_radar.py` via the `tech-radar` workflow. "
        "Re-run anytime with `python scripts/tech_radar.py`._",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the digest here instead of stdout.",
    )
    args = parser.parse_args()

    pins = read_pins("requirements.txt", "requirements-dev.txt")
    if not pins:
        print("No pinned packages found in requirements files.", file=sys.stderr)
        return 1

    report = build_report(pins)
    if args.output:
        args.output.write_text(report + "\n")
        print(f"Wrote digest to {args.output}", file=sys.stderr)
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
