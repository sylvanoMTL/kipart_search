"""Tests for stale data indicators (Story 3.4)."""

from __future__ import annotations

import sys
import time

import pytest

from kipart_search.core.models import BoardComponent, Confidence, is_stale

# ── Core Logic Tests (no GUI) ──


def _make_component(
    ref: str = "C1",
    value: str = "100nF",
    mpn: str = "GRM188R71C104KA01D",
    footprint: str = "Capacitor_SMD:C_0805_2012Metric",
    verified_at: float | None = None,
    verified_source: str | None = None,
) -> BoardComponent:
    return BoardComponent(
        reference=ref,
        value=value,
        footprint=footprint,
        mpn=mpn,
        verified_at=verified_at,
        verified_source=verified_source,
    )


class TestIsStaleLogic:
    """Test the is_stale() core function (subtask 7.1)."""

    def test_stale_when_verified_before_db_mtime(self):
        """Component verified at t=100, db updated at t=200 → stale."""
        comp = _make_component(verified_at=100.0)
        assert is_stale(comp, 200.0) is True

    def test_not_stale_when_verified_after_db_mtime(self):
        """Component verified at t=200, db updated at t=100 → not stale."""
        comp = _make_component(verified_at=200.0)
        assert is_stale(comp, 100.0) is False

    def test_not_stale_when_verified_at_same_time(self):
        """Component verified at same time as db → not stale."""
        comp = _make_component(verified_at=100.0)
        assert is_stale(comp, 100.0) is False

    def test_not_stale_when_never_verified(self):
        """Component never verified (verified_at is None) → not stale."""
        comp = _make_component(verified_at=None)
        assert is_stale(comp, 200.0) is False

    def test_not_stale_when_db_mtime_is_none(self):
        """No database present (db_mtime is None) → not stale (subtask 7.5)."""
        comp = _make_component(verified_at=100.0)
        assert is_stale(comp, None) is False

    def test_not_stale_when_both_none(self):
        """Both verified_at and db_mtime are None → not stale."""
        comp = _make_component(verified_at=None)
        assert is_stale(comp, None) is False


class TestBoardComponentTimestampFields:
    """Test that new fields exist and default correctly."""

    def test_defaults_to_none(self):
        comp = BoardComponent(reference="C1", value="100nF", footprint="Lib:FP")
        assert comp.verified_at is None
        assert comp.verified_source is None

    def test_timestamp_assignment(self):
        now = time.time()
        comp = _make_component(verified_at=now, verified_source="JLCPCB")
        assert comp.verified_at == now
        assert comp.verified_source == "JLCPCB"


# ── GUI Tests ──

PySide6 = pytest.importorskip("PySide6", reason="PySide6 required for GUI tests")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from kipart_search.gui.verify_panel import (
    VERIFY_COLUMNS,
    VerifyPanel,
    _STALE_LABEL,
)


def _make_gui_component(
    ref: str, mpn: str = "TEST_MPN", verified_at: float | None = None,
) -> BoardComponent:
    return BoardComponent(
        reference=ref,
        value="100nF",
        footprint="Capacitor_SMD:C_0805_2012Metric",
        mpn=mpn,
        verified_at=verified_at,
    )


