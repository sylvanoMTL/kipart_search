"""Verification dashboard — Scan Project results with colour-coded status."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QApplication,
    QHeaderView,
    QLabel,
    QMenu,
    QProgressBar,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from kipart_search.core.models import Confidence
from kipart_search.core.models import BoardComponent


# Colours for confidence levels
COLORS = {
    Confidence.GREEN: QColor(200, 255, 200),   # Light green
    Confidence.AMBER: QColor(255, 235, 180),   # Light amber
    Confidence.RED: QColor(255, 200, 200),      # Light red
}

_EMPTY_GUIDANCE = "Scan a project or open a BOM to begin"

# Hex color strings matching the COLORS QColor values
_COLOR_HEX = {
    Confidence.GREEN: "#C8FFC8",
    Confidence.AMBER: "#FFEBB4",
    Confidence.RED: "#FFC8C8",
}

VERIFY_COLUMNS = ["Reference", "Value", "MPN", "MPN Status", "Footprint"]


class VerifyPanel(QWidget):
    """Verification dashboard showing BOM health."""

    component_clicked = Signal(str)  # Emits reference when row clicked
    search_for_component = Signal(int)  # Emits row index on double-click missing MPN

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Summary bar
        self.summary_label = QLabel(_EMPTY_GUIDANCE)
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.summary_label.setStyleSheet("color: #888;")
        self.summary_label.setAccessibleName("BOM health summary")
        layout.addWidget(self.summary_label)

        # Health bar
        self.health_bar = QProgressBar()
        self.health_bar.setMinimum(0)
        self.health_bar.setTextVisible(True)
        self.health_bar.setVisible(False)
        self.health_bar.setAccessibleName("BOM health progress")
        self.health_bar.setAccessibleDescription(
            "Shows percentage of components with verified MPNs"
        )
        layout.addWidget(self.health_bar)

        # Splitter: table (top) | detail (bottom)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Verification table
        self.table = QTableWidget()
        self.table.setColumnCount(len(VERIFY_COLUMNS))
        self.table.setHorizontalHeaderLabels(VERIFY_COLUMNS)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            "QTableWidget { gridline-color: #d0d0d0; }"
            "QTableWidget::item:selected { background-color: #3399ff; color: white; }"
            "QTableWidget::item:hover { background-color: #e0eeff; }"
        )
        self.table.setAccessibleName("Component verification table")
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        splitter.addWidget(self.table)

        # Detail browser
        self._detail = QTextBrowser()
        self._detail.setReadOnly(True)
        self._detail.setOpenExternalLinks(True)
        splitter.addWidget(self._detail)

        # Table gets most space; detail is secondary and collapsible
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setCollapsible(1, True)

        layout.addWidget(splitter)

        self._components: list[BoardComponent] = []
        self._mpn_statuses: dict[str, Confidence] = {}

    def set_results(
        self,
        components: list[BoardComponent],
        mpn_statuses: dict[str, Confidence],
    ) -> None:
        """Populate the verification table.

        Args:
            components: List of board components from KiCad
            mpn_statuses: Map of reference -> confidence level from MPN verification
        """
        self._components = list(components)
        self._mpn_statuses = dict(mpn_statuses)
        self._detail.clear()

        # Disable sorting during insertion to avoid mid-build reorder
        self.table.setSortingEnabled(False)
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
            ref_item.setData(Qt.ItemDataRole.UserRole, row)  # original index
            self.table.setItem(row, 0, ref_item)

            # Value
            val_item = QTableWidgetItem(comp.value)
            val_item.setBackground(bg_color)
            val_item.setData(Qt.ItemDataRole.UserRole, row)
            self.table.setItem(row, 1, val_item)

            # MPN
            mpn_item = QTableWidgetItem(comp.mpn if comp.has_mpn else "(missing)")
            mpn_item.setBackground(bg_color)
            mpn_item.setData(Qt.ItemDataRole.UserRole, row)
            self.table.setItem(row, 2, mpn_item)

            # MPN Status — descriptive labels + tooltips + accessibility
            status_text = {
                Confidence.GREEN: "Verified",
                Confidence.AMBER: "Needs attention",
                Confidence.RED: "Missing MPN" if not comp.has_mpn else "Not found",
            }[status]
            tooltip = {
                Confidence.GREEN: "Part verified — found in configured source",
                Confidence.AMBER: "Needs attention — verify MPN manually",
                Confidence.RED: (
                    "No MPN assigned — right-click to search or assign"
                    if not comp.has_mpn
                    else "MPN not found in any configured source"
                ),
            }[status]
            status_item = QTableWidgetItem(status_text)
            status_item.setBackground(bg_color)
            status_item.setToolTip(tooltip)
            status_item.setData(Qt.ItemDataRole.UserRole, row)
            self.table.setItem(row, 3, status_item)

            # Footprint
            fp_item = QTableWidgetItem(comp.footprint_short)
            fp_color = COLORS[Confidence.GREEN] if comp.footprint else COLORS[Confidence.RED]
            fp_item.setBackground(fp_color)
            fp_item.setData(Qt.ItemDataRole.UserRole, row)
            self.table.setItem(row, 4, fp_item)

        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)

        # Update summary
        total = len(components)
        if total > 0:
            self.summary_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self.summary_label.setStyleSheet("")
            pct = int(has_mpn / total * 100)
            summary = (
                f"Components: {total} total | "
                f"Valid MPN: {has_mpn} | "
                f"Needs attention: {issues} | "
                f"Missing MPN: {missing_mpn}"
            )
            if pct >= 100:
                summary += " — Ready for export"
            self.summary_label.setText(summary)
            self.health_bar.setMaximum(total)
            self.health_bar.setValue(has_mpn)
            self.health_bar.setFormat(f"Ready: {pct}%")
            self.health_bar.setVisible(True)
            self._update_health_bar_style(pct)
        else:
            self.summary_label.setText("No components found")
            self.summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.summary_label.setStyleSheet("color: #888;")
            self.health_bar.setVisible(False)

    def update_component_status(self, reference: str, new_status: Confidence) -> None:
        """Update a single component's MPN status and refresh the health bar.

        Used for live updates after MPN assignment — avoids a full re-scan.
        """
        self._mpn_statuses[reference] = new_status
        new_bg = COLORS[new_status]

        # Update the visual row (sort-safe: iterate all rows, check UserRole)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is None:
                continue
            orig_idx = item.data(Qt.ItemDataRole.UserRole)
            if orig_idx is not None and 0 <= orig_idx < len(self._components):
                comp = self._components[orig_idx]
                if comp.reference == reference:
                    # Update background for all cells in this row
                    for col in range(self.table.columnCount()):
                        cell = self.table.item(row, col)
                        if cell:
                            cell.setBackground(new_bg)
                    # Update MPN Status cell text and tooltip (column 3)
                    status_item = self.table.item(row, 3)
                    if status_item:
                        status_text = {
                            Confidence.GREEN: "Verified",
                            Confidence.AMBER: "Needs attention",
                            Confidence.RED: "Not found",
                        }[new_status]
                        tooltip = {
                            Confidence.GREEN: "Part verified — found in configured source",
                            Confidence.AMBER: "Needs attention — verify MPN manually",
                            Confidence.RED: "MPN not found in any configured source",
                        }[new_status]
                        status_item.setText(status_text)
                        status_item.setToolTip(tooltip)
                    break

        # Recompute counts from _mpn_statuses
        has_mpn = 0
        missing_mpn = 0
        issues = 0
        for comp in self._components:
            status = self._mpn_statuses.get(comp.reference, Confidence.RED)
            if not comp.has_mpn and status == Confidence.RED:
                missing_mpn += 1
            elif status == Confidence.GREEN:
                has_mpn += 1
            else:
                issues += 1

        total = len(self._components)
        if total > 0:
            pct = int(has_mpn / total * 100)
            summary = (
                f"Components: {total} total | "
                f"Valid MPN: {has_mpn} | "
                f"Needs attention: {issues} | "
                f"Missing MPN: {missing_mpn}"
            )
            if pct >= 100:
                summary += " — Ready for export"
            self.summary_label.setText(summary)
            self.health_bar.setValue(has_mpn)
            self.health_bar.setFormat(f"Ready: {pct}%")
            self._update_health_bar_style(pct)

    def _update_health_bar_style(self, pct: int) -> None:
        """Apply color-coded stylesheet to the health bar based on percentage."""
        if pct >= 100:
            color = _COLOR_HEX[Confidence.GREEN]
        elif pct >= 50:
            color = _COLOR_HEX[Confidence.AMBER]
        else:
            color = _COLOR_HEX[Confidence.RED]
        self.health_bar.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {color}; }}"
        )

    def _original_index(self, row: int) -> int | None:
        """Return the original component index stored in a visual row."""
        item = self.table.item(row, 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def get_component(self, row: int) -> BoardComponent | None:
        """Return the BoardComponent for a given visual row (sort-safe)."""
        idx = self._original_index(row)
        if idx is not None and 0 <= idx < len(self._components):
            return self._components[idx]
        return None

    def _on_cell_clicked(self, row: int, _col: int):
        comp = self.get_component(row)
        if comp:
            self.component_clicked.emit(comp.reference)
            status = self._mpn_statuses.get(comp.reference, Confidence.RED)
            self._detail.setHtml(self._render_detail(comp, status))

    def _on_cell_double_clicked(self, row: int, _col: int):
        """Double-click any row to open guided search for that component."""
        if 0 <= row < len(self._components):
            self.search_for_component.emit(row)

    def _on_context_menu(self, pos: QPoint):
        """Show right-click context menu for a verification table row."""
        item = self.table.itemAt(pos)
        if item is None:
            return
        row = item.row()
        menu = self._build_context_menu(row)
        if menu:
            menu.exec(self.table.viewport().mapToGlobal(pos))

    def _build_context_menu(self, row: int) -> QMenu | None:
        """Build context menu for the given row. Returns None if row is invalid."""
        comp = self.get_component(row)
        if comp is None:
            return None

        menu = QMenu(self)

        search_action = QAction("Search for this component", self)
        search_action.triggered.connect(lambda: self.search_for_component.emit(row))
        menu.addAction(search_action)

        assign_action = QAction("Assign MPN", self)
        assign_action.triggered.connect(lambda: self.component_clicked.emit(comp.reference))
        menu.addAction(assign_action)

        copy_action = QAction("Copy MPN", self)
        mpn = comp.mpn if comp.has_mpn else ""
        if mpn:
            copy_action.triggered.connect(lambda: QApplication.clipboard().setText(mpn))
        else:
            copy_action.setEnabled(False)
        menu.addAction(copy_action)

        return menu

    def clear(self):
        """Clear the verification table."""
        self.table.setRowCount(0)
        self.summary_label.setText(_EMPTY_GUIDANCE)
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.summary_label.setStyleSheet("color: #888;")
        self.health_bar.setVisible(False)
        self._detail.clear()

    @staticmethod
    def _render_detail(comp: BoardComponent, status: Confidence) -> str:
        """Render HTML detail view for a BoardComponent."""
        status_labels = {
            Confidence.GREEN: ('<span style="color: green;">Verified</span>'),
            Confidence.AMBER: ('<span style="color: #cc8800;">Uncertain</span>'),
            Confidence.RED: ('<span style="color: red;">Missing / Not Found</span>'),
        }

        lines: list[str] = []
        lines.append(f"<h2>{escape(comp.reference)}</h2>")
        lines.append(f"<b>Value:</b> {escape(comp.value)}<br>")
        lines.append(f"<b>MPN:</b> {escape(comp.mpn) if comp.has_mpn else '<i>(missing)</i>'}<br>")
        lines.append(f"<b>Status:</b> {status_labels[status]}<br>")
        lines.append(f"<b>Footprint:</b> {escape(comp.footprint)}<br>")

        if comp.datasheet:
            url = escape(comp.datasheet)
            lines.append(f'<b>Datasheet:</b> <a href="{url}">{url}</a><br>')

        # Extra fields
        if comp.extra_fields:
            lines.append("<h3>Fields</h3>")
            lines.append('<table border="1" cellpadding="4" cellspacing="0">')
            lines.append("<tr><th>Field</th><th>Value</th></tr>")
            for fname, fval in sorted(comp.extra_fields.items()):
                lines.append(
                    f"<tr><td>{escape(fname)}</td>"
                    f"<td>{escape(fval)}</td></tr>"
                )
            lines.append("</table>")

        return "\n".join(lines)
