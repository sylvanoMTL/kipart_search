"""Search bar widget — keyword input with live query transformation preview."""

from __future__ import annotations

from functools import partial

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget

from kipart_search.core.query_transform import strip_quotes, transform_query

# Special symbols that are useful in EE search queries
_SYMBOL_BUTTONS = [
    ("\u03a9", "Ohm symbol"),        # Ω
    ("\u00b1", "Plus/minus"),        # ±
    ("\u00b5", "Micro prefix"),      # µ
]


class SearchBar(QWidget):
    """Search input with transformed query preview and search button."""

    search_requested = Signal(str)  # Emits the transformed query string

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Row 1: user input + symbol buttons + search button
        row1 = QHBoxLayout()
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText(
            "Search parts (e.g. '100nF capacitor MLCC 0805', 'R_0805 10kohm')"
        )
        self.query_input.textChanged.connect(self._on_query_changed)
        self.query_input.returnPressed.connect(self._on_search)
        row1.addWidget(self.query_input)

        # Symbol insert buttons
        for symbol, tooltip in _SYMBOL_BUTTONS:
            btn = QPushButton(symbol)
            btn.setFixedWidth(28)
            btn.setToolTip(f"Insert {tooltip} ({symbol})")
            btn.clicked.connect(partial(self._insert_symbol, symbol))
            row1.addWidget(btn)

        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self._on_search)
        row1.addWidget(self.search_button)
        layout.addLayout(row1)

        # Row 2: transformed query preview (editable)
        self._transformed_input = QLineEdit()
        self._transformed_input.setPlaceholderText("Transformed query (editable)")
        self._transformed_input.setStyleSheet(
            "font-style: italic; background-color: #f0f4ff;"
        )
        self._transformed_input.returnPressed.connect(self._on_search)
        layout.addWidget(self._transformed_input)

    def set_query(self, query: str):
        """Set the raw search input text programmatically.

        The transformed preview updates automatically via textChanged.
        """
        self.query_input.setText(query)

    def _insert_symbol(self, symbol: str):
        """Insert a special symbol at the cursor position in the query input."""
        self.query_input.insert(symbol)
        self.query_input.setFocus()

    def _on_query_changed(self, text: str):
        """Live-transform the user's query and display in the preview."""
        transformed = transform_query(text)
        if self._transformed_input.text() != transformed:
            self._transformed_input.setText(transformed)

    def _on_search(self):
        query = strip_quotes(self._transformed_input.text().strip())
        if query:
            self.search_requested.emit(query)
