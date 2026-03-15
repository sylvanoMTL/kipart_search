"""Results table widget — displays search results with filters and detail view."""

from __future__ import annotations

from html import escape

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


COLUMNS = ["MPN", "Manufacturer", "Description", "Package", "Category", "Source"]


class ResultsTable(QWidget):
    """Table displaying component search results with filters and detail view."""

    part_selected = Signal(int)  # Emits row index on double-click (for assignment)

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
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        self.table.cellClicked.connect(self._on_click)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        splitter.addWidget(self.table)

        self._detail = QTextBrowser()
        self._detail.setReadOnly(True)
        self._detail.setOpenExternalLinks(True)
        splitter.addWidget(self._detail)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

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

        # Populate table
        self.table.setRowCount(len(results))
        for row, part in enumerate(results):
            self.table.setItem(row, 0, QTableWidgetItem(part.mpn))
            self.table.setItem(row, 1, QTableWidgetItem(part.manufacturer))
            self.table.setItem(row, 2, QTableWidgetItem(part.description))
            self.table.setItem(row, 3, QTableWidgetItem(part.package))
            self.table.setItem(row, 4, QTableWidgetItem(part.category))
            self.table.setItem(row, 5, QTableWidgetItem(part.source))

        self.table.resizeColumnsToContents()
        self._apply_filters()

    def get_result(self, row: int) -> PartResult | None:
        """Return the PartResult for a given row index."""
        if 0 <= row < len(self._results):
            return self._results[row]
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

        for row, part in enumerate(self._results):
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
            self._detail.setHtml(self._render_detail(part))

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

    # ── Detail rendering ──

    @staticmethod
    def _render_detail(part: PartResult) -> str:
        """Render an HTML detail view for a PartResult."""
        lines: list[str] = []

        lines.append(f"<h2>{escape(part.mpn)}</h2>")

        if part.source_part_id:
            lines.append(f"<b>LCSC:</b> {escape(part.source_part_id)}<br>")
        if part.manufacturer:
            lines.append(f"<b>Manufacturer:</b> {escape(part.manufacturer)}<br>")
        if part.category:
            lines.append(f"<b>Category:</b> {escape(part.category)}<br>")
        if part.package:
            lines.append(f"<b>Package:</b> {escape(part.package)}<br>")
        if part.lifecycle:
            lines.append(f"<b>Lifecycle:</b> {escape(part.lifecycle)}<br>")
        if part.description:
            lines.append(f"<b>Description:</b> {escape(part.description)}<br>")
        if part.datasheet_url:
            url = escape(part.datasheet_url)
            lines.append(f'<b>Datasheet:</b> <a href="{url}">{url}</a><br>')
        if part.source_url:
            url = escape(part.source_url)
            lines.append(f'<b>Source:</b> <a href="{url}">{url}</a><br>')
        if part.stock is not None:
            lines.append(f"<b>Stock:</b> {part.stock:,}<br>")

        # Parametric specs table
        if part.specs:
            lines.append("<h3>Parameters</h3>")
            lines.append('<table border="1" cellpadding="4" cellspacing="0">')
            lines.append("<tr><th>Parameter</th><th>Value</th></tr>")
            for spec in part.specs:
                lines.append(
                    f"<tr><td>{escape(spec.name)}</td>"
                    f"<td>{escape(spec.raw_value)}</td></tr>"
                )
            lines.append("</table>")

        # Pricing table
        if part.price_breaks:
            lines.append("<h3>Pricing</h3>")
            lines.append('<table border="1" cellpadding="4" cellspacing="0">')
            lines.append("<tr><th>Qty</th><th>Unit Price</th></tr>")
            for pb in part.price_breaks:
                lines.append(
                    f"<tr><td>{pb.quantity}</td>"
                    f"<td>{pb.unit_price:.4f} {escape(pb.currency)}</td></tr>"
                )
            lines.append("</table>")

        return "\n".join(lines)