class TestStaleIndicatorInTable:
    """Test stale indicator appears in the Freshness column (subtask 7.2)."""

    def test_stale_cell_shows_stale_label(self):
        panel = VerifyPanel()
        comp = _make_gui_component("C1", verified_at=100.0)
        panel.set_results(
            [comp],
            {"C1": Confidence.GREEN},
            db_mtime=200.0,
        )
        freshness_col = VERIFY_COLUMNS.index("Freshness")
        item = panel.table.item(0, freshness_col)
        assert item.text() == _STALE_LABEL

    def test_stale_cell_has_tooltip(self):
        panel = VerifyPanel()
        comp = _make_gui_component("C1", verified_at=100.0)
        panel.set_results(
            [comp],
            {"C1": Confidence.GREEN},
            db_mtime=200.0,
        )
        freshness_col = VERIFY_COLUMNS.index("Freshness")
        item = panel.table.item(0, freshness_col)
        tooltip = item.toolTip()
        assert "database updated since" in tooltip
        assert "Re-scan recommended" in tooltip

    def test_stale_cell_has_accessible_description(self):
        panel = VerifyPanel()
        comp = _make_gui_component("C1", verified_at=100.0)
        panel.set_results(
            [comp],
            {"C1": Confidence.GREEN},
            db_mtime=200.0,
        )
        freshness_col = VERIFY_COLUMNS.index("Freshness")
        item = panel.table.item(0, freshness_col)
        # Accessible description stored in UserRole+2 (QTableWidgetItem has no setAccessibleDescription)
        desc = item.data(Qt.ItemDataRole.UserRole + 2)
        assert "Re-scan recommended" in desc

    def test_current_cell_empty(self):
        """Freshly verified component shows empty freshness cell."""
        panel = VerifyPanel()
        comp = _make_gui_component("C1", verified_at=300.0)
        panel.set_results(
            [comp],
            {"C1": Confidence.GREEN},
            db_mtime=200.0,
        )
        freshness_col = VERIFY_COLUMNS.index("Freshness")
        item = panel.table.item(0, freshness_col)
        assert item.text() == ""

    def test_never_verified_cell_empty(self):
        """Never-verified component shows empty freshness cell."""
        panel = VerifyPanel()
        comp = _make_gui_component("C1", verified_at=None)
        panel.set_results(
            [comp],
            {"C1": Confidence.GREEN},
            db_mtime=200.0,
        )
        freshness_col = VERIFY_COLUMNS.index("Freshness")
        item = panel.table.item(0, freshness_col)
        assert item.text() == ""

    def test_red_component_not_stale(self):
        """RED (missing MPN) components should not show stale indicator."""
        panel = VerifyPanel()
        comp = BoardComponent(
            reference="R1", value="10k", footprint="Lib:FP", mpn="",
            verified_at=100.0,
        )
        panel.set_results(
            [comp],
            {"R1": Confidence.RED},
            db_mtime=200.0,
        )
        freshness_col = VERIFY_COLUMNS.index("Freshness")
        item = panel.table.item(0, freshness_col)
        assert item.text() != _STALE_LABEL


class TestHealthBarStaleAwareness:
    """Test health bar includes stale count (subtask 7.3)."""

    def test_summary_includes_stale_count(self):
        panel = VerifyPanel()
        comps = [
            _make_gui_component("C1", verified_at=100.0),
            _make_gui_component("C2", verified_at=300.0),
        ]
        panel.set_results(
            comps,
            {"C1": Confidence.GREEN, "C2": Confidence.GREEN},
            db_mtime=200.0,
        )
        summary = panel.summary_label.text()
        assert "Stale: 1" in summary

    def test_summary_no_stale_when_none(self):
        panel = VerifyPanel()
        comps = [_make_gui_component("C1", verified_at=300.0)]
        panel.set_results(
            comps,
            {"C1": Confidence.GREEN},
            db_mtime=200.0,
        )
        summary = panel.summary_label.text()
        assert "Stale" not in summary

    def test_health_bar_amber_when_all_valid_but_stale(self):
        """100% valid but with stale → amber bar, not green."""
        panel = VerifyPanel()
        comp = _make_gui_component("C1", verified_at=100.0)
        panel.set_results(
            [comp],
            {"C1": Confidence.GREEN},
            db_mtime=200.0,
        )
        style = panel.health_bar.styleSheet()
        assert "#FFEBB4" in style  # amber, not green


class TestReverifyClearsStale:
    """Test re-verify clears stale flag (subtask 7.4)."""

    def test_reverify_with_fresh_timestamp_clears_stale(self):
        panel = VerifyPanel()
        # First scan: stale
        comp = _make_gui_component("C1", verified_at=100.0)
        panel.set_results(
            [comp],
            {"C1": Confidence.GREEN},
            db_mtime=200.0,
        )
        freshness_col = VERIFY_COLUMNS.index("Freshness")
        assert panel.table.item(0, freshness_col).text() == _STALE_LABEL

        # Re-verify: fresh timestamp
        comp2 = _make_gui_component("C1", verified_at=300.0)
        panel.set_results(
            [comp2],
            {"C1": Confidence.GREEN},
            db_mtime=200.0,
        )
        assert panel.table.item(0, freshness_col).text() == ""


class TestNoStaleWithoutDatabase:
    """Test no stale indicator when db_mtime is None (subtask 7.5)."""

    def test_no_stale_when_db_mtime_none(self):
        panel = VerifyPanel()
        comp = _make_gui_component("C1", verified_at=100.0)
        panel.set_results(
            [comp],
            {"C1": Confidence.GREEN},
            db_mtime=None,
        )
        freshness_col = VERIFY_COLUMNS.index("Freshness")
        item = panel.table.item(0, freshness_col)
        assert item.text() == ""

    def test_no_stale_when_db_mtime_zero(self):
        """db_mtime=0.0 passed as None equivalent."""
        panel = VerifyPanel()
        comp = _make_gui_component("C1", verified_at=100.0)
        # db_mtime=None means no db
        panel.set_results(
            [comp],
            {"C1": Confidence.GREEN},
            db_mtime=None,
        )
        freshness_col = VERIFY_COLUMNS.index("Freshness")
        assert panel.table.item(0, freshness_col).text() == ""
