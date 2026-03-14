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
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from kipart_search import __version__
from kipart_search.core.sources import JLCPCBSource
from kipart_search.core.search import SearchOrchestrator
from kipart_search.gui.search_bar import SearchBar
from kipart_search.gui.results_table import ResultsTable


class SearchWorker(QThread):
    """Background thread for running searches."""

    results_ready = Signal(list)  # list[PartResult]
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

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Top bar with action buttons
        top_bar = QHBoxLayout()
        self.scan_btn = QPushButton("Scan Project")
        self.scan_btn.setToolTip("Connect to KiCad and verify BOM")
        self.search_btn = QPushButton("Search Parts")
        self.search_btn.setToolTip("Parametric search across distributors")
        self.db_btn = QPushButton("Download Database")
        self.db_btn.setToolTip("Download or update the JLCPCB parts database")
        top_bar.addWidget(self.scan_btn)
        top_bar.addWidget(self.search_btn)
        top_bar.addWidget(self.db_btn)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Search bar
        self.search_bar = SearchBar()
        layout.addWidget(self.search_bar)

        # Results count label
        self.results_label = QLabel("")
        layout.addWidget(self.results_label)

        # Results table
        self.results_table = ResultsTable()
        layout.addWidget(self.results_table)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Connect signals
        self.search_bar.search_requested.connect(self._on_search)
        self.db_btn.clicked.connect(self._on_download_db)

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
        parts.append("KiCad: not connected")
        self.status_bar.showMessage(" | ".join(parts))

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

    def _on_download_db(self):
        """Open the database download dialog."""
        from kipart_search.gui.download_dialog import DownloadDialog

        dialog = DownloadDialog(self)
        dialog.download_complete.connect(self._on_db_downloaded)
        dialog.exec()

    def _on_db_downloaded(self, db_path: str):
        """Handle database download completion."""
        # Reinitialize the source with the new database
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
