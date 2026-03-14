"""Verification dashboard — Scan Project results with colour-coded status."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from kipart_search.core.models import Confidence
from kipart_search.gui.kicad_bridge import BoardComponent


# Colours for confidence levels
COLORS = {
    Confidence.GREEN: QColor(200, 255, 200),   # Light green
    Confidence.AMBER: QColor(255, 235, 180),   # Light amber
    Confidence.RED: QColor(255, 200, 200),      # Light red
}

VERIFY_COLUMNS = ["Reference", "Value", "MPN", "MPN Status", "Footprint"]


class VerifyPanel(QWidget):
    """Verification dashboard showing BOM health."""

    component_clicked = Signal(str)  # Emits reference when row clicked

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Summary bar
        self.summary_label = QLabel("")
        layout.addWidget(self.summary_label)

        # Health bar
        self.health_bar = QProgressBar()
        self.health_bar.setMinimum(0)
        self.health_bar.setTextVisible(True)
        self.health_bar.setVisible(False)
        layout.addWidget(self.health_bar)

        # Verification table
        self.table = QTableWidget()
        self.table.setColumnCount(len(VERIFY_COLUMNS))
        self.table.setHorizontalHeaderLabels(VERIFY_COLUMNS)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellClicked.connect(self._on_cell_clicked)
        layout.addWidget(self.table)

    def set_results(
        self,
        components: list[BoardComponent],
        mpn_statuses: dict[str, Confidence],
    ) -> None:
        """Populate the verification table.

        Args:
            components: List of board components from KiCad
            mpn_statuses: Map of reference → confidence level from MPN verification
        """
        self.table.setRowCount(len(components))

        has_mpn = 0
        missing_mpn = 0
        issues = 0

        for row, comp in enumerate(components):
            status = mpn_statuses.get(comp.reference, Confidence.RED)

            # Categorize
            if not comp.has_mpn:
                missing_mpn += 1
                status = Confidence.RED
            elif status == Confidence.GREEN:
                has_mpn += 1
            else:
                issues += 1

            bg_color = COLORS[status]

            # Reference
            ref_item = QTableWidgetItem(comp.reference)
            ref_item.setBackground(bg_color)
            self.table.setItem(row, 0, ref_item)

            # Value
            val_item = QTableWidgetItem(comp.value)
            val_item.setBackground(bg_color)
            self.table.setItem(row, 1, val_item)

            # MPN
            mpn_item = QTableWidgetItem(comp.mpn if comp.has_mpn else "(missing)")
            mpn_item.setBackground(bg_color)
            self.table.setItem(row, 2, mpn_item)

            # MPN Status
            status_text = {
                Confidence.GREEN: "OK",
                Confidence.AMBER: "?",
                Confidence.RED: "Missing" if not comp.has_mpn else "Not found",
            }[status]
            status_item = QTableWidgetItem(status_text)
            status_item.setBackground(bg_color)
            self.table.setItem(row, 3, status_item)

            # Footprint
            fp_item = QTableWidgetItem(comp.footprint_short)
            fp_color = COLORS[Confidence.GREEN] if comp.footprint else COLORS[Confidence.RED]
            fp_item.setBackground(fp_color)
            self.table.setItem(row, 4, fp_item)

        # Update summary
        total = len(components)
        if total > 0:
            pct = int(has_mpn / total * 100)
            self.summary_label.setText(
                f"Components: {total} total | "
                f"Valid MPN: {has_mpn} | "
                f"Needs attention: {issues} | "
                f"Missing MPN: {missing_mpn}"
            )
            self.health_bar.setMaximum(total)
            self.health_bar.setValue(has_mpn)
            self.health_bar.setFormat(f"Ready: {pct}%")
            self.health_bar.setVisible(True)
        else:
            self.summary_label.setText("No components found")
            self.health_bar.setVisible(False)

    def _on_cell_clicked(self, row: int, _col: int):
        ref_item = self.table.item(row, 0)
        if ref_item:
            self.component_clicked.emit(ref_item.text())

    def clear(self):
        """Clear the verification table."""
        self.table.setRowCount(0)
        self.summary_label.setText("")
        self.health_bar.setVisible(False)
