"""Results table widget — displays search results with filters and detail view."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from kipart_search.core.models import PartResult
from kipart_search.gui.detail_panel import render_part_html


COLUMNS = ["MPN", "Manufacturer", "Description", "Package", "Category", "Source"]


class ResultsTable(QWidget):
    """Table displaying component search results with filters and detail view."""

    part_selected = Signal(int)  # Emits row index on double-click (for assignment)
    part_clicked = Signal(int)   # Emits row index on single-click (for detail panel)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._results: list[PartResult] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Filter row ──
        filter_row = QHBoxLayout()

        filter_row.addWidget(QLabel("Manufacturer:"))
        self._filter_mfr = QComboBox()
        self._filter_mfr.addItem("All")
        self._filter_mfr.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._filter_mfr.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self._filter_mfr)

        filter_row.addWidget(QLabel("Package:"))
        self._filter_pkg = QComboBox()
        self._filter_pkg.addItem("All")
        self._filter_pkg.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._filter_pkg.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self._filter_pkg)

        filter_row.addStretch()
        self._count_label = QLabel("")
        filter_row.addWidget(self._count_label)

        layout.addLayout(filter_row)

        # ── Splitter: results table (top) | detail browser (bottom) ──
        splitter = QSplitter(Qt.Orientation.Vertical)

        self.table = QTableWidget()
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        self.table.cellClicked.connect(self._on_click)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        splitter.addWidget(self.table)

        self._detail = QTextBrowser()
        self._detail.setReadOnly(True)
        self._detail.setOpenExternalLinks(True)
        splitter.addWidget(self._detail)

        # Table gets most space; detail is secondary and collapsible
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setCollapsible(1, True)

        layout.addWidget(splitter)

    def set_results(self, results: list[PartResult]) -> None:
        """Populate the table and filter dropdowns from search results."""
        self._results = list(results)
        self._detail.clear()

        # Populate filter combos
        self._filter_mfr.blockSignals(True)
        self._filter_pkg.blockSignals(True)

        self._filter_mfr.clear()
        self._filter_mfr.addItem("All")
        self._filter_pkg.clear()
        self._filter_pkg.addItem("All")

        manufacturers = sorted({p.manufacturer for p in results} - {""})
        packages = sorted({p.package for p in results} - {""})
        self._filter_mfr.addItems(manufacturers)
        self._filter_pkg.addItems(packages)

        self._filter_mfr.blockSignals(False)
        self._filter_pkg.blockSignals(False)

        # Populate table (disable sorting during insertion to avoid mid-build reorder)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(results))
        for row, part in enumerate(results):
            items = [
                QTableWidgetItem(part.mpn),
                QTableWidgetItem(part.manufacturer),
                QTableWidgetItem(part.description),
                QTableWidgetItem(part.package),
                QTableWidgetItem(part.category),
                QTableWidgetItem(part.source),
            ]
            for col, item in enumerate(items):
                item.setData(Qt.ItemDataRole.UserRole, row)  # original index
                self.table.setItem(row, col, item)

        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)
        self._apply_filters()

    def _original_index(self, row: int) -> int | None:
        """Return the original result index stored in a visual row."""
        item = self.table.item(row, 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def get_result(self, row: int) -> PartResult | None:
        """Return the PartResult for a given visual row (sort-safe)."""
        idx = self._original_index(row)
        if idx is not None and 0 <= idx < len(self._results):
            return self._results[idx]
        return None

    def clear_results(self) -> None:
        """Clear all results from the table."""
        self._results.clear()
        self.table.setRowCount(0)
        self._detail.clear()
        self._count_label.setText("")

    # ── Filtering ──

    def _apply_filters(self):
        """Show/hide rows based on filter selection."""
        mfr_filter = self._filter_mfr.currentText()
        pkg_filter = self._filter_pkg.currentText()
        visible = 0

        for row in range(self.table.rowCount()):
            part = self.get_result(row)
            if part is None:
                continue
            hide = False
            if mfr_filter != "All" and part.manufacturer != mfr_filter:
                hide = True
            if pkg_filter != "All" and part.package != pkg_filter:
                hide = True
            self.table.setRowHidden(row, hide)
            if not hide:
                visible += 1

        total = len(self._results)
        if total == 0:
            self._count_label.setText("")
        elif visible == total:
            self._count_label.setText(f"{total} results")
        else:
            self._count_label.setText(f"{visible} of {total} results")

    # ── Selection ──

    def _on_click(self, row: int, _col: int):
        """Show detail for the clicked result."""
        part = self.get_result(row)
        if part:
            self._detail.setHtml(render_part_html(part))
            self.part_clicked.emit(row)

    def _on_double_click(self, row: int, _col: int):
        """Emit part_selected for assignment."""
        self.part_selected.emit(row)

    def _on_context_menu(self, pos):
        """Show right-click context menu."""
        item = self.table.itemAt(pos)
        if item is None:
            return
        row = item.row()
        part = self.get_result(row)
        if part is None:
            return

        menu = QMenu(self)

        assign_action = QAction("Assign to component", self)
        assign_action.triggered.connect(lambda: self.part_selected.emit(row))
        menu.addAction(assign_action)

        menu.exec(self.table.viewport().mapToGlobal(pos))

