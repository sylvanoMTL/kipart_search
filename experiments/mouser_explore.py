"""Mouser API breadboard — standalone PySide6 GUI for testing search integration.

Usage:
    python experiments/mouser_explore.py

Features:
    - API key input (persisted in env var for session)
    - Dummy BOM component table (double-click to search)
    - Mouser keyword search via POST /api/v1/search/keyword
    - Mouser MPN lookup via POST /api/v1/search/partnumber
    - Results table with key fields
    - Raw JSON inspector for debugging
"""

from __future__ import annotations

import json
import sys
import time

import httpx
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


# ── Mouser API client ───────────────────────────────────────────

MOUSER_BASE = "https://api.mouser.com/api"


def mouser_keyword_search(
    client: httpx.Client,
    api_key: str,
    keyword: str,
    records: int = 20,
    search_options: str = "None",
) -> dict:
    """POST /v1/search/keyword — returns raw JSON response."""
    url = f"{MOUSER_BASE}/v1/search/keyword?apiKey={api_key}"
    body = {
        "SearchByKeywordRequest": {
            "keyword": keyword,
            "records": records,
            "startingRecord": 0,
            "searchOptions": search_options,
            "searchWithYourSignUpLanguage": "false",
        }
    }
    resp = client.post(url, json=body)
    resp.raise_for_status()
    return resp.json()


def mouser_partnumber_search(
    client: httpx.Client,
    api_key: str,
    part_number: str,
    exact: bool = False,
) -> dict:
    """POST /v1/search/partnumber — returns raw JSON response."""
    url = f"{MOUSER_BASE}/v1/search/partnumber?apiKey={api_key}"
    body = {
        "SearchByPartRequest": {
            "mouserPartNumber": part_number,
            "partSearchOptions": "Exact" if exact else "None",
        }
    }
    resp = client.post(url, json=body)
    resp.raise_for_status()
    return resp.json()


# ── Search worker (background thread) ───────────────────────────

class SearchWorker(QThread):
    results_ready = Signal(dict, float)  # raw_json, elapsed_seconds
    error = Signal(str)

    def __init__(
        self,
        client: httpx.Client,
        api_key: str,
        query: str,
        search_type: str = "keyword",
        search_options: str = "None",
        records: int = 20,
    ):
        super().__init__()
        self.client = client
        self.api_key = api_key
        self.query = query
        self.search_type = search_type
        self.search_options = search_options
        self.records = records

    def run(self):
        try:
            t0 = time.perf_counter()
            if self.search_type == "keyword":
                data = mouser_keyword_search(
                    self.client, self.api_key, self.query,
                    records=self.records,
                    search_options=self.search_options,
                )
            else:
                data = mouser_partnumber_search(
                    self.client, self.api_key, self.query,
                    exact=(self.search_type == "exact"),
                )
            elapsed = time.perf_counter() - t0
            self.results_ready.emit(data, elapsed)
        except Exception as e:
            self.error.emit(str(e))


# ── Dummy BOM data ──────────────────────────────────────────────

DUMMY_BOM = [
    {"ref": "C1", "value": "100nF", "footprint": "0402", "type": "capacitor", "mpn": ""},
    {"ref": "C2", "value": "10uF", "footprint": "0805", "type": "capacitor", "mpn": ""},
    {"ref": "R1", "value": "10k", "footprint": "0402", "type": "resistor", "mpn": ""},
    {"ref": "R2", "value": "47", "footprint": "0402", "type": "resistor", "mpn": ""},
    {"ref": "R3", "value": "1k", "footprint": "0603", "type": "resistor", "mpn": ""},
    {"ref": "U1", "value": "STM32F405RGT6", "footprint": "LQFP-64", "type": "IC", "mpn": "STM32F405RGT6"},
    {"ref": "U2", "value": "LM1117-3.3", "footprint": "SOT-223", "type": "IC", "mpn": "LM1117IMPX-3.3"},
    {"ref": "D1", "value": "LED Green", "footprint": "0603", "type": "LED", "mpn": ""},
    {"ref": "L1", "value": "4.7uH", "footprint": "1210", "type": "inductor", "mpn": ""},
    {"ref": "Y1", "value": "8MHz", "footprint": "HC49", "type": "crystal", "mpn": ""},
]


