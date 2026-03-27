"""Update dialog with download progress for app updates."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from kipart_search import __version__
from kipart_search.core.update_check import UpdateInfo


class _DownloadWorker(QThread):
    """Background thread for downloading the update installer."""

    progress = Signal(int, int)  # (downloaded_bytes, total_bytes)
    finished = Signal(str)       # final file path
    error = Signal(str)          # error message

    def __init__(self, url: str, dest: Path, expected_size: int):
        super().__init__()
        self.url = url
        self.dest = dest
        self.expected_size = expected_size

    def run(self):
        import httpx

        partial = self.dest.with_suffix(self.dest.suffix + ".partial")
        try:
            with httpx.stream(
                "GET", self.url, timeout=300.0, follow_redirects=True
            ) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0
                with open(partial, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.progress.emit(downloaded, total)
            # Rename .partial → final
            if self.dest.exists():
                self.dest.unlink()
            partial.rename(self.dest)
            # Verify size
            actual = self.dest.stat().st_size
            if self.expected_size > 0 and actual != self.expected_size:
                try:
                    self.dest.unlink()
                except OSError:
                    pass
                self.error.emit(
                    f"Size mismatch: expected {self.expected_size}, got {actual}"
                )
                return
            self.finished.emit(str(self.dest))
        except Exception as e:
            # Clean up partial file
            if partial.exists():
                try:
                    partial.unlink()
                except OSError:
                    pass
            self.error.emit(str(e))


class UpdateDialog(QDialog):
    """Dialog showing release notes and download progress for an available update."""

    def __init__(self, info: UpdateInfo, parent=None):
        super().__init__(parent)
        self._info = info
        self._worker: _DownloadWorker | None = None

        self.setWindowTitle("KiPart Search Update Available")
        self.setMinimumWidth(480)
        self.setMinimumHeight(320)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Version header
        header = QLabel(
            f"Version {info.latest_version} is available (you have {__version__})"
        )
        header.setStyleSheet("font-size: 13px; font-weight: bold;")
        layout.addWidget(header)

        # Release notes
        notes_label = QLabel("Release Notes:")
        layout.addWidget(notes_label)

        self._notes_edit = QTextEdit()
        self._notes_edit.setReadOnly(True)
        self._notes_edit.setPlainText(info.release_notes or "(no release notes)")
        layout.addWidget(self._notes_edit, 1)

        # Progress bar (hidden by default)
        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        # Status label (hidden by default)
        self._status_label = QLabel()
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label)

        # Buttons
        btn_row = QHBoxLayout()

        self._update_btn = QPushButton("Update Now")
        self._update_btn.setEnabled(bool(info.asset_url))
        if not info.asset_url:
            self._update_btn.setToolTip("No installer available for this platform")
        self._update_btn.clicked.connect(self._on_update_now)
        btn_row.addWidget(self._update_btn)

        self._remind_btn = QPushButton("Remind Me Later")
        self._remind_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._remind_btn)

        self._skip_btn = QPushButton("Skip This Version")
        self._skip_btn.clicked.connect(self._on_skip)
        btn_row.addWidget(self._skip_btn)

        layout.addLayout(btn_row)

        # Post-download buttons (hidden by default)
        self._post_row = QHBoxLayout()
        self._open_folder_btn = QPushButton("Open Folder")
        self._open_folder_btn.setVisible(False)
        self._open_folder_btn.clicked.connect(self._on_open_folder)
        self._post_row.addWidget(self._open_folder_btn)

        self._close_btn = QPushButton("Close")
        self._close_btn.setVisible(False)
        self._close_btn.clicked.connect(self.accept)
        self._post_row.addWidget(self._close_btn)

        layout.addLayout(self._post_row)

        self._downloaded_path: str = ""

        # If no asset URL available, show note
        if not info.asset_url:
            self._status_label.setText(
                "No installer available for this platform. "
                "Visit the release page to download manually."
            )
            self._status_label.setVisible(True)

    def _on_skip(self):
        """Persist the skipped version and close."""
        from kipart_search.core.paths import config_path
        from kipart_search.core.update_check import save_skipped_version

        save_skipped_version(config_path(), self._info.latest_version)
        self.reject()

    def _on_update_now(self):
        """Start downloading the update installer."""
        self._update_btn.setEnabled(False)
        self._remind_btn.setEnabled(False)
        self._skip_btn.setEnabled(False)

        self._progress_bar.setVisible(True)
        self._status_label.setText("Downloading...")
        self._status_label.setVisible(True)

        dest = Path(tempfile.gettempdir()) / (
            f"kipart-search-update-v{self._info.latest_version}.exe"
        )

        self._worker = _DownloadWorker(
            url=self._info.asset_url,
            dest=dest,
            expected_size=self._info.asset_size,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_download_finished)
        self._worker.error.connect(self._on_download_error)
        self._worker.start()

    def _on_progress(self, downloaded: int, total: int):
        if total > 0:
            self._progress_bar.setMaximum(total)
            self._progress_bar.setValue(downloaded)
            mb_done = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            self._status_label.setText(
                f"Downloading... {mb_done:.1f} / {mb_total:.1f} MB"
            )
        else:
            self._progress_bar.setMaximum(0)  # indeterminate
            mb_done = downloaded / (1024 * 1024)
            self._status_label.setText(f"Downloading... {mb_done:.1f} MB")

    def _on_download_finished(self, path: str):
        self._downloaded_path = path
        self._progress_bar.setVisible(False)
        self._status_label.setText(f"Downloaded to: {path}")

        # Hide initial buttons, show post-download buttons
        self._update_btn.setVisible(False)
        self._remind_btn.setVisible(False)
        self._skip_btn.setVisible(False)
        self._open_folder_btn.setVisible(True)
        self._close_btn.setVisible(True)

    def _on_download_error(self, error_msg: str):
        self._progress_bar.setVisible(False)
        self._status_label.setText(
            f"Download failed: {error_msg}\n\n"
            "Download may have been blocked. Download manually from GitHub."
        )

        # Re-enable buttons and add fallback link
        self._update_btn.setVisible(False)
        self._remind_btn.setVisible(False)
        self._skip_btn.setVisible(False)

        # Show fallback button to open release page (guard against re-entry)
        if not hasattr(self, "_fallback_btn"):
            self._fallback_btn = QPushButton("Open Release Page")
            self._fallback_btn.clicked.connect(self._on_open_release_page)
            self._post_row.insertWidget(0, self._fallback_btn)
        self._fallback_btn.setVisible(True)
        self._close_btn.setVisible(True)

    def _on_open_folder(self):
        """Open the folder containing the downloaded installer."""
        if self._downloaded_path:
            import sys
            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", self._downloaded_path])
            else:
                from PySide6.QtCore import QUrl
                from PySide6.QtGui import QDesktopServices
                QDesktopServices.openUrl(
                    QUrl.fromLocalFile(str(Path(self._downloaded_path).parent))
                )

    def _on_open_release_page(self):
        """Open the GitHub release page in the default browser."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        if self._info.release_url:
            QDesktopServices.openUrl(QUrl(self._info.release_url))
