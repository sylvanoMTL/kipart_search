"""Source Preferences Dialog — enable/disable sources, enter API keys, test connections."""

from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from kipart_search.core.source_config import (
    SOURCE_REGISTRY,
    SourceConfig,
    SourceConfigManager,
)

log = logging.getLogger(__name__)

# Colour constants — same as verify_panel.py
_GREEN = "#C8FFC8"
_AMBER = "#FFEBB4"
_RED = "#FFC8C8"

_STATUS_COLORS = {
    "configured": _GREEN,
    "key_missing": _AMBER,
    "key_invalid": _RED,
    "not_downloaded": _AMBER,
}

_STATUS_LABELS = {
    "configured": "Configured",
    "key_missing": "Key missing",
    "key_invalid": "Key invalid",
    "not_downloaded": "Not downloaded",
}


class ConnectionTestWorker(QThread):
    """Background worker that tests an API connection."""

    result_ready = Signal(str, bool, str)  # source_name, success, message

    def __init__(self, source_name: str, credentials: dict[str, str]):
        super().__init__()
        self._source_name = source_name
        self._credentials = credentials

    def run(self):
        # No actual source adapters exist yet — return placeholder
        self.result_ready.emit(
            self._source_name,
            True,
            "Source adapter not yet implemented \u2014 credentials saved for future use",
        )


