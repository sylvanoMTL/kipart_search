"""Search bar widget — keyword input with category filter."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget


class SearchBar(QWidget):
    """Search input with a search button."""

    search_requested = Signal(str)  # Emits the query string

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText(
            "Search parts (e.g. '100nF capacitor MLCC 0805')"
        )
        self.query_input.returnPressed.connect(self._on_search)
        layout.addWidget(self.query_input)

        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self._on_search)
        layout.addWidget(self.search_button)

    def _on_search(self):
        query = self.query_input.text().strip()
        if query:
            self.search_requested.emit(query)
