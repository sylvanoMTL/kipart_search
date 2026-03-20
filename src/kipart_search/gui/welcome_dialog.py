"""Welcome / first-run dialog for new users."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from kipart_search.gui.download_dialog import DownloadWorker
from kipart_search.core.sources import JLCPCBSource

log = logging.getLogger(__name__)


class WelcomeDialog(QDialog):
    """Modal welcome dialog shown on first launch.

    Offers three options: download JLCPCB database, configure API sources,
    or skip setup for now.
    """

    source_configured = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to KiPart Search")
        self.setFixedSize(480, 340)
        self.setModal(True)

        self._worker: DownloadWorker | None = None
        self._db_path: Path | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Title
        title = QLabel("Welcome to KiPart Search")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "Fast parametric electronic component search across multiple\n"
            "distributor APIs, with KiCad integration.\n\n"
            "To get started, set up at least one data source:"
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addSpacing(8)

        # ── Option buttons ──
        self._btn_download = QPushButton("Download JLCPCB Database")
        self._btn_download.setToolTip("No API key needed — ~500 MB offline database")
        self._btn_download.setMinimumHeight(40)
        self._btn_download.clicked.connect(self._on_download)
        layout.addWidget(self._btn_download)

        self._subtitle_download = QLabel("No API key needed — ~500 MB offline database")
        self._subtitle_download.setStyleSheet("color: gray; font-size: 11px;")
        self._subtitle_download.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._subtitle_download)

        self._btn_configure = QPushButton("Configure API Source")
        self._btn_configure.setToolTip("Set up DigiKey, Mouser, or Octopart")
        self._btn_configure.setMinimumHeight(40)
        self._btn_configure.clicked.connect(self._on_configure)
        layout.addWidget(self._btn_configure)

        self._subtitle_configure = QLabel("Set up DigiKey, Mouser, or Octopart")
        self._subtitle_configure.setStyleSheet("color: gray; font-size: 11px;")
        self._subtitle_configure.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._subtitle_configure)

        self._btn_skip = QPushButton("Skip for now")
        self._btn_skip.setToolTip("Configure sources later in Preferences")
        self._btn_skip.setMinimumHeight(32)
        self._btn_skip.clicked.connect(self._on_skip)
        layout.addWidget(self._btn_skip)

        self._subtitle_skip = QLabel("Configure sources later in Preferences")
        self._subtitle_skip.setStyleSheet("color: gray; font-size: 11px;")
        self._subtitle_skip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._subtitle_skip)

        # ── Download state widgets (hidden initially) ──
        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._progress_label = QLabel("")
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._progress_label.setVisible(False)
        layout.addWidget(self._progress_label)

        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.setVisible(False)
        self._btn_cancel.clicked.connect(self._on_cancel_download)
        layout.addWidget(self._btn_cancel)

        layout.addStretch()

    # ── Option handlers ──────────────────────────────────────────

    def _on_download(self):
        """Start JLCPCB database download, switching to progress view."""
        self._set_download_state(True)

        target_dir = JLCPCBSource.default_db_path().parent
        self._worker = DownloadWorker(target_dir)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_download_complete)
        self._worker.error.connect(self._on_download_error)
        self._worker.start()

    def _on_configure(self):
        """Open the Source Preferences Dialog as a nested modal."""
        from kipart_search.gui.source_preferences_dialog import SourcePreferencesDialog
        from kipart_search.core.source_config import SourceConfigManager

        mgr = SourceConfigManager()
        dialog = SourcePreferencesDialog(config_manager=mgr, parent=self)
        if dialog.exec():
            self._saved_configs = dialog.get_saved_configs()
            self.source_configured.emit()
            self.accept()

    def _on_skip(self):
        """Close dialog without configuring any source."""
        self.reject()

    # ── Download state management ────────────────────────────────

    def _set_download_state(self, downloading: bool):
        """Toggle between the 3-button view and the progress view."""
        # Option buttons and subtitles
        for widget in (
            self._btn_download, self._subtitle_download,
            self._btn_configure, self._subtitle_configure,
            self._btn_skip, self._subtitle_skip,
        ):
            widget.setVisible(not downloading)

        # Progress widgets
        self._progress_bar.setVisible(downloading)
        self._progress_label.setVisible(downloading)
        self._btn_cancel.setVisible(downloading)

        if downloading:
            self._progress_bar.setValue(0)
            self._progress_label.setText("Starting download...")

    def _on_progress(self, current: int, total: int, message: str):
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(current)
        self._progress_label.setText(message)

    def _on_download_complete(self, db_path: str):
        self._db_path = Path(db_path)
        self.source_configured.emit()
        self.accept()

    def _on_download_error(self, error_msg: str):
        if "cancelled" in error_msg.lower():
            # Return to initial state — partial files cleaned by DownloadWorker
            self._set_download_state(False)
        else:
            self._progress_label.setText(f"Error: {error_msg}")
            self._btn_cancel.setText("Back")

    def _on_cancel_download(self):
        """Cancel an in-progress download."""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._progress_label.setText("Cancelling...")
            self._btn_cancel.setEnabled(False)
            # Worker will emit error with "cancelled" message,
            # which triggers _on_download_error → return to initial state
        else:
            # "Back" button after error — return to initial state
            self._set_download_state(False)
            self._btn_cancel.setText("Cancel")
            self._btn_cancel.setEnabled(True)

    # ── Public accessors ─────────────────────────────────────────

    def get_db_path(self) -> Path | None:
        """Return the downloaded database path, or None if not downloaded."""
        return self._db_path

    def get_saved_configs(self) -> list:
        """Return configs saved via the Configure API option."""
        return getattr(self, "_saved_configs", [])
