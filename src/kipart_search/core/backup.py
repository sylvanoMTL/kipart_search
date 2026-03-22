"""Backup system and undo log for KiCad write-back operations."""

from __future__ import annotations

import csv
import json
import logging
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class BackupEntry:
    """Metadata for a single backup snapshot."""
    path: Path
    project: str
    timestamp: str
    component_count: int
    change_count: int


class BackupManager:
    """Manages session backups and per-field undo logs.

    One backup per session: the first write triggers a snapshot of all
    component state.  Subsequent writes in the same session only append
    to the undo log CSV.
    """

    def __init__(self, backup_dir: Path | None = None):
        self._backup_dir = backup_dir or Path.home() / ".kipart-search" / "backups"
        self._session_backup_dir: Path | None = None
        self._sch_backed_up: bool = False

    # -- Public API --

    def ensure_session_backup(
        self, project_name: str, components: list[dict],
    ) -> Path:
        """Create a timestamped backup on first call per session.

        *components* should be a list of dicts with at least
        ``reference``, ``value``, ``footprint``, ``mpn``, ``datasheet``
        and ``extra_fields`` keys (i.e. the output of
        ``dataclasses.asdict(board_component)``).

        Returns the backup directory path.  Second+ calls in the same
        session return the existing path without writing again.
        """
        if self._session_backup_dir is not None:
            return self._session_backup_dir

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        backup_path = self._backup_dir / project_name / timestamp
        backup_path.mkdir(parents=True, exist_ok=True)

        # Write component snapshot
        components_file = backup_path / "components.json"
        components_file.write_text(json.dumps(components, indent=2), encoding="utf-8")

        self._session_backup_dir = backup_path
        log.info(
            "Session backup created: %s (%d components)",
            backup_path, len(components),
        )
        return backup_path

    def backup_schematic_files(
        self, project_name: str, sch_paths: list[Path],
    ) -> Path:
        """Copy all .kicad_sch files to a timestamped backup directory.

        One schematic backup per session: second+ calls return the
        existing path without copying again.  Uses ``shutil.copy2()``
        to preserve timestamps.

        If a session backup directory already exists (e.g. from
        ``ensure_session_backup``), the schematic files are copied
        into that same directory rather than creating a new one.

        Returns the backup directory path.
        """
        if self._sch_backed_up and self._session_backup_dir is not None:
            return self._session_backup_dir

        # Reuse existing session dir or create a new one
        if self._session_backup_dir is not None:
            backup_path = self._session_backup_dir
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
            backup_path = self._backup_dir / project_name / timestamp
            backup_path.mkdir(parents=True, exist_ok=True)
            self._session_backup_dir = backup_path

        for sch in sch_paths:
            if sch.exists():
                shutil.copy2(sch, backup_path / sch.name)

        self._sch_backed_up = True
        log.info(
            "Schematic backup created: %s (%d files)",
            backup_path, len(sch_paths),
        )
        return backup_path

    def log_field_change(
        self,
        project_name: str,
        reference: str,
        field_name: str,
        old_value: str,
        new_value: str,
    ) -> None:
        """Append a field change to the undo log CSV.

        If no session backup exists yet (standalone mode), the CSV is
        written to ``{backup_dir}/{project_name}/standalone/``.
        """
        if self._session_backup_dir is not None:
            csv_dir = self._session_backup_dir
        else:
            csv_dir = self._backup_dir / project_name / "standalone"
            csv_dir.mkdir(parents=True, exist_ok=True)

        csv_path = csv_dir / "undo_log.csv"
        write_header = not csv_path.exists() or csv_path.stat().st_size == 0

        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(["timestamp", "reference", "field", "old_value", "new_value"])
            writer.writerow([
                datetime.now().isoformat(timespec="seconds"),
                reference,
                field_name,
                old_value,
                new_value,
            ])

    def list_backups(self, project_name: str) -> list[BackupEntry]:
        """Return available backups for *project_name*, newest first."""
        project_dir = self._backup_dir / project_name
        if not project_dir.is_dir():
            return []

        entries: list[BackupEntry] = []
        for child in project_dir.iterdir():
            if not child.is_dir():
                continue
            # Skip the standalone log dir
            if child.name == "standalone":
                continue

            comp_file = child / "components.json"
            csv_file = child / "undo_log.csv"

            component_count = 0
            if comp_file.exists():
                try:
                    data = json.loads(comp_file.read_text(encoding="utf-8"))
                    component_count = len(data)
                except Exception:
                    pass

            change_count = 0
            if csv_file.exists():
                try:
                    with open(csv_file, encoding="utf-8") as f:
                        reader = csv.reader(f)
                        rows = list(reader)
                        # Subtract header row
                        change_count = max(0, len(rows) - 1)
                except Exception:
                    pass

            entries.append(BackupEntry(
                path=child,
                project=project_name,
                timestamp=child.name,
                component_count=component_count,
                change_count=change_count,
            ))

        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries

    def load_backup(self, backup_path: Path) -> list[dict]:
        """Read components.json from a backup directory."""
        comp_file = backup_path / "components.json"
        if not comp_file.exists():
            log.warning("No components.json in %s", backup_path)
            return []
        try:
            return json.loads(comp_file.read_text(encoding="utf-8"))
        except Exception as exc:
            log.error("Failed to load backup %s: %s", backup_path, exc)
            return []

    def reset_session(self) -> None:
        """Clear session state so the next write triggers a new backup."""
        self._session_backup_dir = None
        self._sch_backed_up = False
        log.info("Backup session reset — next write will create a new backup")
