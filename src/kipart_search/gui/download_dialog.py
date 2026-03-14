"""Database download dialog with progress bar."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from kipart_search.core.sources import JLCPCBSource


class DownloadWorker(QThread):
    """Background thread for downloading the JLCPCB database."""

    progress = Signal(int, int, str)  # current, total, message
    finished = Signal(str)            # path to database
    error = Signal(str)               # error message

    def __init__(self, target_dir: Path | None = None):
        super().__init__()
        self.target_dir = target_dir

    def run(self):
        try:
            db_path = JLCPCBSource.download_database(
                target_dir=self.target_dir,
                progress_callback=lambda cur, total, msg: self.progress.emit(cur, total, msg),
            )
            self.finished.emit(str(db_path))
        except Exception as e:
            self.error.emit(str(e))


class DownloadDialog(QDialog):
    """Dialog for downloading the JLCPCB parts database."""

    download_complete = Signal(str)  # path to database

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download JLCPCB Database")
        self.setMinimumWidth(450)
        self.setModal(True)

        layout = QVBoxLayout(self)

        self.info_label = QLabel(
            "The JLCPCB parts database (~500 MB) needs to be downloaded.\n"
            "This is a one-time download. You can update it later."
        )
        layout.addWidget(self.info_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self._start_download)
        layout.addWidget(self.download_btn)

        self.close_btn = QPushButton("Cancel")
        self.close_btn.clicked.connect(self.reject)
        layout.addWidget(self.close_btn)

        self._worker: DownloadWorker | None = None

    def _start_download(self):
        self.download_btn.setEnabled(False)
        self.close_btn.setText("Cancel")
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)

        self._worker = DownloadWorker()
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, current: int, total: int, message: str):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(message)

    def _on_finished(self, db_path: str):
        self.status_label.setText("Database downloaded successfully!")
        self.close_btn.setText("Close")
        self.download_complete.emit(db_path)

    def _on_error(self, error_msg: str):
        self.status_label.setText(f"Error: {error_msg}")
        self.download_btn.setEnabled(True)
        self.download_btn.setText("Retry")
