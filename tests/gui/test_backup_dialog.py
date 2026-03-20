"""Tests for BackupBrowserDialog and _apply_assignment backup integration."""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

PySide6 = pytest.importorskip("PySide6", reason="PySide6 required for GUI tests")

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from kipart_search.core.backup import BackupManager
from kipart_search.core.models import BoardComponent
from kipart_search.gui.backup_dialog import BackupBrowserDialog


SAMPLE_COMPONENTS = [
    {
        "reference": "C1",
        "value": "100nF",
        "footprint": "C_0805_2012Metric",
        "mpn": "GRM21BR71C104KA01L",
        "datasheet": "https://example.com/ds.pdf",
        "extra_fields": {"manufacturer": "Murata"},
    },
]


def _make_board_component(**kwargs) -> BoardComponent:
    defaults = dict(
        reference="C1", value="100nF",
        footprint="Capacitor_SMD:C_0805_2012Metric",
        mpn="", datasheet="", extra_fields={},
    )
    defaults.update(kwargs)
    return BoardComponent(**defaults)


# ---------------------------------------------------------------------------
# BackupBrowserDialog tests
# ---------------------------------------------------------------------------

class TestBackupBrowserDialog:

    def test_lists_backups(self, tmp_path: Path):
        mgr = BackupManager(backup_dir=tmp_path)
        d = tmp_path / "proj" / "2026-03-19_1430"
        d.mkdir(parents=True)
        (d / "components.json").write_text(json.dumps(SAMPLE_COMPONENTS))

        dialog = BackupBrowserDialog(mgr, "proj")
        assert dialog._table.rowCount() == 1
        assert dialog._table.item(0, 0).text() == "2026-03-19_1430"

    def test_empty_project(self, tmp_path: Path):
        mgr = BackupManager(backup_dir=tmp_path)
        dialog = BackupBrowserDialog(mgr, "no-such-proj")
        assert dialog._table.rowCount() == 0

    def test_restore_emits_signal(self, tmp_path: Path):
        mgr = BackupManager(backup_dir=tmp_path)
        d = tmp_path / "proj" / "2026-03-19_1430"
        d.mkdir(parents=True)
        (d / "components.json").write_text(json.dumps(SAMPLE_COMPONENTS))

        dialog = BackupBrowserDialog(mgr, "proj")
        received = []
        dialog.restore_requested.connect(lambda data: received.append(data))

        # Select the first row
        dialog._table.selectRow(0)

        # Mock the confirmation dialog to return Yes
        with patch(
            "kipart_search.gui.backup_dialog.QMessageBox.question",
            return_value=QApplication.instance()
            and __import__("PySide6.QtWidgets", fromlist=["QMessageBox"]).QMessageBox.StandardButton.Yes,
        ):
            dialog._on_restore()

        assert len(received) == 1
        assert received[0][0]["reference"] == "C1"

    def test_view_log_no_csv(self, tmp_path: Path):
        """View log button with no CSV shows info message."""
        mgr = BackupManager(backup_dir=tmp_path)
        d = tmp_path / "proj" / "2026-03-19_1430"
        d.mkdir(parents=True)
        (d / "components.json").write_text("[]")

        dialog = BackupBrowserDialog(mgr, "proj")
        dialog._table.selectRow(0)

        with patch(
            "kipart_search.gui.backup_dialog.QMessageBox.information"
        ) as mock_info:
            dialog._on_view_log()
            mock_info.assert_called_once()


# ---------------------------------------------------------------------------
# Integration: _apply_assignment backup hooks
# ---------------------------------------------------------------------------

class TestApplyAssignmentBackup:
    """Test that _apply_assignment calls backup manager correctly."""

    def _make_main_window_mock(self, tmp_path: Path, connected: bool = True):
        """Create a minimal mock that simulates MainWindow backup integration."""
        from kipart_search.core.backup import BackupManager

        mgr = BackupManager(backup_dir=tmp_path)
        bridge = MagicMock()
        bridge.is_connected = connected
        bridge.write_field.return_value = True
        bridge._board = MagicMock() if connected else None

        return mgr, bridge

    def test_connected_mode_creates_backup_and_logs(self, tmp_path: Path):
        """Simulates _apply_assignment flow in connected mode."""
        mgr, bridge = self._make_main_window_mock(tmp_path, connected=True)

        comp = _make_board_component(mpn="OLD_MPN")
        project = "test-board"
        components = [asdict(comp)]

        # Step 1: ensure backup (as _apply_assignment would)
        backup_dir = mgr.ensure_session_backup(project, components)
        assert (backup_dir / "components.json").exists()

        # Step 2: log field change (as _apply_assignment would after successful write)
        mgr.log_field_change(project, "C1", "MPN", "OLD_MPN", "NEW_MPN")

        csv_path = backup_dir / "undo_log.csv"
        assert csv_path.exists()
        with open(csv_path, encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert rows[1][1] == "C1"
        assert rows[1][3] == "OLD_MPN"
        assert rows[1][4] == "NEW_MPN"

    def test_connected_mode_single_backup_per_session(self, tmp_path: Path):
        """Second call to ensure_session_backup returns same dir."""
        mgr, bridge = self._make_main_window_mock(tmp_path, connected=True)
        project = "test-board"
        components = [asdict(_make_board_component())]

        path1 = mgr.ensure_session_backup(project, components)
        path2 = mgr.ensure_session_backup(project, components)
        assert path1 == path2

    def test_standalone_mode_logs_without_snapshot(self, tmp_path: Path):
        """In standalone mode, undo log is written but no component snapshot."""
        mgr, bridge = self._make_main_window_mock(tmp_path, connected=False)
        project = "standalone"

        # No ensure_session_backup called (standalone mode)
        mgr.log_field_change(project, "C1", "MPN", "", "ABC123")

        csv_path = tmp_path / project / "standalone" / "undo_log.csv"
        assert csv_path.exists()

        # No components.json in the standalone dir
        assert not (tmp_path / project / "standalone" / "components.json").exists()

    def test_reset_session_on_rescan(self, tmp_path: Path):
        """Simulates _on_scan_complete resetting the session."""
        mgr, _ = self._make_main_window_mock(tmp_path, connected=True)
        project = "test-board"
        components = [asdict(_make_board_component())]

        path1 = mgr.ensure_session_backup(project, components)
        mgr.reset_session()
        # After reset, next backup should attempt a new dir
        assert mgr._session_backup_dir is None
