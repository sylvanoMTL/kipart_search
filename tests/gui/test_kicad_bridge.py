"""Tests for KiCad IPC API bridge (Story 5.1)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

PySide6 = pytest.importorskip("PySide6", reason="PySide6 required for GUI tests")

from PySide6.QtWidgets import QApplication

# Ensure a QApplication exists before any widget/thread tests
app = QApplication.instance() or QApplication(sys.argv)

from kipart_search.core.models import BoardComponent, MPN_FIELD_NAMES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_footprint(
    reference: str = "C1",
    value: str = "100nF",
    footprint_id: str = "Capacitor_SMD:C_0805_2012Metric",
    datasheet: str = "",
    custom_fields: dict[str, str] | None = None,
) -> MagicMock:
    """Create a mock kipy FootprintInstance with realistic field structure."""
    fp = MagicMock()
    fp.reference_field.text.value = reference
    fp.value_field.text.value = value

    defn = MagicMock()
    defn.id = footprint_id
    fp.definition = defn

    fp.datasheet_field.text.value = datasheet

    # Build texts_and_fields iterable from custom_fields dict
    items = []
    if custom_fields:
        for fname, fval in custom_fields.items():
            item = MagicMock()
            item.name = fname
            item.text.value = fval
            items.append(item)
    fp.texts_and_fields = items

    return fp


def _make_bridge_with_mock_board(footprints: list[MagicMock] | None = None):
    """Create a KiCadBridge connected to a mock board with given footprints."""
    from kipart_search.gui.kicad_bridge import KiCadBridge

    bridge = KiCadBridge()
    bridge._board = MagicMock()
    bridge._kicad = MagicMock()
    if footprints is not None:
        bridge._board.get_footprints.return_value = footprints
    return bridge


def _import_blocker(blocked_module: str):
    """Return an __import__ replacement that blocks a specific module."""
    import builtins
    original_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name == blocked_module or name.startswith(blocked_module + "."):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    return _blocked_import


# ---------------------------------------------------------------------------
# Task 4.1: KiCadBridge connect success/failure
# ---------------------------------------------------------------------------

class TestKiCadBridgeConnect:
    """Test KiCadBridge.connect() with mocked kipy."""

    def test_connect_success(self):
        """Successful connection returns (True, 'Connected')."""
        mock_kicad_cls = MagicMock()
        mock_kicad_instance = MagicMock()
        mock_board = MagicMock()
        mock_kicad_cls.return_value = mock_kicad_instance
        mock_kicad_instance.get_board.return_value = mock_board

        with patch.dict("sys.modules", {"kipy": MagicMock(KiCad=mock_kicad_cls)}):
            from kipart_search.gui.kicad_bridge import KiCadBridge
            bridge = KiCadBridge()
            ok, msg = bridge.connect()

        assert ok is True
        assert msg == "Connected"
        assert bridge.is_connected is True

    def test_connect_failure_kicad_not_running(self):
        """Connection failure returns (False, error_message)."""
        mock_kicad_cls = MagicMock()
        mock_kicad_cls.side_effect = ConnectionRefusedError("KiCad not running")

        with patch.dict("sys.modules", {"kipy": MagicMock(KiCad=mock_kicad_cls)}):
            from kipart_search.gui.kicad_bridge import KiCadBridge
            bridge = KiCadBridge()
            ok, msg = bridge.connect()

        assert ok is False
        assert "KiCad not running" in msg
        assert bridge.is_connected is False

    def test_connect_kipy_not_installed(self):
        """ImportError when kipy is not installed returns (False, message)."""
        from kipart_search.gui.kicad_bridge import KiCadBridge

        bridge = KiCadBridge()

        # Patch the import inside connect() to raise ImportError
        with patch("builtins.__import__", side_effect=_import_blocker("kipy")):
            ok, msg = bridge.connect()

        assert ok is False
        assert "kipy" in msg.lower() or "not installed" in msg.lower()
        assert bridge.is_connected is False


# ---------------------------------------------------------------------------
# Task 4.2: get_components() returns properly-populated BoardComponent list
# ---------------------------------------------------------------------------

class TestGetComponents:
    """Test get_components() returns properly-populated BoardComponent list."""

    def test_basic_component_fields(self):
        """Basic fields (reference, value, footprint) are extracted correctly."""
        fp = _make_mock_footprint(
            reference="C3",
            value="100nF",
            footprint_id="Capacitor_SMD:C_0805_2012Metric",
        )
        bridge = _make_bridge_with_mock_board([fp])

        components = bridge.get_components()

        assert len(components) == 1
        c = components[0]
        assert c.reference == "C3"
        assert c.value == "100nF"
        assert c.footprint == "Capacitor_SMD:C_0805_2012Metric"

    def test_mpn_extracted_from_custom_fields(self):
        """MPN is extracted when a field name matches MPN_FIELD_NAMES."""
        fp = _make_mock_footprint(
            reference="R1",
            value="10k",
            custom_fields={"MPN": "RC0805FR-0710KL"},
        )
        bridge = _make_bridge_with_mock_board([fp])

        components = bridge.get_components()

        assert components[0].mpn == "RC0805FR-0710KL"

    def test_mpn_case_insensitive(self):
        """MPN field matching is case-insensitive."""
        fp = _make_mock_footprint(
            reference="U1",
            value="STM32F405",
            custom_fields={"Manf#": "STM32F405RGT6"},
        )
        bridge = _make_bridge_with_mock_board([fp])

        components = bridge.get_components()

        assert components[0].mpn == "STM32F405RGT6"

    def test_mpn_alias_mfr_part(self):
        """MPN extraction works with 'mfr part' alias."""
        fp = _make_mock_footprint(
            custom_fields={"Mfr Part": "GRM188R71C104KA01D"},
        )
        bridge = _make_bridge_with_mock_board([fp])

        assert bridge.get_components()[0].mpn == "GRM188R71C104KA01D"

    def test_datasheet_field_extracted(self):
        """Datasheet URL is extracted from the datasheet field."""
        fp = _make_mock_footprint(
            datasheet="https://example.com/datasheet.pdf",
        )
        bridge = _make_bridge_with_mock_board([fp])

        assert bridge.get_components()[0].datasheet == "https://example.com/datasheet.pdf"

    def test_extra_fields_captured(self):
        """All custom fields are captured in extra_fields dict."""
        fp = _make_mock_footprint(
            custom_fields={
                "MPN": "ABC123",
                "Manufacturer": "Murata",
                "Description": "100nF 50V X7R 0805",
                "LCSC": "C49678",
            },
        )
        bridge = _make_bridge_with_mock_board([fp])

        c = bridge.get_components()[0]
        assert c.extra_fields["Manufacturer"] == "Murata"
        assert c.extra_fields["Description"] == "100nF 50V X7R 0805"
        assert c.extra_fields["LCSC"] == "C49678"

    def test_multiple_components(self):
        """Multiple footprints produce multiple BoardComponents."""
        fps = [
            _make_mock_footprint(reference="C1", value="100nF"),
            _make_mock_footprint(reference="R1", value="10k"),
            _make_mock_footprint(reference="U1", value="STM32F405"),
        ]
        bridge = _make_bridge_with_mock_board(fps)

        components = bridge.get_components()

        assert len(components) == 3
        refs = [c.reference for c in components]
        assert "C1" in refs
        assert "R1" in refs
        assert "U1" in refs

    def test_empty_board_returns_empty_list(self):
        """An empty board returns an empty component list."""
        bridge = _make_bridge_with_mock_board([])
        assert bridge.get_components() == []

    def test_component_without_mpn(self):
        """Component without MPN field has empty mpn string."""
        fp = _make_mock_footprint(reference="C1", value="100nF", custom_fields={})
        bridge = _make_bridge_with_mock_board([fp])

        c = bridge.get_components()[0]
        assert c.mpn == ""
        assert c.has_mpn is False

    def test_no_definition_returns_empty_footprint(self):
        """Component with no definition returns empty footprint string."""
        fp = _make_mock_footprint()
        fp.definition = None
        bridge = _make_bridge_with_mock_board([fp])

        assert bridge.get_components()[0].footprint == ""

    def test_datasheet_field_exception_returns_empty(self):
        """Exception reading datasheet field returns empty string."""
        fp = _make_mock_footprint()
        # Make the datasheet_field property raise an exception
        type(fp).datasheet_field = PropertyMock(side_effect=AttributeError("no datasheet"))
        bridge = _make_bridge_with_mock_board([fp])

        assert bridge.get_components()[0].datasheet == ""

    def test_footprint_cache_populated(self):
        """After get_components(), the footprint cache maps references to footprint objects."""
        fp = _make_mock_footprint(reference="C1")
        bridge = _make_bridge_with_mock_board([fp])

        bridge.get_components()

        assert "C1" in bridge._footprint_cache
        assert bridge._footprint_cache["C1"] is fp


# ---------------------------------------------------------------------------
# Task 4.3: Graceful degradation when kipy is not installed
# ---------------------------------------------------------------------------

class TestGracefulDegradationNoKipy:
    """Test graceful degradation when kipy is not installed."""

    def test_get_components_when_not_connected(self):
        """get_components() returns empty list when not connected."""
        from kipart_search.gui.kicad_bridge import KiCadBridge
        bridge = KiCadBridge()

        assert bridge.is_connected is False
        assert bridge.get_components() == []

    def test_select_component_when_not_connected(self):
        """select_component() returns False when not connected."""
        from kipart_search.gui.kicad_bridge import KiCadBridge
        bridge = KiCadBridge()

        assert bridge.select_component("C1") is False

    def test_write_field_when_not_connected(self):
        """write_field() returns False when not connected."""
        from kipart_search.gui.kicad_bridge import KiCadBridge
        bridge = KiCadBridge()

        assert bridge.write_field("C1", "MPN", "ABC123") is False

    def test_is_connected_false_by_default(self):
        """New bridge instance is not connected."""
        from kipart_search.gui.kicad_bridge import KiCadBridge
        bridge = KiCadBridge()

        assert bridge.is_connected is False

    def test_diagnostics_available_without_connection(self):
        """get_diagnostics() works even without kipy installed."""
        from kipart_search.gui.kicad_bridge import KiCadBridge
        bridge = KiCadBridge()

        diag = bridge.get_diagnostics()
        assert "Platform:" in diag
        assert "Bridge connected: False" in diag


# ---------------------------------------------------------------------------
# Task 4.4: Graceful degradation when KiCad is not running
# ---------------------------------------------------------------------------

class TestGracefulDegradationKiCadNotRunning:
    """Test graceful degradation when KiCad is not running (connection refused)."""

    def test_connect_returns_false_on_exception(self):
        """Connection failure sets board to None and returns False."""
        mock_kicad_cls = MagicMock()
        mock_kicad_cls.return_value.get_board.side_effect = Exception("Connection refused")

        with patch.dict("sys.modules", {"kipy": MagicMock(KiCad=mock_kicad_cls)}):
            from kipart_search.gui.kicad_bridge import KiCadBridge
            bridge = KiCadBridge()
            ok, msg = bridge.connect()

        assert ok is False
        assert bridge._board is None
        assert bridge._kicad is None

    def test_get_components_after_failed_connect(self):
        """get_components() returns empty list after failed connect."""
        from kipart_search.gui.kicad_bridge import KiCadBridge
        bridge = KiCadBridge()
        # Simulate a failed connect — board stays None
        assert bridge.get_components() == []

    def test_get_footprints_exception_returns_empty(self):
        """Exception during get_footprints() returns empty list."""
        bridge = _make_bridge_with_mock_board()
        bridge._board.get_footprints.side_effect = Exception("IPC error")

        assert bridge.get_components() == []

    def test_select_component_not_in_cache(self):
        """select_component() returns False for unknown reference."""
        bridge = _make_bridge_with_mock_board([])
        bridge.get_components()  # populate empty cache

        assert bridge.select_component("C99") is False

    def test_select_component_exception_returns_false(self):
        """select_component() returns False on IPC exception."""
        fp = _make_mock_footprint(reference="C1")
        bridge = _make_bridge_with_mock_board([fp])
        bridge.get_components()  # populate cache

        bridge._board.add_to_selection.side_effect = Exception("IPC error")
        assert bridge.select_component("C1") is False


# ---------------------------------------------------------------------------
# Task 4.5: ScanWorker completes and emits correct signals
# ---------------------------------------------------------------------------

class TestScanWorker:
    """Test ScanWorker completes and emits correct signals."""

    def test_scan_worker_emits_components(self, qtbot):
        """ScanWorker emits scan_complete with components and statuses."""
        from kipart_search.gui.main_window import ScanWorker

        mock_bridge = MagicMock()
        mock_bridge.get_components.return_value = [
            BoardComponent(
                reference="C1", value="100nF",
                footprint="Capacitor_SMD:C_0805_2012Metric",
                mpn="GRM188R71C104KA01D",
            ),
        ]

        mock_orchestrator = MagicMock()
        mock_result = MagicMock()
        mock_result.confidence = MagicMock()
        mock_result.confidence.__eq__ = lambda self, other: True
        mock_result.source = "JLCPCB"
        mock_orchestrator.verify_mpn.return_value = mock_result
        mock_orchestrator.get_db_modified_time.return_value = 1000.0

        worker = ScanWorker(mock_bridge, mock_orchestrator)

        with qtbot.waitSignal(worker.scan_complete, timeout=5000) as blocker:
            worker.start()

        components, mpn_statuses, db_mtime = blocker.args
        assert len(components) == 1
        assert components[0].reference == "C1"
        assert "C1" in mpn_statuses
        assert db_mtime == 1000.0

    def test_scan_worker_error_on_empty_board(self, qtbot):
        """ScanWorker emits error when no components found."""
        from kipart_search.gui.main_window import ScanWorker

        mock_bridge = MagicMock()
        mock_bridge.get_components.return_value = []

        mock_orchestrator = MagicMock()

        worker = ScanWorker(mock_bridge, mock_orchestrator)

        with qtbot.waitSignal(worker.error, timeout=5000) as blocker:
            worker.start()

        assert "No components" in blocker.args[0]

    def test_scan_worker_handles_missing_mpn(self, qtbot):
        """ScanWorker assigns RED confidence to components without MPN."""
        from kipart_search.core.models import Confidence
        from kipart_search.gui.main_window import ScanWorker

        mock_bridge = MagicMock()
        mock_bridge.get_components.return_value = [
            BoardComponent(
                reference="C1", value="100nF",
                footprint="Capacitor_SMD:C_0805_2012Metric",
                mpn="",  # No MPN
            ),
        ]

        mock_orchestrator = MagicMock()
        mock_orchestrator.get_db_modified_time.return_value = None

        worker = ScanWorker(mock_bridge, mock_orchestrator)

        with qtbot.waitSignal(worker.scan_complete, timeout=5000) as blocker:
            worker.start()

        components, mpn_statuses, _ = blocker.args
        assert mpn_statuses["C1"] == Confidence.RED

    def test_scan_worker_handles_exception(self, qtbot):
        """ScanWorker emits error signal on unexpected exception."""
        from kipart_search.gui.main_window import ScanWorker

        mock_bridge = MagicMock()
        mock_bridge.get_components.side_effect = RuntimeError("Unexpected error")

        mock_orchestrator = MagicMock()

        worker = ScanWorker(mock_bridge, mock_orchestrator)

        with qtbot.waitSignal(worker.error, timeout=5000) as blocker:
            worker.start()

        assert "Unexpected error" in blocker.args[0]

    def test_scan_worker_log_messages(self, qtbot):
        """ScanWorker emits log messages during scan."""
        from kipart_search.gui.main_window import ScanWorker

        mock_bridge = MagicMock()
        mock_bridge.get_components.return_value = [
            BoardComponent(
                reference="R1", value="10k",
                footprint="Resistor_SMD:R_0805_2012Metric",
                mpn="RC0805FR-0710KL",
            ),
        ]

        mock_orchestrator = MagicMock()
        mock_result = MagicMock()
        mock_result.confidence = MagicMock()
        mock_result.source = "JLCPCB"
        mock_orchestrator.verify_mpn.return_value = mock_result
        mock_orchestrator.get_db_modified_time.return_value = None

        worker = ScanWorker(mock_bridge, mock_orchestrator)

        log_messages = []
        worker.log.connect(log_messages.append)

        with qtbot.waitSignal(worker.scan_complete, timeout=5000):
            worker.start()

        assert any("Reading components" in m for m in log_messages)
        assert any("Scan complete" in m for m in log_messages)


# ---------------------------------------------------------------------------
# Select component tests
# ---------------------------------------------------------------------------

class TestSelectComponent:
    """Test select_component() for highlighting in KiCad."""

    def test_select_component_success(self):
        """select_component() returns True and calls board selection methods."""
        fp = _make_mock_footprint(reference="C1")
        bridge = _make_bridge_with_mock_board([fp])
        bridge.get_components()  # populate cache

        result = bridge.select_component("C1")

        assert result is True
        bridge._board.clear_selection.assert_called_once()
        bridge._board.add_to_selection.assert_called_once_with(fp)

    def test_select_unknown_reference(self):
        """select_component() returns False for unknown reference."""
        bridge = _make_bridge_with_mock_board([])
        bridge.get_components()

        assert bridge.select_component("UNKNOWN") is False


# ---------------------------------------------------------------------------
# Write field tests
# ---------------------------------------------------------------------------

class TestWriteField:
    """Test write_field() for writing back to KiCad."""

    def test_write_empty_custom_field(self):
        """write_field() writes to empty custom field and returns True."""
        fp = _make_mock_footprint(
            reference="C1",
            custom_fields={"MPN": ""},
        )
        bridge = _make_bridge_with_mock_board([fp])
        bridge.get_components()

        result = bridge.write_field("C1", "MPN", "GRM188R71C104KA01D")

        assert result is True
        bridge._board.update_items.assert_called_once()

    def test_write_nonempty_field_blocked(self):
        """write_field() refuses to overwrite non-empty field."""
        fp = _make_mock_footprint(
            reference="C1",
            custom_fields={"MPN": "EXISTING_VALUE"},
        )
        bridge = _make_bridge_with_mock_board([fp])
        bridge.get_components()

        result = bridge.write_field("C1", "MPN", "NEW_VALUE")

        assert result is False
        bridge._board.update_items.assert_not_called()

    def test_write_datasheet_field(self):
        """write_field() can write to the datasheet predefined field."""
        fp = _make_mock_footprint(reference="C1", datasheet="")
        bridge = _make_bridge_with_mock_board([fp])
        bridge.get_components()

        result = bridge.write_field("C1", "datasheet", "https://example.com/ds.pdf")

        assert result is True

    def test_write_datasheet_nonempty_blocked(self):
        """write_field() refuses to overwrite non-empty datasheet."""
        fp = _make_mock_footprint(reference="C1", datasheet="https://existing.com/ds.pdf")
        bridge = _make_bridge_with_mock_board([fp])
        bridge.get_components()

        result = bridge.write_field("C1", "datasheet", "https://new.com/ds.pdf")

        assert result is False

    def test_write_unknown_field_returns_false(self):
        """write_field() returns False for nonexistent field name."""
        fp = _make_mock_footprint(reference="C1", custom_fields={})
        bridge = _make_bridge_with_mock_board([fp])
        bridge.get_components()

        result = bridge.write_field("C1", "NonExistentField", "value")

        assert result is False


# ---------------------------------------------------------------------------
# Story 5.2: Click-to-highlight cross-probe tests
# ---------------------------------------------------------------------------

class TestSelectComponentEdgeCases:
    """Story 5.2 — Edge case tests for select_component() cross-probe."""

    def test_select_calls_clear_then_add_in_order(self):
        """select_component() calls clear_selection before add_to_selection."""
        fp = _make_mock_footprint(reference="R1")
        bridge = _make_bridge_with_mock_board([fp])
        bridge.get_components()

        call_order = []
        bridge._board.clear_selection.side_effect = lambda: call_order.append("clear")
        bridge._board.add_to_selection.side_effect = lambda x: call_order.append("add")

        bridge.select_component("R1")

        assert call_order == ["clear", "add"]

    def test_select_when_clear_selection_raises(self):
        """select_component() returns False when clear_selection raises."""
        fp = _make_mock_footprint(reference="C1")
        bridge = _make_bridge_with_mock_board([fp])
        bridge.get_components()

        bridge._board.clear_selection.side_effect = Exception("IPC timeout")

        result = bridge.select_component("C1")
        assert result is False

    def test_select_when_add_to_selection_raises(self):
        """select_component() returns False when add_to_selection raises."""
        fp = _make_mock_footprint(reference="C1")
        bridge = _make_bridge_with_mock_board([fp])
        bridge.get_components()

        bridge._board.add_to_selection.side_effect = Exception("IPC error")

        result = bridge.select_component("C1")
        assert result is False

    def test_select_not_connected_returns_false(self):
        """select_component() returns False immediately when not connected."""
        from kipart_search.gui.kicad_bridge import KiCadBridge
        bridge = KiCadBridge()

        result = bridge.select_component("C1")

        assert result is False

    def test_select_reference_not_in_cache(self):
        """select_component() returns False for reference deleted after scan."""
        fp = _make_mock_footprint(reference="C1")
        bridge = _make_bridge_with_mock_board([fp])
        bridge.get_components()

        # Reference that was never on the board
        result = bridge.select_component("C99")

        assert result is False
        bridge._board.clear_selection.assert_not_called()
        bridge._board.add_to_selection.assert_not_called()

    def test_select_multiple_components_sequentially(self):
        """Selecting multiple components clears selection each time."""
        fp1 = _make_mock_footprint(reference="C1")
        fp2 = _make_mock_footprint(reference="R1")
        bridge = _make_bridge_with_mock_board([fp1, fp2])
        bridge.get_components()

        bridge.select_component("C1")
        bridge.select_component("R1")

        assert bridge._board.clear_selection.call_count == 2
        assert bridge._board.add_to_selection.call_count == 2

    def test_footprint_cache_cleared_on_rescan(self):
        """Footprint cache is cleared and repopulated on each get_components()."""
        fp1 = _make_mock_footprint(reference="C1")
        fp2 = _make_mock_footprint(reference="R1")

        bridge = _make_bridge_with_mock_board([fp1])
        bridge.get_components()
        assert "C1" in bridge._footprint_cache

        # Re-scan with different components
        bridge._board.get_footprints.return_value = [fp2]
        bridge.get_components()

        assert "C1" not in bridge._footprint_cache
        assert "R1" in bridge._footprint_cache

    def test_select_after_rescan_uses_new_cache(self):
        """After re-scan, select_component uses the new footprint cache."""
        fp1 = _make_mock_footprint(reference="C1")
        fp2 = _make_mock_footprint(reference="C1")  # Same ref, new fp object

        bridge = _make_bridge_with_mock_board([fp1])
        bridge.get_components()

        # Re-scan replaces cache
        bridge._board.get_footprints.return_value = [fp2]
        bridge.get_components()

        bridge.select_component("C1")
        bridge._board.add_to_selection.assert_called_with(fp2)


class TestOnComponentClickedSignalChain:
    """Story 5.2 — Test the verify panel → main window → bridge signal chain."""

    def test_on_component_clicked_calls_select(self):
        """_on_component_clicked calls bridge.select_component with reference."""
        from kipart_search.gui.kicad_bridge import KiCadBridge
        from kipart_search.gui.main_window import MainWindow

        window = MainWindow.__new__(MainWindow)
        window._bridge = MagicMock(spec=KiCadBridge)
        window.dock_search = MagicMock()
        window.dock_search.isVisible.return_value = False

        window._on_component_clicked("C1")

        window._bridge.select_component.assert_called_once_with("C1")

    def test_on_component_clicked_no_error_when_select_fails(self):
        """_on_component_clicked does not raise when select_component returns False."""
        from kipart_search.gui.kicad_bridge import KiCadBridge
        from kipart_search.gui.main_window import MainWindow

        window = MainWindow.__new__(MainWindow)
        window._bridge = MagicMock(spec=KiCadBridge)
        window._bridge.select_component.return_value = False
        window.dock_search = MagicMock()
        window.dock_search.isVisible.return_value = False

        # Should not raise
        window._on_component_clicked("C1")

    def test_on_component_clicked_updates_assign_target(self):
        """_on_component_clicked updates assign target when search dock is visible."""
        from kipart_search.gui.kicad_bridge import KiCadBridge
        from kipart_search.gui.main_window import MainWindow

        comp = BoardComponent(reference="C1", value="100nF", footprint="C_0805", mpn="ABC")

        window = MainWindow.__new__(MainWindow)
        window._bridge = MagicMock(spec=KiCadBridge)
        window.dock_search = MagicMock()
        window.dock_search.isVisible.return_value = True
        window._search_target_label = MagicMock()
        window.detail_panel = MagicMock()
        window.results_table = MagicMock()
        window._assign_target = None

        # Mock verify_panel table
        mock_table = MagicMock()
        mock_table.rowCount.return_value = 1
        window.verify_panel = MagicMock()
        window.verify_panel.table = mock_table
        window.verify_panel.get_component.return_value = comp

        window._on_component_clicked("C1")

        assert window._assign_target is comp

    def test_verify_panel_emits_reference_on_cell_click(self):
        """VerifyPanel._on_cell_clicked emits component_clicked with reference."""
        from kipart_search.gui.verify_panel import VerifyPanel
        from kipart_search.core.models import Confidence

        panel = VerifyPanel()
        comp = BoardComponent(reference="R5", value="10k", footprint="R_0805", mpn="XYZ")
        panel.set_results(
            [comp],
            {"R5": Confidence.GREEN},
        )

        emitted = []
        panel.component_clicked.connect(emitted.append)

        # Click first row, first column
        panel._on_cell_clicked(0, 0)

        assert len(emitted) == 1
        assert emitted[0] == "R5"

    def test_verify_panel_detail_updates_on_click(self):
        """VerifyPanel detail browser updates on click regardless of bridge state."""
        from kipart_search.gui.verify_panel import VerifyPanel
        from kipart_search.core.models import Confidence

        panel = VerifyPanel()
        comp = BoardComponent(reference="U1", value="STM32", footprint="QFP-48", mpn="STM32F4")
        panel.set_results(
            [comp],
            {"U1": Confidence.GREEN},
        )

        # Click the row
        panel._on_cell_clicked(0, 0)

        # Detail browser should have content (the panel updates its own detail)
        html = panel._detail.toHtml()
        assert "U1" in html
        assert "STM32" in html
