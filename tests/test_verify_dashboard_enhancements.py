"""Tests for verification dashboard enhancements (Story 3.3)."""

from __future__ import annotations

import sys

import pytest

PySide6 = pytest.importorskip("PySide6", reason="PySide6 required for GUI tests")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

# Ensure a QApplication exists before any widget tests
app = QApplication.instance() or QApplication(sys.argv)

from kipart_search.core.models import BoardComponent, Confidence
from kipart_search.gui.verify_panel import (
    VERIFY_COLUMNS,
    VerifyPanel,
    _SORT_ORDER,
    _StatusItem,
    _UNVERIFIED_LABEL,
)


# ── Helpers ──

def _make_component(ref: str, value: str, mpn: str = "", footprint: str = "Lib:FP") -> BoardComponent:
    return BoardComponent(reference=ref, value=value, footprint=footprint, mpn=mpn)


def _mixed_components() -> tuple[list[BoardComponent], dict[str, Confidence]]:
    """Create a mix of GREEN, AMBER, and RED components."""
    comps = [
        _make_component("C1", "100nF", mpn="GRM188R71C104KA01D"),  # GREEN
        _make_component("R1", "10k"),                                # RED (no MPN)
        _make_component("U1", "STM32F405", mpn="STM32F405RGT6"),   # AMBER
        _make_component("C2", "10uF", mpn="CL10A106KP8NNNC"),      # GREEN
        _make_component("R2", "4.7k"),                                # RED (no MPN)
    ]
    statuses = {
        "C1": Confidence.GREEN,
        "R1": Confidence.RED,
        "U1": Confidence.AMBER,
        "C2": Confidence.GREEN,
        "R2": Confidence.RED,
    }
    return comps, statuses


# ── Status Label Tests ──

class TestStatusLabels:
    def test_missing_mpn_label(self):
        """RED + no MPN should show 'Missing MPN'."""
        panel = VerifyPanel()
        comp = _make_component("R1", "10k")  # no MPN
        panel.set_results([comp], {"R1": Confidence.RED})

        status_item = panel.table.item(0, VERIFY_COLUMNS.index("MPN Status"))
        assert status_item.text() == "Missing MPN"

    def test_not_found_label(self):
        """RED + has MPN + sources available should show 'Not found'."""
        panel = VerifyPanel()
        comp = _make_component("U1", "IC", mpn="UNKNOWN123")
        panel.set_results([comp], {"U1": Confidence.RED}, has_active_sources=True)

        status_item = panel.table.item(0, VERIFY_COLUMNS.index("MPN Status"))
        assert status_item.text() == "Not found"

    def test_needs_attention_label(self):
        """AMBER should show 'Needs attention'."""
        panel = VerifyPanel()
        comp = _make_component("U1", "IC", mpn="STM32F405RGT6")
        panel.set_results([comp], {"U1": Confidence.AMBER})

        status_item = panel.table.item(0, VERIFY_COLUMNS.index("MPN Status"))
        assert status_item.text() == "Needs attention"

    def test_verified_label(self):
        """GREEN should show 'Verified'."""
        panel = VerifyPanel()
        comp = _make_component("C1", "100nF", mpn="GRM188R71C104KA01D")
        panel.set_results([comp], {"C1": Confidence.GREEN})

        status_item = panel.table.item(0, VERIFY_COLUMNS.index("MPN Status"))
        assert status_item.text() == "Verified"

    def test_unverified_label_no_sources(self):
        """RED + has MPN + no sources should show 'Unverified' (downgraded to AMBER)."""
        panel = VerifyPanel()
        comp = _make_component("U1", "IC", mpn="STM32F405RGT6")
        panel.set_results([comp], {"U1": Confidence.RED}, has_active_sources=False)

        status_item = panel.table.item(0, VERIFY_COLUMNS.index("MPN Status"))
        assert status_item.text() == _UNVERIFIED_LABEL


# ── Sort Order Tests ──

