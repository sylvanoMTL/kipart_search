"""Main application window."""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSettings, QThread, QTimer, Signal, Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDockWidget,
    QFileDialog,
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
from kipart_search.core.backup import BackupManager
from kipart_search.core.models import Confidence
from kipart_search.core.cache import QueryCache
from kipart_search.core.sources import JLCPCBSource
from kipart_search.core.search import SearchOrchestrator
from kipart_search.core.units import generate_query_variants
from kipart_search.core.models import BoardComponent
from kipart_search.gui.kicad_bridge import KiCadBridge
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

    def __init__(self, orchestrator: SearchOrchestrator, query: str, source_name: str | None = None):
        super().__init__()
        self.orchestrator = orchestrator
        self.query = query
        self.source_name = source_name

    def run(self):
        try:
            variants = generate_query_variants(self.query)
            source_label = self.source_name if self.source_name and self.source_name != "All Sources" else "all sources"
            if len(variants) > 1:
                self.log.emit(
                    f"Searching {source_label} for '{self.query}' + {len(variants) - 1} "
                    f"equivalent(s): {', '.join(repr(v) for v in variants)}"
                )
            else:
                self.log.emit(f"Searching {source_label} for '{self.query}' ...")

            if self.source_name and self.source_name != "All Sources":
                results = self.orchestrator.search_source(self.query, self.source_name, limit=200)
            else:
                results = self.orchestrator.search(self.query, limit=200)

            self.log.emit(f"Found {len(results)} result(s).")
            self.results_ready.emit(results)
        except Exception as e:
            self.log.emit(f"Search error: {e}")
            self.error.emit(str(e))


class ScanWorker(QThread):
    """Background thread for scanning and verifying a KiCad project."""

    scan_complete = Signal(list, dict, object, bool)  # components, mpn_statuses, db_mtime, is_refresh
    error = Signal(str)
    log = Signal(str)

    def __init__(self, bridge: KiCadBridge, orchestrator: SearchOrchestrator,
                 skip_verify: bool = False):
        super().__init__()
        self.bridge = bridge
        self.orchestrator = orchestrator
        self.skip_verify = skip_verify

    def run(self):
        try:
            self.log.emit("Reading components from KiCad board ...")
            components = self.bridge.get_components()
            if not components:
                self.error.emit("No components found on the board")
                return

            self.log.emit(f"Read {len(components)} components from PCB.")

            # Attempt schematic merge (graceful degradation)
            components = self._merge_schematic_data(components)

            if self.skip_verify:
                # Refresh BOM: skip MPN verification, emit empty statuses
                self.log.emit(f"Refresh complete: {len(components)} components read.")
                self.scan_complete.emit(components, {}, None, True)
                return

            self.log.emit("Verifying MPNs ...")

            # Capture database mtime at scan time for stale detection
            db_mtime = self.orchestrator.get_db_modified_time("JLCPCB")

            mpn_statuses: dict[str, Confidence] = {}
            green = 0
            red = 0
            for comp in components:
                if not comp.has_mpn:
                    mpn_statuses[comp.reference] = Confidence.RED
                    red += 1
                    continue

                result = self.orchestrator.verify_mpn(comp.mpn)
                now = time.time()
                if result:
                    mpn_statuses[comp.reference] = result.confidence
                    comp.verified_at = now
                    comp.verified_source = result.source
                    if result.confidence == Confidence.GREEN:
                        green += 1
                else:
                    mpn_statuses[comp.reference] = Confidence.RED
                    comp.verified_at = now
                    red += 1

            self.log.emit(
                f"Scan complete: {green} verified, {red} missing/not found, "
                f"{len(components) - green - red} uncertain."
            )
            self.scan_complete.emit(components, mpn_statuses, db_mtime, False)
        except Exception as e:
            self.log.emit(f"Scan error: {e}")
            self.error.emit(str(e))

    def _merge_schematic_data(self, components: list[BoardComponent]) -> list[BoardComponent]:
        """Read schematic files and merge with PCB data. Falls back to PCB-only on failure."""
        try:
            from kipart_search.core import kicad_sch
            from kipart_search.core.merge import merge_pcb_sch
        except ImportError:
            return components

        try:
            project_dir = self.bridge.get_project_dir()
            if project_dir is None:
                self.log.emit("Schematic files not found — using PCB data only")
                return components

            sch_files = kicad_sch.find_schematic_files(project_dir)
            if not sch_files:
                self.log.emit("Schematic files not found — using PCB data only")
                return components

            # Read all symbols from all sheets
            all_symbols: list = []
            for sch_path in sch_files:
                try:
                    symbols = kicad_sch.read_symbols(sch_path)
                    all_symbols.extend(symbols)
                except Exception as exc:
                    self.log.emit(f"Warning: failed to read {sch_path.name}: {exc}")

            self.log.emit(
                f"Reading schematic files: {len(sch_files)} sheet(s) found, "
                f"{len(all_symbols)} symbol(s) read"
            )

            # Merge
            components = merge_pcb_sch(components, all_symbols)
            return components

        except Exception as exc:
            self.log.emit(f"Schematic reading failed ({exc}) — using PCB data only")
            return components


class _ConnectWorker(QThread):
    """Background thread for auto-connecting to KiCad on startup.

    Calls bridge.connect() on a worker thread and emits the result.
    The main thread must perform the actual bridge.connect() call
    based on the result, to keep bridge state single-threaded.
    """

    finished = Signal(bool, str)  # (ok, message)

    def __init__(self, bridge: KiCadBridge):
        super().__init__()
        self._bridge = bridge

    def run(self):
        ok, msg = self._bridge.connect()
        self.finished.emit(ok, msg)


class _UpdateCheckWorker(QThread):
    """Background thread for checking GitHub for app updates.

    Emits one of:
    - UpdateInfo with skipped=False  → update available
    - UpdateInfo with skipped=True   → update available but skipped by policy
    - None                           → already up to date
    - "offline"                      → network check failed
    """

    result = Signal(object)  # UpdateInfo | None | "offline"

    def run(self):
        from kipart_search.core.update_check import (
            should_check, check_for_update, save_update_cache, load_cached_update,
            load_skipped_version, load_skip_policy, _compare_versions,
        )
        from kipart_search.core.paths import config_path

        cfg = config_path()
        skipped = load_skipped_version(cfg)
        policy = load_skip_policy(cfg)

        if not should_check(cfg):
            log.info("Update check: using cached result (< 24 h old)")
            cached = load_cached_update(cfg)
            # Invalidate cache if user upgraded past the cached version
            if cached and not _compare_versions(__version__, cached.latest_version):
                cached = None
            # Mark as skipped (don't suppress — let handler show correct message)
            if cached and (policy == "all" or (skipped and cached.latest_version == skipped)):
                cached.skipped = True
            self.result.emit(cached)
            return
        log.info("Update check: querying GitHub API")
        info = check_for_update(__version__, skipped_version=skipped, skip_policy=policy)
        if info:
            save_update_cache(cfg, info)
            self.result.emit(info)
        elif info is None:
            # Distinguish "up to date" from "network failed": check_for_update
            # returns None for both.  Try a minimal connectivity test.
            import httpx
            try:
                httpx.head("https://api.github.com", timeout=3.0)
                # Reachable → genuinely up to date
                log.info("Update check: already up to date (v%s)", __version__)
                self.result.emit(None)
            except (httpx.HTTPError, httpx.TimeoutException):
                log.info("Update check: offline or GitHub unreachable")
                self.result.emit("offline")


