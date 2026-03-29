"""In-app version check against GitHub Releases.

Checks api.github.com for the latest release tag, compares against the
running version, and caches the result for 24 hours in config.json.
Zero GUI dependencies — the QThread worker lives in gui/main_window.py.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

GITHUB_REPO = "sylvanoMTL/kipart_search"


@dataclass
class UpdateInfo:
    """Result of a successful version check."""

    latest_version: str
    release_url: str
    release_notes: str
    check_time: float
    asset_url: str = ""
    asset_size: int = 0


def _compare_versions(current: str, latest: str) -> bool:
    """Return True if *latest* is strictly newer than *current*."""

    def _parse(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in v.split(".") if x.isdigit())

    return _parse(latest) > _parse(current)


def check_for_update(
    current_version: str,
    skipped_version: str | None = None,
) -> UpdateInfo | None:
    """Call GitHub API and return UpdateInfo if a newer release exists.

    Returns None on any failure (network, timeout, parse error), if
    the running version is already current, or if the latest version
    matches *skipped_version*.
    """
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        resp = httpx.get(url, timeout=5.0, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, httpx.TimeoutException, ValueError):
        return None

    tag = data.get("tag_name", "")
    latest = tag.lstrip("v")
    if not latest or not _compare_versions(current_version, latest):
        return None

    if skipped_version and latest == skipped_version:
        return None

    # Resolve platform-specific installer asset
    asset_url = ""
    asset_size = 0
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if sys.platform == "win32" and name.endswith("-setup.exe"):
            asset_url = asset.get("browser_download_url", "")
            asset_size = asset.get("size", 0)
            break
        # elif sys.platform == "darwin" and name.endswith(".dmg"):  # future
        # elif sys.platform == "linux" and name.endswith(".AppImage"):  # future

    return UpdateInfo(
        latest_version=latest,
        release_url=data.get("html_url", ""),
        release_notes=data.get("body", ""),
        check_time=time.time(),
        asset_url=asset_url,
        asset_size=asset_size,
    )


def load_cached_update(config_path: Path) -> UpdateInfo | None:
    """Read cached UpdateInfo from config.json, or None if absent/corrupt."""
    if not config_path.exists():
        return None
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        uc = raw.get("update_check")
        if not uc or not isinstance(uc, dict):
            return None
        return UpdateInfo(
            latest_version=uc["latest_version"],
            release_url=uc["release_url"],
            release_notes=uc.get("release_notes", ""),
            check_time=uc["check_time"],
            asset_url=uc.get("asset_url", ""),
            asset_size=uc.get("asset_size", 0),
        )
    except (json.JSONDecodeError, OSError, KeyError, TypeError):
        return None


def save_update_cache(config_path: Path, info: UpdateInfo) -> None:
    """Persist UpdateInfo into the ``update_check`` key of config.json.

    Reads existing config, merges, and writes back — same pattern as
    ``SourceConfigManager.set_welcome_version()``.
    """
    raw: dict = {}
    if config_path.exists():
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            raw = {}
    raw["update_check"] = asdict(info)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")


def save_skipped_version(config_path: Path, version: str) -> None:
    """Persist a skipped version string into config.json."""
    raw: dict = {}
    if config_path.exists():
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            raw = {}
    raw.setdefault("update_check", {})["skipped_version"] = version
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")


def load_skipped_version(config_path: Path) -> str | None:
    """Read the skipped version from config.json, or None if absent."""
    if not config_path.exists():
        return None
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        return raw.get("update_check", {}).get("skipped_version")
    except (json.JSONDecodeError, OSError):
        return None


def should_check(config_path: Path, ttl_hours: int = 24) -> bool:
    """Return True if no cached check exists or the cache has expired."""
    cached = load_cached_update(config_path)
    if cached is None:
        return True
    age_hours = (time.time() - cached.check_time) / 3600
    return age_hours >= ttl_hours
