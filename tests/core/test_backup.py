"""Tests for core/backup.py — BackupManager."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from kipart_search.core.backup import BackupManager, BackupEntry


SAMPLE_COMPONENTS = [
    {
        "reference": "C1",
        "value": "100nF",
        "footprint": "C_0805_2012Metric",
        "mpn": "GRM21BR71C104KA01L",
        "datasheet": "https://example.com/ds.pdf",
        "extra_fields": {"manufacturer": "Murata"},
    },
    {
        "reference": "R1",
        "value": "10k",
        "footprint": "R_0402_1005Metric",
        "mpn": "",
        "datasheet": "",
        "extra_fields": {},
    },
]


class TestEnsureSessionBackup:
    """AC #1: first call creates dir + components.json, second returns same path."""

    def test_first_call_creates_snapshot(self, tmp_path: Path):
        mgr = BackupManager(backup_dir=tmp_path)
        path = mgr.ensure_session_backup("my-board", SAMPLE_COMPONENTS)

        assert path.is_dir()
        comp_file = path / "components.json"
        assert comp_file.exists()

        data = json.loads(comp_file.read_text(encoding="utf-8"))
        assert len(data) == 2
        assert data[0]["reference"] == "C1"

    def test_second_call_returns_same_path(self, tmp_path: Path):
        mgr = BackupManager(backup_dir=tmp_path)
        path1 = mgr.ensure_session_backup("my-board", SAMPLE_COMPONENTS)
        path2 = mgr.ensure_session_backup("my-board", SAMPLE_COMPONENTS)

        assert path1 == path2
        # Only one directory should exist under the project folder
        dirs = [d for d in (tmp_path / "my-board").iterdir() if d.is_dir()]
        assert len(dirs) == 1

    def test_backup_dir_structure(self, tmp_path: Path):
        mgr = BackupManager(backup_dir=tmp_path)
        path = mgr.ensure_session_backup("test-project", SAMPLE_COMPONENTS)

        # Path should be: tmp_path / test-project / YYYY-MM-DD_HHMM
        assert path.parent.name == "test-project"
        assert path.parent.parent == tmp_path


