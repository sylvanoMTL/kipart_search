"""Tests for the Source Preferences Dialog (Story 6.1)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PySide6 = pytest.importorskip("PySide6", reason="PySide6 required for GUI tests")

from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QDialogButtonBox, QLineEdit

app = QApplication.instance() or QApplication(sys.argv)

from kipart_search.core.source_config import SourceConfig, SourceConfigManager
from kipart_search.gui.source_preferences_dialog import (
    SourcePreferencesDialog,
    ConnectionTestWorker,
    _SourceRow,
)


@pytest.fixture
def config_manager(tmp_path: Path):
    return SourceConfigManager(config_path=tmp_path / "config.json")


@pytest.fixture
def dialog(config_manager: SourceConfigManager):
    with patch.object(SourceConfigManager, "get_credential", return_value=None):
        dlg = SourcePreferencesDialog(config_manager=config_manager)
    yield dlg
    dlg.close()


# ── Dialog construction ─────────────────────────────────────────


class TestDialogConstruction:
    def test_dialog_title(self, dialog: SourcePreferencesDialog):
        assert dialog.windowTitle() == "Source Preferences"

    def test_four_source_rows(self, dialog: SourcePreferencesDialog):
        assert len(dialog._source_rows) == 4

    def test_source_names_in_order(self, dialog: SourcePreferencesDialog):
        names = [r.source_name for r in dialog._source_rows]
        assert names == ["JLCPCB", "DigiKey", "Mouser", "Octopart"]

    def test_default_combo_exists(self, dialog: SourcePreferencesDialog):
        assert isinstance(dialog._default_combo, QComboBox)

    def test_default_combo_has_none_option(self, dialog: SourcePreferencesDialog):
        assert dialog._default_combo.itemText(0) == "None"

    def test_button_box_ok_cancel(self, dialog: SourcePreferencesDialog):
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons is not None


# ── Source row enable/disable ────────────────────────────────────


class TestSourceRowToggle:
    def test_jlcpcb_enabled_by_default(self, dialog: SourcePreferencesDialog):
        jlcpcb = dialog._source_rows[0]
        assert jlcpcb.enable_checkbox.isChecked()

    def test_api_sources_disabled_by_default(self, dialog: SourcePreferencesDialog):
        for row in dialog._source_rows[1:]:
            assert not row.enable_checkbox.isChecked()

    def test_enable_shows_config_area(self, dialog: SourcePreferencesDialog):
        dk_row = dialog._source_rows[1]  # DigiKey
        assert dk_row._config_area.isHidden()
        dk_row.enable_checkbox.setChecked(True)
        assert not dk_row._config_area.isHidden()

    def test_disable_hides_config_area(self, dialog: SourcePreferencesDialog):
        dk_row = dialog._source_rows[1]  # DigiKey
        dk_row.enable_checkbox.setChecked(True)
        assert not dk_row._config_area.isHidden()
        dk_row.enable_checkbox.setChecked(False)
        assert dk_row._config_area.isHidden()


# ── API key inputs ───────────────────────────────────────────────


class TestApiKeyInputs:
    def test_digikey_has_two_key_fields(self, dialog: SourcePreferencesDialog):
        dk_row = dialog._source_rows[1]
        assert len(dk_row._key_inputs) == 2
        assert "client_id" in dk_row._key_inputs
        assert "client_secret" in dk_row._key_inputs

    def test_mouser_has_one_key_field(self, dialog: SourcePreferencesDialog):
        mouser_row = dialog._source_rows[2]
        assert len(mouser_row._key_inputs) == 1
        assert "api_key" in mouser_row._key_inputs

    def test_key_inputs_are_password_mode(self, dialog: SourcePreferencesDialog):
        dk_row = dialog._source_rows[1]
        for edit in dk_row._key_inputs.values():
            assert edit.echoMode() == QLineEdit.EchoMode.Password

    def test_jlcpcb_has_no_key_inputs(self, dialog: SourcePreferencesDialog):
        jlcpcb_row = dialog._source_rows[0]
        assert len(jlcpcb_row._key_inputs) == 0

    def test_test_button_exists_for_api_sources(self, dialog: SourcePreferencesDialog):
        for row in dialog._source_rows[1:]:
            assert row._test_button is not None

    def test_no_test_button_for_jlcpcb(self, dialog: SourcePreferencesDialog):
        jlcpcb_row = dialog._source_rows[0]
        assert jlcpcb_row._test_button is None


# ── Status indicators ───────────────────────────────────────────


class TestStatusIndicators:
    def test_status_label_shows_text(self, dialog: SourcePreferencesDialog):
        for row in dialog._source_rows:
            assert row.status_label.text().strip() != ""

    def test_set_status_updates_label(self, dialog: SourcePreferencesDialog):
        row = dialog._source_rows[1]  # DigiKey
        row.set_status("configured")
        assert "Configured" in row.status_label.text()

    def test_set_status_key_missing(self, dialog: SourcePreferencesDialog):
        row = dialog._source_rows[1]
        row.set_status("key_missing")
        assert "Key missing" in row.status_label.text()

    def test_set_status_key_invalid(self, dialog: SourcePreferencesDialog):
        row = dialog._source_rows[1]
        row.set_status("key_invalid")
        assert "Key invalid" in row.status_label.text()


# ── Default source combo ────────────────────────────────────────


class TestDefaultSourceCombo:
    def test_combo_updates_on_enable(self, dialog: SourcePreferencesDialog):
        dk_row = dialog._source_rows[1]
        dk_row.enable_checkbox.setChecked(True)
        items = [dialog._default_combo.itemText(i) for i in range(dialog._default_combo.count())]
        assert "DigiKey" in items

    def test_combo_updates_on_disable(self, dialog: SourcePreferencesDialog):
        dk_row = dialog._source_rows[1]
        dk_row.enable_checkbox.setChecked(True)
        dk_row.enable_checkbox.setChecked(False)
        items = [dialog._default_combo.itemText(i) for i in range(dialog._default_combo.count())]
        assert "DigiKey" not in items

    def test_combo_always_has_none(self, dialog: SourcePreferencesDialog):
        items = [dialog._default_combo.itemText(i) for i in range(dialog._default_combo.count())]
        assert "None" in items


# ── Save / accept flow ──────────────────────────────────────────


class TestSaveFlow:
    def test_get_config_from_row(self, dialog: SourcePreferencesDialog):
        row = dialog._source_rows[0]
        cfg = row.get_config()
        assert isinstance(cfg, SourceConfig)
        assert cfg.source_name == "JLCPCB"

    def test_save_credentials_calls_keyring(self, dialog: SourcePreferencesDialog):
        dk_row = dialog._source_rows[1]
        dk_row._key_inputs["client_id"].setText("my_id")
        dk_row._key_inputs["client_secret"].setText("my_secret")
        with patch.object(dialog._config_manager, "set_credential") as mock_set:
            dk_row.save_credentials()
        assert mock_set.call_count == 2

    def test_save_credentials_deletes_empty(self, dialog: SourcePreferencesDialog):
        dk_row = dialog._source_rows[1]
        dk_row._key_inputs["client_id"].setText("")
        dk_row._key_inputs["client_secret"].setText("")
        with patch.object(dialog._config_manager, "delete_credential") as mock_del:
            dk_row.save_credentials()
        assert mock_del.call_count == 2


# ── TestConnectionWorker ────────────────────────────────────────


class TestConnWorker:
    def test_worker_emits_placeholder(self, qtbot):
        worker = ConnectionTestWorker("DigiKey", {"client_id": "x"})
        with qtbot.waitSignal(worker.result_ready, timeout=5000) as sig:
            worker.start()
        source, success, message = sig.args
        assert source == "DigiKey"
        assert success is True
        assert "not yet implemented" in message
