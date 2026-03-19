"""Tests for AssignDialog — search-result and manual-entry modes (Story 5.3)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

PySide6 = pytest.importorskip("PySide6", reason="PySide6 required for GUI tests")

from PySide6.QtWidgets import QApplication

# Ensure a QApplication exists before any widget tests
app = QApplication.instance() or QApplication(sys.argv)

from kipart_search.core.models import BoardComponent, Confidence, PartResult
from kipart_search.gui.assign_dialog import AssignDialog, _check_mismatches


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_component(
    reference: str = "C1",
    value: str = "100nF",
    footprint: str = "Capacitor_SMD:C_0805_2012Metric",
    mpn: str = "",
    datasheet: str = "",
    extra_fields: dict[str, str] | None = None,
) -> BoardComponent:
    return BoardComponent(
        reference=reference,
        value=value,
        footprint=footprint,
        mpn=mpn,
        datasheet=datasheet,
        extra_fields=extra_fields or {},
    )


def _make_part(
    mpn: str = "GRM188R71C104KA01D",
    manufacturer: str = "Murata",
    description: str = "100nF 50V X7R 0805 MLCC Capacitor",
    package: str = "0805",
    category: str = "Capacitors",
    datasheet_url: str = "https://example.com/ds.pdf",
) -> PartResult:
    return PartResult(
        mpn=mpn,
        manufacturer=manufacturer,
        description=description,
        package=package,
        category=category,
        datasheet_url=datasheet_url,
    )


# ---------------------------------------------------------------------------
# Task 5.1: Test AssignDialog with PartResult — fields_to_write populated
# ---------------------------------------------------------------------------

class TestAssignDialogWithPartResult:
    """Test AssignDialog in search-result mode (existing behavior)."""

    def test_fields_to_write_populated(self):
        """fields_to_write contains all empty fields from the component."""
        comp = _make_component()
        part = _make_part()

        dialog = AssignDialog(comp, part)
        fields = dialog.fields_to_write

        assert "MPN" in fields
        assert fields["MPN"] == "GRM188R71C104KA01D"
        assert "Manufacturer" in fields
        assert fields["Manufacturer"] == "Murata"
        assert "Datasheet" in fields
        assert "Description" in fields

    def test_nonempty_fields_skipped(self):
        """Fields that already have values are not in fields_to_write."""
        comp = _make_component(mpn="EXISTING_MPN")
        part = _make_part()

        dialog = AssignDialog(comp, part)
        fields = dialog.fields_to_write

        assert "MPN" not in fields
        # Other empty fields should still be present
        assert "Manufacturer" in fields

    def test_assign_button_enabled_when_fields_to_write(self):
        """Assign button enabled when there are writable fields."""
        comp = _make_component()
        part = _make_part()

        dialog = AssignDialog(comp, part)

        assert dialog.assign_btn.isEnabled()

    def test_assign_button_disabled_when_no_writable_fields(self):
        """Assign button disabled when all fields are already populated."""
        comp = _make_component(
            mpn="ABC",
            datasheet="https://existing.com",
            extra_fields={"Manufacturer": "Murata", "Description": "Cap"},
        )
        part = _make_part()

        dialog = AssignDialog(comp, part)

        assert not dialog.assign_btn.isEnabled()

    def test_part_attribute_required(self):
        """AssignDialog with part=None starts in manual mode."""
        comp = _make_component()
        dialog = AssignDialog(comp, part=None)
        assert dialog._manual_mode is True


# ---------------------------------------------------------------------------
# Task 5.2: Test AssignDialog in manual mode
# ---------------------------------------------------------------------------

class TestAssignDialogManualMode:
    """Test AssignDialog in manual entry mode."""

    def test_manual_mode_starts_with_empty_fields(self):
        """Manual mode starts with no fields_to_write."""
        comp = _make_component()
        dialog = AssignDialog(comp, part=None)

        assert dialog.fields_to_write == {}

    def test_manual_mode_editable_fields_present(self):
        """Manual mode has QLineEdit widgets for all fields."""
        comp = _make_component()
        dialog = AssignDialog(comp, part=None)

        assert "MPN" in dialog._manual_edits
        assert "Manufacturer" in dialog._manual_edits
        assert "Datasheet" in dialog._manual_edits
        assert "Description" in dialog._manual_edits

    def test_manual_mode_typing_updates_fields_to_write(self):
        """Typing in manual fields updates fields_to_write."""
        comp = _make_component()
        dialog = AssignDialog(comp, part=None)

        dialog._manual_edits["MPN"].setText("TEST-MPN-123")
        dialog._manual_edits["Manufacturer"].setText("TestCorp")

        fields = dialog.fields_to_write
        assert fields["MPN"] == "TEST-MPN-123"
        assert fields["Manufacturer"] == "TestCorp"

    def test_manual_mode_nonempty_current_fields_skipped(self):
        """Manual mode skips fields that already have values in component."""
        comp = _make_component(mpn="EXISTING")
        dialog = AssignDialog(comp, part=None)

        # Even if user types in the MPN edit, it should be skipped
        dialog._manual_edits["MPN"].setText("NEW-MPN")

        fields = dialog.fields_to_write
        assert "MPN" not in fields  # Current value is not empty → skipped

    def test_manual_mode_live_preview_update(self):
        """Action column updates as user types."""
        comp = _make_component()
        dialog = AssignDialog(comp, part=None)

        # Initially no action text for MPN row
        dialog._manual_edits["MPN"].setText("ABC")

        # Check action column for MPN row (row 0)
        action_item = dialog.table.item(0, 3)
        assert action_item.text() == "Will write"


# ---------------------------------------------------------------------------
# Task 5.3: Test AssignDialog manual mode with empty MPN — Assign disabled
# ---------------------------------------------------------------------------

class TestAssignDialogManualModeValidation:
    """Test Assign button enable/disable in manual mode."""

    def test_assign_disabled_when_mpn_empty(self):
        """Assign button disabled when MPN field is empty in manual mode."""
        comp = _make_component()
        dialog = AssignDialog(comp, part=None)

        assert not dialog.assign_btn.isEnabled()

    def test_assign_enabled_when_mpn_entered(self):
        """Assign button enabled when MPN is typed in manual mode."""
        comp = _make_component()
        dialog = AssignDialog(comp, part=None)

        dialog._manual_edits["MPN"].setText("TEST-123")

        assert dialog.assign_btn.isEnabled()

    def test_assign_disabled_when_mpn_cleared(self):
        """Assign button disabled again when MPN is cleared."""
        comp = _make_component()
        dialog = AssignDialog(comp, part=None)

        dialog._manual_edits["MPN"].setText("TEST-123")
        assert dialog.assign_btn.isEnabled()

        dialog._manual_edits["MPN"].setText("")
        assert not dialog.assign_btn.isEnabled()

    def test_assign_disabled_when_only_whitespace(self):
        """Assign button disabled when MPN is only whitespace."""
        comp = _make_component()
        dialog = AssignDialog(comp, part=None)

        dialog._manual_edits["MPN"].setText("   ")

        assert not dialog.assign_btn.isEnabled()


# ---------------------------------------------------------------------------
# Task 5.4: Test standalone assignment — BoardComponent updated in-memory
# ---------------------------------------------------------------------------

class TestStandaloneAssignment:
    """Test assignment when KiCad is not connected (standalone mode)."""

    def test_apply_assignment_updates_component_in_memory(self):
        """In standalone mode, fields are written to BoardComponent in-memory."""
        from kipart_search.gui.kicad_bridge import KiCadBridge
        from kipart_search.gui.main_window import MainWindow

        comp = _make_component(reference="C1")
        fields = {"MPN": "TEST-123", "Manufacturer": "TestCorp"}

        window = MainWindow.__new__(MainWindow)
        window._bridge = MagicMock(spec=KiCadBridge)
        window._bridge.is_connected = False
        window._assign_target = comp
        window.verify_panel = MagicMock()
        window.log_panel = MagicMock()
        window._search_target_label = MagicMock()
        window.detail_panel = MagicMock()
        window.results_table = MagicMock()

        window._apply_assignment(fields)

        assert comp.mpn == "TEST-123"
        assert comp.extra_fields["manufacturer"] == "TestCorp"
        window.verify_panel.update_component_status.assert_called_once_with(
            "C1", Confidence.GREEN
        )

    def test_apply_assignment_no_bridge_write_when_disconnected(self):
        """In standalone mode, bridge.write_field is NOT called."""
        from kipart_search.gui.kicad_bridge import KiCadBridge
        from kipart_search.gui.main_window import MainWindow

        comp = _make_component(reference="R1")

        window = MainWindow.__new__(MainWindow)
        window._bridge = MagicMock(spec=KiCadBridge)
        window._bridge.is_connected = False
        window._assign_target = comp
        window.verify_panel = MagicMock()
        window.log_panel = MagicMock()
        window._search_target_label = MagicMock()
        window.detail_panel = MagicMock()
        window.results_table = MagicMock()

        window._apply_assignment({"MPN": "ABC"})

        window._bridge.write_field.assert_not_called()


# ---------------------------------------------------------------------------
# Task 5.5: Test connected assignment — write_field called, panel goes GREEN
# ---------------------------------------------------------------------------

class TestConnectedAssignment:
    """Test assignment when KiCad is connected."""

    def test_apply_assignment_calls_write_field(self):
        """In connected mode, bridge.write_field is called for each field."""
        from kipart_search.gui.kicad_bridge import KiCadBridge
        from kipart_search.gui.main_window import MainWindow

        comp = _make_component(reference="C1")
        fields = {"MPN": "ABC123", "Manufacturer": "Murata"}

        window = MainWindow.__new__(MainWindow)
        window._bridge = MagicMock(spec=KiCadBridge)
        window._bridge.is_connected = True
        window._bridge.write_field.return_value = True
        window._assign_target = comp
        window.verify_panel = MagicMock()
        window.log_panel = MagicMock()
        window._search_target_label = MagicMock()
        window.detail_panel = MagicMock()
        window.results_table = MagicMock()

        window._apply_assignment(fields)

        assert window._bridge.write_field.call_count == 2
        window._bridge.write_field.assert_any_call("C1", "MPN", "ABC123")
        window._bridge.write_field.assert_any_call("C1", "Manufacturer", "Murata")
        window.verify_panel.update_component_status.assert_called_once_with(
            "C1", Confidence.GREEN
        )

    def test_apply_assignment_updates_component_in_memory_connected(self):
        """Connected mode also updates component in-memory."""
        from kipart_search.gui.kicad_bridge import KiCadBridge
        from kipart_search.gui.main_window import MainWindow

        comp = _make_component(reference="U1")

        window = MainWindow.__new__(MainWindow)
        window._bridge = MagicMock(spec=KiCadBridge)
        window._bridge.is_connected = True
        window._bridge.write_field.return_value = True
        window._assign_target = comp
        window.verify_panel = MagicMock()
        window.log_panel = MagicMock()
        window._search_target_label = MagicMock()
        window.detail_panel = MagicMock()
        window.results_table = MagicMock()

        window._apply_assignment({"MPN": "STM32F405RGT6"})

        assert comp.mpn == "STM32F405RGT6"

    def test_apply_assignment_clears_assign_target(self):
        """After assignment, assign target is cleared."""
        from kipart_search.gui.kicad_bridge import KiCadBridge
        from kipart_search.gui.main_window import MainWindow

        comp = _make_component()

        window = MainWindow.__new__(MainWindow)
        window._bridge = MagicMock(spec=KiCadBridge)
        window._bridge.is_connected = False
        window._assign_target = comp
        window.verify_panel = MagicMock()
        window.log_panel = MagicMock()
        window._search_target_label = MagicMock()
        window.detail_panel = MagicMock()
        window.results_table = MagicMock()

        window._apply_assignment({"MPN": "X"})

        assert window._assign_target is None


# ---------------------------------------------------------------------------
# Task 5.6: Test mismatch warnings still display in both modes
# ---------------------------------------------------------------------------

class TestMismatchWarnings:
    """Test mismatch warnings work correctly."""

    def test_mismatch_warning_with_part_result(self):
        """Mismatch warnings are generated when part category doesn't match."""
        comp = _make_component(reference="C1")  # Capacitor
        part = _make_part(
            category="Resistors",
            description="10k 0805 Resistor",
        )

        warnings = _check_mismatches(comp, part)

        assert len(warnings) >= 1
        assert any("COMPONENT TYPE MISMATCH" in w for w in warnings)

    def test_no_mismatch_when_part_matches(self):
        """No warnings when part category matches component type."""
        comp = _make_component(reference="C1")
        part = _make_part(category="Capacitors", description="100nF Capacitor")

        warnings = _check_mismatches(comp, part)

        assert not any("COMPONENT TYPE MISMATCH" in w for w in warnings)

    def test_package_mismatch_warning(self):
        """Package mismatch generates a warning."""
        comp = _make_component(
            footprint="Capacitor_SMD:C_0805_2012Metric"
        )
        part = _make_part(package="0402")

        warnings = _check_mismatches(comp, part)

        assert any("PACKAGE MISMATCH" in w for w in warnings)

    def test_manual_mode_no_mismatch_check(self):
        """Manual mode (part=None) does not crash — no mismatch warnings shown."""
        comp = _make_component()
        dialog = AssignDialog(comp, part=None)

        # Dialog should open without error in manual mode
        assert dialog._manual_mode is True
        # No mismatch warnings since there's no part to compare


