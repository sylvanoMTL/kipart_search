"""Assign Part dialog — preview and confirm write-back to KiCad."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
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

from kipart_search.core.models import (
    BoardComponent,
    PartResult,
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
    Only empty fields are checked for writing. Non-empty fields show an
    opt-in overwrite checkbox (unchecked by default).

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
        self._overwrite_fields: set[str] = set()
        self._manual_mode = part is None
        self._manual_edits: dict[str, QLineEdit] = {}
        self._overwrite_checkboxes: dict[str, QCheckBox] = {}
        self._has_mismatches = False

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
        self._mismatch_ack_checkbox: QCheckBox | None = None
        if part is not None:
            warnings = _check_mismatches(component, part)
            if warnings:
                self._has_mismatches = True
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

                # Mismatch acknowledgment checkbox (Task 2)
                self._mismatch_ack_checkbox = QCheckBox(
                    "I understand and want to proceed"
                )
                self._mismatch_ack_checkbox.setStyleSheet(
                    "margin: 4px 0; font-weight: bold;"
                )
                self._mismatch_ack_checkbox.toggled.connect(
                    self._update_assign_button
                )
                layout.addWidget(self._mismatch_ack_checkbox)

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
        self.cancel_btn.setDefault(True)  # Default is Cancel for safety
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.assign_btn = QPushButton("Assign")
        self.assign_btn.setDefault(False)
        self.assign_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.assign_btn)

        layout.addLayout(btn_layout)

        self._update_assign_button()

    def _populate_table(self):
        """Build the preview table comparing current vs new values."""
        self._manual_edits.clear()
        self._write_fields.clear()
        self._overwrite_fields.clear()
        self._overwrite_checkboxes.clear()

        if self._manual_mode:
            self._populate_manual_table()
        else:
            self._populate_part_table()

    def _populate_part_table(self):
        """Populate table from a PartResult (read-only new values)."""
        rows: list[tuple[str, str, str, str, bool]] = []
        row_kicad_fields: list[str] = []
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
                action = f"Current: {current_value}"

            rows.append((display_name, current_value, new_value, action, is_empty))
            row_kicad_fields.append(kicad_field)

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

            if is_empty:
                action_item = QTableWidgetItem(action)
                action_item.setBackground(QColor(200, 255, 200))  # Green
                self.table.setItem(row, 3, action_item)
            else:
                # Non-empty: overwrite checkbox (opt-in, unchecked by default)
                kicad_field = row_kicad_fields[row]
                cb = QCheckBox("Overwrite")
                cb.setChecked(False)
                cb.toggled.connect(
                    lambda checked, kf=kicad_field, nv=new: self._on_overwrite_toggled(
                        kf, nv, checked
                    )
                )
                self._overwrite_checkboxes[kicad_field] = cb
                self.table.setCellWidget(row, 3, cb)
                # Set amber background on the row
                for col in range(3):
                    item = self.table.item(row, col)
                    if item:
                        item.setBackground(QColor(255, 235, 180))

        self.table.resizeColumnsToContents()

        # Make Current Value and New Value columns equal width (use the larger of the two)
        w1 = self.table.columnWidth(1)
        w2 = self.table.columnWidth(2)
        equal_width = max(w1, w2)
        self.table.setColumnWidth(1, equal_width)
        self.table.setColumnWidth(2, equal_width)

    def _on_overwrite_toggled(self, kicad_field: str, new_value: str, checked: bool):
        """Handle overwrite checkbox toggle in part-result mode."""
        if checked:
            self._write_fields[kicad_field] = new_value
            self._overwrite_fields.add(kicad_field)
        else:
            self._write_fields.pop(kicad_field, None)
            self._overwrite_fields.discard(kicad_field)
        self._update_assign_button()

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
            if is_empty:
                edit.setPlaceholderText(f"Enter {display_name}...")
                edit.setEnabled(True)
            else:
                edit.setText(current_value)
                edit.setEnabled(False)  # Disabled until overwrite checked
            edit.textChanged.connect(self._on_manual_field_changed)
            self._manual_edits[kicad_field] = edit
            self.table.setCellWidget(row, 2, edit)

            # Action column
            if is_empty:
                action_item = QTableWidgetItem("Will write")
                action_item.setBackground(QColor(200, 255, 200))
                self.table.setItem(row, 3, action_item)
            else:
                # Overwrite checkbox for non-empty fields
                cb = QCheckBox("Overwrite")
                cb.setChecked(False)
                cb.toggled.connect(
                    lambda checked, kf=kicad_field: self._on_manual_overwrite_toggled(
                        kf, checked
                    )
                )
                self._overwrite_checkboxes[kicad_field] = cb
                self.table.setCellWidget(row, 3, cb)
                # Amber background for non-empty field info cells
                for col in range(2):
                    item = self.table.item(row, col)
                    if item:
                        item.setBackground(QColor(255, 235, 180))

        self.table.resizeColumnsToContents()
        # Give the editable column more space
        self.table.setColumnWidth(2, 200)

    def _on_manual_overwrite_toggled(self, kicad_field: str, checked: bool):
        """Handle overwrite checkbox toggle in manual mode."""
        edit = self._manual_edits.get(kicad_field)
        if edit is None:
            return

        if checked:
            edit.setEnabled(True)
            self._overwrite_fields.add(kicad_field)
        else:
            edit.setEnabled(False)
            self._overwrite_fields.discard(kicad_field)
            # Remove from write fields when unchecked
            self._write_fields.pop(kicad_field, None)

        # Trigger re-evaluation of write fields
        self._on_manual_field_changed()

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

            if is_empty and text:
                self._write_fields[kicad_field] = text
            elif not is_empty and kicad_field in self._overwrite_fields and text:
                self._write_fields[kicad_field] = text

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
        # Mismatch gate: if mismatches exist and not acknowledged, disable
        if self._has_mismatches and self._mismatch_ack_checkbox is not None:
            if not self._mismatch_ack_checkbox.isChecked():
                self.assign_btn.setEnabled(False)
                self.assign_btn.setToolTip(
                    "Acknowledge mismatch warnings to enable assignment"
                )
                return

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

    @property
    def overwrite_fields(self) -> set[str]:
        """Return set of field names that are overwrites of non-empty fields."""
        return set(self._overwrite_fields)
