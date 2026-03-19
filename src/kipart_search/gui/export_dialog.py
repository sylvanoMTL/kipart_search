"""BOM Export dialog — template selection, preview, and file export."""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from kipart_search.core.bom_export import (
    PRESET_TEMPLATES,
    BOMTemplate,
    export_bom,
    group_components,
)
from kipart_search.core.models import BoardComponent

log = logging.getLogger(__name__)


class ExportDialog(QDialog):
    """Non-modal dialog for BOM export with template selection and preview."""

    def __init__(
        self,
        components: list[BoardComponent],
        health_pct: int,
        missing_count: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._components = list(components)
        self._health_pct = health_pct
        self._missing_count = missing_count
        self._exported_path: Path | None = None

        self.setWindowTitle("Export BOM")
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout(self)

        # ── Health warning banner ──
        self._warning_banner = QLabel()
        self._warning_banner.setStyleSheet(
            "background-color: #FFEBB4; padding: 8px; border-radius: 4px;"
        )
        self._warning_banner.setWordWrap(True)
        layout.addWidget(self._warning_banner)
        if health_pct < 100:
            self._warning_banner.setText(
                f"\u26a0 {missing_count} component(s) still missing MPNs "
                f"— export anyway or go back to fix."
            )
        else:
            self._warning_banner.setVisible(False)

        # ── Controls row ──
        controls = QHBoxLayout()

        controls.addWidget(QLabel("Template:"))
        self._template_combo = QComboBox()
        for tmpl in PRESET_TEMPLATES:
            self._template_combo.addItem(tmpl.name, tmpl)
        self._template_combo.currentIndexChanged.connect(self._on_template_changed)
        controls.addWidget(self._template_combo)

        controls.addWidget(QLabel("DNP:"))
        self._dnp_combo = QComboBox()
        self._dnp_combo.addItem("Include marked", "include_marked")
        self._dnp_combo.addItem("Exclude entirely", "exclude")
        self._dnp_combo.currentIndexChanged.connect(self._refresh_preview)
        controls.addWidget(self._dnp_combo)

        controls.addWidget(QLabel("Format:"))
        self._format_combo = QComboBox()
        self._format_combo.addItem("Excel (.xlsx)", "xlsx")
        self._format_combo.addItem("CSV (.csv)", "csv")
        controls.addWidget(self._format_combo)

        controls.addStretch()
        layout.addLayout(controls)

        # ── Preview table ──
        self._preview_table = QTableWidget()
        self._preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._preview_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._preview_table.setAlternatingRowColors(True)
        self._preview_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._preview_table)

        # ── Button row ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._success_label = QLabel()
        self._success_label.setVisible(False)
        btn_layout.addWidget(self._success_label)

        self._open_file_btn = QPushButton("Open File")
        self._open_file_btn.setVisible(False)
        self._open_file_btn.clicked.connect(self._on_open_file)
        btn_layout.addWidget(self._open_file_btn)

        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self._close_btn)

        self._export_btn = QPushButton("Export")
        self._export_btn.setDefault(True)
        self._export_btn.clicked.connect(self._on_export)
        btn_layout.addWidget(self._export_btn)

        layout.addLayout(btn_layout)

        # Sync format combo to match the first template's default
        self._sync_format_to_template()
        self._refresh_preview()

    def _selected_template(self) -> BOMTemplate:
        return self._template_combo.currentData()

    def _selected_dnp(self) -> str:
        return self._dnp_combo.currentData()

    def _selected_format(self) -> str:
        return self._format_combo.currentData()

    def _on_template_changed(self) -> None:
        """Sync format combo to template default and refresh preview."""
        self._sync_format_to_template()
        self._refresh_preview()

    def _sync_format_to_template(self) -> None:
        """Set the format combo to match the selected template's default."""
        tmpl = self._selected_template()
        idx = self._format_combo.findData(tmpl.file_format)
        if idx >= 0:
            self._format_combo.blockSignals(True)
            self._format_combo.setCurrentIndex(idx)
            self._format_combo.blockSignals(False)

    def _filtered_components(self) -> list[BoardComponent]:
        """Return components filtered by DNP setting."""
        if self._selected_dnp() == "exclude":
            return [c for c in self._components if not c.is_dnp]
        return self._components

    def _refresh_preview(self) -> None:
        """Rebuild the preview table from current settings."""
        tmpl = self._selected_template()
        if tmpl is None:
            return

        components = self._filtered_components()
        rows = group_components(components)

        headers = [col.header for col in tmpl.columns]
        self._preview_table.setColumnCount(len(headers))
        self._preview_table.setHorizontalHeaderLabels(headers)
        self._preview_table.setRowCount(len(rows))

        for r, row_data in enumerate(rows):
            for c, col in enumerate(tmpl.columns):
                value = str(row_data.get(col.field, ""))
                item = QTableWidgetItem(value)
                self._preview_table.setItem(r, c, item)

        self._preview_table.resizeColumnsToContents()
        # Stretch last section after resize
        header = self._preview_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)

    def _on_export(self) -> None:
        """Handle Export button click — open file dialog and write BOM."""
        tmpl = self._selected_template()
        fmt = self._selected_format()
        ext = "csv" if fmt == "csv" else "xlsx"

        default_name = f"BOM.{ext}"

        file_filter = (
            "CSV Files (*.csv)" if ext == "csv"
            else "Excel Files (*.xlsx)"
        )

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export BOM",
            default_name,
            file_filter,
        )
        if not path:
            return

        output_path = Path(path)
        export_template = replace(tmpl, file_format=fmt)

        try:
            components = self._filtered_components()
            export_bom(components, export_template, output_path)
            self._exported_path = output_path
            log.info("BOM exported to %s", output_path)

            # Show success state
            self._export_btn.setVisible(False)
            self._success_label.setText(f"Exported to: {output_path}")
            self._success_label.setVisible(True)
            self._open_file_btn.setVisible(True)
        except Exception as e:
            log.error("BOM export failed: %s", e)
            QMessageBox.warning(self, "Export Failed", str(e))

    def _on_open_file(self) -> None:
        """Open the exported file with the system default application."""
        if self._exported_path and self._exported_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._exported_path)))
