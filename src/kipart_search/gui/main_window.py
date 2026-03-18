"""Main application window."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSettings, QThread, QTimer, Signal, Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

log = logging.getLogger(__name__)

from kipart_search import __version__
from kipart_search.core.models import Confidence
from kipart_search.core.sources import JLCPCBSource
from kipart_search.core.search import SearchOrchestrator
from kipart_search.core.units import generate_query_variants
from kipart_search.gui.kicad_bridge import BoardComponent, KiCadBridge
from kipart_search.gui.detail_panel import DetailPanel
from kipart_search.gui.log_panel import LogPanel
from kipart_search.gui.search_bar import SearchBar
from kipart_search.gui.results_table import ResultsTable
from kipart_search.gui.verify_panel import VerifyPanel


class SearchWorker(QThread):
    """Background thread for running searches."""

    results_ready = Signal(list)
    error = Signal(str)
    log = Signal(str)

    def __init__(self, orchestrator: SearchOrchestrator, query: str):
        super().__init__()
        self.orchestrator = orchestrator
        self.query = query

    def run(self):
        try:
            variants = generate_query_variants(self.query)
            if len(variants) > 1:
                self.log.emit(
                    f"Searching for '{self.query}' + {len(variants) - 1} "
                    f"equivalent(s): {', '.join(repr(v) for v in variants)}"
                )
            else:
                self.log.emit(f"Searching for '{self.query}' ...")
            results = self.orchestrator.search(self.query, limit=200)
            self.log.emit(f"Found {len(results)} result(s).")
            self.results_ready.emit(results)
        except Exception as e:
            self.log.emit(f"Search error: {e}")
            self.error.emit(str(e))


class ScanWorker(QThread):
    """Background thread for scanning and verifying a KiCad project."""

    scan_complete = Signal(list, dict)  # components, mpn_statuses
    error = Signal(str)
    log = Signal(str)

    def __init__(self, bridge: KiCadBridge, orchestrator: SearchOrchestrator):
        super().__init__()
        self.bridge = bridge
        self.orchestrator = orchestrator

    def run(self):
        try:
            self.log.emit("Reading components from KiCad board ...")
            components = self.bridge.get_components()
            if not components:
                self.error.emit("No components found on the board")
                return

            self.log.emit(f"Read {len(components)} components. Verifying MPNs ...")

            mpn_statuses: dict[str, Confidence] = {}
            green = 0
            red = 0
            for comp in components:
                if not comp.has_mpn:
                    mpn_statuses[comp.reference] = Confidence.RED
                    red += 1
                    continue

                result = self.orchestrator.verify_mpn(comp.mpn)
                if result:
                    mpn_statuses[comp.reference] = result.confidence
                    if result.confidence == Confidence.GREEN:
                        green += 1
                else:
                    mpn_statuses[comp.reference] = Confidence.RED
                    red += 1

            self.log.emit(
                f"Scan complete: {green} verified, {red} missing/not found, "
                f"{len(components) - green - red} uncertain."
            )
            self.scan_complete.emit(components, mpn_statuses)
        except Exception as e:
            self.log.emit(f"Scan error: {e}")
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """KiPart Search main window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"KiPart Search v{__version__}")
        self.setMinimumSize(1000, 600)

        # Core engine
        self._orchestrator = SearchOrchestrator()
        self._jlcpcb_source: JLCPCBSource | None = None
        self._search_worker: SearchWorker | None = None
        self._scan_worker: ScanWorker | None = None
        self._bridge = KiCadBridge()
        self._assign_target: BoardComponent | None = None

        # ── Hidden central widget (QDockWidgets fill around it) ──
        # Dock-only layout: central widget shrinks to zero but stays resizable
        # so Qt's internal splitters between dock areas can function.
        placeholder = QWidget()
        placeholder.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setCentralWidget(placeholder)

        # ── Panel widgets ──
        self.verify_panel = VerifyPanel()
        self.verify_panel.component_clicked.connect(self._on_component_clicked)
        self.verify_panel.search_for_component.connect(self._on_guided_search)

        self.search_bar = SearchBar()
        self.search_bar.search_requested.connect(self._on_search)

        self.results_table = ResultsTable()
        self.results_table.part_selected.connect(self._on_part_selected)
        self.results_table.part_clicked.connect(self._on_part_clicked)

        self.detail_panel = DetailPanel()
        self.detail_panel.assign_requested.connect(self._on_detail_assign)

        self.log_panel = LogPanel()

        # ── Verify dock container ──
        verify_container = QWidget()
        verify_layout = QVBoxLayout(verify_container)
        verify_layout.setContentsMargins(0, 0, 0, 0)
        verify_layout.setSpacing(4)
        verify_layout.addWidget(self.verify_panel)

        # ── Search dock container ──
        search_container = QWidget()
        search_layout = QVBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(4)

        self._search_target_label = QLabel("")
        search_layout.addWidget(self._search_target_label)
        search_layout.addWidget(self.search_bar)
        search_layout.addWidget(self.results_table)

        # ── Dock widgets ──
        self.dock_verify = self._create_dock(
            "Verify", verify_container, Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.dock_search = self._create_dock(
            "Search", search_container, Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.dock_detail = self._create_dock(
            "Detail", self.detail_panel, Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.dock_detail.hide()  # hidden by default; available via View menu
        self.dock_log = self._create_dock(
            "Log", self.log_panel, Qt.DockWidgetArea.BottomDockWidgetArea
        )

        self._first_show = True

        # ── Toolbar ──
        self.toolbar = QToolBar("Main Toolbar", self)
        self.toolbar.setObjectName("main_toolbar")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        self._act_scan = QAction("Scan Project", self)
        self._act_scan.setToolTip("Connect to KiCad and verify BOM")
        self._act_scan.triggered.connect(self._on_scan)
        self.toolbar.addAction(self._act_scan)

        self._act_export = QAction("Export BOM", self)
        self._act_export.setEnabled(False)
        self._act_export.setToolTip("Export BOM (not yet implemented)")
        self.toolbar.addAction(self._act_export)

        self._act_push = QAction("Push to KiCad", self)
        self._act_push.setEnabled(False)
        self._act_push.setToolTip("Push changes to KiCad (requires connection)")
        self.toolbar.addAction(self._act_push)

        self._act_prefs = QAction("Preferences", self)
        self._act_prefs.setEnabled(False)
        self._act_prefs.setToolTip("Preferences (not yet implemented)")
        self.toolbar.addAction(self._act_prefs)

        # ── Menus (order: File, View, Help) ──
        self._build_menus()

        # ── Status bar with 3 zones ──
        self.status_bar = QStatusBar()
        self._mode_label = QLabel("  Standalone  ")
        self._sources_label = QLabel("")
        self._action_label = QLabel("Ready")
        self.status_bar.addWidget(self._mode_label)
        self.status_bar.addWidget(self._sources_label, 1)
        self.status_bar.addPermanentWidget(self._action_label)
        self.setStatusBar(self.status_bar)

        # Try to load existing database
        self._init_jlcpcb_source()
        self._update_status()

        # ── Restore saved layout (must come after all docks exist) ──
        settings = QSettings("kipart-search", "kipart-search")
        geometry = settings.value("geometry")
        state = settings.value("windowState")
        if geometry is not None:
            self.restoreGeometry(geometry)
        if state is not None:
            if not self.restoreState(state):
                log.warning("Failed to restore window state, using defaults")
                self._reset_layout()
            else:
                self._first_show = False  # skip default sizing, user has saved layout

    # --- Show / Close / persistence ---

    def showEvent(self, event):
        """Apply default dock sizes on first show, deferred so layout is finalised."""
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            QTimer.singleShot(0, self._apply_default_dock_sizes)

    def closeEvent(self, event: QCloseEvent):
        """Save window geometry and dock state before closing."""
        settings = QSettings("kipart-search", "kipart-search")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        event.accept()

    # --- Menu bar ---

    def _build_menus(self):
        """Build all menus in order: File, View, Help."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        scan_action = QAction("Scan Project", self)
        scan_action.triggered.connect(self._on_scan)
        file_menu.addAction(scan_action)

        db_action = QAction("Download Database", self)
        db_action.triggered.connect(self._on_download_db)
        file_menu.addAction(db_action)

        file_menu.addSeparator()

        quit_action = QAction("Close", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # View menu
        view_menu = menubar.addMenu("View")
        view_menu.addAction(self.dock_verify.toggleViewAction())
        view_menu.addAction(self.dock_search.toggleViewAction())
        view_menu.addAction(self.dock_detail.toggleViewAction())
        view_menu.addAction(self.dock_log.toggleViewAction())
        view_menu.addSeparator()
        reset_action = QAction("Reset Layout", self)
        reset_action.triggered.connect(self._reset_layout)
        view_menu.addAction(reset_action)

        # Help menu (last)
        help_menu = menubar.addMenu("Help")

        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_about(self):
        QMessageBox.about(
            self,
            "About KiPart Search",
            f"<h3>KiPart Search v{__version__}</h3>"
            "<p>Parametric electronic component search with KiCad integration.</p>"
            "<p><b>Author:</b> Sylvain Boyer (MecaFrog)</p>"
            "<p><b>License:</b> MIT</p>"
            '<p><a href="https://github.com/sylvanoMTL/kipart-search">'
            "github.com/sylvanoMTL/kipart-search</a></p>",
        )

    # --- Dock helpers ---

    def _create_dock(
        self, title: str, widget: QWidget, area: Qt.DockWidgetArea
    ) -> QDockWidget:
        """Create a QDockWidget wrapping *widget* and add it to *area*."""
        dock = QDockWidget(title, self)
        dock.setWidget(widget)
        dock.setObjectName(f"dock_{title.lower().replace(' ', '_')}")
        self.addDockWidget(area, dock)
        return dock

    def _apply_default_dock_sizes(self):
        """Set default dock proportions: Verify 50% | Search 50%, Log 20% height."""
        h = self.height()
        w = self.width()
        # Vertical: top panels 80%, log 20%
        self.resizeDocks(
            [self.dock_verify, self.dock_log],
            [int(h * 0.80), int(h * 0.20)],
            Qt.Orientation.Vertical,
        )
        # Horizontal: verify 50%, search 50%
        self.resizeDocks(
            [self.dock_verify, self.dock_search],
            [int(w * 0.50), int(w * 0.50)],
            Qt.Orientation.Horizontal,
        )

    def _reset_layout(self):
        """Restore default dock positions: Verify left, Search right, Log bottom, Detail hidden."""
        for dock, area in [
            (self.dock_verify, Qt.DockWidgetArea.LeftDockWidgetArea),
            (self.dock_search, Qt.DockWidgetArea.RightDockWidgetArea),
            (self.dock_detail, Qt.DockWidgetArea.RightDockWidgetArea),
            (self.dock_log, Qt.DockWidgetArea.BottomDockWidgetArea),
        ]:
            self.removeDockWidget(dock)
            self.addDockWidget(area, dock)
            dock.setFloating(False)
            dock.show()
        self.dock_detail.hide()  # hidden by default
        QTimer.singleShot(0, self._apply_default_dock_sizes)
        settings = QSettings("kipart-search", "kipart-search")
        settings.remove("geometry")
        settings.remove("windowState")

    # --- Init & status ---

    def _init_jlcpcb_source(self):
        """Initialize JLCPCB source if database exists."""
        db_path = JLCPCBSource.default_db_path()
        self._jlcpcb_source = JLCPCBSource(db_path)
        if self._jlcpcb_source.is_configured():
            self._orchestrator.add_source(self._jlcpcb_source)

    def _update_status(self):
        """Update the status bar 3 zones: mode badge, sources, action."""
        # Left zone: mode badge
        if self._bridge.is_connected:
            self._mode_label.setText("  Connected to KiCad  ")
            self._mode_label.setStyleSheet(
                "background-color: #2d7d46; color: white; padding: 2px 8px; "
                "border-radius: 8px; font-weight: bold; font-size: 11px;"
            )
        else:
            self._mode_label.setText("  Standalone  ")
            self._mode_label.setStyleSheet(
                "background-color: #6b7280; color: white; padding: 2px 8px; "
                "border-radius: 8px; font-weight: bold; font-size: 11px;"
            )

        # Center zone: active source names
        sources: list[str] = []
        if self._jlcpcb_source and self._jlcpcb_source.is_configured():
            db_path = self._jlcpcb_source.db_path
            try:
                stat = db_path.stat()
                dt = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")
                size_mb = stat.st_size / (1024 * 1024)
                sources.append(f"JLCPCB ({size_mb:.0f} MB, {dt})")
            except OSError:
                sources.append("JLCPCB")
        if sources:
            self._sources_label.setText(" + ".join(sources))
        else:
            self._sources_label.setText("No sources configured")

        # Update Push to KiCad button state
        self._act_push.setEnabled(self._bridge.is_connected)

    def _set_action_status(self, text: str):
        """Update the right zone of the status bar with an action message."""
        self._action_label.setText(text)

    # --- Search ---

    def _on_search(self, query: str):
        """Handle search request from the search bar."""
        if not self._orchestrator.active_sources:
            QMessageBox.information(
                self,
                "No Data Source",
                "No data source available. Please download the JLCPCB database first.",
            )
            return

        self.search_bar.search_button.setEnabled(False)
        self.log_panel.clear()

        # Log query transformation if it happened
        raw = self.search_bar.query_input.text().strip()
        if raw != query:
            self.log_panel.log(f"Query: '{raw}' \u2192 '{query}'")

        self._search_worker = SearchWorker(self._orchestrator, query)
        self._search_worker.log.connect(self.log_panel.log)
        self._search_worker.results_ready.connect(self._on_results)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.start()

    def _on_results(self, results):
        """Display search results."""
        self.results_table.set_results(results)
        self.detail_panel.set_part(None)
        self.search_bar.search_button.setEnabled(True)
        self._set_action_status(f"{len(results)} results found")

    def _on_search_error(self, error_msg: str):
        """Handle search error."""
        self.log_panel.log(f"Search error: {error_msg}")
        self.search_bar.search_button.setEnabled(True)
        self._set_action_status("Search failed")

    # --- Detail panel ---

    def _on_part_clicked(self, row: int):
        """Show part detail in the detail panel on single-click."""
        part = self.results_table.get_result(row)
        if part:
            self.detail_panel.set_part(part)

    def _on_detail_assign(self):
        """Handle assign button click from the detail panel."""
        part = self.detail_panel.current_part
        if part is None:
            return
        # Find the row for this part so we can reuse _on_part_selected
        for row in range(self.results_table.table.rowCount()):
            if self.results_table.get_result(row) is part:
                self._on_part_selected(row)
                return

    # --- Scan Project ---

    def _on_scan(self):
        """Scan the KiCad project and verify BOM."""
        if not self._bridge.is_connected:
            ok, error_msg = self._bridge.connect()
            if not ok:
                self._show_connection_error(error_msg)
                return

        self._update_status()
        self._act_scan.setEnabled(False)
        self._set_action_status("Scanning...")
        self.log_panel.clear()

        self._scan_worker = ScanWorker(self._bridge, self._orchestrator)
        self._scan_worker.log.connect(self.log_panel.log)
        self._scan_worker.scan_complete.connect(self._on_scan_complete)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.start()

    def _on_scan_complete(self, components, mpn_statuses):
        """Display scan/verification results."""
        self.verify_panel.set_results(components, mpn_statuses)
        self._act_scan.setEnabled(True)
        self._set_action_status(f"Scan complete: {len(components)} components")

    def _on_scan_error(self, error_msg: str):
        """Handle scan error."""
        QMessageBox.warning(self, "Scan Error", error_msg)
        self._act_scan.setEnabled(True)
        self._set_action_status("Scan failed")

    def _show_connection_error(self, error_msg: str):
        """Show a connection error dialog with copyable diagnostics."""
        diag = self._bridge.get_diagnostics()

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("KiCad Connection Failed")
        dialog.setText(
            "Could not connect to KiCad IPC API.\n\n"
            "Checklist:\n"
            "  1. KiCad 9+ is running\n"
            "  2. A board (.kicad_pcb) is open in the PCB editor\n"
            "  3. IPC API is enabled (Preferences \u2192 API)\n"
            "  4. KiCad was restarted after enabling the API"
        )
        dialog.setDetailedText(
            f"Error:\n{error_msg}\n\n"
            f"--- Diagnostics ---\n{diag}"
        )
        dialog.setMinimumWidth(500)
        dialog.exec()

    def _on_component_clicked(self, reference: str):
        """Highlight the clicked component in KiCad and update assign target."""
        self._bridge.select_component(reference)

        # Update assign target if search panel is open
        if self.dock_search.isVisible():
            # Find the component by reference
            for i in range(len(self.verify_panel._components)):
                comp = self.verify_panel.get_component(i)
                if comp and comp.reference == reference:
                    self._assign_target = comp
                    self._search_target_label.setText(f"Assigning to: {comp.reference}")
                    self.detail_panel.set_assign_target(comp.reference)
                    break

    # --- Guided search & assign ---

    def _on_guided_search(self, row: int):
        """Open search panel pre-filled with a smart query built from component metadata."""
        comp = self.verify_panel.get_component(row)
        if comp is None:
            return

        self._assign_target = comp
        self.dock_search.show()
        self.dock_search.raise_()
        self._search_target_label.setText(f"Assigning to: {comp.reference}")
        self.detail_panel.set_assign_target(comp.reference)
        raw_query = comp.build_search_query()
        self.log_panel.log(
            f"Guided search for {comp.reference}: "
            f"value={comp.value!r}, footprint={comp.footprint_short!r} "
            f"\u2192 query={raw_query!r}"
        )
        # Set query and trigger search through the SearchBar so it goes
        # through the same transform pipeline as a manual search.
        self.search_bar.set_query(raw_query)
        self.search_bar.search_button.click()

    def _on_part_selected(self, row: int):
        """Handle double-click on a search result to assign it."""
        part = self.results_table.get_result(row)
        if part is None:
            return

        if not self._bridge.is_connected:
            QMessageBox.information(
                self,
                "Not Connected",
                "Connect to KiCad first (Scan Project) to assign parts.",
            )
            return

        if self._assign_target is None:
            QMessageBox.information(
                self,
                "No Target",
                "Double-click a missing-MPN component in the BOM table first,\n"
                "then double-click a search result to assign it.",
            )
            return

        from kipart_search.gui.assign_dialog import AssignDialog

        dialog = AssignDialog(self._assign_target, part, parent=self)
        if dialog.exec():
            fields = dialog.fields_to_write
            ref = self._assign_target.reference
            written = 0
            for field_name, value in fields.items():
                if self._bridge.write_field(ref, field_name, value):
                    written += 1

            if written > 0:
                self.log_panel.log(f"Wrote {written} field(s) to {ref}")
            else:
                self.log_panel.log(f"No fields written to {ref}")

            self._assign_target = None
            self._search_target_label.setText("")
            self.detail_panel.set_assign_target(None)

    # --- Database ---

    def _on_download_db(self):
        """Open the database download dialog."""
        from kipart_search.gui.download_dialog import DownloadDialog

        db_path = self._jlcpcb_source.db_path if self._jlcpcb_source else None
        dialog = DownloadDialog(db_path=db_path, parent=self)
        dialog.download_complete.connect(self._on_db_downloaded)
        dialog.exec()

    def _on_db_downloaded(self, db_path: str):
        """Handle database download completion."""
        if self._jlcpcb_source:
            self._jlcpcb_source.close()

        self._orchestrator = SearchOrchestrator()
        self._jlcpcb_source = JLCPCBSource(Path(db_path))
        if self._jlcpcb_source.is_configured():
            self._orchestrator.add_source(self._jlcpcb_source)

        self._update_status()
        self.log_panel.log(f"Database loaded: {db_path}")


def run_app() -> int:
    """Launch the PySide6 application."""
    app = QApplication(sys.argv)
    app.setApplicationName("KiPart Search")
    app.setApplicationVersion(__version__)

    window = MainWindow()
    window.show()

    return app.exec()