class TestDefaultSort:
    def test_sort_keys_set_correctly(self):
        """UserRole+1 sort keys should be RED=0, AMBER=1, GREEN=2."""
        panel = VerifyPanel()
        comps, statuses = _mixed_components()
        panel.set_results(comps, statuses)

        status_col = VERIFY_COLUMNS.index("MPN Status")
        sort_keys = []
        for row in range(panel.table.rowCount()):
            item = panel.table.item(row, status_col)
            sort_keys.append(item.data(Qt.ItemDataRole.UserRole + 1))

        # After default sort (ascending), sort keys should be in non-decreasing order
        assert sort_keys == sorted(sort_keys)

    def test_red_rows_first(self):
        """After set_results(), red-status rows should appear before amber and green."""
        panel = VerifyPanel()
        comps, statuses = _mixed_components()
        panel.set_results(comps, statuses)

        status_col = VERIFY_COLUMNS.index("MPN Status")
        labels = []
        for row in range(panel.table.rowCount()):
            item = panel.table.item(row, status_col)
            labels.append(item.text())

        # RED labels first, then AMBER, then GREEN
        red_labels = {"Missing MPN", "Not found"}
        amber_labels = {"Needs attention", "Unverified"}
        green_labels = {"Verified"}

        # Find transition points
        last_red = -1
        first_amber = None
        last_amber = -1
        first_green = None
        for i, label in enumerate(labels):
            if label in red_labels:
                last_red = i
            elif label in amber_labels:
                if first_amber is None:
                    first_amber = i
                last_amber = i
            elif label in green_labels:
                if first_green is None:
                    first_green = i

        # Red should come before amber and green
        if first_amber is not None:
            assert last_red < first_amber
        if first_green is not None:
            assert last_red < first_green
            if last_amber >= 0:
                assert last_amber < first_green

    def test_status_item_comparison(self):
        """_StatusItem should sort by UserRole+1 data, not text."""
        item_red = _StatusItem("Not found")
        item_red.setData(Qt.ItemDataRole.UserRole + 1, _SORT_ORDER[Confidence.RED])

        item_green = _StatusItem("Verified")
        item_green.setData(Qt.ItemDataRole.UserRole + 1, _SORT_ORDER[Confidence.GREEN])

        assert item_red < item_green
        assert not item_green < item_red

    def test_user_role_preserved(self):
        """UserRole (original component index) should not be overwritten by sort key."""
        panel = VerifyPanel()
        comps, statuses = _mixed_components()
        panel.set_results(comps, statuses)

        status_col = VERIFY_COLUMNS.index("MPN Status")
        for row in range(panel.table.rowCount()):
            item = panel.table.item(row, status_col)
            orig_idx = item.data(Qt.ItemDataRole.UserRole)
            sort_key = item.data(Qt.ItemDataRole.UserRole + 1)
            # Both should be set and different roles
            assert orig_idx is not None
            assert sort_key is not None
            assert isinstance(orig_idx, int)
            assert isinstance(sort_key, int)


# ── Re-verify Button Tests ──

@pytest.mark.xfail(
    reason="VerifyPanel.reverify_button / reverify_requested removed — "
    "re-verify now uses toolbar Scan action + refresh_requested signal",
)
class TestReverifyButton:
    def test_button_hidden_initially(self):
        """Re-verify button should be hidden before any scan."""
        panel = VerifyPanel()
        assert panel.reverify_button.isHidden()

    def test_button_visible_after_scan(self):
        """Re-verify button should be visible after set_results with components."""
        panel = VerifyPanel()
        comp = _make_component("C1", "100nF", mpn="GRM188R71C104KA01D")
        panel.set_results([comp], {"C1": Confidence.GREEN})
        assert not panel.reverify_button.isHidden()

    def test_button_hidden_after_clear(self):
        """Re-verify button should be hidden after clear()."""
        panel = VerifyPanel()
        comp = _make_component("C1", "100nF", mpn="GRM188R71C104KA01D")
        panel.set_results([comp], {"C1": Confidence.GREEN})
        assert not panel.reverify_button.isHidden()
        panel.clear()
        assert panel.reverify_button.isHidden()

    def test_button_hidden_empty_results(self):
        """Re-verify button should stay hidden with zero components."""
        panel = VerifyPanel()
        panel.set_results([], {})
        assert panel.reverify_button.isHidden()

    def test_reverify_signal_emitted(self):
        """Clicking Re-verify should emit reverify_requested signal."""
        panel = VerifyPanel()
        comp = _make_component("C1", "100nF", mpn="GRM188R71C104KA01D")
        panel.set_results([comp], {"C1": Confidence.GREEN})

        signal_received = []
        panel.reverify_requested.connect(lambda: signal_received.append(True))
        panel.reverify_button.click()
        assert len(signal_received) == 1
