"""Verification dashboard — Scan Project results with colour-coded status."""

from __future__ import annotations

from html import escape
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from kipart_search.core.models import BoardComponent, Confidence, UserVerificationStatus

# Pro-gated verification columns (future: datasheet URL check, footprint consistency)
# These columns will show a "Pro" tooltip when the full checks are implemented.
_PRO_VERIFY_COLUMNS = {"Datasheet", "Symbol"}


# Colours for confidence levels
COLORS = {
    Confidence.GREEN: QColor(200, 255, 200),   # Light green
    Confidence.AMBER: QColor(255, 235, 180),   # Light amber
    Confidence.RED: QColor(255, 200, 200),      # Light red
}

# Special colors for dual-source scan states
_COLOR_SCH_ONLY = QColor(200, 224, 255)     # Light blue (#C8E0FF)
_COLOR_DESYNC = QColor(255, 235, 180)       # Amber (same as AMBER)

_EMPTY_GUIDANCE = "Scan a project or open a BOM to begin"

# Hex color strings matching the COLORS QColor values
_COLOR_HEX = {
    Confidence.GREEN: "#C8FFC8",
    Confidence.AMBER: "#FFEBB4",
    Confidence.RED: "#FFC8C8",
}

_STATUS_LABELS = {
    Confidence.GREEN: "Verified",
    Confidence.AMBER: "Needs attention",
    Confidence.RED: "Not found",
}

# Labels for components with MPN when no sources were available to verify
_UNVERIFIED_LABEL = "Unverified"
_UNVERIFIED_TOOLTIP = "MPN present but no sources were available to verify it"

_STATUS_TOOLTIPS = {
    Confidence.GREEN: "Part verified — found in configured source",
    Confidence.AMBER: "Needs attention — verify MPN manually",
    Confidence.RED: "MPN not found in any configured source",
}

VERIFY_COLUMNS = ["Reference", "Value", "MPN", "MPN Status", "Review", "Footprint"]

# User review status colors and labels
_REVIEW_COLORS = {
    UserVerificationStatus.VERIFIED: QColor(200, 255, 200),   # Light green
    UserVerificationStatus.ATTENTION: QColor(255, 235, 180),  # Light amber
    UserVerificationStatus.REJECTED: QColor(255, 200, 200),   # Light red
}
_REVIEW_LABELS = {
    UserVerificationStatus.NONE: "",
    UserVerificationStatus.VERIFIED: "Verified",
    UserVerificationStatus.ATTENTION: "Needs Attention",
    UserVerificationStatus.REJECTED: "Rejected",
}
_REVIEW_SORT_ORDER = {
    UserVerificationStatus.NONE: 3,
    UserVerificationStatus.REJECTED: 0,
    UserVerificationStatus.ATTENTION: 1,
    UserVerificationStatus.VERIFIED: 2,
}

# Sort order for status: red first, then amber, then green
_SORT_ORDER = {Confidence.RED: 0, Confidence.AMBER: 1, Confidence.GREEN: 2}


class _StatusItem(QTableWidgetItem):
    """Table item that sorts by confidence level rather than text."""

    def __lt__(self, other: QTableWidgetItem) -> bool:
        my_order = self.data(Qt.ItemDataRole.UserRole + 1)
        other_order = other.data(Qt.ItemDataRole.UserRole + 1)
        if my_order is not None and other_order is not None:
            return my_order < other_order
        return super().__lt__(other)


