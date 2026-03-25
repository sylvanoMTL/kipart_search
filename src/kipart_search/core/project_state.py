"""Per-project verification state persistence.

Zero GUI dependencies. Pure functions operating on dicts and JSON files.
Stores user review decisions (Verified / Attention / Rejected) per component,
in a `.kipart-search/` folder alongside the KiCad project.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from kipart_search.core.models import UserVerificationStatus

log = logging.getLogger(__name__)

_FORMAT_VERSION = 1
_STATE_DIR = ".kipart-search"
_STATE_FILE = "verification-state.json"


def project_state_path(project_dir: Path) -> Path:
    """Path to a project's verification state JSON.

    Location: {project_dir}/.kipart-search/verification-state.json
    Creates the .kipart-search directory if needed.
    """
    d = project_dir / _STATE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d / _STATE_FILE


def load_user_statuses(project_dir: Path) -> dict[str, UserVerificationStatus]:
    """Read verification-state.json. Returns empty dict if file doesn't exist."""
    path = project_state_path(project_dir)
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Failed to read project state %s: %s", path, exc)
        return {}

    statuses: dict[str, UserVerificationStatus] = {}
    for ref, value in data.get("statuses", {}).items():
        try:
            status = UserVerificationStatus(value)
            if status != UserVerificationStatus.NONE:
                statuses[ref] = status
        except ValueError:
            log.warning("Unknown user status '%s' for %s — skipping", value, ref)
    return statuses


def save_user_statuses(
    project_dir: Path, statuses: dict[str, UserVerificationStatus]
) -> None:
    """Atomic write: write to .tmp file, then rename. Only saves non-NONE statuses."""
    path = project_state_path(project_dir)

    # Filter out NONE entries (sparse storage)
    filtered = {
        ref: status.value
        for ref, status in statuses.items()
        if status != UserVerificationStatus.NONE
    }

    data = {
        "format_version": _FORMAT_VERSION,
        "statuses": filtered,
    }

    tmp_path = path.with_suffix(".tmp")
    try:
        tmp_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(path)
    except OSError as exc:
        log.warning("Failed to save project state %s: %s", path, exc)
        # Clean up temp file if rename failed
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