class MainWindow(QMainWindow):
    """KiPart Search main window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"KiPart Search v{__version__}")
        self.setMinimumSize(1000, 600)

        # Core engine
        self._cache = self._init_cache()
        self._orchestrator = SearchOrchestrator(cache=self._cache)
        self._jlcpcb_source: JLCPCBSource | None = None
        self._search_worker: SearchWorker | None = None
        self._scan_worker: ScanWorker | None = None
        self._bridge = KiCadBridge()
        self._assign_target: BoardComponent | None = None
        self._backup_manager: BackupManager | None = None
        self._connect_worker: _ConnectWorker | None = None
        self._local_assignments: dict[str, dict[str, str]] = {}  # ref → {field: value}
        self._local_overwrites: dict[str, set[str]] = {}  # ref → set of overwrite-approved fields
        self._cached_mpn_statuses: dict[str, Confidence] = {}  # ref → last-known status
        self._cached_mpn_values: dict[str, str] = {}  # ref → MPN at time of caching
        self._last_has_sources: bool | None = None  # cached from previous scan for Refresh BOM
        self._last_db_mtime: float | None = None  # cached db mtime for Refresh BOM
        self._project_dir: Path | None = None  # cached project dir for push

        # License — subscribe to tier changes
        from kipart_search.core.license import License
        self._license = License.instance()
        self._license.on_change(self._on_license_changed)

        # ── Hidden central widget (QDockWidgets fill around it) ──
        # Zero width so left/right docks fill the full window width.
        # Height left unconstrained so the vertical splitter between
        # top docks and the bottom log dock remains draggable.
        placeholder = QWidget()
        placeholder.setMaximumWidth(0)
        placeholder.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setCentralWidget(placeholder)

        # ── Panel widgets ──
        self.verify_panel = VerifyPanel()
        self.verify_panel.component_clicked.connect(self._on_component_clicked)
        self.verify_panel.search_for_component.connect(self._on_guided_search)
        self.verify_panel.manual_assign_requested.connect(self._on_manual_assign)
        self.verify_panel.refresh_requested.connect(self._on_refresh_bom)
        self.verify_panel.user_status_changed.connect(self._on_user_status_changed)

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
        self._act_export.setToolTip("Export BOM to Excel or CSV")
        self._act_export.triggered.connect(self._on_export_bom)
        self.toolbar.addAction(self._act_export)

        self._act_push = QAction("Push to KiCad", self)
        self._act_push.setToolTip(
            "Push local MPN assignments into .kicad_sch schematic files"
        )
        self._act_push.setEnabled(False)  # Enabled when assignments exist
        self._act_push.triggered.connect(self._on_push_to_kicad)
        self.toolbar.addAction(self._act_push)

        self._act_prefs = QAction("Preferences", self)
        self._act_prefs.setToolTip("Configure data sources and API keys")
        self._act_prefs.triggered.connect(self._on_preferences)
        self.toolbar.addAction(self._act_prefs)

        # ── Menus (order: File, View, Help) ──
        self._build_menus()

        # ── Status bar with 3 zones + license badge ──
        self.status_bar = QStatusBar()
        self._mode_label = QLabel("  Standalone  ")
        self._mode_label.setAccessibleName("Connection mode")
        self._sources_label = QLabel("")
        self._sources_label.setAccessibleName("Active sources")
        self._action_label = QLabel("Ready")
        self._action_label.setAccessibleName("Current action")
        self._license_badge = QLabel()
        self._license_badge.setAccessibleName("License tier")
        self._update_label = QLabel()
        self._update_label.setVisible(False)
        self._update_label.setCursor(Qt.PointingHandCursor)
        self._update_label.setAccessibleName("Update notification")
        self._update_release_url = ""
        self._update_label.installEventFilter(self)

        self.status_bar.addWidget(self._mode_label)
        self.status_bar.addWidget(self._sources_label, 1)
        self.status_bar.addPermanentWidget(self._license_badge)
        self.status_bar.addPermanentWidget(self._update_label)
        self.status_bar.addPermanentWidget(self._action_label)
        self.setStatusBar(self.status_bar)

        # Load saved source configs and init enabled sources
        self._init_sources_from_config()
        self._update_status()

        # Welcome dialog deferred to showEvent so splash closes first

        # ── Restore saved layout (must come after all docks exist) ──
        settings = QSettings("kipart-search", "kipart-search")
        geometry = settings.value("geometry")
        state = settings.value("windowState")
        if geometry is not None:
            self.restoreGeometry(geometry)
        if state is not None:
            if not self.restoreState(state, 1):
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
            # Deferred welcome dialog (after splash closes)
            QTimer.singleShot(0, self._check_welcome)
    def start_background_tasks(self):
        """Kick off background startup tasks (KiCad connect + update check).

        Called from run_app() after the window is shown and the splash is closed,
        so the event loop is guaranteed to be running.
        """
        # Auto-connect to KiCad in background
        self._connect_worker = _ConnectWorker(self._bridge)
        self._connect_worker.finished.connect(self._on_auto_connect_result)
        self._connect_worker.start()
        # Auto-check for app updates (non-blocking, cached 24h)
        self._auto_show_update_dialog = True
        self._update_label.setText("  Checking for updates...  ")
        self._update_label.setStyleSheet(
            "QLabel { color: #888888; padding: 0 6px; }"
        )
        self._update_label.setVisible(True)
        self._update_check_worker = _UpdateCheckWorker()
        self._update_check_worker.result.connect(self._on_update_check_result)
        self._update_check_worker.start()

    def _on_update_check_result(self, info):
        """Show status bar notification if a newer version is available."""
        if info == "offline":
            # Network unavailable — show version, no popup
            self._update_label.setText(f"  v{__version__}  ")
            self._update_label.setStyleSheet(
                "QLabel { color: #888888; padding: 0 6px; }"
            )
            self._update_label.setCursor(Qt.ArrowCursor)
            self._update_label.setVisible(True)
            self._auto_show_update_dialog = False
            self.log_panel.log("Update check skipped (offline)")
            return
        if info is None or getattr(info, "skipped", False):
            # Show version permanently in status bar
            self._update_label.setText(f"  v{__version__}  ")
            self._update_label.setStyleSheet(
                "QLabel { color: #888888; padding: 0 6px; }"
            )
            self._update_label.setCursor(Qt.ArrowCursor)
            self._update_label.setVisible(True)
            # Auto-show dialog on startup
            if getattr(self, "_auto_show_update_dialog", False):
                self._auto_show_update_dialog = False
                if info is not None and info.skipped:
                    msg = (f"v{info.latest_version} is available but was skipped.\n"
                           f"You are running v{__version__}.\n\n"
                           f"You can un-skip it from Preferences or via\n"
                           f"Help \u2192 Check for Updates.")
                else:
                    msg = f"You are running the latest version (v{__version__})."
                QTimer.singleShot(500, lambda: QMessageBox.information(
                    self, "Check for Updates", msg))
            return
        self._update_info = info
        self._update_release_url = info.release_url
        self._update_label.setText(f"  Update available: v{info.latest_version}  ")
        self._update_label.setStyleSheet(
            "QLabel { color: #b8860b; padding: 0 6px; }"
            "QLabel:hover { text-decoration: underline; }"
        )
        self._update_label.setVisible(True)
        # Auto-open the update dialog on startup
        if getattr(self, "_auto_show_update_dialog", False):
            self._auto_show_update_dialog = False
            QTimer.singleShot(500, self._show_update_dialog)

    def _show_update_dialog(self):
        """Open the UpdateDialog for the pending update info."""
        info = getattr(self, "_update_info", None)
        if info:
            from kipart_search.gui.update_dialog import UpdateDialog
            dlg = UpdateDialog(info, parent=self)
            dlg.exec()

    def eventFilter(self, obj, event):
        """Handle click on the update notification label."""
        if obj is self._update_label and event.type() == event.Type.MouseButtonPress:
            self._show_update_dialog()
            return True
        return super().eventFilter(obj, event)


    def _on_auto_connect_result(self, ok: bool, msg: str):
        """Handle background KiCad auto-connect completion."""
        if ok:
            log.info("Auto-connected to KiCad")
            self.log_panel.log("Auto-connected to KiCad IPC API")
        else:
            log.debug("Auto-connect to KiCad failed: %s", msg)
        self._update_status()

    def closeEvent(self, event: QCloseEvent):
        """Save window geometry and dock state before closing."""
        settings = QSettings("kipart-search", "kipart-search")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState(1))
        # Wait for background workers if still running
        if self._connect_worker is not None and self._connect_worker.isRunning():
            self._connect_worker.wait(3000)  # 3s timeout
        if hasattr(self, "_update_check_worker") and self._update_check_worker.isRunning():
            self._update_check_worker.wait(2000)
        if self._cache:
            self._cache.close()
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

        self._menu_export = QAction("Export BOM...", self)
        self._menu_export.setEnabled(False)
        self._menu_export.triggered.connect(self._on_export_bom)
        file_menu.addAction(self._menu_export)

        db_action = QAction("Download / Refresh Database", self)
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

        # Tools menu
        tools_menu = menubar.addMenu("Tools")
        prefs_action = QAction("Preferences...", self)
        prefs_action.triggered.connect(self._on_preferences)
        tools_menu.addAction(prefs_action)
        backup_action = QAction("Backups...", self)
        backup_action.triggered.connect(self._on_open_backups)
        tools_menu.addAction(backup_action)

        # Help menu (last)
        help_menu = menubar.addMenu("Help")

        check_update_action = QAction("Check for Updates...", self)
        check_update_action.triggered.connect(self._on_check_update)
        help_menu.addAction(check_update_action)

        help_menu.addSeparator()

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
            '<p><a href="https://github.com/sylvanoMTL/kipart_search">'
            "github.com/sylvanoMTL/kipart_search</a></p>",
        )

    def _on_check_update(self):
        """Manually trigger an update check and show the result in a dialog."""
        from kipart_search.core.update_check import check_for_update

        self.log_panel.log("Checking for updates...")
        # Force a fresh check (ignore cache, ignore skip policy)
        info = check_for_update(__version__)
        if info:
            self._update_info = info
            self._update_release_url = info.release_url
            self._update_label.setText(f"  Update available: v{info.latest_version}  ")
            self._update_label.setStyleSheet(
                "QLabel { color: #b8860b; padding: 0 6px; }"
                "QLabel:hover { text-decoration: underline; }"
            )
            self._update_label.setVisible(True)
            from kipart_search.gui.update_dialog import UpdateDialog
            dlg = UpdateDialog(info, parent=self)
            dlg.exec()
        else:
            # Distinguish offline from up-to-date
            import httpx
            try:
                httpx.head("https://api.github.com", timeout=3.0)
                msg = f"You are running the latest version (v{__version__})."
                self.log_panel.log(f"Already up to date (v{__version__})")
            except (httpx.HTTPError, httpx.TimeoutException):
                msg = (f"Could not check for updates (no internet connection).\n"
                       f"You are running v{__version__}.")
                self.log_panel.log("Update check failed (offline)")
            QMessageBox.information(self, "Check for Updates", msg)

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

    @staticmethod
    def _init_cache() -> QueryCache | None:
        """Create the query cache, returning None if it fails."""
        try:
            return QueryCache()
        except Exception:
            log.warning("Failed to initialise query cache, continuing without cache")
            return None

    def _init_sources_from_config(self):
        """Load saved source configs and register enabled sources."""
        from kipart_search.core.source_config import SourceConfigManager

        mgr = SourceConfigManager()
        configs = mgr.get_all_configs()

        # Check if JLCPCB is enabled (default: yes)
        jlcpcb_enabled = True
        default_source: str | None = None
        for cfg in configs:
            if cfg.source_name == "JLCPCB":
                jlcpcb_enabled = cfg.enabled
            if cfg.is_default and cfg.enabled:
                default_source = cfg.source_name

        if jlcpcb_enabled:
            self._init_jlcpcb_source()
        else:
            self.search_bar.set_sources(self._orchestrator.get_source_names())

        # Set default source in search bar
        if default_source:
            self.search_bar.set_default_source(default_source)

    def _check_welcome(self):
        """Show the welcome dialog on first launch or after major.minor version change."""
        from kipart_search.core.source_config import SourceConfigManager
        from kipart_search.gui.welcome_dialog import WelcomeDialog

        mgr = SourceConfigManager()
        current_mm = mgr.current_major_minor()
        if mgr.get_welcome_version() == current_mm:
            return  # already shown for this version

        dialog = WelcomeDialog(parent=self)

        def _on_source_configured(dlg=dialog):
            # Check if it was a download or an API configuration
            db_path = dlg.get_db_path()
            if db_path:
                self._on_db_downloaded(str(db_path))
            else:
                configs = dlg.get_saved_configs()
                if configs:
                    self._apply_source_configs(configs)

        dialog.source_configured.connect(_on_source_configured)
        result = dialog.exec()

        mgr.set_welcome_version(current_mm)

        if result == QDialog.DialogCode.Rejected:
            # User skipped — emphasise the Preferences button
            prefs_widget = self.toolbar.widgetForAction(self._act_prefs)
            if prefs_widget:
                prefs_widget.setStyleSheet("font-weight: bold;")
                self._act_prefs.setToolTip("Configure data sources to start searching")

        self._update_status()

    def _init_jlcpcb_source(self):
        """Initialize JLCPCB source if database exists.

        If the DB file is missing, silently skips (Welcome Dialog handles first-run).
        If the DB file exists but is corrupted, prompts to re-download.
        """
        db_path = JLCPCBSource.default_db_path()
        self._jlcpcb_source = JLCPCBSource(db_path)

        if not db_path.exists():
            # No database — Welcome Dialog or File > Download handles this
            self.search_bar.set_sources(self._orchestrator.get_source_names())
            return

        # Database exists — check integrity
        ok, msg = JLCPCBSource.check_database_integrity(db_path)
        if not ok:
            log.warning("JLCPCB database integrity check failed: %s", msg)
            reply = QMessageBox.warning(
                self,
                "Database Corrupted",
                f"The JLCPCB database appears corrupted:\n{msg}\n\n"
                "Download a fresh copy?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                db_path.unlink(missing_ok=True)
                self._on_download_db()
            self.search_bar.set_sources(self._orchestrator.get_source_names())
            return

        # Database is valid — add to orchestrator
        if self._jlcpcb_source.is_configured():
            self._orchestrator.add_source(self._jlcpcb_source)
        self.search_bar.set_sources(self._orchestrator.get_source_names())

    def _on_license_changed(self) -> None:
        """React to license tier changes — update badge and gated UI."""
        self._update_license_badge()
        self._update_license_gated_actions()
        self.verify_panel.update_license_state()
        self.search_bar.set_sources(self._orchestrator.get_source_names())

    def _update_license_badge(self) -> None:
        """Show/hide the Pro badge in the status bar."""
        if self._license.is_pro:
            self._license_badge.setText("  Pro  ")
            self._license_badge.setStyleSheet(
                "background-color: #2d7d46; color: white; padding: 2px 8px; "
                "border-radius: 8px; font-weight: bold; font-size: 11px;"
            )
            self._license_badge.setVisible(True)
        else:
            self._license_badge.setVisible(False)

    def _update_license_gated_actions(self) -> None:
        """Enable/disable toolbar actions based on license tier."""
        is_pro = self._license.is_pro
        pro_tip = "" if is_pro else " (requires Pro license)"

        # Push to KiCad (batch) — gated
        if not is_pro:
            self._act_push.setToolTip("Push to KiCad" + pro_tip)

        # Export BOM tooltip update
        self._act_export.setToolTip("Export BOM to Excel or CSV" + pro_tip)

    def _update_status(self):
        """Update the status bar 3 zones: mode badge, sources, action."""
        # License badge
        self._update_license_badge()
        self._update_license_gated_actions()
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

        # Center zone: source availability with local/online distinction
        local_parts: list[str] = []
        online_parts: list[str] = []
        for source in self._orchestrator.active_sources:
            if source.is_local:
                # Show size + date for local database sources
                mtime = source.get_db_modified_time()
                if mtime is not None:
                    try:
                        dt = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
                        db_path = getattr(source, "db_path", None)
                        if db_path is not None:
                            size_mb = Path(db_path).stat().st_size / (1024 * 1024)
                            local_parts.append(f"{source.name} ({size_mb:.0f} MB, {dt})")
                        else:
                            local_parts.append(f"{source.name} ({dt})")
                    except OSError:
                        local_parts.append(source.name)
                else:
                    local_parts.append(source.name)
            else:
                # Future API sources — placeholder for online/offline state
                online_parts.append(source.name)

        parts: list[str] = local_parts
        if online_parts:
            parts.append(f"{len(online_parts)} online source(s)")

        if parts:
            label = " + ".join(parts)
            if not online_parts:
                label += "  [Local DB]"
            self._sources_label.setText(label)
        else:
            self._sources_label.setText("No sources configured")

        # Push to KiCad: enabled when local assignments exist
        self._update_push_button_state()

    def _update_push_button_state(self):
        """Enable/disable Push to KiCad based on local assignments."""
        has_assignments = bool(self._local_assignments)
        self._act_push.setEnabled(has_assignments)
        if has_assignments:
            count = sum(len(f) for f in self._local_assignments.values())
            self._act_push.setToolTip(
                f"Push {count} local assignment(s) into .kicad_sch files"
            )
        else:
            self._act_push.setToolTip("No local assignments to push")

    def _set_action_status(self, text: str):
        """Update the right zone of the status bar with an action message."""
        self._action_label.setText(text)

    # --- Search ---

    def _on_search(self, query: str, source: str = "All Sources"):
        """Handle search request from the search bar."""
        if not self._orchestrator.active_sources:
            QMessageBox.information(
                self,
                "No Data Source",
                "No data source available. Please download the JLCPCB database first.",
            )
            return

        self.search_bar.search_button.setEnabled(False)
        self.log_panel.section("Search")

        # Log query transformation if it happened
        raw = self.search_bar.query_input.text().strip()
        if raw != query:
            self.log_panel.log(f"Query: '{raw}' \u2192 '{query}'")

        # Show/hide Source column based on search mode
        is_unified = source == "All Sources"
        self.results_table.set_source_column_visible(is_unified)

        self._search_worker = SearchWorker(self._orchestrator, query, source_name=source)
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
        if self._scan_worker is not None and self._scan_worker.isRunning():
            self.log_panel.log("Scan already in progress")
            return

        if not self._orchestrator.active_sources:
            QMessageBox.information(
                self,
                "No Data Source",
                "No data source available.\n\n"
                "Download the JLCPCB database (File > Download Database) "
                "or configure API keys in Tools > Preferences.",
            )
            return

        # Wait for background auto-connect to finish before attempting manual connect
        if self._connect_worker is not None and self._connect_worker.isRunning():
            self.log_panel.log("Waiting for auto-connect to finish...")
            self._connect_worker.wait(5000)

        # Always reconnect to get a fresh board object (may be stale after push)
        ok, error_msg = self._bridge.connect()
        if not ok:
            self.log_panel.log(f"KiCad connection failed: {error_msg}")
            self._show_connection_error(error_msg)
            return
        if not self._bridge.is_connected:
            self.log_panel.log("KiCad connection failed: bridge not connected")
            return
        self.log_panel.log("Connected to KiCad IPC API")

        self._update_status()
        self._act_scan.setEnabled(False)
        self._set_action_status("Scanning...")
        self.log_panel.section("Scan Project")

        self._scan_worker = ScanWorker(self._bridge, self._orchestrator)
        self._scan_worker.log.connect(self.log_panel.log)
        self._scan_worker.scan_complete.connect(self._on_scan_complete)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.start()

    def _on_refresh_bom(self):
        """Re-read BOM from KiCad without re-verifying MPNs.

        Reconnects to KiCad to pick up board changes after push + F8.
        Preserves all cached MPN verification statuses.
        """
        if self._scan_worker is not None and self._scan_worker.isRunning():
            self.log_panel.log("Scan already in progress")
            return

        self.log_panel.section("Refresh BOM")
        self.verify_panel.refresh_button.setEnabled(False)
        self._act_scan.setEnabled(False)
        self._set_action_status("Refreshing BOM...")

        ok, error_msg = self._bridge.connect()
        if not ok:
            QMessageBox.warning(
                self, "Not Connected",
                f"Cannot reconnect to KiCad: {error_msg}\n\n"
                "Make sure KiCad is running.",
            )
            self.verify_panel.refresh_button.setEnabled(True)
            self._act_scan.setEnabled(True)
            self._set_action_status("")
            return
        self.log_panel.log(
            f"Refreshing {len(self.verify_panel.get_components())} components..."
        )

        self._scan_worker = ScanWorker(
            self._bridge, self._orchestrator, skip_verify=True
        )
        self._scan_worker.log.connect(self.log_panel.log)
        self._scan_worker.scan_complete.connect(self._on_scan_complete)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.start()

    def _on_scan_complete(self, components, mpn_statuses, db_mtime, is_refresh=False):
        """Display scan/verification results."""

        # Cache project directory from bridge while connection is active
        if self._project_dir is None and self._bridge.is_connected:
            bridge_dir = self._bridge.get_project_dir()
            if bridge_dir is not None:
                self._project_dir = bridge_dir
                self.log_panel.log(f"Project directory: {bridge_dir}")

        # Reset backup session so next write creates a fresh backup
        if self._backup_manager is not None:
            self._backup_manager.reset_session()

        # For Refresh BOM: carry forward all cached statuses before local-assignment restore
        if is_refresh:
            for comp in components:
                ref = comp.reference
                cached = self._cached_mpn_statuses.get(ref)
                if cached is not None:
                    mpn_statuses[ref] = cached
                elif not comp.has_mpn:
                    mpn_statuses[ref] = Confidence.RED
                else:
                    # MPN present but never verified (new component or first refresh)
                    mpn_statuses[ref] = Confidence.RED

        # Re-apply local assignments that couldn't be written to KiCad
        restored = 0
        if self._local_assignments:
            for comp in components:
                local_fields = self._local_assignments.get(comp.reference)
                if not local_fields:
                    continue
                for fn, fv in local_fields.items():
                    if fn == "MPN":
                        comp.mpn = fv
                    comp.extra_fields[fn.lower()] = fv
                # Update status to GREEN since MPN is assigned locally
                if "MPN" in local_fields:
                    mpn_statuses[comp.reference] = Confidence.GREEN
                    restored += 1

        # Use cached has_sources for Refresh BOM to avoid incorrect downgrade.
        # If no prior scan (sentinel None), fall back to current source availability.
        if is_refresh and self._last_has_sources is not None:
            has_sources = self._last_has_sources
        else:
            has_sources = bool(self._orchestrator.active_sources)
            if not is_refresh:
                self._last_has_sources = has_sources

        # Restore cached MPN statuses for components whose MPN hasn't changed.
        # After push + re-scan, the MPN is now in the schematic but the source
        # may not find it (e.g. JLCPCB doesn't stock it) — cached GREEN is valid
        # as long as the MPN text is identical.
        cache_restored = 0
        if not is_refresh:
            for comp in components:
                ref = comp.reference
                cached_status = self._cached_mpn_statuses.get(ref)
                if cached_status == Confidence.GREEN and mpn_statuses.get(ref) != Confidence.GREEN:
                    cached_mpn = self._cached_mpn_values.get(ref)
                    if comp.has_mpn and comp.mpn == cached_mpn:
                        mpn_statuses[ref] = cached_status
                        cache_restored += 1

        # Cache db_mtime from full scans; reuse on refresh
        if is_refresh:
            db_mtime = self._last_db_mtime
        else:
            self._last_db_mtime = db_mtime

        # Update cache with current results
        self._cached_mpn_statuses = dict(mpn_statuses)
        self._cached_mpn_values = {
            comp.reference: comp.mpn
            for comp in components
            if comp.has_mpn
        }

        # Load per-project user verification statuses
        user_statuses = {}
        if self._project_dir is not None:
            from kipart_search.core.project_state import load_user_statuses

            user_statuses = load_user_statuses(self._project_dir)
            if user_statuses:
                self.log_panel.log(
                    f"Restored {len(user_statuses)} user review status(es)"
                )

        self.verify_panel.set_results(
            components, mpn_statuses, has_sources, db_mtime=db_mtime,
            user_statuses=user_statuses, project_dir=self._project_dir,
        )
        self._act_scan.setEnabled(True)
        self.verify_panel.refresh_button.setEnabled(True)
        self._act_export.setEnabled(True)
        self._menu_export.setEnabled(True)
        if is_refresh:
            self._set_action_status(f"Refresh complete: {len(components)} components")
        else:
            self._set_action_status(f"Scan complete: {len(components)} components")

        if restored > 0:
            self.log_panel.log(
                f"Restored {restored} local MPN assignment(s) — not yet in KiCad"
            )
        if cache_restored > 0:
            self.log_panel.log(
                f"Restored {cache_restored} verified MPN status(es) from previous scan"
            )

        # Log schematic sync warnings
        sch_only_count = sum(1 for c in components if c.source == "sch_only")
        desync_count = sum(1 for c in components if c.sync_mismatches)
        if sch_only_count > 0:
            self.log_panel.log(
                f"{sch_only_count} component(s) found in schematic but not placed on PCB"
            )
        if sch_only_count > 0 or desync_count > 0:
            total_attention = sch_only_count + desync_count
            self.log_panel.log(
                f"{total_attention} component(s) need attention — run Update PCB "
                "from Schematic (F8) in KiCad, then re-scan."
            )

    def _on_user_status_changed(self, references: list[str], status) -> None:
        """Persist user review status changes and log them."""
        from kipart_search.core.models import UserVerificationStatus
        from kipart_search.core.project_state import save_user_statuses

        label = {
            UserVerificationStatus.VERIFIED: "Verified",
            UserVerificationStatus.ATTENTION: "Needs Attention",
            UserVerificationStatus.REJECTED: "Rejected",
            UserVerificationStatus.NONE: "cleared",
        }.get(status, str(status))

        for ref in references:
            self.log_panel.log(f"Marked {ref} as {label}")

        project_dir = self.verify_panel.get_project_dir()
        if project_dir:
            save_user_statuses(project_dir, self.verify_panel.get_user_statuses())

    def _on_scan_error(self, error_msg: str):
        """Handle scan error."""
        QMessageBox.warning(self, "Scan Error", error_msg)
        self._act_scan.setEnabled(True)
        self.verify_panel.refresh_button.setEnabled(True)
        self._set_action_status("Scan failed")

    def _on_push_to_kicad(self):
        """Push local MPN assignments into .kicad_sch files on disk."""
        from kipart_search.core import kicad_sch
        from kipart_search.core.license import FeatureNotAvailable, License

        # License gate: batch write-back requires Pro
        if not License.instance().has("batch_writeback"):
            QMessageBox.information(
                self, "Pro Feature",
                "Batch 'Push to KiCad' requires a Pro license.\n\n"
                "Single-component assignment is available in the free tier.\n"
                "Go to Tools > Preferences > License to activate.",
            )
            return

        # Guard: anything to push?
        if not self._local_assignments:
            QMessageBox.information(
                self, "No Assignments",
                "No local assignments to push. Assign MPNs first.",
            )
            return

        self.log_panel.section("Push to KiCad")

        # Resolve project directory
        project_dir = self._resolve_project_dir()
        if project_dir is None:
            self.log_panel.log("Push cancelled — no project directory")
            return

        # Discover schematic files
        sch_files = kicad_sch.find_schematic_files(project_dir)
        if not sch_files:
            QMessageBox.warning(
                self, "No Schematics Found",
                f"No .kicad_sch files found in:\n{project_dir}\n\n"
                "Make sure this is a valid KiCad project directory.",
            )
            self.log_panel.log(f"No .kicad_sch files in {project_dir}")
            return

        # Check lock files — block if any schematic is open
        locked = [p for p in sch_files if kicad_sch.is_schematic_locked(p)]
        if locked:
            names = "\n".join(f"  {p.name}" for p in locked)
            QMessageBox.warning(
                self, "Schematic Open in KiCad",
                "Close the schematic editor in KiCad before pushing "
                "changes. File-based write cannot proceed while the "
                f"schematic is open.\n\nLocked files:\n{names}",
            )
            self.log_panel.log("Push blocked — schematic lock file(s) detected")
            return

        # Count fields and components
        total_fields = sum(len(flds) for flds in self._local_assignments.values())
        total_refs = len(self._local_assignments)

        # Confirmation dialog
        reply = QMessageBox.question(
            self, "Push to KiCad",
            f"Push {total_fields} field(s) to {total_refs} component(s) "
            f"into schematic files?\n\n"
            f"This will modify .kicad_sch files on disk.\n"
            f"A backup will be created first.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Ok:
            self.log_panel.log("Push cancelled by user")
            return

        # Backup all schematic files
        backup_mgr = self._ensure_backup_manager()
        project_name = self._get_project_name()
        try:
            backup_path = backup_mgr.backup_schematic_files(project_name, sch_files)
            self.log_panel.log(f"Backup created: {backup_path}")
        except Exception as exc:
            QMessageBox.critical(
                self, "Backup Failed",
                f"Cannot create backup — push aborted.\n\n{exc}",
            )
            self.log_panel.log(f"Backup failed: {exc} — push aborted")
            return

        # Push each assignment
        written_count = 0
        skipped_count = 0
        failed_refs: list[tuple[str, str]] = []  # (ref, error)

        for ref, field_map in list(self._local_assignments.items()):
            # Find which sheet contains this reference
            sheet = kicad_sch.find_symbol_sheet(project_dir, ref)
            if sheet is None:
                failed_refs.append((ref, "symbol not found in any schematic sheet"))
                self.log_panel.log(f"  {ref}: symbol not found — skipped")
                continue

            # Read old values for undo log
            old_values: dict[str, str] = {}
            try:
                symbols = kicad_sch.read_symbols(sheet)
                for sym in symbols:
                    if sym.reference == ref:
                        old_values = dict(sym.fields)
                        break
            except Exception as exc:
                log.warning("Failed to read symbols from %s: %s", sheet, exc)

            written_fields: list[str] = []
            overwrite_set = self._local_overwrites.get(ref, set())

            for field_name, value in field_map.items():
                allow_overwrite = field_name in overwrite_set
                try:
                    ok = kicad_sch.set_field(
                        sheet, ref, field_name, value,
                        allow_overwrite=allow_overwrite,
                    )
                    if ok:
                        # Log to undo CSV
                        old_val = old_values.get(field_name, "")
                        backup_mgr.log_field_change(
                            project_name, ref, field_name, old_val, value,
                        )
                        written_fields.append(field_name)
                        written_count += 1
                        self.log_panel.log(
                            f"  {ref}.{field_name} = \"{value}\" (in {sheet.name})"
                        )
                    else:
                        skipped_count += 1
                        self.log_panel.log(
                            f"  {ref}.{field_name}: skipped (non-empty, overwrite not approved)"
                        )
                except Exception as exc:
                    failed_refs.append((ref, f"{field_name}: {exc}"))
                    self.log_panel.log(f"  {ref}.{field_name}: ERROR — {exc}")

            # Remove successfully written fields; keep failed ones for retry
            for fn in written_fields:
                field_map.pop(fn, None)
            if not field_map:
                self._local_assignments.pop(ref, None)
                self._local_overwrites.pop(ref, None)

        # Update toolbar button state
        self._update_push_button_state()

        # How many components had at least one field removed (= written)
        written_refs_count = total_refs - len(self._local_assignments)

        # Result dialog
        if failed_refs and written_count > 0:
            fail_lines = "\n".join(f"  {r}: {e}" for r, e in failed_refs)
            QMessageBox.warning(
                self, "Push Partially Complete",
                f"Written {written_count} field(s) to "
                f"{written_refs_count} component(s).\n\n"
                f"Failed components:\n{fail_lines}\n\n"
                f"Run 'Update PCB from Schematic' (F8) in KiCad to sync the board.",
            )
            self.log_panel.log(
                f"Push partial: {written_count} written, {len(failed_refs)} failed. "
                f"Run Update PCB from Schematic (F8) to sync."
            )
        elif failed_refs:
            fail_lines = "\n".join(f"  {r}: {e}" for r, e in failed_refs)
            QMessageBox.warning(
                self, "Push Failed",
                f"No fields were written.\n\n{fail_lines}",
            )
            self.log_panel.log("Push failed — no fields written")
        elif written_count == 0 and skipped_count > 0:
            QMessageBox.information(
                self, "Nothing Written",
                f"All {skipped_count} field(s) were skipped because the "
                f"target fields already have values and overwrite was "
                f"not approved.\n\n"
                f"To overwrite existing values, re-assign with the "
                f"overwrite checkbox enabled.",
            )
            self.log_panel.log(
                f"Push: {skipped_count} field(s) skipped (existing values, "
                f"overwrite not approved)"
            )
        elif written_count == 0:
            QMessageBox.information(
                self, "Nothing to Write",
                "No fields were written. Assignments may be empty.",
            )
            self.log_panel.log("Push: no fields to write")
        else:
            QMessageBox.information(
                self, "Push Complete",
                f"Written {written_count} field(s) to "
                f"{written_refs_count} component(s).\n\n"
                f"Run 'Update PCB from Schematic' (F8) in KiCad "
                f"to sync the board.",
            )
            self.log_panel.log(
                f"Pushed {written_count} field(s) to .kicad_sch — "
                f"run Update PCB from Schematic (F8) to sync"
            )

    def _resolve_project_dir(self) -> Path | None:
        """Determine the KiCad project directory for push operations.

        Priority:
        1. Cached project directory (from previous scan or resolution)
        2. Connected KiCad: extract from board path
        3. Standalone: derive from last-loaded BOM path (if any)
        4. Fallback: prompt user with folder picker
        """
        # 1. Cached from previous scan/resolution (validate still exists)
        if self._project_dir is not None and self._project_dir.exists():
            self.log_panel.log(f"Project directory (cached): {self._project_dir}")
            return self._project_dir

        # 2. Connected mode
        project_dir = self._bridge.get_project_dir()
        if project_dir is not None:
            self._project_dir = project_dir
            self.log_panel.log(f"Project directory (from KiCad): {project_dir}")
            return project_dir

        # 3. Standalone: check if BOM was loaded from file
        # TODO: wire _last_bom_path when standalone BOM import is implemented
        bom_path = getattr(self, "_last_bom_path", None)
        if bom_path is not None:
            project_dir = Path(bom_path).parent
            self._project_dir = project_dir
            self.log_panel.log(f"Project directory (from BOM): {project_dir}")
            return project_dir

        # 4. Prompt user
        folder = QFileDialog.getExistingDirectory(
            self, "Select KiCad Project Directory",
        )
        if folder:
            self._project_dir = Path(folder)
            self.log_panel.log(f"Project directory (user selected): {folder}")
            return self._project_dir

        return None

    def _on_export_bom(self):
        """Open the BOM export dialog."""
        components = self.verify_panel.get_components()
        if not components:
            QMessageBox.information(
                self,
                "No Components",
                "Scan a KiCad project first before exporting BOM.",
            )
            return

        from kipart_search.gui.export_dialog import ExportDialog

        health_pct = self.verify_panel.get_health_percentage()
        missing_count = self.verify_panel.get_missing_mpn_count()
        self._export_dialog = ExportDialog(
            components, health_pct, missing_count, parent=self,
        )
        self._export_dialog.show()  # Non-modal

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
        # Check if this is a schematic-only component (no PCB footprint to highlight)
        is_sch_only = False
        panel = getattr(self, "verify_panel", None)
        if panel is not None:
            for comp in panel.get_components():
                if comp.reference == reference and comp.source == "sch_only":
                    is_sch_only = True
                    break

        if is_sch_only:
            log.info("Component %s exists only in schematic — cannot highlight in PCB", reference)
            log_panel = getattr(self, "log_panel", None)
            if log_panel is not None:
                log_panel.log(
                    f"Component {reference} exists only in schematic — cannot highlight in PCB"
                )
        else:
            self._bridge.select_component(reference)

        # Update assign target if search panel is open
        if self.dock_search.isVisible():
            # Find the component by reference
            for i in range(self.verify_panel.table.rowCount()):
                comp = self.verify_panel.get_component(i)
                if comp and comp.reference == reference:
                    self._assign_target = comp
                    self._search_target_label.setText(f"Assigning to: {comp.reference}")
                    self.detail_panel.set_assign_target(comp.reference)
                    self.results_table.set_assign_target(comp.reference)
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
        self.results_table.set_assign_target(comp.reference)
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
            self._apply_assignment(dialog.fields_to_write, dialog.overwrite_fields)

    def _on_manual_assign(self, reference: str):
        """Open AssignDialog in manual-entry mode for the given component."""
        # Find the component by reference in the verify panel
        comp = None
        for i in range(self.verify_panel.table.rowCount()):
            c = self.verify_panel.get_component(i)
            if c and c.reference == reference:
                comp = c
                break
        if comp is None:
            return

        from kipart_search.gui.assign_dialog import AssignDialog

        self._assign_target = comp
        dialog = AssignDialog(comp, part=None, parent=self)
        if dialog.exec():
            self._apply_assignment(dialog.fields_to_write, dialog.overwrite_fields)

    def _get_project_name(self) -> str:
        """Extract project name from KiCad board filename or fallback."""
        name = self._bridge.get_project_name()
        return name if name else "standalone"

    def _ensure_backup_manager(self) -> BackupManager:
        """Lazily create the BackupManager on first use.

        Uses project-scoped backup dir when a project directory is known,
        falls back to platformdirs data dir backups/ for standalone mode.
        """
        if self._backup_manager is None:
            if self._project_dir is not None:
                backup_dir = self._project_dir / ".kipart-search" / "backups"
            else:
                from kipart_search.core.paths import backups_dir
                backup_dir = backups_dir()
            self._backup_manager = BackupManager(backup_dir=backup_dir)
        return self._backup_manager

    def _apply_assignment(
        self, fields: dict[str, str], overwrite_fields: set[str] | None = None,
    ):
        """Write assignment fields via bridge (connected) or in-memory (standalone)."""
        if not fields or self._assign_target is None:
            return

        # Cache the target component reference immediately — the GUI thread
        # could update self._assign_target if the user clicks another row.
        comp = self._assign_target
        overwrite_fields = overwrite_fields or set()
        ref = comp.reference
        written = 0
        failed: list[tuple[str, str]] = []  # (field_name, error_msg)
        mpn_written = False
        backup_mgr = self._ensure_backup_manager()
        project = self._get_project_name()

        # Pre-session backup (connected mode only)
        if self._bridge.is_connected:
            try:
                from dataclasses import asdict
                components = self.verify_panel.get_components()
                comp_dicts = [asdict(c) for c in components]
                backup_mgr.ensure_session_backup(project, comp_dicts)
            except Exception as exc:
                log.warning("Failed to create session backup: %s", exc)

        # Capture old values before writing (comp state is still pre-write)
        old_values: dict[str, str] = {}
        for field_name in fields:
            if field_name == "MPN":
                old_values[field_name] = comp.mpn
            elif field_name.lower() == "datasheet":
                old_values[field_name] = comp.datasheet
            else:
                old_values[field_name] = comp.extra_fields.get(field_name.lower(), "")

        # Connected mode: try to write via IPC API, fall back to local state
        local_only: list[str] = []  # fields assigned locally (not in KiCad)
        if self._bridge.is_connected:
            for field_name, value in fields.items():
                try:
                    ok = self._bridge.write_field(
                        ref, field_name, value,
                        allow_overwrite=(field_name in overwrite_fields),
                    )
                    if ok:
                        written += 1
                        if field_name == "MPN":
                            mpn_written = True
                        # Log successful write to undo CSV
                        backup_mgr.log_field_change(
                            project, ref, field_name,
                            old_values.get(field_name, ""), value,
                        )
                    else:
                        # Field doesn't exist on footprint — assign locally
                        local_only.append(field_name)
                except Exception as exc:
                    failed.append((field_name, str(exc)))

            if written > 0:
                self.log_panel.log(f"Wrote {written} field(s) to {ref} via KiCad")
            if local_only:
                # Track local assignments so re-verify can restore them
                if ref not in self._local_assignments:
                    self._local_assignments[ref] = {}
                for fn in local_only:
                    self._local_assignments[ref][fn] = fields[fn]
                # Track overwrite permissions for push-to-kicad
                if overwrite_fields:
                    if ref not in self._local_overwrites:
                        self._local_overwrites[ref] = set()
                    self._local_overwrites[ref].update(
                        fn for fn in local_only if fn in overwrite_fields
                    )
                self.log_panel.log(
                    f"Assigned {len(local_only)} field(s) to {ref} locally "
                    f"({', '.join(local_only)}) — KiCad 9 IPC API cannot "
                    f"create new symbol fields. BOM export will include them."
                )
            if failed:
                fail_lines = [f"  {fn}: {err}" for fn, err in failed]
                fail_msg = "\n".join(fail_lines)
                self.log_panel.log(
                    f"Failed to write {len(failed)} field(s) to {ref}:\n{fail_msg}"
                )
                QMessageBox.warning(
                    self,
                    "Write-Back Error",
                    f"Some fields could not be written to {ref}:\n\n{fail_msg}",
                )

        # Total failure (exceptions only) in connected mode: skip in-memory update
        if self._bridge.is_connected and written == 0 and not local_only and failed:
            self.log_panel.log(f"No fields written to {ref} — skipping in-memory update")
            self._assign_target = None
            self._search_target_label.setText("")
            self.detail_panel.set_assign_target(None)
            self.results_table.set_assign_target(None)
            return

        # Update component in-memory (both modes)
        # Include IPC-written fields + local-only fields; exclude hard failures
        # (comp was cached at method entry to avoid race with GUI thread)
        if self._bridge.is_connected:
            failed_names = {fn for fn, _ in failed}
            written_fields = {
                fn: fv for fn, fv in fields.items() if fn not in failed_names
            }
        else:
            written_fields = fields
            # Standalone mode: store as local assignments for push-to-kicad
            if ref not in self._local_assignments:
                self._local_assignments[ref] = {}
            self._local_assignments[ref].update(written_fields)
            # Track overwrite permissions
            if overwrite_fields:
                if ref not in self._local_overwrites:
                    self._local_overwrites[ref] = set()
                self._local_overwrites[ref].update(overwrite_fields)
            # Log all field changes to undo CSV (no snapshot)
            for field_name, value in written_fields.items():
                backup_mgr.log_field_change(
                    project, ref, field_name,
                    old_values.get(field_name, ""), value,
                )

        # MPN counts as assigned if written to KiCad, fell through IPC to
        # local_only, or assigned in standalone mode (present in written_fields)
        mpn_assigned = (
            mpn_written
            or "MPN" in local_only
            or (not self._bridge.is_connected and "MPN" in written_fields)
        )

        if comp and "MPN" in written_fields:
            comp.mpn = written_fields["MPN"]
        if comp:
            for fname, fval in written_fields.items():
                comp.extra_fields[fname.lower()] = fval
            if not self._bridge.is_connected:
                self.log_panel.log(
                    f"Assigned {len(written_fields)} field(s) to {ref} (in-memory)"
                )

        # Live-update the verify panel — GREEN if MPN was assigned (IPC or local)
        if mpn_assigned or "MPN" not in fields:
            self.verify_panel.update_component_status(ref, Confidence.GREEN)
            # Update MPN status cache so re-verify preserves GREEN
            self._cached_mpn_statuses[ref] = Confidence.GREEN
            mpn_val = fields.get("MPN", comp.mpn)
            if mpn_val:
                self._cached_mpn_values[ref] = mpn_val
            pct = self.verify_panel.get_health_percentage()
            self.log_panel.log(f"{ref} status updated to Verified — BOM health: {pct}%")
        elif self._bridge.is_connected:
            self.log_panel.log(
                f"{ref} MPN write failed — status not changed to Verified"
            )

        self._assign_target = None
        self._search_target_label.setText("")
        self.detail_panel.set_assign_target(None)
        self.results_table.set_assign_target(None)
        self._update_push_button_state()

    # --- Preferences ---

    def _on_preferences(self):
        """Open the Source Preferences dialog."""
        from kipart_search.gui.source_preferences_dialog import SourcePreferencesDialog
        from kipart_search.core.source_config import SourceConfigManager

        # Remove emphasis added by welcome-skip flow
        prefs_widget = self.toolbar.widgetForAction(self._act_prefs)
        if prefs_widget:
            prefs_widget.setStyleSheet("")
        self._act_prefs.setToolTip("Configure data sources and API keys")

        mgr = SourceConfigManager()
        dialog = SourcePreferencesDialog(config_manager=mgr, parent=self)
        dialog.license_changed.connect(self._on_license_changed)
        if dialog.exec():
            configs = dialog.get_saved_configs()
            self._apply_source_configs(configs)

    def _apply_source_configs(self, configs: list):
        """Update orchestrator sources and UI based on saved preferences."""
        from kipart_search.core.source_config import SourceConfig

        # Rebuild orchestrator with only enabled sources
        self._orchestrator = SearchOrchestrator(cache=self._cache)

        for cfg in configs:
            if not cfg.enabled:
                continue
            if cfg.source_name == "JLCPCB":
                if not self._jlcpcb_source:
                    self._init_jlcpcb_source()
                if self._jlcpcb_source and self._jlcpcb_source.is_configured():
                    self._orchestrator.add_source(self._jlcpcb_source)
            # Future API sources would be instantiated here

        self.search_bar.set_sources(self._orchestrator.get_source_names())
        self._update_status()

        # Update search bar default source
        for cfg in configs:
            if cfg.is_default and cfg.enabled:
                self.search_bar.set_default_source(cfg.source_name)
                break

        self.log_panel.log(
            f"Sources updated: {', '.join(self._orchestrator.get_source_names()) or 'none'}"
        )

    # --- Backups ---

    def _on_open_backups(self):
        """Open the backup browser dialog."""
        from kipart_search.gui.backup_dialog import BackupBrowserDialog

        backup_mgr = self._ensure_backup_manager()
        project = self._get_project_name()

        dialog = BackupBrowserDialog(backup_mgr, project, parent=self)
        dialog.restore_requested.connect(self._on_restore_backup)
        dialog.exec()

    def _on_restore_backup(self, component_dicts: list[dict]):
        """Restore component fields from a backup snapshot."""
        if not self._bridge.is_connected:
            QMessageBox.warning(
                self, "Not Connected",
                "Restore requires an active KiCad connection.",
            )
            return

        backup_mgr = self._ensure_backup_manager()
        project = self._get_project_name()

        # Safety net: create a new backup before restoring
        try:
            from dataclasses import asdict
            current_components = self.verify_panel.get_components()
            comp_dicts = [asdict(c) for c in current_components]
            backup_mgr.reset_session()
            backup_mgr.ensure_session_backup(project, comp_dicts)
        except Exception as exc:
            log.warning("Failed to create safety backup before restore: %s", exc)

        restored = 0
        failed = 0
        for comp_dict in component_dicts:
            ref = comp_dict.get("reference", "")
            if not ref:
                continue
            for field_name in ("mpn", "datasheet"):
                value = comp_dict.get(field_name, "")
                if value:
                    try:
                        # Map field names to KiCad convention
                        kicad_name = "MPN" if field_name == "mpn" else field_name.capitalize()
                        ok = self._bridge.write_field(
                            ref, kicad_name, value, allow_overwrite=True,
                        )
                        if ok:
                            restored += 1
                            backup_mgr.log_field_change(
                                project, ref, kicad_name, "", value,
                            )
                    except Exception:
                        failed += 1
            # Restore extra fields
            for fname, fval in comp_dict.get("extra_fields", {}).items():
                if fval:
                    try:
                        ok = self._bridge.write_field(
                            ref, fname, fval, allow_overwrite=True,
                        )
                        if ok:
                            restored += 1
                            backup_mgr.log_field_change(
                                project, ref, fname, "", fval,
                            )
                    except Exception:
                        failed += 1

        msg = f"Restored {restored} field(s) across {len(component_dicts)} components."
        if failed:
            msg += f" ({failed} field(s) failed)"
        self.log_panel.log(msg)
        QMessageBox.information(self, "Restore Complete", msg)

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

        self._orchestrator = SearchOrchestrator(cache=self._cache)
        self._jlcpcb_source = JLCPCBSource(Path(db_path))
        if self._jlcpcb_source.is_configured():
            self._orchestrator.add_source(self._jlcpcb_source)

        self.search_bar.set_sources(self._orchestrator.get_source_names())
        self._update_status()
        self.log_panel.log(f"Database loaded: {db_path}")


def _create_splash(app: QApplication) -> "QSplashScreen":
    """Create a splash screen with app name and version rendered programmatically."""
    from PySide6.QtCore import Qt as _Qt
    from PySide6.QtGui import QColor, QFont, QPixmap, QPainter
    from PySide6.QtWidgets import QSplashScreen

    logical_w, logical_h = 420, 260
    dpr = app.primaryScreen().devicePixelRatio() if app.primaryScreen() else 1.0
    pixmap = QPixmap(int(logical_w * dpr), int(logical_h * dpr))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(QColor("#1a1a2e"))

    painter = QPainter()
    if painter.begin(pixmap):
        try:
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

            title_font = QFont()
            title_font.setPointSize(28)
            title_font.setWeight(QFont.Weight.Bold)
            painter.setFont(title_font)
            painter.setPen(QColor("#e0e0e0"))
            painter.drawText(
                0, 0, logical_w, logical_h,
                _Qt.AlignmentFlag.AlignCenter, "KiPart Search",
            )

            ver_font = QFont()
            ver_font.setPointSize(12)
            painter.setFont(ver_font)
            painter.setPen(QColor("#8888aa"))
            painter.drawText(
                0, 60, logical_w, logical_h,
                _Qt.AlignmentFlag.AlignHCenter | _Qt.AlignmentFlag.AlignCenter,
                f"v{__version__}",
            )
        finally:
            painter.end()

    splash = QSplashScreen(pixmap)
    splash.setWindowFlag(_Qt.WindowType.WindowStaysOnTopHint)
    return splash


def run_app() -> int:
    """Launch the PySide6 application."""
    app = QApplication(sys.argv)
    app.setApplicationName("KiPart Search")
    app.setApplicationVersion(__version__)

    splash = _create_splash(app)
    splash.show()
    app.processEvents()

    window = MainWindow()
    window.show()
    splash.finish(window)

    # Start background tasks after splash closes and event loop is running
    window.start_background_tasks()

    return app.exec()
