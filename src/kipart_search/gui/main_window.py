"""Main application window."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from kipart_search import __version__
from kipart_search.gui.search_bar import SearchBar
from kipart_search.gui.results_table import ResultsTable


class MainWindow(QMainWindow):
    """KiPart Search main window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"KiPart Search v{__version__}")
        self.setMinimumSize(900, 600)

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
        top_bar.addWidget(self.scan_btn)
        top_bar.addWidget(self.search_btn)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Search bar
        self.search_bar = SearchBar()
        layout.addWidget(self.search_bar)

        # Results table
        self.results_table = ResultsTable()
        layout.addWidget(self.results_table)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status()

    def _update_status(self):
        """Update the status bar with data source info."""
        # TODO: Show actual source status (JLCPCB DB loaded, APIs configured, etc.)
        self.status_bar.showMessage(
            "KiCad: not connected | JLCPCB database: not loaded"
        )


def run_app() -> int:
    """Launch the PySide6 application."""
    app = QApplication(sys.argv)
    app.setApplicationName("KiPart Search")
    app.setApplicationVersion(__version__)

    window = MainWindow()
    window.show()

    return app.exec()
