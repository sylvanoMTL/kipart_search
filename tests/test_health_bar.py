"""Tests for health summary bar color-coding and live updates (Story 2.3)."""

from __future__ import annotations

import sys

import pytest

PySide6 = pytest.importorskip("PySide6", reason="PySide6 required for GUI tests")

from PySide6.QtWidgets import QApplication

# Ensure a QApplication exists before any widget tests
app = QApplication.instance() or QApplication(sys.argv)

from kipart_search.core.models import BoardComponent, Confidence
from kipart_search.gui.verify_panel import COLORS, VerifyPanel


def _make_components(n: int, mpn_count: int = 0) -> list[BoardComponent]:
    """Create n BoardComponents; first mpn_count have MPNs assigned."""
    comps = []
    for i in range(n):
        has = i < mpn_count
        comps.append(
            BoardComponent(
                reference=f"C{i + 1}",
                value="100nF",
                footprint="Capacitor_SMD:C_0805_2012Metric",
                mpn=f"GRM21BR71C104KA01L" if has else "",
            )
        )
    return comps


def _make_statuses(
    comps: list[BoardComponent],
) -> dict[str, Confidence]:
    """Build mpn_statuses: GREEN if has_mpn, RED otherwise."""
    return {
        c.reference: Confidence.GREEN if c.has_mpn else Confidence.RED
        for c in comps
    }


class TestHealthBarColorCoding:
    """AC #1, #3, #4, #5: Health bar color-coding by percentage."""

    def test_red_below_50(self):
        panel = VerifyPanel()
        comps = _make_components(10, mpn_count=2)  # 20%
        panel.set_results(comps, _make_statuses(comps))
        style = panel.health_bar.styleSheet()
        assert "#FFC8C8" in style  # red
        panel.close()

    def test_amber_at_50(self):
        panel = VerifyPanel()
        comps = _make_components(10, mpn_count=5)  # 50%
        panel.set_results(comps, _make_statuses(comps))
        style = panel.health_bar.styleSheet()
        assert "#FFEBB4" in style  # amber
        panel.close()

    def test_amber_at_99(self):
        panel = VerifyPanel()
        comps = _make_components(100, mpn_count=99)  # 99%
        panel.set_results(comps, _make_statuses(comps))
        style = panel.health_bar.styleSheet()
        assert "#FFEBB4" in style  # amber
        panel.close()

    def test_green_at_100(self):
        panel = VerifyPanel()
        comps = _make_components(10, mpn_count=10)  # 100%
        panel.set_results(comps, _make_statuses(comps))
        style = panel.health_bar.styleSheet()
        assert "#C8FFC8" in style  # green
        panel.close()

    def test_ready_for_export_text_at_100(self):
        panel = VerifyPanel()
        comps = _make_components(5, mpn_count=5)  # 100%
        panel.set_results(comps, _make_statuses(comps))
        assert "Ready for export" in panel.summary_label.text()
        panel.close()

    def test_no_ready_for_export_below_100(self):
        panel = VerifyPanel()
        comps = _make_components(5, mpn_count=4)  # 80%
        panel.set_results(comps, _make_statuses(comps))
        assert "Ready for export" not in panel.summary_label.text()
        panel.close()

    def test_zero_percent(self):
        panel = VerifyPanel()
        comps = _make_components(5, mpn_count=0)  # 0%
        panel.set_results(comps, _make_statuses(comps))
        style = panel.health_bar.styleSheet()
        assert "#FFC8C8" in style  # red
        panel.close()


class TestHealthBarAccessibility:
    """AC #7: Accessibility names set on health bar and summary label."""

    def test_health_bar_accessible_name(self):
        panel = VerifyPanel()
        assert panel.health_bar.accessibleName() == "BOM health progress"
        panel.close()

    def test_health_bar_accessible_description(self):
        panel = VerifyPanel()
        assert "verified MPNs" in panel.health_bar.accessibleDescription()
        panel.close()

    def test_summary_label_accessible_name(self):
        panel = VerifyPanel()
        assert panel.summary_label.accessibleName() == "BOM health summary"
        panel.close()


