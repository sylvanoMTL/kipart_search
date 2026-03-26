"""Centralised path resolution for all user data.

Every module that needs a filesystem path to user data MUST go through
this module.  No module should ever construct ~/.kipart-search/ directly.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import platformdirs

log = logging.getLogger(__name__)

_LEGACY_DIR = Path.home() / ".kipart-search"


def data_dir() -> Path:
    """Base data directory. Creates if needed."""
    d = Path(platformdirs.user_data_dir("KiPartSearch", appauthor=False))
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    """Path to config.json."""
    return data_dir() / "config.json"


def cache_path() -> Path:
    """Path to the SQLite query cache."""
    return data_dir() / "cache.db"


def jlcpcb_dir() -> Path:
    """Directory for JLCPCB database files. Creates if needed."""
    d = data_dir() / "jlcpcb"
    d.mkdir(parents=True, exist_ok=True)
    return d


def backups_dir() -> Path:
    """Standalone-mode fallback backup directory. Creates if needed.

    When connected to a KiCad project, backups go to
    ``{project_dir}/.kipart-search/backups/`` instead (see main_window.py).
    This function is only used when no project directory is known.
    """
    d = data_dir() / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def templates_dir() -> Path:
    """BOM export templates directory. Creates if needed."""
    d = data_dir() / "templates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def migrate_legacy_data() -> None:
    """One-time migration from ~/.kipart-search/ to platformdirs location.

    Triggers when the legacy directory exists AND the new location is
    empty or missing.  Per-file strategy: copy2 → verify size → unlink old.
    On any per-file failure, both copies are preserved and a warning is logged.
    """
    if not _LEGACY_DIR.is_dir():
        return

    new_root = data_dir()

    # Only migrate if new location has no files yet (empty subdirs don't count)
    if any(f.is_file() for f in new_root.rglob("*")):
        log.debug("New data dir already has files — skipping migration")
        return

    log.info("Migrating data from %s to %s", _LEGACY_DIR, new_root)
    migrated = 0
    failed = 0

    for old_file in _LEGACY_DIR.rglob("*"):
        if not old_file.is_file():
            continue

        relative = old_file.relative_to(_LEGACY_DIR)
        new_file = new_root / relative
        new_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            shutil.copy2(old_file, new_file)
            if new_file.stat().st_size != old_file.stat().st_size:
                log.warning("Size mismatch after copy: %s — keeping both", relative)
                failed += 1
                continue
            old_file.unlink()
            migrated += 1
        except OSError as exc:
            log.warning("Failed to migrate %s: %s — keeping both copies", relative, exc)
            failed += 1

    # Clean up empty directories in old tree (bottom-up)
    for old_dir in sorted(_LEGACY_DIR.rglob("*"), reverse=True):
        if old_dir.is_dir():
            try:
                old_dir.rmdir()  # only succeeds if empty
            except OSError:
                pass
    # Try to remove the legacy root itself
    try:
        _LEGACY_DIR.rmdir()
    except OSError:
        pass

    if failed:
        log.warning(
            "Partial migration: %d files moved, %d failed — old dir preserved",
            migrated, failed,
        )
    else:
        log.info("Migration complete: %d files moved", migrated)
