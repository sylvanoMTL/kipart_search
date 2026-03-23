"""Database download dialog with update check and location picker."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from kipart_search.core.sources import JLCPCBSource


class UpdateCheckWorker(QThread):
    """Background thread for checking if a database update is available."""

    result = Signal(bool, str)  # (update_available, message)

    def __init__(self, db_path: Path | None = None):
        super().__init__()
        self.db_path = db_path

    def run(self):
        try:
            available, msg = JLCPCBSource.check_for_update(self.db_path)
            self.result.emit(available, msg)
        except Exception as e:
            self.result.emit(False, f"Check failed: {e}")


class DownloadWorker(QThread):
    """Background thread for downloading the JLCPCB database."""

    progress = Signal(int, int, str)  # current, total, message
    finished = Signal(str)            # path to database
    error = Signal(str)               # error message

    def __init__(self, target_dir: Path):
        super().__init__()
        self.target_dir = target_dir
        self._cancelled = False

    def cancel(self):
        """Request cancellation of the download."""
        self._cancelled = True

    def run(self):
        try:
            db_path = JLCPCBSource.download_database(
                target_dir=self.target_dir,
                progress_callback=lambda cur, total, msg: self.progress.emit(cur, total, msg),
                cancel_check=lambda: self._cancelled,
            )
            if not self._cancelled:
                self.finished.emit(str(db_path))
        except RuntimeError as e:
            if self._cancelled:
                self.error.emit("Download cancelled")
            else:
                self.error.emit(str(e))
        except Exception as e:
            self.error.emit(str(e))


class DownloadDialog(QDialog):
    """Dialog for downloading/updating the JLCPCB parts database."""

    download_complete = Signal(str)  # path to database

    def __init__(self, db_path: Path | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("JLCPCB Database")
        self.setMinimumWidth(500)
        self.setModal(True)

        self._db_path = db_path or JLCPCBSource.default_db_path()
        self._worker: DownloadWorker | None = None
        self._check_worker: UpdateCheckWorker | None = None

        layout = QVBoxLayout(self)

        # Database location
        loc_label = QLabel("Database location:")
        layout.addWidget(loc_label)

        loc_row = QHBoxLayout()
        self.path_edit = QLineEdit(str(self._db_path.parent))
        self.path_edit.setReadOnly(True)
        loc_row.addWidget(self.path_edit)
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._on_browse)
        loc_row.addWidget(self.browse_btn)
        layout.addLayout(loc_row)

        # Status / info
        self.info_label = QLabel("Checking for updates...")
        layout.addWidget(self.info_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        # Buttons
        btn_row = QHBoxLayout()
        self.download_btn = QPushButton("Download")
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._start_download)
        btn_row.addWidget(self.download_btn)

        self.close_btn = QPushButton("Cancel")
        self.close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.close_btn)
        layout.addLayout(btn_row)

        # Auto-check on open
        self._check_for_update()

    def _on_browse(self):
        """Let the user pick a directory for the database."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Database Directory", str(self._db_path.parent)
        )
        if directory:
            self._db_path = Path(directory) / "parts-fts5.db"
            self.path_edit.setText(directory)
            # Re-check with new path
            self._check_for_update()

    def _check_for_update(self):
        """Check if the database needs downloading/updating."""
        self.info_label.setText("Checking for updates...")
        self.download_btn.setEnabled(False)

        if self._check_worker and self._check_worker.isRunning():
            self._check_worker.wait()
        self._check_worker = UpdateCheckWorker(self._db_path)
        self._check_worker.result.connect(self._on_check_result)
        self._check_worker.start()

    def _on_check_result(self, update_available: bool, message: str):
        self.info_label.setText(message)
        if update_available:
            self.download_btn.setEnabled(True)
            self.download_btn.setText("Download")
        else:
            self.download_btn.setEnabled(False)
            self.download_btn.setText("Up to date")
            self.close_btn.setText("Close")

    def _start_download(self):
        self.download_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.close_btn.setText("Cancel")
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)

        # Rewire close button to cancel during download
        try:
            self.close_btn.clicked.disconnect(self.reject)
        except TypeError:
            pass  # slot wasn't connected
        self.close_btn.clicked.connect(self._on_cancel)

        target_dir = self._db_path.parent
        self._worker = DownloadWorker(target_dir)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_cancel(self):
        """Cancel an in-progress download."""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.status_label.setText("Cancelling...")
            self.close_btn.setEnabled(False)
        else:
            self.reject()

    def _on_progress(self, current: int, total: int, message: str):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(message)

    def _on_finished(self, db_path: str):
        self.status_label.setText("Database downloaded successfully!")
        self.close_btn.setText("Close")
        self.close_btn.setEnabled(True)
        # Rewire close button back to reject
        try:
            self.close_btn.clicked.disconnect(self._on_cancel)
        except TypeError:
            pass
        self.close_btn.clicked.connect(self.reject)
        self.browse_btn.setEnabled(True)
        self.download_complete.emit(db_path)

    def _on_error(self, error_msg: str):
        self.status_label.setText(f"Error: {error_msg}")
        self.browse_btn.setEnabled(True)
        self.close_btn.setEnabled(True)
        # Rewire close button back to reject
        try:
            self.close_btn.clicked.disconnect(self._on_cancel)
        except TypeError:
            pass
        self.close_btn.clicked.connect(self.reject)
        self.download_btn.setEnabled(True)
        self.download_btn.setText("Retry")
        if "cancelled" in error_msg.lower():
            self.close_btn.setText("Close")