def build_search_query(comp: dict) -> str:
    """Build a keyword search query from a BOM component."""
    parts = []
    if comp["value"]:
        parts.append(comp["value"])
    if comp["footprint"]:
        parts.append(comp["footprint"])
    if comp["type"] and comp["type"] not in ("IC",):
        parts.append(comp["type"])
    return " ".join(parts)


# ── Result columns ──────────────────────────────────────────────

RESULT_COLUMNS = [
    ("MPN", "ManufacturerPartNumber"),
    ("Manufacturer", "Manufacturer"),
    ("Description", "Description"),
    ("Category", "Category"),
    ("In Stock", "AvailabilityInStock"),
    ("Lifecycle", "LifecycleStatus"),
    ("Discontinued", "IsDiscontinued"),
    ("Mouser #", "MouserPartNumber"),
    ("Datasheet", "DataSheetUrl"),
    ("Lead Time", "LeadTime"),
]


# ── Main window ─────────────────────────────────────────────────

class MouserBreadboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mouser API Breadboard")
        self.setMinimumSize(1200, 700)

        self._client = httpx.Client(
            timeout=httpx.Timeout(20.0, connect=5.0),
            headers={"Content-Type": "application/json"},
        )
        self._worker: SearchWorker | None = None
        self._last_raw: dict = {}
        self._elapsed: float = 0.0
        self._visible_parts: list[dict] = []

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # ── API key bar ──
        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("Mouser API Key:"))
        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("Paste your Mouser Search API key here")
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setMinimumWidth(350)
        key_row.addWidget(self._key_input)

        self._show_key_btn = QPushButton("Show")
        self._show_key_btn.setCheckable(True)
        self._show_key_btn.toggled.connect(self._toggle_key_visibility)
        key_row.addWidget(self._show_key_btn)

        key_row.addStretch()
        main_layout.addLayout(key_row)

        # ── Manual search bar ──
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Manual search:"))
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Type a keyword or MPN...")
        self._search_input.returnPressed.connect(self._on_manual_search)
        search_row.addWidget(self._search_input)

        self._search_type = QComboBox()
        self._search_type.addItems(["Keyword", "Part Number", "Part Number (Exact)"])
        search_row.addWidget(self._search_type)

        self._options_combo = QComboBox()
        self._options_combo.addItems(["None", "InStock", "Rohs", "RohsAndInStock"])
        self._options_combo.setCurrentText("None")
        search_row.addWidget(QLabel("Options:"))
        search_row.addWidget(self._options_combo)

        self._records_combo = QComboBox()
        self._records_combo.addItems(["5", "10", "20", "50"])
        self._records_combo.setCurrentText("20")
        search_row.addWidget(QLabel("Records:"))
        search_row.addWidget(self._records_combo)

        self._search_btn = QPushButton("Search")
        self._search_btn.clicked.connect(self._on_manual_search)
        search_row.addWidget(self._search_btn)

        main_layout.addLayout(search_row)

        # ── Splitter: BOM (left) | Results + JSON (right) ──
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter, stretch=1)

        # Left: BOM table
        bom_group = QGroupBox("Dummy BOM (double-click to search)")
        bom_layout = QVBoxLayout(bom_group)
        self._bom_table = QTableWidget()
        bom_headers = ["Ref", "Value", "Footprint", "Type", "MPN", "Query"]
        self._bom_table.setColumnCount(len(bom_headers))
        self._bom_table.setHorizontalHeaderLabels(bom_headers)
        self._bom_table.setRowCount(len(DUMMY_BOM))
        self._bom_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._bom_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._bom_table.cellDoubleClicked.connect(self._on_bom_double_click)

        for row, comp in enumerate(DUMMY_BOM):
            query = build_search_query(comp)
            for col, val in enumerate([
                comp["ref"], comp["value"], comp["footprint"],
                comp["type"], comp["mpn"], query,
            ]):
                self._bom_table.setItem(row, col, QTableWidgetItem(val))

        self._bom_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        bom_layout.addWidget(self._bom_table)
        splitter.addWidget(bom_group)

        # Right: Results + JSON
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Results table
        results_group = QGroupBox("Search Results")
        results_layout = QVBoxLayout(results_group)
        self._status_label = QLabel("Ready. Double-click a BOM component or use manual search.")
        results_layout.addWidget(self._status_label)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter by Manufacturer:"))
        self._mfr_filter = QComboBox()
        self._mfr_filter.addItem("All")
        self._mfr_filter.setMinimumWidth(200)
        self._mfr_filter.currentTextChanged.connect(self._apply_manufacturer_filter)
        filter_row.addWidget(self._mfr_filter)
        filter_row.addStretch()
        self._filter_count_label = QLabel("")
        filter_row.addWidget(self._filter_count_label)
        results_layout.addLayout(filter_row)

        self._results_table = QTableWidget()
        self._results_table.setColumnCount(len(RESULT_COLUMNS))
        self._results_table.setHorizontalHeaderLabels([c[0] for c in RESULT_COLUMNS])
        self._results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._results_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self._results_table.cellDoubleClicked.connect(self._on_result_double_click)
        results_layout.addWidget(self._results_table)
        right_layout.addWidget(results_group, stretch=2)

        # JSON inspector
        json_group = QGroupBox("Raw JSON (click a result row to inspect)")
        json_layout = QVBoxLayout(json_group)
        self._json_view = QTextEdit()
        self._json_view.setReadOnly(True)
        self._json_view.setFontFamily("Consolas")
        self._json_view.setFontPointSize(9)
        json_layout.addWidget(self._json_view)
        right_layout.addWidget(json_group, stretch=1)

        splitter.addWidget(right_widget)
        splitter.setSizes([350, 850])

        # Connect result row selection to JSON inspector
        self._results_table.currentCellChanged.connect(self._on_result_selected)

        # Store parsed parts for JSON inspection
        self._parts: list[dict] = []

    def _toggle_key_visibility(self, checked: bool):
        if checked:
            self._key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self._show_key_btn.setText("Hide")
        else:
            self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._show_key_btn.setText("Show")

    def _get_api_key(self) -> str | None:
        key = self._key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "No API Key", "Enter your Mouser API key first.")
            return None
        return key

    def _on_bom_double_click(self, row: int, _col: int):
        key = self._get_api_key()
        if not key:
            return

        comp = DUMMY_BOM[row]

        # If component has an MPN, do a part number search; otherwise keyword search
        if comp["mpn"]:
            query = comp["mpn"]
            search_type = "partnumber"
            self._status_label.setText(
                f"Searching Mouser for MPN: {query} (from {comp['ref']})"
            )
        else:
            query = build_search_query(comp)
            search_type = "keyword"
            self._status_label.setText(
                f"Searching Mouser for: {query} (from {comp['ref']})"
            )

        self._run_search(key, query, search_type)

    def _on_manual_search(self):
        key = self._get_api_key()
        if not key:
            return

        query = self._search_input.text().strip()
        if not query:
            return

        type_map = {
            "Keyword": "keyword",
            "Part Number": "partnumber",
            "Part Number (Exact)": "exact",
        }
        search_type = type_map[self._search_type.currentText()]
        self._status_label.setText(f"Searching ({search_type}): {query}")
        self._run_search(key, query, search_type)

    def _run_search(self, api_key: str, query: str, search_type: str):
        if self._worker and self._worker.isRunning():
            self._status_label.setText("Search already in progress...")
            return

        self._search_btn.setEnabled(False)
        self._results_table.setRowCount(0)
        self._json_view.clear()
        self._parts = []

        self._worker = SearchWorker(
            self._client,
            api_key,
            query,
            search_type=search_type,
            search_options=self._options_combo.currentText(),
            records=int(self._records_combo.currentText()),
        )
        self._worker.results_ready.connect(self._on_results)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(lambda: self._search_btn.setEnabled(True))
        self._worker.start()

    def _on_results(self, data: dict, elapsed: float):
        self._last_raw = data

        errors = data.get("Errors", [])
        if errors:
            msgs = [e.get("Message", str(e)) for e in errors]
            self._status_label.setText(f"API Error: {'; '.join(msgs)}")
            self._json_view.setPlainText(json.dumps(data, indent=2))
            return

        results = data.get("SearchResults", {})
        total = results.get("NumberOfResult", 0)
        parts = results.get("Parts", [])
        self._parts = parts
        self._elapsed = elapsed

        # Populate manufacturer filter dropdown
        manufacturers = sorted({p.get("Manufacturer", "") for p in parts} - {""})
        self._mfr_filter.blockSignals(True)
        self._mfr_filter.clear()
        self._mfr_filter.addItem("All")
        self._mfr_filter.addItems(manufacturers)
        self._mfr_filter.setCurrentText("All")
        self._mfr_filter.blockSignals(False)

        self._status_label.setText(
            f"Found {total} total, showing {len(parts)} — {elapsed:.2f}s"
        )
        self._filter_count_label.setText("")

        self._populate_table(parts)

        # Show full response JSON
        self._json_view.setPlainText(json.dumps(data, indent=2))

    def _apply_manufacturer_filter(self, manufacturer: str):
        """Filter results table by selected manufacturer."""
        if not self._parts:
            return

        if manufacturer == "All":
            filtered = self._parts
        else:
            filtered = [p for p in self._parts if p.get("Manufacturer") == manufacturer]

        self._filter_count_label.setText(
            f"{len(filtered)} of {len(self._parts)} shown"
        )
        self._populate_table(filtered)

    def _populate_table(self, parts: list[dict]):
        """Fill the results table with the given parts list."""
        # Store visible parts for JSON inspector indexing
        self._visible_parts = parts

        self._results_table.setRowCount(len(parts))
        for row, part in enumerate(parts):
            for col, (_, field) in enumerate(RESULT_COLUMNS):
                val = str(part.get(field, ""))
                item = QTableWidgetItem(val)
                # Colour lifecycle/discontinued cells
                if field == "IsDiscontinued" and val.lower() == "true":
                    item.setBackground(Qt.GlobalColor.red)
                    item.setForeground(Qt.GlobalColor.white)
                elif field == "LifecycleStatus" and val:
                    if "obsolete" in val.lower() or "end of life" in val.lower():
                        item.setBackground(Qt.GlobalColor.red)
                        item.setForeground(Qt.GlobalColor.white)
                    elif "not recommended" in val.lower():
                        item.setBackground(Qt.GlobalColor.yellow)
                elif field == "AvailabilityInStock":
                    try:
                        stock = int(val) if val else 0
                        if stock == 0:
                            item.setBackground(Qt.GlobalColor.red)
                            item.setForeground(Qt.GlobalColor.white)
                        elif stock < 100:
                            item.setBackground(Qt.GlobalColor.yellow)
                    except ValueError:
                        pass
                self._results_table.setItem(row, col, item)

        self._results_table.resizeColumnsToContents()

    def _on_error(self, msg: str):
        self._status_label.setText(f"Error: {msg}")
        self._search_btn.setEnabled(True)

    def _on_result_selected(self, row: int, _col: int, _prev_row: int, _prev_col: int):
        """Show the raw JSON of the selected part in the inspector."""
        visible = getattr(self, "_visible_parts", self._parts)
        if 0 <= row < len(visible):
            part = visible[row]
            self._json_view.setPlainText(json.dumps(part, indent=2))

    def _on_result_double_click(self, row: int, col: int):
        """Double-click a result: copy MPN to clipboard, or open datasheet URL."""
        visible = getattr(self, "_visible_parts", self._parts)
        if row < 0 or row >= len(visible):
            return

        part = visible[row]
        field = RESULT_COLUMNS[col][1]

        if field == "DataSheetUrl":
            url = part.get("DataSheetUrl", "")
            if url:
                import webbrowser
                webbrowser.open(url)
                self._status_label.setText(f"Opened datasheet: {url}")
            else:
                self._status_label.setText("No datasheet URL for this part")
        elif field == "ManufacturerPartNumber":
            mpn = part.get("ManufacturerPartNumber", "")
            if mpn:
                QApplication.clipboard().setText(mpn)
                self._status_label.setText(f"Copied MPN to clipboard: {mpn}")
        else:
            val = str(part.get(field, ""))
            if val:
                QApplication.clipboard().setText(val)
                self._status_label.setText(f"Copied to clipboard: {val}")

    def closeEvent(self, event):
        self._client.close()
        super().closeEvent(event)


# ── Entry point ─────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MouserBreadboard()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