class VerifyPanel(QWidget):
    """Verification dashboard showing BOM health."""

    component_clicked = Signal(str)  # Emits reference when row clicked
    search_for_component = Signal(int)  # Emits row index on double-click missing MPN
    manual_assign_requested = Signal(str)  # Emits reference for manual MPN assignment
    refresh_requested = Signal()  # Emitted when Refresh BOM button is clicked
    user_status_changed = Signal(list, object)  # Emits (references, UserVerificationStatus)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Summary row: label (stretch) + Re-verify button
        summary_row = QHBoxLayout()
        self.summary_label = QLabel(_EMPTY_GUIDANCE)
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.summary_label.setStyleSheet("color: #888;")
        self.summary_label.setAccessibleName("BOM health summary")
        summary_row.addWidget(self.summary_label, 1)

        self.refresh_button = QPushButton("Refresh BOM")
        self.refresh_button.setAccessibleName("Refresh BOM")
        self.refresh_button.setToolTip("Re-read components from KiCad (preserves verification status)")
        self.refresh_button.setVisible(False)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        summary_row.addWidget(self.refresh_button)

        layout.addLayout(summary_row)

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
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
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
        self._has_active_sources: bool = True
        self._db_mtime: float | None = None
        self._user_statuses: dict[str, UserVerificationStatus] = {}
        self._project_dir: Path | None = None

    def set_results(
        self,
        components: list[BoardComponent],
        mpn_statuses: dict[str, Confidence],
        has_active_sources: bool = True,
        db_mtime: float | None = None,
        user_statuses: dict[str, UserVerificationStatus] | None = None,
        project_dir: Path | None = None,
    ) -> None:
        """Populate the verification table.

        Args:
            components: List of board components from KiCad
            mpn_statuses: Map of reference -> confidence level from MPN verification
            has_active_sources: Whether any data sources were available for verification
            db_mtime: Database file modification time for stale detection
            user_statuses: Map of reference -> user review status (persisted per-project)
            project_dir: KiCad project directory for state persistence
        """
        self._components = list(components)
        self._mpn_statuses = dict(mpn_statuses)
        self._has_active_sources = has_active_sources
        self._db_mtime = db_mtime
        if user_statuses is not None:
            self._user_statuses = dict(user_statuses)
        if project_dir is not None:
            self._project_dir = project_dir
        self._detail.clear()

        # Disable sorting during insertion to avoid mid-build reorder
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(components))

        footprint_col = VERIFY_COLUMNS.index("Footprint")
        review_col = VERIFY_COLUMNS.index("Review")

        for row, comp in enumerate(components):
            status = mpn_statuses.get(comp.reference, Confidence.RED)

            # Resolve status label/tooltip — handle dual-source states first
            if comp.source == "sch_only":
                status_text = "Not on PCB"
                tooltip = "Component exists only in schematic — not placed on PCB"
                bg_color = _COLOR_SCH_ONLY
            elif comp.sync_mismatches:
                status_text = "PCB out of sync"
                tooltip = "\n".join(comp.sync_mismatches)
                tooltip += "\nRun Update PCB from Schematic (F8) in KiCad"
                bg_color = _COLOR_DESYNC
            elif status == Confidence.RED and not comp.has_mpn:
                status_text = "Missing MPN"
                tooltip = "No MPN assigned — right-click to search or assign"
                bg_color = COLORS[status]
            elif status == Confidence.RED and comp.has_mpn and not has_active_sources:
                status_text = _UNVERIFIED_LABEL
                tooltip = _UNVERIFIED_TOOLTIP
                status = Confidence.AMBER  # Downgrade: has MPN, just unverified
                bg_color = COLORS[status]
            else:
                status_text = _STATUS_LABELS[status]
                tooltip = _STATUS_TOOLTIPS[status]
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
            status_item = _StatusItem(status_text)
            status_item.setBackground(bg_color)
            status_item.setToolTip(tooltip)
            status_item.setData(Qt.ItemDataRole.UserRole, row)
            # Sort desynced/sch-only as AMBER so they appear near the top
            if comp.source == "sch_only" or comp.sync_mismatches:
                sort_order = _SORT_ORDER[Confidence.AMBER]
            else:
                sort_order = _SORT_ORDER[status]
            status_item.setData(Qt.ItemDataRole.UserRole + 1, sort_order)
            self.table.setItem(row, 3, status_item)

            # Review (user verification status)
            user_status = self._user_statuses.get(
                comp.reference, UserVerificationStatus.NONE
            )
            review_item = _StatusItem(_REVIEW_LABELS[user_status])
            review_item.setData(Qt.ItemDataRole.UserRole, row)
            review_item.setData(
                Qt.ItemDataRole.UserRole + 1, _REVIEW_SORT_ORDER[user_status]
            )
            if user_status != UserVerificationStatus.NONE:
                review_item.setBackground(_REVIEW_COLORS[user_status])
            review_item.setToolTip(
                "Right-click to set your review decision"
                if user_status == UserVerificationStatus.NONE
                else f"Your review: {_REVIEW_LABELS[user_status]}"
            )
            self.table.setItem(row, review_col, review_item)

            # Footprint
            fp_item = QTableWidgetItem(comp.footprint_short)
            fp_color = COLORS[Confidence.GREEN] if comp.footprint else COLORS[Confidence.RED]
            fp_item.setBackground(fp_color)
            fp_item.setData(Qt.ItemDataRole.UserRole, row)
            self.table.setItem(row, footprint_col, fp_item)

        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)

        # Default sort: red first, then amber, then green
        status_col = VERIFY_COLUMNS.index("MPN Status")
        self.table.sortByColumn(status_col, Qt.SortOrder.AscendingOrder)

        # Update summary using shared counting logic
        self._refresh_health_bar()

    def update_component_status(self, reference: str, new_status: Confidence) -> None:
        """Update a single component's MPN status and refresh the health bar.

        Used for live updates after MPN assignment — avoids a full re-scan.
        """
        self._mpn_statuses[reference] = new_status

        # Update the visual row (sort-safe: iterate all rows, check UserRole)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is None:
                continue
            orig_idx = item.data(Qt.ItemDataRole.UserRole)
            if orig_idx is not None and 0 <= orig_idx < len(self._components):
                comp = self._components[orig_idx]
                if comp.reference == reference:
                    # Resolve visual state — sch-only/desynced override normal colors
                    if comp.source == "sch_only":
                        bg = _COLOR_SCH_ONLY
                        label = "Not on PCB"
                        tip = "Component exists only in schematic — not placed on PCB"
                        sort = _SORT_ORDER[Confidence.AMBER]
                    elif comp.sync_mismatches:
                        bg = _COLOR_DESYNC
                        label = "PCB out of sync"
                        tip = "\n".join(comp.sync_mismatches)
                        tip += "\nRun Update PCB from Schematic (F8) in KiCad"
                        sort = _SORT_ORDER[Confidence.AMBER]
                    else:
                        bg = COLORS[new_status]
                        label = _STATUS_LABELS[new_status]
                        tip = _STATUS_TOOLTIPS[new_status]
                        sort = _SORT_ORDER[new_status]

                    # Update background for all cells except Review column
                    review_col = VERIFY_COLUMNS.index("Review")
                    for col in range(self.table.columnCount()):
                        if col == review_col:
                            continue  # Review column has its own color
                        cell = self.table.item(row, col)
                        if cell:
                            cell.setBackground(bg)
                    # Update MPN cell text (column 2) if MPN was assigned
                    mpn_item = self.table.item(row, 2)
                    if mpn_item and comp.has_mpn:
                        mpn_item.setText(comp.mpn)
                    # Update MPN Status cell text and tooltip (column 3)
                    status_item = self.table.item(row, 3)
                    if status_item:
                        status_item.setText(label)
                        status_item.setToolTip(tip)
                        status_item.setData(
                            Qt.ItemDataRole.UserRole + 1, sort,
                        )
                    break

        self._refresh_health_bar()

    @staticmethod
    def _build_summary(
        total: int, has_mpn: int, issues: int, missing_mpn: int, pct: int,
        sch_only: int = 0,
    ) -> str:
        """Build the health summary text."""
        summary = (
            f"Components: {total} total | "
            f"Valid MPN: {has_mpn} | "
            f"Needs attention: {issues} | "
            f"Missing MPN: {missing_mpn}"
        )
        if sch_only > 0:
            summary += f" | Not on PCB: {sch_only}"
        if pct >= 100 and sch_only == 0:
            summary += " — Ready for export"
        return summary

    def _is_healthy(self, comp: BoardComponent) -> bool:
        """Determine if a component is healthy for health bar counting.

        User review status overrides auto-check:
        - VERIFIED → healthy (regardless of auto-check)
        - REJECTED / ATTENTION → unhealthy (regardless of auto-check)
        - NONE → fall back to auto-check logic
        """
        user_status = self._user_statuses.get(
            comp.reference, UserVerificationStatus.NONE
        )
        if user_status == UserVerificationStatus.VERIFIED:
            return True
        if user_status in (UserVerificationStatus.REJECTED, UserVerificationStatus.ATTENTION):
            return False
        # NONE — fall back to auto-check
        if comp.source == "sch_only":
            return False
        if comp.sync_mismatches:
            return False
        return self._mpn_statuses.get(comp.reference) == Confidence.GREEN

    def _compute_health_counts(self) -> tuple[int, int, int, int, int]:
        """Compute health counts respecting user review overrides.

        Returns (total, healthy, issues, missing_mpn, sch_only).
        """
        healthy = 0
        missing_mpn = 0
        issues = 0
        sch_only_count = 0

        for comp in self._components:
            if comp.source == "sch_only":
                sch_only_count += 1
                issues += 1
                continue

            if self._is_healthy(comp):
                healthy += 1
            elif not comp.has_mpn:
                user_status = self._user_statuses.get(
                    comp.reference, UserVerificationStatus.NONE
                )
                if user_status == UserVerificationStatus.NONE:
                    missing_mpn += 1
                else:
                    issues += 1
            else:
                issues += 1

        return len(self._components), healthy, issues, missing_mpn, sch_only_count

    def _refresh_health_bar(self) -> None:
        """Recompute and update the health bar and summary label."""
        total, healthy, issues, missing_mpn, sch_only = self._compute_health_counts()
        if total > 0:
            self.summary_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self.summary_label.setStyleSheet("")
            pct = int(healthy / total * 100)
            self.summary_label.setText(
                self._build_summary(total, healthy, issues, missing_mpn, pct,
                                    sch_only=sch_only)
            )
            self.health_bar.setMaximum(total)
            self.health_bar.setValue(healthy)
            self.health_bar.setFormat(f"Ready: {pct}%")
            self.health_bar.setVisible(True)
            self._update_health_bar_style(pct)
            self.refresh_button.setVisible(True)
        else:
            self.summary_label.setText("No components found")
            self.summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.summary_label.setStyleSheet("color: #888;")
            self.health_bar.setVisible(False)
            self.refresh_button.setVisible(False)

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
        if self.get_component(row) is not None:
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

    def _get_selected_references(self) -> list[str]:
        """Return references for all selected rows."""
        refs: list[str] = []
        seen_rows: set[int] = set()
        for item in self.table.selectedItems():
            visual_row = item.row()
            if visual_row in seen_rows:
                continue
            seen_rows.add(visual_row)
            comp = self.get_component(visual_row)
            if comp:
                refs.append(comp.reference)
        return refs

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

        manual_action = QAction("Manual Assign", self)
        manual_action.triggered.connect(lambda: self.manual_assign_requested.emit(comp.reference))
        menu.addAction(manual_action)

        copy_action = QAction("Copy MPN", self)
        mpn = comp.mpn if comp.has_mpn else ""
        if mpn:
            copy_action.triggered.connect(lambda: QApplication.clipboard().setText(mpn))
        else:
            copy_action.setEnabled(False)
        menu.addAction(copy_action)

        # --- User review status ---
        menu.addSeparator()

        for label, status in [
            ("Mark as Verified", UserVerificationStatus.VERIFIED),
            ("Mark as Needs Attention", UserVerificationStatus.ATTENTION),
            ("Mark as Rejected", UserVerificationStatus.REJECTED),
            ("Clear Review Status", UserVerificationStatus.NONE),
        ]:
            action = QAction(label, self)
            # Capture status in closure via default arg
            action.triggered.connect(
                lambda checked=False, s=status: self.set_user_status(
                    self._get_selected_references(), s
                )
            )
            menu.addAction(action)

        return menu

    def get_components(self) -> list[BoardComponent]:
        """Return the list of board components from the last scan."""
        return list(self._components)

    def get_health_percentage(self) -> int:
        """Return the current BOM health percentage (0-100).

        User review status overrides auto-check:
        - VERIFIED → healthy (regardless of auto-check)
        - REJECTED / ATTENTION → unhealthy (regardless of auto-check)
        - NONE → fall back to auto-check logic

        Sch-only components are excluded from both numerator and denominator.
        """
        pcb_components = [c for c in self._components if c.source != "sch_only"]
        total = len(pcb_components)
        if total == 0:
            return 0
        healthy = sum(1 for c in pcb_components if self._is_healthy(c))
        return int(healthy / total * 100)

    def get_missing_mpn_count(self) -> int:
        """Return the count of components missing an MPN."""
        return sum(1 for c in self._components if not c.has_mpn)

    def set_user_status(
        self, references: list[str], status: UserVerificationStatus
    ) -> None:
        """Update user review status for given components. Persists immediately."""
        if not references:
            return

        review_col = VERIFY_COLUMNS.index("Review")

        for ref in references:
            if status == UserVerificationStatus.NONE:
                self._user_statuses.pop(ref, None)
            else:
                self._user_statuses[ref] = status

            # Update the visual Review cell
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item is None:
                    continue
                orig_idx = item.data(Qt.ItemDataRole.UserRole)
                if orig_idx is not None and 0 <= orig_idx < len(self._components):
                    if self._components[orig_idx].reference == ref:
                        review_item = self.table.item(row, review_col)
                        if review_item:
                            review_item.setText(_REVIEW_LABELS[status])
                            review_item.setData(
                                Qt.ItemDataRole.UserRole + 1,
                                _REVIEW_SORT_ORDER[status],
                            )
                            if status != UserVerificationStatus.NONE:
                                review_item.setBackground(
                                    _REVIEW_COLORS[status]
                                )
                                review_item.setToolTip(
                                    f"Your review: {_REVIEW_LABELS[status]}"
                                )
                            else:
                                review_item.setBackground(QColor())
                                review_item.setToolTip(
                                    "Right-click to set your review decision"
                                )
                        break

        self._refresh_health_bar()
        self.user_status_changed.emit(references, status)

    def get_project_dir(self) -> Path | None:
        """Return the current project directory (or None if not set)."""
        return self._project_dir

    def get_user_statuses(self) -> dict[str, UserVerificationStatus]:
        """Return the current user verification statuses dict."""
        return dict(self._user_statuses)

    def update_license_state(self) -> None:
        """Update Pro-gated visual indicators based on current license tier.

        Currently the verify panel only performs basic MPN presence checks
        (free tier). When full verification is implemented (datasheet URL
        reachability, footprint consistency against distributor data, symbol
        validation), this method will enable/disable those check columns.
        """
        from kipart_search.core.license import License

        is_pro = License.instance().has("full_verification")
        # Future: when Datasheet/Symbol columns are added to VERIFY_COLUMNS,
        # gray them out and add "Requires Pro license" tooltip when !is_pro.

    def clear(self):
        """Clear the verification table."""
        self.table.setRowCount(0)
        self.summary_label.setText(_EMPTY_GUIDANCE)
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.summary_label.setStyleSheet("color: #888;")
        self.health_bar.setVisible(False)
        self.refresh_button.setVisible(False)
        self._detail.clear()
        self._user_statuses.clear()
        self._project_dir = None

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

        if comp.source == "sch_only":
            lines.append('<b>Source:</b> <span style="color: #3366aa;">Schematic only — not placed on PCB</span><br>')
        elif comp.source == "both" and comp.sync_mismatches:
            lines.append('<b>Source:</b> <span style="color: #cc8800;">PCB out of sync with schematic</span><br>')
            lines.append("<b>Mismatches:</b><ul>")
            for mm in comp.sync_mismatches:
                lines.append(f"<li>{escape(mm)}</li>")
            lines.append("</ul>")

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
