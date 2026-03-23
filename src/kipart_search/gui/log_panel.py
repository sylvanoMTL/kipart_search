"""Timestamped log panel for operation feedback."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class LogPanel(QWidget):
    """Read-only log panel with timestamped entries."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Toolbar row: copy button ──
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.addStretch()

        self._copy_btn = QPushButton("Copy Log")
        self._copy_btn.setFixedHeight(22)
        self._copy_btn.clicked.connect(self.copy_log)
        toolbar.addWidget(self._copy_btn)

        layout.addLayout(toolbar)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setMinimumHeight(30)
        self._text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self._text.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._text.customContextMenuRequested.connect(self._on_context_menu)
        self._text.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        layout.addWidget(self._text)
        self.log("Ready")

    def sizeHint(self) -> QSize:
        """Suggest a compact height so the log dock doesn't dominate the layout."""
        return QSize(super().sizeHint().width(), 120)

    def log(self, msg: str):
        """Append a timestamped line."""
        from html import escape
        ts = datetime.now().strftime("%H:%M:%S")
        self._text.append(f"[{ts}] {escape(msg)}")
        self._scroll_to_bottom()

    def section(self, title: str) -> None:
        """Append a visual section separator."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._text.append(
            f'<div style="color: #888; margin-top: 4px;">'
            f"[{ts}] ── {title} ──</div>"
        )
        self._scroll_to_bottom()

    def copy_log(self):
        """Copy the full log text to the clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self._text.toPlainText())

    def clear(self):
        """Clear all log entries."""
        self._text.clear()

    def _scroll_to_bottom(self):
        """Scroll the log view to the latest entry."""
        sb = self._text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _build_context_menu(self):
        """Build the context menu with a Clear Log action appended."""
        menu = self._text.createStandardContextMenu()
        menu.addSeparator()
        clear_action = menu.addAction("Clear Log")
        clear_action.triggered.connect(self.clear)
        return menu

    def _on_context_menu(self, pos):
        """Show the context menu at the requested position."""
        menu = self._build_context_menu()
        menu.exec(self._text.mapToGlobal(pos))
