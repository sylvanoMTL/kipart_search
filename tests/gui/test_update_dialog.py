"""Tests for gui/update_dialog.py — download worker and update dialog behaviour."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kipart_search.core.update_check import UpdateInfo


def _make_info(**overrides) -> UpdateInfo:
    defaults = dict(
        latest_version="2.0.0",
        release_url="https://github.com/sylvanoMTL/kipart_search/releases/latest",
        release_notes="notes",
        check_time=time.time(),
        asset_url="https://example.com/setup.exe",
        asset_size=1000,
    )
    defaults.update(overrides)
    return UpdateInfo(**defaults)


class TestDownloadWorkerQuarantine:
    """Test AV quarantine detection in _DownloadWorker."""

    def test_quarantine_error_emitted_when_file_vanishes(self, tmp_path):
        """After rename succeeds but file disappears, emit 'quarantine' error."""
        from kipart_search.gui.update_dialog import _DownloadWorker

        dest = tmp_path / "kipart-search-update-v2.0.0.exe"
        worker = _DownloadWorker(
            url="https://example.com/setup.exe",
            dest=dest,
            expected_size=0,  # skip size check
        )

        errors: list[str] = []
        finished: list[str] = []
        worker.error.connect(errors.append)
        worker.finished.connect(finished.append)

        # Mock httpx.stream to write data then rename will succeed
        partial = dest.with_suffix(dest.suffix + ".partial")

        class FakeResp:
            headers = {"content-length": "5"}
            def raise_for_status(self): pass
            def iter_bytes(self, chunk_size=65536):
                yield b"hello"
            def __enter__(self): return self
            def __exit__(self, *a): pass

        class FakeStream:
            def __call__(self, *a, **kw):
                return FakeResp()

        with (
            patch("httpx.stream", FakeStream()),
            patch("time.sleep"),  # don't actually sleep
        ):
            # After rename, make the file disappear (simulating AV quarantine)
            original_rename = Path.rename
            original_exists = Path.exists
            renamed = False

            def fake_rename(self, target):
                nonlocal renamed
                result = original_rename(self, target)
                renamed = True
                return result

            def fake_exists(self):
                # After rename completes, report dest as missing (quarantined)
                if self == dest and renamed:
                    return False
                return original_exists(self)

            with (
                patch.object(Path, "rename", fake_rename),
                patch.object(Path, "exists", fake_exists),
            ):
                worker.run()

        assert errors == ["quarantine"]
        assert finished == []


class TestUpdateDialogQuarantineMessage:
    """Test that quarantine error shows correct message and copies URL."""

    def test_quarantine_copies_url_to_clipboard(self, qtbot):
        from kipart_search.gui.update_dialog import UpdateDialog
        from PySide6.QtWidgets import QApplication

        info = _make_info()
        dlg = UpdateDialog(info)
        qtbot.addWidget(dlg)

        mock_clipboard = MagicMock()
        with patch.object(QApplication, "clipboard", return_value=mock_clipboard):
            dlg._on_download_error("quarantine")

        mock_clipboard.setText.assert_called_once_with(info.release_url)
        assert "antivirus" in dlg._status_label.text().lower()


class TestUpdateDialogShimFailureClipboard:
    """Test that shim launch failure copies installer path to clipboard."""

    def test_clipboard_set_on_shim_failure(self, qtbot):
        from kipart_search.gui.update_dialog import UpdateDialog
        from PySide6.QtWidgets import QApplication

        info = _make_info()
        dlg = UpdateDialog(info)
        qtbot.addWidget(dlg)
        dlg._downloaded_path = r"C:\Temp\setup.exe"

        mock_clipboard = MagicMock()
        with (
            patch.object(QApplication, "clipboard", return_value=mock_clipboard),
            patch("kipart_search.gui.update_dialog.write_update_shim") as mock_shim,
            patch("kipart_search.gui.update_dialog.launch_shim_and_exit", return_value=False),
            patch("kipart_search.gui.update_dialog.get_app_exe_path"),
            patch("kipart_search.gui.update_dialog.QMessageBox") as mock_msgbox,
        ):
            # First call is the UAC confirmation
            mock_msgbox.StandardButton.Ok = 1024
            mock_msgbox.StandardButton.Cancel = 4194304
            mock_msgbox.information.return_value = 1024
            mock_msgbox.ButtonRole = MagicMock()

            dlg._on_install_now()

        mock_clipboard.setText.assert_called_once_with(r"C:\Temp\setup.exe")
