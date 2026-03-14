"""Assign Part dialog — preview and confirm write-back to KiCad."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from kipart_search.core.models import PartResult
from kipart_search.gui.kicad_bridge import BoardComponent


# Field mapping: (display name, source attribute on PartResult, KiCad field name)
ASSIGNABLE_FIELDS = [
    ("MPN", "mpn", "MPN"),
    ("Manufacturer", "manufacturer", "Manufacturer"),
    ("Datasheet", "datasheet_url", "Datasheet"),
    ("Description", "description", "Description"),
]


class AssignDialog(QDialog):
    """Preview dialog for writing part data back to a KiCad component.

    Shows a table of fields with current (KiCad) vs new (search result) values.
    Only empty fields are checked for writing. Non-empty fields show a warning
    and are unchecked by default.
    """

    def __init__(
        self,
        component: BoardComponent,
        part: PartResult,
        parent=None,
    ):
        super().__init__(parent)
        self.component = component
        self.part = part
        self._write_fields: dict[str, str] = {}

        self.setWindowTitle(f"Assign Part to {component.reference}")
        self.setMinimumWidth(550)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Header
        header = QLabel(
            f"<b>Component:</b> {component.reference} ({component.value})<br>"
            f"<b>Part:</b> {part.mpn} — {part.manufacturer}"
        )
        layout.addWidget(header)

        # Field preview table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Field", "Current Value", "New Value", "Action"]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        layout.addWidget(self.table)

        self._populate_table()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.assign_btn = QPushButton("Assign")
        self.assign_btn.setDefault(True)
        self.assign_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.assign_btn)

        layout.addLayout(btn_layout)

        # Disable assign if nothing to write
        if not self._write_fields:
            self.assign_btn.setEnabled(False)
            self.assign_btn.setToolTip("No empty fields to write")

    def _populate_table(self):
        """Build the preview table comparing current vs new values."""
        rows = []
        for display_name, part_attr, kicad_field in ASSIGNABLE_FIELDS:
            new_value = getattr(self.part, part_attr, "") or ""
            if not new_value:
                continue  # Nothing to assign for this field

            # Get current value from component
            current_value = self._get_current_value(kicad_field)
            is_empty = not current_value.strip()

            if is_empty:
                action = "Will write"
                self._write_fields[kicad_field] = new_value
            else:
                action = "Skip (not empty)"

            rows.append((display_name, current_value, new_value, action, is_empty))

        self.table.setRowCount(len(rows))
        for row, (name, current, new, action, is_empty) in enumerate(rows):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(current or "(empty)"))
            self.table.setItem(row, 2, QTableWidgetItem(new))

            action_item = QTableWidgetItem(action)
            if is_empty:
                action_item.setBackground(QColor(200, 255, 200))  # Green
            else:
                action_item.setBackground(QColor(255, 235, 180))  # Amber
            self.table.setItem(row, 3, action_item)

        self.table.resizeColumnsToContents()

    def _get_current_value(self, field_name: str) -> str:
        """Look up the current value of a field on the component."""
        lower = field_name.lower()
        if lower == "mpn":
            return self.component.mpn
        if lower == "datasheet":
            return self.component.datasheet
        # Check extra_fields
        for k, v in self.component.extra_fields.items():
            if k.lower() == lower:
                return v
        return ""

    @property
    def fields_to_write(self) -> dict[str, str]:
        """Return dict of {kicad_field_name: value} to write."""
        return dict(self._write_fields)