# ---------------------------------------------------------------------------
# Test toggle between modes
# ---------------------------------------------------------------------------

class TestModeToggle:
    """Test switching between search-result and manual-entry modes."""

    def test_toggle_to_manual_mode(self):
        """Toggling to manual mode switches the table to editable."""
        comp = _make_component()
        part = _make_part()

        dialog = AssignDialog(comp, part)
        assert dialog._manual_mode is False

        dialog._toggle_manual_mode()
        assert dialog._manual_mode is True
        assert "MPN" in dialog._manual_edits

    def test_toggle_back_to_part_mode(self):
        """Toggling back restores read-only part values."""
        comp = _make_component()
        part = _make_part()

        dialog = AssignDialog(comp, part)
        dialog._toggle_manual_mode()  # → manual
        dialog._toggle_manual_mode()  # → back to part

        assert dialog._manual_mode is False
        fields = dialog.fields_to_write
        assert "MPN" in fields
        assert fields["MPN"] == part.mpn

    def test_no_toggle_button_in_manual_only_mode(self):
        """No toggle button when opened without a PartResult."""
        comp = _make_component()
        dialog = AssignDialog(comp, part=None)

        assert not hasattr(dialog, "_manual_toggle")


# ---------------------------------------------------------------------------
# Test manual assign signal from verify panel
# ---------------------------------------------------------------------------

class TestVerifyPanelManualAssign:
    """Test manual_assign_requested signal from VerifyPanel."""

    def test_manual_assign_signal_exists(self):
        """VerifyPanel has manual_assign_requested signal."""
        from kipart_search.gui.verify_panel import VerifyPanel

        panel = VerifyPanel()
        emitted = []
        panel.manual_assign_requested.connect(emitted.append)

        panel.manual_assign_requested.emit("C1")

        assert emitted == ["C1"]

    def test_context_menu_has_manual_assign(self):
        """Context menu includes Manual Assign action."""
        from kipart_search.gui.verify_panel import VerifyPanel

        panel = VerifyPanel()
        comp = BoardComponent(
            reference="C1", value="100nF", footprint="C_0805", mpn=""
        )
        panel.set_results([comp], {"C1": Confidence.RED})

        menu = panel._build_context_menu(0)
        assert menu is not None

        action_texts = [a.text() for a in menu.actions()]
        assert "Manual Assign" in action_texts
