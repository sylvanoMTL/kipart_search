"""Tests for the Welcome / First-Run Dialog (Story 6.2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

PySide6 = pytest.importorskip("PySide6", reason="PySide6 required for GUI tests")

from PySide6.QtWidgets import QApplication, QDialog

app = QApplication.instance() or QApplication(sys.argv)

from kipart_search.core.source_config import SourceConfigManager
from kipart_search.gui.welcome_dialog import WelcomeDialog


@pytest.fixture
def dialog():
    dlg = WelcomeDialog()
    yield dlg
    dlg.close()


# ── Dialog construction ─────────────────────────────────────────


class TestDialogConstruction:
    def test_window_title(self, dialog: WelcomeDialog):
        assert dialog.windowTitle() == "Welcome to KiPart Search"

    def test_dialog_is_modal(self, dialog: WelcomeDialog):
        assert dialog.isModal()

    def test_fixed_size(self, dialog: WelcomeDialog):
        assert dialog.minimumSize() == dialog.maximumSize()

    def test_three_option_buttons_not_hidden(self, dialog: WelcomeDialog):
        # Widgets not shown yet, so use isHidden() which checks explicit hide
        assert not dialog._btn_download.isHidden()
        assert not dialog._btn_configure.isHidden()
        assert not dialog._btn_skip.isHidden()

    def test_progress_bar_hidden_initially(self, dialog: WelcomeDialog):
        assert dialog._progress_bar.isHidden()

    def test_cancel_button_hidden_initially(self, dialog: WelcomeDialog):
        assert dialog._btn_cancel.isHidden()


# ── Option 3: Skip ──────────────────────────────────────────────


class TestSkipOption:
    def test_skip_rejects_dialog(self, dialog: WelcomeDialog):
        """Clicking Skip should close the dialog with Rejected result."""
        dialog.show()
        dialog._on_skip()
        assert dialog.result() == QDialog.DialogCode.Rejected


# ── Download state transitions ──────────────────────────────────


class TestDownloadState:
    def test_clicking_download_shows_progress(self, dialog: WelcomeDialog):
        """Clicking Download should hide buttons and show progress widgets."""
        with patch("kipart_search.gui.welcome_dialog.DownloadWorker") as MockWorker:
            mock_worker = MagicMock()
            MockWorker.return_value = mock_worker
            dialog._on_download()

        # Buttons should be hidden
        assert dialog._btn_download.isHidden()
        assert dialog._btn_configure.isHidden()
        assert dialog._btn_skip.isHidden()

        # Progress should not be hidden
        assert not dialog._progress_bar.isHidden()
        assert not dialog._progress_label.isHidden()
        assert not dialog._btn_cancel.isHidden()

    def test_cancel_returns_to_initial_state(self, dialog: WelcomeDialog):
        """After cancel, dialog should return to 3-button view."""
        dialog._set_download_state(True)
        assert dialog._btn_download.isHidden()

        dialog._set_download_state(False)
        assert not dialog._btn_download.isHidden()
        assert not dialog._btn_configure.isHidden()
        assert not dialog._btn_skip.isHidden()
        assert dialog._progress_bar.isHidden()


# ── Option 2: Configure API Source ──────────────────────────────


class TestConfigureOption:
    def test_configure_opens_preferences_dialog(self, dialog: WelcomeDialog):
        """Option 2 should open SourcePreferencesDialog as nested modal."""
        with patch("kipart_search.gui.source_preferences_dialog.SourcePreferencesDialog") as MockPrefDlg, \
             patch("kipart_search.core.source_config.SourceConfigManager"):
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = False  # User cancels prefs
            MockPrefDlg.return_value = mock_dlg

            dialog._on_configure()

            MockPrefDlg.assert_called_once()
            mock_dlg.exec.assert_called_once()


# ── Signal emission ─────────────────────────────────────────────


class TestSignalEmission:
    def test_source_configured_emitted_on_download_complete(self, dialog: WelcomeDialog, qtbot):
        """source_configured signal should be emitted when download finishes."""
        with qtbot.waitSignal(dialog.source_configured, timeout=1000):
            dialog._on_download_complete("/fake/path/parts-fts5.db")

    def test_db_path_stored_on_download_complete(self, dialog: WelcomeDialog):
        dialog._on_download_complete("/fake/path/parts-fts5.db")
        assert dialog.get_db_path() == Path("/fake/path/parts-fts5.db")

    def test_source_configured_emitted_on_configure_accept(self, dialog: WelcomeDialog, qtbot):
        """source_configured should be emitted when user accepts preferences."""
        with patch("kipart_search.gui.source_preferences_dialog.SourcePreferencesDialog") as MockPrefDlg, \
             patch("kipart_search.core.source_config.SourceConfigManager"):
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = True
            mock_dlg.get_saved_configs.return_value = [MagicMock()]
            MockPrefDlg.return_value = mock_dlg

            with qtbot.waitSignal(dialog.source_configured, timeout=1000):
                dialog._on_configure()


# ── First-run detection (integration with SourceConfigManager) ──


class TestFirstRunDetection:
    def test_welcome_shown_when_no_config(self, tmp_path: Path):
        """No config.json → welcome_shown should be False."""
        mgr = SourceConfigManager(config_path=tmp_path / "config.json")
        assert mgr.get_welcome_shown() is False

    def test_welcome_not_shown_when_flag_true(self, tmp_path: Path):
        """config.json with welcome_shown=true → should not show dialog."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"welcome_shown": True}), encoding="utf-8")
        mgr = SourceConfigManager(config_path=config_file)
        assert mgr.get_welcome_shown() is True


# ── Download cancellation ───────────────────────────────────────


class TestDownloadCancellation:
    def test_cancel_error_returns_to_initial(self, dialog: WelcomeDialog):
        """A 'cancelled' error message should return to 3-button state."""
        dialog._set_download_state(True)
        dialog._on_download_error("Download cancelled")
        assert not dialog._btn_download.isHidden()
        assert dialog._progress_bar.isHidden()

    def test_non_cancel_error_shows_message(self, dialog: WelcomeDialog):
        """A real error should display the error message in the progress label."""
        dialog._set_download_state(True)
        dialog._on_download_error("Network timeout")
        assert "Network timeout" in dialog._progress_label.text()
        # Cancel button becomes "Back"
        assert dialog._btn_cancel.text() == "Back"


# ── Progress updates ────────────────────────────────────────────


class TestProgressUpdates:
    def test_progress_updates_bar(self, dialog: WelcomeDialog):
        dialog._set_download_state(True)
        dialog._on_progress(50, 100, "Downloading chunk 5/10")
        assert dialog._progress_bar.maximum() == 100
        assert dialog._progress_bar.value() == 50
        assert "chunk 5/10" in dialog._progress_label.text()
