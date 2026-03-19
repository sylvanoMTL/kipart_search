"""Assign Part dialog — preview and confirm write-back to KiCad."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from kipart_search.core.models import PartResult
from kipart_search.core.models import (
    BoardComponent,
    extract_package_from_footprint as _extract_package_from_footprint,
    extract_ref_prefix,
)

# Field mapping: (display name, source attribute on PartResult, KiCad field name)
ASSIGNABLE_FIELDS = [
    ("MPN", "mpn", "MPN"),
    ("Manufacturer", "manufacturer", "Manufacturer"),
    ("Datasheet", "datasheet_url", "Datasheet"),
    ("Description", "description", "Description"),
]

# Reference prefix → (human-readable type name, keywords expected in part category/description)
_REF_CATEGORY_HINTS: dict[str, tuple[str, list[str]]] = {
    "C": ("Capacitor", ["capacitor", "cap", "mlcc", "ceramic", "electrolytic", "tantalum"]),
    "R": ("Resistor", ["resistor", "res", "thermistor", "varistor", "potentiometer"]),
    "L": ("Inductor", ["inductor", "coil", "choke", "ferrite"]),
    "D": ("Diode", ["diode", "led", "zener", "schottky", "tvs", "rectifier"]),
    "Q": ("Transistor", ["transistor", "mosfet", "bjt", "jfet", "igbt"]),
    "U": ("IC", ["ic", "mcu", "microcontroller", "regulator", "amplifier",
                  "interface", "driver", "converter", "controller", "processor",
                  "memory", "eeprom", "flash", "sensor", "adc", "dac", "op-amp"]),
    "J": ("Connector", ["connector", "header", "socket", "plug", "jack", "terminal"]),
    "SW": ("Switch", ["switch", "button", "key"]),
    "Y": ("Crystal", ["crystal", "oscillator", "resonator"]),
    "F": ("Fuse", ["fuse", "ptc", "polyfuse"]),
    "K": ("Relay", ["relay"]),
    "T": ("Transformer", ["transformer"]),
    "BT": ("Battery", ["battery", "holder"]),
}


def _check_mismatches(
    component: BoardComponent, part: PartResult
) -> list[str]:
    """Return a list of mismatch warnings between the component and part."""
    warnings: list[str] = []

    ref_prefix = extract_ref_prefix(component.reference)
    haystack = f"{part.category} {part.description}".lower()

    # Check 1: does the part match what this component type expects?
    hint_entry = _REF_CATEGORY_HINTS.get(ref_prefix)
    if hint_entry:
        type_name, hints = hint_entry
        if not any(h in haystack for h in hints):
            warnings.append(
                f"COMPONENT TYPE MISMATCH: {component.reference} is a "
                f"{type_name} ({ref_prefix}), but the selected part's "
                f"category is \"{part.category}\". "
                f"Are you sure this is the right part?"
            )

    # Check 2: does the part look like a DIFFERENT component type?
    for prefix, (type_name, hints) in _REF_CATEGORY_HINTS.items():
        if prefix == ref_prefix:
            continue
        if any(h in haystack for h in hints):
            # The part matches a different component type
            if hint_entry is None:
                # Component type is unknown — warn about the part type
                warnings.append(
                    f"PART TYPE WARNING: the selected part appears to be a "
                    f"{type_name}, but component {component.reference} "
                    f"has reference prefix \"{ref_prefix}\" which is not "
                    f"a standard {type_name} designator."
                )
            break  # Only report the first match

    # Check package/footprint
    comp_package = _extract_package_from_footprint(component.footprint)
    if comp_package and part.package:
        comp_pkg_norm = comp_package.upper()
        part_pkg_norm = part.package.upper()
        if comp_pkg_norm not in part_pkg_norm and part_pkg_norm not in comp_pkg_norm:
            warnings.append(
                f"PACKAGE MISMATCH: component footprint is {comp_package}, "
                f"but part package is {part.package}."
            )

    return warnings


class AssignDialog(QDialog):
    """Preview dialog for writing part data back to a KiCad component.

    Shows a table of fields with current (KiCad) vs new (search result) values.
    Only empty fields are checked for writing. Non-empty fields show a warning
    and are unchecked by default.

    When ``part`` is None, opens in manual entry mode with editable fields.
    """

    def __init__(
        self,
        component: BoardComponent,
        part: PartResult | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.component = component
        self.part = part
        self._write_fields: dict[str, str] = {}
        self._manual_mode = part is None
        self._manual_edits: dict[str, QLineEdit] = {}

        self.setWindowTitle(f"Assign Part to {component.reference}")
        self.setMinimumSize(550, 400)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Header
        if part is not None:
            header_text = (
                f"<b>Component:</b> {component.reference} ({component.value})<br>"
                f"<b>Part:</b> {part.mpn} — {part.manufacturer}"
            )
        else:
            header_text = (
                f"<b>Component:</b> {component.reference} ({component.value})<br>"
                f"<b>Mode:</b> Manual Entry"
            )
        header = QLabel(header_text)
        layout.addWidget(header)

        # Mismatch warnings (only when a PartResult is provided)
        if part is not None:
            warnings = _check_mismatches(component, part)
            if warnings:
                warning_html = "<br><br>".join(
                    f"\u26a0 <b>{w}</b>" for w in warnings
                )
                warning_label = QLabel(warning_html)
                warning_label.setWordWrap(True)
                warning_label.setTextFormat(Qt.TextFormat.RichText)
                warning_label.setStyleSheet(
                    "background-color: #fff3cd; color: #e65100; "
                    "border: 2px solid #ff9800; border-radius: 6px; "
                    "padding: 10px; margin: 6px 0; font-size: 13px;"
                )
                layout.addWidget(warning_label)

        # Field preview table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Field", "Current Value", "New Value", "Action"]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setStretchLastSection(False)
        # Give Current/New columns equal initial width
        header_view.setDefaultSectionSize(180)
        layout.addWidget(self.table)

        self._populate_table()

        # Buttons
        btn_layout = QHBoxLayout()

        # Manual Entry toggle (only when a PartResult is provided)
        if part is not None:
            self._manual_toggle = QPushButton("Manual Entry")
            self._manual_toggle.setToolTip("Switch to manual entry mode")
            self._manual_toggle.clicked.connect(self._toggle_manual_mode)
            btn_layout.addWidget(self._manual_toggle)

        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.assign_btn = QPushButton("Assign")
        self.assign_btn.setDefault(True)
        self.assign_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.assign_btn)

        layout.addLayout(btn_layout)

        self._update_assign_button()

    def _populate_table(self):
        """Build the preview table comparing current vs new values."""
        self._manual_edits.clear()
        self._write_fields.clear()

        if self._manual_mode:
            self._populate_manual_table()
        else:
            self._populate_part_table()

    def _populate_part_table(self):
        """Populate table from a PartResult (read-only new values)."""
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
            name_item = QTableWidgetItem(name)
            name_item.setToolTip(name)
            self.table.setItem(row, 0, name_item)

            current_display = current or "(empty)"
            current_item = QTableWidgetItem(current_display)
            current_item.setToolTip(current_display)
            self.table.setItem(row, 1, current_item)

            new_item = QTableWidgetItem(new)
            new_item.setToolTip(new)
            self.table.setItem(row, 2, new_item)

            action_item = QTableWidgetItem(action)
            if is_empty:
                action_item.setBackground(QColor(200, 255, 200))  # Green
            else:
                action_item.setBackground(QColor(255, 235, 180))  # Amber
            self.table.setItem(row, 3, action_item)

        self.table.resizeColumnsToContents()

        # Make Current Value and New Value columns equal width (use the larger of the two)
        w1 = self.table.columnWidth(1)
        w2 = self.table.columnWidth(2)
        equal_width = max(w1, w2)
        self.table.setColumnWidth(1, equal_width)
        self.table.setColumnWidth(2, equal_width)

    def _populate_manual_table(self):
        """Populate table with editable QLineEdit widgets for manual entry."""
        self.table.setRowCount(len(ASSIGNABLE_FIELDS))

        for row, (display_name, _part_attr, kicad_field) in enumerate(ASSIGNABLE_FIELDS):
            current_value = self._get_current_value(kicad_field)
            is_empty = not current_value.strip()

            # Field name
            name_item = QTableWidgetItem(display_name)
            name_item.setToolTip(display_name)
            self.table.setItem(row, 0, name_item)

            # Current value
            current_display = current_value or "(empty)"
            current_item = QTableWidgetItem(current_display)
            current_item.setToolTip(current_display)
            self.table.setItem(row, 1, current_item)

            # Editable new value (QLineEdit)
            edit = QLineEdit()
            edit.setPlaceholderText(f"Enter {display_name}...")
            edit.textChanged.connect(self._on_manual_field_changed)
            self._manual_edits[kicad_field] = edit
            self.table.setCellWidget(row, 2, edit)

            # Action column — will update dynamically
            if is_empty:
                action_item = QTableWidgetItem("Will write")
                action_item.setBackground(QColor(200, 255, 200))
            else:
                action_item = QTableWidgetItem("Skip (not empty)")
                action_item.setBackground(QColor(255, 235, 180))
            self.table.setItem(row, 3, action_item)

        self.table.resizeColumnsToContents()
        # Give the editable column more space
        self.table.setColumnWidth(2, 200)

    def _on_manual_field_changed(self):
        """Update _write_fields and action column when manual entry text changes."""
        self._write_fields.clear()

        for row, (_display_name, _part_attr, kicad_field) in enumerate(ASSIGNABLE_FIELDS):
            edit = self._manual_edits.get(kicad_field)
            if edit is None:
                continue
            text = edit.text().strip()
            current_value = self._get_current_value(kicad_field)
            is_empty = not current_value.strip()

            action_item = self.table.item(row, 3)
            if not action_item:
                continue

            if is_empty and text:
                self._write_fields[kicad_field] = text
                action_item.setText("Will write")
                action_item.setBackground(QColor(200, 255, 200))
            elif not is_empty:
                action_item.setText("Skip (not empty)")
                action_item.setBackground(QColor(255, 235, 180))
            else:
                action_item.setText("")
                action_item.setBackground(QColor(255, 255, 255))

        self._update_assign_button()

    def _toggle_manual_mode(self):
        """Toggle between search-result and manual-entry mode."""
        self._manual_mode = not self._manual_mode

        if hasattr(self, "_manual_toggle"):
            if self._manual_mode:
                self._manual_toggle.setText("Use Search Result")
                self._manual_toggle.setToolTip("Switch back to search result values")
            else:
                self._manual_toggle.setText("Manual Entry")
                self._manual_toggle.setToolTip("Switch to manual entry mode")

        self._populate_table()
        self._update_assign_button()

    def _update_assign_button(self):
        """Enable/disable the Assign button based on current state."""
        if self._manual_mode:
            # In manual mode, MPN must be non-empty
            mpn_edit = self._manual_edits.get("MPN")
            has_mpn = bool(mpn_edit and mpn_edit.text().strip())
            self.assign_btn.setEnabled(has_mpn)
            if not has_mpn:
                self.assign_btn.setToolTip("Enter an MPN to enable assignment")
            else:
                self.assign_btn.setToolTip("")
        else:
            # In part-result mode, enable if there are fields to write
            has_fields = bool(self._write_fields)
            self.assign_btn.setEnabled(has_fields)
            if not has_fields:
                self.assign_btn.setToolTip("No empty fields to write")
            else:
                self.assign_btn.setToolTip("")

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
