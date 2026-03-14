"""Results table widget — displays search results with source provenance."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem, QWidget

from kipart_search.core.models import PartResult


COLUMNS = ["MPN", "Manufacturer", "Description", "Package", "Category", "Source"]


class ResultsTable(QWidget):
    """Table displaying component search results."""

    part_selected = Signal(int)  # Emits row index on double-click

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        from PySide6.QtWidgets import QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._results: list[PartResult] = []

        self.table = QTableWidget()
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table)

    def set_results(self, results: list[PartResult]) -> None:
        """Populate the table with search results."""
        self._results = list(results)
        self.table.setRowCount(len(results))
        for row, part in enumerate(results):
            self.table.setItem(row, 0, QTableWidgetItem(part.mpn))
            self.table.setItem(row, 1, QTableWidgetItem(part.manufacturer))
            self.table.setItem(row, 2, QTableWidgetItem(part.description))
            self.table.setItem(row, 3, QTableWidgetItem(part.package))
            self.table.setItem(row, 4, QTableWidgetItem(part.category))
            self.table.setItem(row, 5, QTableWidgetItem(part.source))

    def get_result(self, row: int) -> PartResult | None:
        """Return the PartResult for a given row index."""
        if 0 <= row < len(self._results):
            return self._results[row]
        return None

    def clear_results(self) -> None:
        """Clear all results from the table."""
        self._results.clear()
        self.table.setRowCount(0)

    def _on_double_click(self, row: int, _col: int):
        self.part_selected.emit(row)
