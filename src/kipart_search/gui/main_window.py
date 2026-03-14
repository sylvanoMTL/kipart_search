"""Main application window."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from kipart_search import __version__
from kipart_search.core.models import Confidence
from kipart_search.core.sources import JLCPCBSource
from kipart_search.core.search import SearchOrchestrator
from kipart_search.gui.kicad_bridge import BoardComponent, KiCadBridge
from kipart_search.gui.search_bar import SearchBar
from kipart_search.gui.results_table import ResultsTable
from kipart_search.gui.verify_panel import VerifyPanel


class SearchWorker(QThread):
    """Background thread for running searches."""

    results_ready = Signal(list)
    error = Signal(str)

    def __init__(self, orchestrator: SearchOrchestrator, query: str):
        super().__init__()
        self.orchestrator = orchestrator
        self.query = query

    def run(self):
        try:
            results = self.orchestrator.search(self.query, limit=200)
            self.results_ready.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class ScanWorker(QThread):
    """Background thread for scanning and verifying a KiCad project."""

    scan_complete = Signal(list, dict)  # components, mpn_statuses
    error = Signal(str)

    def __init__(self, bridge: KiCadBridge, orchestrator: SearchOrchestrator):
        super().__init__()
        self.bridge = bridge
        self.orchestrator = orchestrator

    def run(self):
        try:
            components = self.bridge.get_components()
            if not components:
                self.error.emit("No components found on the board")
                return

            # Verify each component's MPN against the database
            mpn_statuses: dict[str, Confidence] = {}
            for comp in components:
                if not comp.has_mpn:
                    mpn_statuses[comp.reference] = Confidence.RED
                    continue

                # Look up MPN in data sources
                result = self.orchestrator.verify_mpn(comp.mpn)
                if result:
                    # Check category consistency
                    mpn_statuses[comp.reference] = result.confidence
                else:
                    # MPN not found in any source
                    mpn_statuses[comp.reference] = Confidence.RED

            self.scan_complete.emit(components, mpn_statuses)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """KiPart Search main window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"KiPart Search v{__version__}")
        self.setMinimumSize(900, 600)

        # Core engine
        self._orchestrator = SearchOrchestrator()
        self._jlcpcb_source: JLCPCBSource | None = None
        self._search_worker: SearchWorker | None = None
        self._scan_worker: ScanWorker | None = None
        self._bridge = KiCadBridge()

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Top bar with action buttons
        top_bar = QHBoxLayout()
        self.scan_btn = QPushButton("Scan Project")
        self.scan_btn.setToolTip("Connect to KiCad and verify BOM")
        self.scan_btn.clicked.connect(self._on_scan)
        self.search_btn = QPushButton("Search Parts")
        self.search_btn.setToolTip("Show parametric search view")
        self.search_btn.clicked.connect(self._show_search_view)
        self.db_btn = QPushButton("Download Database")
        self.db_btn.setToolTip("Download or update the JLCPCB parts database")
        self.db_btn.clicked.connect(self._on_download_db)
        top_bar.addWidget(self.scan_btn)
        top_bar.addWidget(self.search_btn)
        top_bar.addWidget(self.db_btn)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Stacked widget: search view (0) and verify view (1)
        self._stack = QStackedWidget()

        # Search view
        search_widget = QWidget()
        search_layout = QVBoxLayout(search_widget)
        search_layout.setContentsMargins(0, 0, 0, 0)
        self.search_bar = SearchBar()
        self.search_bar.search_requested.connect(self._on_search)
        search_layout.addWidget(self.search_bar)
        self.results_label = QLabel("")
        search_layout.addWidget(self.results_label)
        self.results_table = ResultsTable()
        search_layout.addWidget(self.results_table)
        self._stack.addWidget(search_widget)

        # Verify view
        self.verify_panel = VerifyPanel()
        self.verify_panel.component_clicked.connect(self._on_component_clicked)
        self._stack.addWidget(self.verify_panel)

        layout.addWidget(self._stack)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Try to load existing database
        self._init_jlcpcb_source()
        self._update_status()

    def _init_jlcpcb_source(self):
        """Initialize JLCPCB source if database exists."""
        db_path = JLCPCBSource.default_db_path()
        self._jlcpcb_source = JLCPCBSource(db_path)
        if self._jlcpcb_source.is_configured():
            self._orchestrator.add_source(self._jlcpcb_source)

    def _update_status(self):
        """Update the status bar with data source info."""
        parts = []
        if self._jlcpcb_source and self._jlcpcb_source.is_configured():
            parts.append("JLCPCB database: loaded")
            self.db_btn.setText("Update Database")
        else:
            parts.append("JLCPCB database: not loaded")
            self.db_btn.setText("Download Database")

        if self._bridge.is_connected:
            parts.append("KiCad: connected")
        else:
            parts.append("KiCad: not connected")

        self.status_bar.showMessage(" | ".join(parts))

    def _show_search_view(self):
        """Switch to the search/results view."""
        self._stack.setCurrentIndex(0)

    def _show_verify_view(self):
        """Switch to the verification dashboard view."""
        self._stack.setCurrentIndex(1)

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
        self.results_label.setText("Searching...")

        self._search_worker = SearchWorker(self._orchestrator, query)
        self._search_worker.results_ready.connect(self._on_results)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.start()

    def _on_results(self, results):
        """Display search results."""
        self.results_table.set_results(results)
        self.results_label.setText(f"{len(results)} results found")
        self.search_bar.search_button.setEnabled(True)

    def _on_search_error(self, error_msg: str):
        """Handle search error."""
        self.results_label.setText(f"Search error: {error_msg}")
        self.search_bar.search_button.setEnabled(True)

    # --- Scan Project ---

    def _on_scan(self):
        """Scan the KiCad project and verify BOM."""
        # Try to connect if not already connected
        if not self._bridge.is_connected:
            if not self._bridge.connect():
                QMessageBox.warning(
                    self,
                    "KiCad Not Found",
                    "Could not connect to KiCad.\n\n"
                    "Make sure KiCad 9+ is running with a board open\n"
                    "and the IPC API is enabled.",
                )
                return

        self._update_status()
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("Scanning...")
        self._show_verify_view()

        self._scan_worker = ScanWorker(self._bridge, self._orchestrator)
        self._scan_worker.scan_complete.connect(self._on_scan_complete)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.start()

    def _on_scan_complete(self, components, mpn_statuses):
        """Display scan/verification results."""
        self.verify_panel.set_results(components, mpn_statuses)
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("Scan Project")

    def _on_scan_error(self, error_msg: str):
        """Handle scan error."""
        QMessageBox.warning(self, "Scan Error", error_msg)
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("Scan Project")

    def _on_component_clicked(self, reference: str):
        """Highlight the clicked component in KiCad."""
        self._bridge.select_component(reference)

    # --- Database ---

    def _on_download_db(self):
        """Open the database download dialog."""
        from kipart_search.gui.download_dialog import DownloadDialog

        dialog = DownloadDialog(self)
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


def run_app() -> int:
    """Launch the PySide6 application."""
    app = QApplication(sys.argv)
    app.setApplicationName("KiPart Search")
    app.setApplicationVersion(__version__)

    window = MainWindow()
    window.show()

    return app.exec()
