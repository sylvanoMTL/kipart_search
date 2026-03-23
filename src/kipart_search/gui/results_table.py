"""Results table widget — displays search results with filters and detail view."""

from __future__ import annotations

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
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


_EMPTY_GUIDANCE = (
    '<p style="text-align:center; color:#888; margin-top:40%;">'
    "Search for components using the query bar above</p>"
)

COLUMNS = ["MPN", "Manufacturer", "Description", "Package", "Category", "Source"]

# Field display name → PartResult attribute name, ordered by usefulness
FILTERABLE_FIELDS: list[tuple[str, str]] = [
    ("Manufacturer", "manufacturer"),
    ("Package", "package"),
    ("Category", "category"),
    ("Source", "source"),
]


class FilterRow(QWidget):
    """Dynamic filter row that creates/destroys QComboBox dropdowns based on results."""

    filters_changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAccessibleName("Search result filters")
        self.setAccessibleDescription(
            "Dynamic filter dropdowns that narrow search results by field values"
        )
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._combos: dict[str, QComboBox] = {}
        self._labels: list[QLabel] = []
        self._count_label = QLabel("")
        self._total = 0

    def update_filters(self, results: list[PartResult]) -> None:
        """Rebuild dropdowns based on the current result set."""
        self._clear_widgets()
        self._total = len(results)

        if not results:
            self.setVisible(False)
            return

        for display_name, attr_name in FILTERABLE_FIELDS:
            values = sorted(
                {getattr(p, attr_name, "") for p in results} - {""}
            )
            if len(values) < 2:
                continue

            label = QLabel(f"{display_name}:")
            combo = QComboBox()
            combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToContents
            )
            combo.blockSignals(True)
            combo.addItem("All")
            combo.addItems(values)
            combo.blockSignals(False)
            combo.currentIndexChanged.connect(self._on_combo_changed)

            self._layout.addWidget(label)
            self._layout.addWidget(combo)
            self._labels.append(label)
            self._combos[attr_name] = combo

        self._layout.addStretch()
        self._layout.addWidget(self._count_label)
        self.setVisible(bool(self._combos))

    def get_active_filters(self) -> dict[str, str]:
        """Return dict of {attr_name: selected_value} for non-'All' selections."""
        return {
            attr: combo.currentText()
            for attr, combo in self._combos.items()
            if combo.currentText() != "All"
        }

    def update_count(self, visible: int) -> None:
        """Update the result count label."""
        if self._total == 0:
            self._count_label.setText("")
        elif visible == self._total:
            self._count_label.setText(f"{self._total} results")
        else:
            self._count_label.setText(f"{visible} of {self._total} results")

    def clear(self) -> None:
        """Clear all filters and hide the row."""
        self._clear_widgets()
        self._total = 0
        self._count_label.setText("")
        self.setVisible(False)

    def _on_combo_changed(self) -> None:
        self.filters_changed.emit()

    def _clear_widgets(self) -> None:
        """Remove all combo boxes, labels, and stretch from the layout."""
        for combo in self._combos.values():
            self._layout.removeWidget(combo)
            combo.deleteLater()
        for label in self._labels:
            self._layout.removeWidget(label)
            label.deleteLater()
        self._combos.clear()
        self._labels.clear()
        # Remove count label and stretch items from layout
        self._layout.removeWidget(self._count_label)
        while self._layout.count():
            item = self._layout.takeAt(0)
            # Stretch items have no widget; just discard
            if item.widget() and item.widget() is not self._count_label:
                item.widget().deleteLater()


class ResultsTable(QWidget):
    """Table displaying component search results with filters and detail view."""

    part_selected = Signal(int)  # Emits row index on double-click (for assignment)
    part_clicked = Signal(int)   # Emits row index on single-click (for detail panel)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._results: list[PartResult] = []
        self._assign_target: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Filter row ──
        self._filter_row = FilterRow()
        self._filter_row.filters_changed.connect(self._apply_filters)
        self._filter_row.setVisible(False)
        layout.addWidget(self._filter_row)

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
        self.table.setAccessibleName("Search results table")
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

        # Show empty-state guidance
        self._detail.setHtml(_EMPTY_GUIDANCE)

    def set_source_column_visible(self, visible: bool) -> None:
        """Show or hide the Source column based on search mode."""
        source_col = COLUMNS.index("Source")
        self.table.setColumnHidden(source_col, not visible)

    def set_results(self, results: list[PartResult]) -> None:
        """Populate the table and filter dropdowns from search results."""
        self._results = list(results)
        self._detail.clear()

        # Rebuild dynamic filter row from new results
        self._filter_row.update_filters(results)

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
        self._detail.setHtml(_EMPTY_GUIDANCE)
        self._filter_row.clear()

    # ── Filtering ──

    def _apply_filters(self):
        """Show/hide rows based on dynamic filter selection."""
        active = self._filter_row.get_active_filters()
        visible = 0

        for row in range(self.table.rowCount()):
            part = self.get_result(row)
            if part is None:
                continue
            hide = any(
                getattr(part, attr, "") != value
                for attr, value in active.items()
            )
            self.table.setRowHidden(row, hide)
            if not hide:
                visible += 1

        self._filter_row.update_count(visible)

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

    def set_assign_target(self, reference: str | None) -> None:
        """Set the current assignment target reference designator."""
        self._assign_target = reference

    def _on_context_menu(self, pos):
        """Show right-click context menu."""
        item = self.table.itemAt(pos)
        if item is None:
            return
        row = item.row()
        menu = self._build_context_menu(row)
        if menu:
            menu.exec(self.table.viewport().mapToGlobal(pos))

    def _build_context_menu(self, row: int) -> QMenu | None:
        """Build context menu for the given row. Returns None if row is invalid."""
        part = self.get_result(row)
        if part is None:
            return None

        menu = QMenu(self)

        if self._assign_target:
            assign_action = QAction(f"Assign to {self._assign_target}", self)
            # Capture row by value (default arg) to avoid stale index
            assign_action.triggered.connect(lambda _=False, r=row: self.part_selected.emit(r))
            menu.addAction(assign_action)

        copy_action = QAction("Copy MPN", self)
        if part.mpn:
            copy_action.triggered.connect(
                lambda: QApplication.clipboard().setText(part.mpn)
            )
        else:
            copy_action.setEnabled(False)
        menu.addAction(copy_action)

        if part.datasheet_url:
            ds_action = QAction("Open Datasheet", self)
            ds_action.triggered.connect(
                lambda: QDesktopServices.openUrl(QUrl(part.datasheet_url))
            )
            menu.addAction(ds_action)

        return menu