class TestLogFieldChange:
    """AC #2: appends row to CSV with correct columns."""

    def test_creates_csv_with_header(self, tmp_path: Path):
        mgr = BackupManager(backup_dir=tmp_path)
        mgr.ensure_session_backup("proj", SAMPLE_COMPONENTS)
        mgr.log_field_change("proj", "C1", "MPN", "", "GRM21BR71C104KA01L")

        csv_path = mgr._session_backup_dir / "undo_log.csv"
        assert csv_path.exists()

        with open(csv_path, encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert rows[0] == ["timestamp", "reference", "field", "old_value", "new_value"]
        assert rows[1][1] == "C1"
        assert rows[1][2] == "MPN"
        assert rows[1][3] == ""
        assert rows[1][4] == "GRM21BR71C104KA01L"

    def test_appends_multiple_rows(self, tmp_path: Path):
        mgr = BackupManager(backup_dir=tmp_path)
        mgr.ensure_session_backup("proj", SAMPLE_COMPONENTS)
        mgr.log_field_change("proj", "C1", "MPN", "", "ABC123")
        mgr.log_field_change("proj", "R1", "MPN", "", "DEF456")

        csv_path = mgr._session_backup_dir / "undo_log.csv"
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert len(rows) == 3  # header + 2 data rows

    def test_standalone_mode_writes_to_standalone_dir(self, tmp_path: Path):
        """Standalone mode: no session backup, CSV goes to standalone/ dir."""
        mgr = BackupManager(backup_dir=tmp_path)
        # Do NOT call ensure_session_backup — simulates standalone mode
        mgr.log_field_change("proj", "C1", "MPN", "", "ABC123")

        csv_path = tmp_path / "proj" / "standalone" / "undo_log.csv"
        assert csv_path.exists()

        with open(csv_path, encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert len(rows) == 2  # header + 1 data row


class TestListBackups:
    """AC #3: returns sorted list, newest first."""

    def test_returns_sorted_list(self, tmp_path: Path):
        mgr = BackupManager(backup_dir=tmp_path)

        # Create two fake backup dirs
        proj_dir = tmp_path / "my-proj"
        for ts in ["2026-03-18_0900", "2026-03-19_1430"]:
            d = proj_dir / ts
            d.mkdir(parents=True)
            (d / "components.json").write_text(json.dumps(SAMPLE_COMPONENTS))

        entries = mgr.list_backups("my-proj")
        assert len(entries) == 2
        assert entries[0].timestamp == "2026-03-19_1430"  # newest first
        assert entries[1].timestamp == "2026-03-18_0900"
        assert entries[0].component_count == 2

    def test_empty_backup_dir(self, tmp_path: Path):
        mgr = BackupManager(backup_dir=tmp_path)
        entries = mgr.list_backups("no-such-project")
        assert entries == []

    def test_skips_standalone_dir(self, tmp_path: Path):
        mgr = BackupManager(backup_dir=tmp_path)
        proj_dir = tmp_path / "proj"
        (proj_dir / "standalone").mkdir(parents=True)
        (proj_dir / "2026-03-19_1430").mkdir(parents=True)
        (proj_dir / "2026-03-19_1430" / "components.json").write_text("[]")

        entries = mgr.list_backups("proj")
        assert len(entries) == 1
        assert entries[0].timestamp == "2026-03-19_1430"

    def test_counts_changes_from_csv(self, tmp_path: Path):
        mgr = BackupManager(backup_dir=tmp_path)
        d = tmp_path / "proj" / "2026-03-19_1430"
        d.mkdir(parents=True)
        (d / "components.json").write_text("[]")
        csv_path = d / "undo_log.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "reference", "field", "old_value", "new_value"])
            writer.writerow(["2026-03-19T14:30:15", "C1", "MPN", "", "ABC"])
            writer.writerow(["2026-03-19T14:31:00", "R1", "MPN", "", "DEF"])

        entries = mgr.list_backups("proj")
        assert entries[0].change_count == 2


class TestLoadBackup:

    def test_loads_components_json(self, tmp_path: Path):
        d = tmp_path / "backup1"
        d.mkdir()
        (d / "components.json").write_text(json.dumps(SAMPLE_COMPONENTS))

        mgr = BackupManager(backup_dir=tmp_path)
        data = mgr.load_backup(d)
        assert len(data) == 2
        assert data[0]["reference"] == "C1"

    def test_missing_components_json(self, tmp_path: Path):
        d = tmp_path / "empty-backup"
        d.mkdir()

        mgr = BackupManager(backup_dir=tmp_path)
        data = mgr.load_backup(d)
        assert data == []

    def test_corrupted_components_json(self, tmp_path: Path):
        d = tmp_path / "corrupt"
        d.mkdir()
        (d / "components.json").write_text("not valid json {{{")

        mgr = BackupManager(backup_dir=tmp_path)
        data = mgr.load_backup(d)
        assert data == []


class TestBackupSchematicFiles:
    """Tests for backup_schematic_files() — Story 5.7."""

    def test_copies_schematic_files(self, tmp_path: Path):
        mgr = BackupManager(backup_dir=tmp_path / "backups")

        # Create fake schematic files
        sch_dir = tmp_path / "project"
        sch_dir.mkdir()
        sch1 = sch_dir / "main.kicad_sch"
        sch2 = sch_dir / "power.kicad_sch"
        sch1.write_text("(kicad_sch main)", encoding="utf-8")
        sch2.write_text("(kicad_sch power)", encoding="utf-8")

        backup_path = mgr.backup_schematic_files("test-proj", [sch1, sch2])

        assert backup_path.is_dir()
        assert (backup_path / "main.kicad_sch").exists()
        assert (backup_path / "power.kicad_sch").exists()
        assert (backup_path / "main.kicad_sch").read_text(encoding="utf-8") == "(kicad_sch main)"

    def test_session_once_pattern(self, tmp_path: Path):
        mgr = BackupManager(backup_dir=tmp_path / "backups")

        sch_dir = tmp_path / "project"
        sch_dir.mkdir()
        sch = sch_dir / "main.kicad_sch"
        sch.write_text("(kicad_sch)", encoding="utf-8")

        path1 = mgr.backup_schematic_files("proj", [sch])
        path2 = mgr.backup_schematic_files("proj", [sch])
        assert path1 == path2

    def test_reset_allows_new_backup(self, tmp_path: Path):
        mgr = BackupManager(backup_dir=tmp_path / "backups")

        sch_dir = tmp_path / "project"
        sch_dir.mkdir()
        sch = sch_dir / "main.kicad_sch"
        sch.write_text("(kicad_sch)", encoding="utf-8")

        path1 = mgr.backup_schematic_files("proj", [sch])
        mgr.reset_session()
        path2 = mgr.backup_schematic_files("proj", [sch])
        assert path2.is_dir()
        # May be same or different path depending on timing

    def test_copies_into_existing_session_dir(self, tmp_path: Path):
        """Schematic backup must copy files even if ensure_session_backup
        already set _session_backup_dir (connected-mode flow)."""
        mgr = BackupManager(backup_dir=tmp_path / "backups")

        # Simulate connected-mode: ensure_session_backup runs first
        mgr.ensure_session_backup("proj", SAMPLE_COMPONENTS)
        session_dir = mgr._session_backup_dir
        assert (session_dir / "components.json").exists()

        # Now push-to-kicad calls backup_schematic_files
        sch_dir = tmp_path / "project"
        sch_dir.mkdir()
        sch = sch_dir / "main.kicad_sch"
        sch.write_text("(kicad_sch main)", encoding="utf-8")

        path = mgr.backup_schematic_files("proj", [sch])

        # Must reuse the same session directory
        assert path == session_dir
        # Schematic file must actually be copied
        assert (path / "main.kicad_sch").exists()
        assert (path / "main.kicad_sch").read_text(encoding="utf-8") == "(kicad_sch main)"
        # components.json still present
        assert (path / "components.json").exists()


class TestResetSession:

    def test_reset_creates_new_backup(self, tmp_path: Path):
        mgr = BackupManager(backup_dir=tmp_path)
        path1 = mgr.ensure_session_backup("proj", SAMPLE_COMPONENTS)
        assert mgr._session_backup_dir is not None

        mgr.reset_session()
        assert mgr._session_backup_dir is None  # flag cleared

        path2 = mgr.ensure_session_backup("proj", SAMPLE_COMPONENTS)
        assert mgr._session_backup_dir is not None  # re-created
        assert path2.is_dir()
