"""Timestamped log panel for operation feedback."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget


class LogPanel(QWidget):
    """Read-only log panel with timestamped entries."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setFixedHeight(90)
        self._text.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        self._text.setPlaceholderText("Activity log ...")
        layout.addWidget(self._text)

    def log(self, msg: str):
        """Append a timestamped line."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._text.append(f"[{ts}] {msg}")

    def clear(self):
        """Clear all log entries."""
        self._text.clear()
