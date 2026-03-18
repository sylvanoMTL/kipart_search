"""Tests for context menus and accessibility labels (Story 1.5)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

PySide6 = pytest.importorskip("PySide6", reason="PySide6 required for GUI tests")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

# Ensure a QApplication exists before any widget tests
app = QApplication.instance() or QApplication(sys.argv)

from kipart_search.core.models import Confidence, PartResult
from kipart_search.core.models import BoardComponent
from kipart_search.gui.results_table import ResultsTable
from kipart_search.gui.verify_panel import VerifyPanel


# ── Fixtures ──


@pytest.fixture
def verify_panel():
    p = VerifyPanel()
    yield p
    p.close()


@pytest.fixture
def results_table():
    t = ResultsTable()
    yield t
    t.close()


@pytest.fixture
def sample_components():
    return [
        BoardComponent(
            reference="C1",
            value="100nF",
            footprint="Capacitor_SMD:C_0805_2012Metric",
            mpn="GRM188R71C104KA01D",
        ),
        BoardComponent(
            reference="R1",
            value="10k",
            footprint="Resistor_SMD:R_0402_1005Metric",
            mpn="",
        ),
        BoardComponent(
            reference="U1",
            value="STM32F405RG",
            footprint="Package_QFP:LQFP-64",
            mpn="STM32F405RGT6",
        ),
        BoardComponent(
            reference="U2",
            value="MAX232",
            footprint="Package_SO:SOIC-16",
            mpn="MAX232CSE+",
        ),
    ]


@pytest.fixture
def sample_statuses():
    return {
        "C1": Confidence.GREEN,
        "R1": Confidence.RED,
        "U1": Confidence.AMBER,
        "U2": Confidence.RED,  # has MPN but not found in any source
    }


@pytest.fixture
def populated_verify(verify_panel, sample_components, sample_statuses):
    verify_panel.set_results(sample_components, sample_statuses)
    return verify_panel


@pytest.fixture
def sample_parts():
    return [
        PartResult(
            mpn="GRM188R71C104KA01D",
            manufacturer="Murata",
            description="100nF 16V X7R 0603",
            datasheet_url="https://example.com/datasheet.pdf",
        ),
        PartResult(
            mpn="",
            manufacturer="Unknown",
            description="No MPN part",
        ),
        PartResult(
            mpn="LM358",
            manufacturer="TI",
            description="Dual Op-Amp",
        ),
    ]


@pytest.fixture
def populated_results(results_table, sample_parts):
    results_table.set_results(sample_parts)
    return results_table


# ── Helpers ──


def _find_row_by_ref(panel: VerifyPanel, ref: str) -> int:
    """Find table row for a component by reference designator."""
    for row in range(panel.table.rowCount()):
        comp = panel.get_component(row)
        if comp and comp.reference == ref:
            return row
    pytest.fail(f"{ref} not found in table")


def _find_row_by_mpn(table: ResultsTable, mpn: str) -> int:
    """Find table row for a part by MPN."""
    for row in range(table.table.rowCount()):
        part = table.get_result(row)
        if part and part.mpn == mpn:
            return row
    pytest.fail(f"MPN '{mpn}' not found in table")


# ── Task 6: Verify panel context menu tests (AC #1) ──


class TestVerifyContextMenu:
    """Context menu on verification table rows."""

    def test_verify_context_menu_policy(self, verify_panel: VerifyPanel):
        assert (
            verify_panel.table.contextMenuPolicy()
            == Qt.ContextMenuPolicy.CustomContextMenu
        )

    def test_verify_context_menu_actions(self, populated_verify: VerifyPanel):
        menu = populated_verify._build_context_menu(0)
        assert menu is not None
        actions = [a.text() for a in menu.actions()]
        assert "Search for this component" in actions
        assert "Assign MPN" in actions
        assert "Copy MPN" in actions

    def test_verify_copy_mpn_disabled_when_empty(
        self, populated_verify: VerifyPanel
    ):
        row = _find_row_by_ref(populated_verify, "R1")
        menu = populated_verify._build_context_menu(row)
        assert menu is not None
        copy_action = [a for a in menu.actions() if a.text() == "Copy MPN"][0]
        assert not copy_action.isEnabled()


# ── Task 7: Results table context menu tests (AC #2) ──


class TestResultsContextMenu:
    """Context menu on results table rows."""

    def test_results_context_menu_no_assign_target(
        self, populated_results: ResultsTable
    ):
        populated_results.set_assign_target(None)
        menu = populated_results._build_context_menu(0)
        assert menu is not None
        actions = [a.text() for a in menu.actions()]
        assert not any(a.startswith("Assign to") for a in actions)

    def test_results_context_menu_with_assign_target(
        self, populated_results: ResultsTable
    ):
        populated_results.set_assign_target("C3")
        menu = populated_results._build_context_menu(0)
        assert menu is not None
        actions = [a.text() for a in menu.actions()]
        assert "Assign to C3" in actions

    def test_results_copy_mpn(self, populated_results: ResultsTable):
        menu = populated_results._build_context_menu(0)
        assert menu is not None
        copy_action = [a for a in menu.actions() if a.text() == "Copy MPN"][0]
        assert copy_action.isEnabled()

    def test_results_copy_mpn_disabled_when_empty(
        self, populated_results: ResultsTable
    ):
        row = _find_row_by_mpn(populated_results, "")
        menu = populated_results._build_context_menu(row)
        assert menu is not None
        copy_action = [a for a in menu.actions() if a.text() == "Copy MPN"][0]
        assert not copy_action.isEnabled()

    def test_results_open_datasheet_only_with_url(
        self, populated_results: ResultsTable
    ):
        # Part with datasheet URL
        row_with = _find_row_by_mpn(populated_results, "GRM188R71C104KA01D")
        menu = populated_results._build_context_menu(row_with)
        assert menu is not None
        actions = [a.text() for a in menu.actions()]
        assert "Open Datasheet" in actions

        # Part without datasheet URL
        row_without = _find_row_by_mpn(populated_results, "LM358")
        menu = populated_results._build_context_menu(row_without)
        assert menu is not None
        actions = [a.text() for a in menu.actions()]
        assert "Open Datasheet" not in actions


# ── Task 8: Accessibility label tests (AC #3, #5) ──


class TestAccessibilityLabels:
    """Accessibility names, descriptions, and status text labels."""

    def test_verify_status_text_labels(self, populated_verify: VerifyPanel):
        status_texts = []
        for row in range(populated_verify.table.rowCount()):
            item = populated_verify.table.item(row, 3)  # MPN Status column
            if item:
                status_texts.append(item.text())

        assert "Verified" in status_texts
        assert "Needs attention" in status_texts
        assert "Missing MPN" in status_texts
        assert "Not found" in status_texts  # MPN present but not in any source
        # Ensure old terse labels are NOT present
        assert "OK" not in status_texts
        assert "?" not in status_texts

    def test_verify_status_tooltips(self, populated_verify: VerifyPanel):
        tooltips = []
        for row in range(populated_verify.table.rowCount()):
            item = populated_verify.table.item(row, 3)
            if item and item.toolTip():
                tooltips.append(item.toolTip())

        assert len(tooltips) == 4
        assert any("verified" in t.lower() for t in tooltips)
        assert any("attention" in t.lower() for t in tooltips)
        assert any("no mpn assigned" in t.lower() for t in tooltips)
        assert any("not found in any" in t.lower() for t in tooltips)

    def test_table_accessible_names(
        self, verify_panel: VerifyPanel, results_table: ResultsTable
    ):
        assert (
            verify_panel.table.accessibleName()
            == "Component verification table"
        )
        assert (
            results_table.table.accessibleName() == "Search results table"
        )

    def test_status_bar_accessible_names(self):
        """Verify status bar labels have accessible names set."""
        from PySide6.QtCore import QSettings

        with patch(
            "kipart_search.gui.main_window.KiCadBridge"
        ) as MockBridge:
            mock_bridge = MagicMock()
            mock_bridge.is_connected = False
            MockBridge.return_value = mock_bridge

            from kipart_search.gui.main_window import MainWindow

            w = MainWindow()
            try:
                assert w._mode_label.accessibleName() == "Connection mode"
                assert w._sources_label.accessibleName() == "Active sources"
                assert w._action_label.accessibleName() == "Current action"
            finally:
                # Prevent closeEvent from polluting QSettings for other tests
                settings = QSettings("kipart-search", "kipart-search")
                settings.remove("geometry")
                settings.remove("windowState")
                w.close()
