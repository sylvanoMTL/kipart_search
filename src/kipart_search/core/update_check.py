"""In-app version check against GitHub Releases."""

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
    skipped: bool = False


def _compare_versions(current: str, latest: str) -> bool:
    """Return True if *latest* is strictly newer than *current*."""

    def _parse(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in v.split(".") if x.isdigit())

    return _parse(latest) > _parse(current)


def check_for_update(
    current_version: str,
    skipped_version: str | None = None,
    skip_policy: str = "none",
) -> UpdateInfo | None:
    """Call GitHub API and return UpdateInfo if a newer release exists.

    Returns None on any failure (network, timeout, parse error), or if
    the running version is already current.  Returns an UpdateInfo with
    ``skipped=True`` when the release is suppressed by *skip_policy*
    ("all") or by *skipped_version* matching (policy "next").
    """
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        resp = httpx.get(url, timeout=5.0, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
        log.info("Update check skipped (no network or API error: %s)", exc)
        return None

    tag = data.get("tag_name", "")
    latest = tag.lstrip("v")
    if not latest or not _compare_versions(current_version, latest):
        return None

    def _skipped_info() -> UpdateInfo:
        return UpdateInfo(
            latest_version=latest,
            release_url=data.get("html_url", ""),
            release_notes=data.get("body", ""),
            check_time=time.time(),
            asset_url="",
            asset_size=0,
            skipped=True,
        )

    if skip_policy == "all":
        return _skipped_info()

    if skipped_version and latest == skipped_version:
        return _skipped_info()

    # -----------------------------------------------------------------------
    # Resolve platform-specific installer asset
    # -----------------------------------------------------------------------
    # Each platform has a different asset naming convention in the GitHub
    # Release.  The build system (build_nuitka.py + CI workflow) produces:
    #   - Windows: kipart-search-{version}-setup.exe    (Inno Setup installer)
    #   - macOS:   kipart-search-{version}-macos.dmg    (disk image, future)
    #   - Linux:   kipart-search-{version}-linux.AppImage (AppImage, future)
    #
    # When a platform is not yet supported, asset_url stays "" and the
    # "Update Now" button is disabled in the dialog with the message:
    # "No installer available for this platform."
    # -----------------------------------------------------------------------
    asset_url = ""
    asset_size = 0
    for asset in data.get("assets", []):
        name = asset.get("name", "")

        # --- Windows (ACTIVE) ---
        if sys.platform == "win32" and name.endswith("-setup.exe"):
            asset_url = asset.get("browser_download_url", "")
            asset_size = asset.get("size", 0)
            break

        # --- macOS (FUTURE) ---
        # Uncomment when macOS builds are shipped via GitHub Releases.
        # The .dmg is opened via subprocess.Popen(["open", path]) in
        # update_shim.launch_installer().
        #
        # if sys.platform == "darwin" and name.endswith(".dmg"):
        #     asset_url = asset.get("browser_download_url", "")
        #     asset_size = asset.get("size", 0)
        #     break

        # --- Linux (FUTURE) ---
        # Uncomment when Linux AppImage builds are shipped.
        # The .AppImage is handled by _linux_replace_appimage() in
        # update_shim.py (chmod +x, replace, relaunch).
        #
        # if sys.platform == "linux" and name.endswith(".AppImage"):
        #     asset_url = asset.get("browser_download_url", "")
        #     asset_size = asset.get("size", 0)
        #     break

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
            skipped=uc.get("skipped", False),
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


def save_skip_policy(config_path: Path, policy: str) -> None:
    """Persist the release skip policy ("none", "next", or "all")."""
    raw: dict = {}
    if config_path.exists():
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            raw = {}
    raw.setdefault("update_check", {})["skip_policy"] = policy
    # Clear skipped_version when switching away from "next"
    if policy != "next":
        raw["update_check"].pop("skipped_version", None)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")


def load_skip_policy(config_path: Path) -> str:
    """Read the skip policy from config.json. Defaults to "none"."""
    if not config_path.exists():
        return "none"
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        policy = raw.get("update_check", {}).get("skip_policy", "none")
        return policy if policy in ("none", "next", "all") else "none"
    except (json.JSONDecodeError, OSError):
        return "none"


def should_check(config_path: Path, ttl_hours: int = 24) -> bool:
    """Return True if no cached check exists or the cache has expired."""
    cached = load_cached_update(config_path)
    if cached is None:
        return True
    age_hours = (time.time() - cached.check_time) / 3600
    return age_hours >= ttl_hours