class TestUpdateComponentStatus:
    """AC #2: Live update of a single component's status."""

    def test_updates_mpn_statuses(self):
        panel = VerifyPanel()
        comps = _make_components(5, mpn_count=2)
        panel.set_results(comps, _make_statuses(comps))
        # C3 was RED (no MPN) — update to GREEN
        panel.update_component_status("C3", Confidence.GREEN)
        assert panel._mpn_statuses["C3"] == Confidence.GREEN
        panel.close()

    def test_updates_summary_counts(self):
        panel = VerifyPanel()
        comps = _make_components(5, mpn_count=2)
        panel.set_results(comps, _make_statuses(comps))
        # 2 valid, 3 missing. Update C3 to GREEN → 3 valid, 2 missing
        panel.update_component_status("C3", Confidence.GREEN)
        text = panel.summary_label.text()
        assert "Valid MPN: 3" in text
        assert "Missing MPN: 2" in text
        panel.close()

    def test_updates_health_bar_value(self):
        panel = VerifyPanel()
        comps = _make_components(5, mpn_count=2)
        panel.set_results(comps, _make_statuses(comps))
        panel.update_component_status("C3", Confidence.GREEN)
        assert panel.health_bar.value() == 3
        panel.close()

    def test_updates_row_background_color(self):
        panel = VerifyPanel()
        comps = _make_components(5, mpn_count=2)
        panel.set_results(comps, _make_statuses(comps))
        panel.update_component_status("C3", Confidence.GREEN)
        # Find the visual row for C3 and check its background
        green_bg = COLORS[Confidence.GREEN]
        found = False
        for row in range(panel.table.rowCount()):
            item = panel.table.item(row, 0)
            if item and item.text() == "C3":
                assert item.background().color() == green_bg
                found = True
                break
        assert found, "C3 row not found in table"
        panel.close()

    def test_updates_mpn_cell_text(self):
        """After assignment, MPN column should show the assigned MPN, not '(missing)'."""
        panel = VerifyPanel()
        comps = _make_components(5, mpn_count=2)
        panel.set_results(comps, _make_statuses(comps))
        # Simulate what main_window does: update comp.mpn, then call update_component_status
        comps[2].mpn = "ASSIGNED-MPN-123"
        panel.update_component_status("C3", Confidence.GREEN)
        # Find the visual row for C3 and check its MPN cell text
        found = False
        for row in range(panel.table.rowCount()):
            item = panel.table.item(row, 0)
            if item and item.text() == "C3":
                mpn_cell = panel.table.item(row, 2)
                assert mpn_cell.text() == "ASSIGNED-MPN-123"
                found = True
                break
        assert found, "C3 row not found in table"
        panel.close()

    def test_color_changes_on_threshold_crossing(self):
        """When update crosses 50% threshold, bar color should change."""
        panel = VerifyPanel()
        comps = _make_components(10, mpn_count=4)  # 40% → red
        panel.set_results(comps, _make_statuses(comps))
        assert "#FFC8C8" in panel.health_bar.styleSheet()
        # Update C5 to GREEN → 50% → amber
        panel.update_component_status("C5", Confidence.GREEN)
        assert "#FFEBB4" in panel.health_bar.styleSheet()
        panel.close()

    def test_reaching_100_shows_ready_for_export(self):
        panel = VerifyPanel()
        comps = _make_components(2, mpn_count=1)  # 50%
        panel.set_results(comps, _make_statuses(comps))
        assert "Ready for export" not in panel.summary_label.text()
        panel.update_component_status("C2", Confidence.GREEN)
        assert "Ready for export" in panel.summary_label.text()
        panel.close()


class TestEmptyStateHealthBar:
    """AC #6: No scan performed — bar hidden, guidance text shown."""

    def test_bar_hidden_initially(self):
        panel = VerifyPanel()
        assert not panel.health_bar.isVisible()
        panel.close()

    def test_guidance_text_shown_initially(self):
        panel = VerifyPanel()
        assert "Scan a project or open a BOM to begin" in panel.summary_label.text()
        panel.close()