class _SourceRow(QWidget):
    """A single source configuration row inside the preferences dialog."""

    def __init__(
        self,
        config: SourceConfig,
        registry_entry: dict,
        config_manager: SourceConfigManager,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.source_name = config.source_name
        self._registry = registry_entry
        self._config_manager = config_manager
        self._test_worker: ConnectionTestWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        # Header row: checkbox + name + status indicator
        header = QHBoxLayout()

        self.enable_checkbox = QCheckBox(config.source_name)
        self.enable_checkbox.setChecked(config.enabled)
        self.enable_checkbox.toggled.connect(self._on_enable_toggled)
        header.addWidget(self.enable_checkbox)

        header.addStretch()

        self.status_label = QLabel()
        header.addWidget(self.status_label)
        layout.addLayout(header)

        # Configuration area (shown when source needs config)
        self._config_area = QWidget()
        config_layout = QFormLayout(self._config_area)
        config_layout.setContentsMargins(24, 0, 0, 0)

        self._key_inputs: dict[str, QLineEdit] = {}
        self._test_button: QPushButton | None = None
        self._test_status_label: QLabel | None = None

        if registry_entry["needs_key"]:
            for kf in registry_entry["key_fields"]:
                line_edit = QLineEdit()
                line_edit.setEchoMode(QLineEdit.EchoMode.Password)
                line_edit.setPlaceholderText(f"Enter {kf.replace('_', ' ')}")
                # Pre-fill from keyring (not env vars — those are runtime)
                existing = config_manager.get_credential(config.source_name, kf)
                if existing:
                    line_edit.setText(existing)
                self._key_inputs[kf] = line_edit
                label = kf.replace("_", " ").title()
                config_layout.addRow(f"{label}:", line_edit)

            # Test Connection button + status
            test_row = QHBoxLayout()
            self._test_button = QPushButton("Test Connection")
            self._test_button.clicked.connect(self._on_test_connection)
            test_row.addWidget(self._test_button)
            self._test_status_label = QLabel()
            test_row.addWidget(self._test_status_label)
            test_row.addStretch()
            config_layout.addRow("", test_row)

        elif registry_entry["is_local"]:
            # JLCPCB: show database status
            self._db_status_label = QLabel()
            self._update_db_status()
            config_layout.addRow("Database:", self._db_status_label)

        layout.addWidget(self._config_area)
        self._config_area.setVisible(config.enabled and self._has_config())

        # Set initial status
        self.set_status(config.status)

    def _has_config(self) -> bool:
        """Whether this source has a configuration area."""
        return bool(self._registry["needs_key"] or self._registry["is_local"])

    def _on_enable_toggled(self, checked: bool):
        self._config_area.setVisible(checked and self._has_config())

    def _update_db_status(self):
        """Update JLCPCB database status label."""
        from kipart_search.core.sources import JLCPCBSource

        db_path = JLCPCBSource.default_db_path()
        if db_path.exists():
            try:
                size_mb = db_path.stat().st_size / (1024 * 1024)
                from datetime import datetime

                mtime = datetime.fromtimestamp(db_path.stat().st_mtime).strftime("%Y-%m-%d")
                self._db_status_label.setText(f"Downloaded ({size_mb:.0f} MB, {mtime})")
            except OSError:
                self._db_status_label.setText("Downloaded")
        else:
            self._db_status_label.setText("Not downloaded")

    def _on_test_connection(self):
        if self._test_button is None:
            return
        self._test_button.setEnabled(False)
        if self._test_status_label:
            self._test_status_label.setText("Testing...")
            self._test_status_label.setStyleSheet("")

        credentials = {kf: edit.text() for kf, edit in self._key_inputs.items()}
        self._test_worker = ConnectionTestWorker(self.source_name, credentials)
        self._test_worker.result_ready.connect(self._on_test_result)
        self._test_worker.start()

    def _on_test_result(self, source_name: str, success: bool, message: str):
        if self._test_button:
            self._test_button.setEnabled(True)
        if self._test_status_label:
            if success:
                self._test_status_label.setText(f"\u2714 {message}")
                self._test_status_label.setStyleSheet(f"color: green;")
            else:
                self._test_status_label.setText(f"\u2718 {message}")
                self._test_status_label.setStyleSheet(f"color: red;")
                self.set_status("key_invalid")

    def set_status(self, status: str):
        """Update the status indicator label."""
        self._status = status
        color = _STATUS_COLORS.get(status, _AMBER)
        label = _STATUS_LABELS.get(status, status)
        self.status_label.setText(f"  {label}  ")
        self.status_label.setStyleSheet(
            f"background-color: {color}; padding: 2px 8px; border-radius: 4px; font-size: 11px;"
        )

    def get_config(self) -> SourceConfig:
        """Build a SourceConfig from current widget state."""
        return SourceConfig(
            source_name=self.source_name,
            enabled=self.enable_checkbox.isChecked(),
            status=self._status,
            is_default=False,  # set by dialog-level combo
        )

    def save_credentials(self):
        """Persist API key values to keyring."""
        for kf, edit in self._key_inputs.items():
            value = edit.text().strip()
            if value:
                self._config_manager.set_credential(self.source_name, kf, value)
            else:
                self._config_manager.delete_credential(self.source_name, kf)


class SourcePreferencesDialog(QDialog):
    """Modal dialog for configuring data sources, API keys, and defaults."""

    def __init__(
        self,
        config_manager: SourceConfigManager | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Source Preferences")
        self.setMinimumWidth(550)

        self._config_manager = config_manager or SourceConfigManager()
        self._source_rows: list[_SourceRow] = []

        layout = QVBoxLayout(self)

        # Load current configs
        configs = self._config_manager.get_all_configs()
        config_map = {c.source_name: c for c in configs}

        # Source rows
        sources_group = QGroupBox("Data Sources")
        sources_layout = QVBoxLayout(sources_group)
        for entry in SOURCE_REGISTRY:
            cfg = config_map.get(entry["name"], SourceConfig(source_name=entry["name"]))
            row = _SourceRow(cfg, entry, self._config_manager, parent=self)
            self._source_rows.append(row)
            sources_layout.addWidget(row)
        layout.addWidget(sources_group)

        # Default source selector
        default_layout = QHBoxLayout()
        default_layout.addWidget(QLabel("Default source:"))
        self._default_combo = QComboBox()
        self._default_combo.addItem("None")
        for cfg in configs:
            if cfg.enabled:
                self._default_combo.addItem(cfg.source_name)
        # Set current default
        for cfg in configs:
            if cfg.is_default and cfg.enabled:
                idx = self._default_combo.findText(cfg.source_name)
                if idx >= 0:
                    self._default_combo.setCurrentIndex(idx)
                break
        default_layout.addWidget(self._default_combo)
        default_layout.addStretch()
        layout.addLayout(default_layout)

        # Update default combo when sources are toggled
        for row in self._source_rows:
            row.enable_checkbox.toggled.connect(self._refresh_default_combo)

        # OK / Cancel
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _refresh_default_combo(self):
        """Update default source combo to reflect currently enabled sources."""
        current = self._default_combo.currentText()
        self._default_combo.clear()
        self._default_combo.addItem("None")
        for row in self._source_rows:
            if row.enable_checkbox.isChecked():
                self._default_combo.addItem(row.source_name)
        idx = self._default_combo.findText(current)
        self._default_combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _on_accept(self):
        """Save all configuration and close."""
        default_source = self._default_combo.currentText()

        configs: list[SourceConfig] = []
        for row in self._source_rows:
            cfg = row.get_config()
            cfg.is_default = (cfg.source_name == default_source and default_source != "None")
            # Save API keys to keyring
            row.save_credentials()
            # Recompute status after saving credentials
            entry = self._config_manager.get_registry_entry(cfg.source_name)
            if entry:
                cfg.status = self._config_manager.compute_status(entry, cfg.enabled)
            configs.append(cfg)

        self._config_manager.save_configs(configs)
        self._saved_configs = configs
        self.accept()

    def get_saved_configs(self) -> list[SourceConfig]:
        """Return configs as saved on accept. Call after exec() returns Accepted."""
        return getattr(self, "_saved_configs", [])
