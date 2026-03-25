"""Tests for Story 9.1: User Verification Status in verify_panel."""

from __future__ import annotations

import sys

import pytest

PySide6 = pytest.importorskip("PySide6", reason="PySide6 required for GUI tests")

from PySide6.QtWidgets import QApplication

# Ensure a QApplication exists before any widget tests
app = QApplication.instance() or QApplication(sys.argv)

from kipart_search.core.models import (
    BoardComponent,
    Confidence,
    UserVerificationStatus,
)
from kipart_search.gui.verify_panel import (
    VERIFY_COLUMNS,
    VerifyPanel,
    _REVIEW_COLORS,
    _REVIEW_LABELS,
)


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
                mpn="GRM21BR71C104KA01L" if has else "",
            )
        )
    return comps


def _make_statuses(comps: list[BoardComponent]) -> dict[str, Confidence]:
    return {
        c.reference: Confidence.GREEN if c.has_mpn else Confidence.RED
        for c in comps
    }


class TestReviewColumnPresent:
    """The Review column exists in VERIFY_COLUMNS."""

    def test_review_column_in_columns(self):
        assert "Review" in VERIFY_COLUMNS

    def test_review_column_between_mpn_status_and_footprint(self):
        idx = VERIFY_COLUMNS.index("Review")
        assert VERIFY_COLUMNS[idx - 1] == "MPN Status"
        assert VERIFY_COLUMNS[idx + 1] == "Footprint"


class TestReviewColumnRendering:
    """Review column shows correct text and colors."""

    def test_empty_review_by_default(self):
        panel = VerifyPanel()
        comps = _make_components(3, mpn_count=3)
        panel.set_results(comps, _make_statuses(comps))

        review_col = VERIFY_COLUMNS.index("Review")
        for row in range(panel.table.rowCount()):
            item = panel.table.item(row, review_col)
            assert item.text() == ""
        panel.close()

    def test_review_column_shows_status_after_set(self):
        panel = VerifyPanel()
        comps = _make_components(3, mpn_count=3)
        user_statuses = {"C1": UserVerificationStatus.VERIFIED}
        panel.set_results(
            comps, _make_statuses(comps), user_statuses=user_statuses
        )

        review_col = VERIFY_COLUMNS.index("Review")
        # Find C1's row (table may be sorted)
        found = False
        for row in range(panel.table.rowCount()):
            ref_item = panel.table.item(row, 0)
            if ref_item and ref_item.text() == "C1":
                review_item = panel.table.item(row, review_col)
                assert review_item.text() == "Verified"
                found = True
                break
        assert found, "C1 row not found in table"
        panel.close()


class TestSetUserStatus:
    """set_user_status() updates visual state and emits signal."""

    def test_set_verified_updates_review_cell(self):
        panel = VerifyPanel()
        comps = _make_components(3, mpn_count=3)
        panel.set_results(comps, _make_statuses(comps))

        signals_received = []
        panel.user_status_changed.connect(
            lambda refs, status: signals_received.append((refs, status))
        )

        panel.set_user_status(["C2"], UserVerificationStatus.VERIFIED)

        review_col = VERIFY_COLUMNS.index("Review")
        for row in range(panel.table.rowCount()):
            ref_item = panel.table.item(row, 0)
            if ref_item and ref_item.text() == "C2":
                review_item = panel.table.item(row, review_col)
                assert review_item.text() == "Verified"
                break

        assert len(signals_received) == 1
        assert signals_received[0][0] == ["C2"]
        assert signals_received[0][1] == UserVerificationStatus.VERIFIED
        panel.close()

    def test_clear_status_resets_cell(self):
        panel = VerifyPanel()
        comps = _make_components(3, mpn_count=3)
        user_statuses = {"C1": UserVerificationStatus.REJECTED}
        panel.set_results(
            comps, _make_statuses(comps), user_statuses=user_statuses
        )

        panel.set_user_status(["C1"], UserVerificationStatus.NONE)

        review_col = VERIFY_COLUMNS.index("Review")
        for row in range(panel.table.rowCount()):
            ref_item = panel.table.item(row, 0)
            if ref_item and ref_item.text() == "C1":
                review_item = panel.table.item(row, review_col)
                assert review_item.text() == ""
                break
        panel.close()

    def test_multi_select_batch_marking(self):
        panel = VerifyPanel()
        comps = _make_components(5, mpn_count=5)
        panel.set_results(comps, _make_statuses(comps))

        panel.set_user_status(
            ["C1", "C2", "C3"], UserVerificationStatus.ATTENTION
        )

        review_col = VERIFY_COLUMNS.index("Review")
        for row in range(panel.table.rowCount()):
            ref_item = panel.table.item(row, 0)
            if ref_item and ref_item.text() in ("C1", "C2", "C3"):
                review_item = panel.table.item(row, review_col)
                assert review_item.text() == "Needs Attention"
        panel.close()


class TestHealthBarWithUserStatus:
    """Health bar respects user review overrides."""

    def test_verified_overrides_red_auto_check(self):
        """User marks a RED component as Verified → counted as healthy."""
        panel = VerifyPanel()
        comps = _make_components(10, mpn_count=5)
        statuses = _make_statuses(comps)
        # C6..C10 are RED (no MPN). Mark C6 as Verified by user.
        user_statuses = {"C6": UserVerificationStatus.VERIFIED}
        panel.set_results(comps, statuses, user_statuses=user_statuses)

        # 5 green from auto + 1 user-verified = 6 healthy out of 10
        assert panel.get_health_percentage() == 60
        panel.close()

    def test_rejected_overrides_green_auto_check(self):
        """User marks a GREEN component as Rejected → counted as unhealthy."""
        panel = VerifyPanel()
        comps = _make_components(10, mpn_count=10)
        statuses = _make_statuses(comps)
        # All 10 are GREEN. Mark C1 as Rejected.
        user_statuses = {"C1": UserVerificationStatus.REJECTED}
        panel.set_results(comps, statuses, user_statuses=user_statuses)

        # 9 healthy out of 10
        assert panel.get_health_percentage() == 90
        panel.close()

    def test_attention_overrides_green_auto_check(self):
        """User marks a GREEN component as Needs Attention → unhealthy."""
        panel = VerifyPanel()
        comps = _make_components(10, mpn_count=10)
        statuses = _make_statuses(comps)
        user_statuses = {"C1": UserVerificationStatus.ATTENTION}
        panel.set_results(comps, statuses, user_statuses=user_statuses)

        assert panel.get_health_percentage() == 90
        panel.close()

    def test_none_status_falls_back_to_auto_check(self):
        """NONE user status uses auto-check logic (no override)."""
        panel = VerifyPanel()
        comps = _make_components(10, mpn_count=5)
        statuses = _make_statuses(comps)
        panel.set_results(comps, statuses)

        # 5 healthy out of 10
        assert panel.get_health_percentage() == 50
        panel.close()

    def test_health_bar_updates_after_set_user_status(self):
        """Health bar recalculates after set_user_status call."""
        panel = VerifyPanel()
        comps = _make_components(10, mpn_count=5)
        statuses = _make_statuses(comps)
        panel.set_results(comps, statuses)

        assert panel.get_health_percentage() == 50

        # Mark 2 missing-MPN components as Verified
        panel.set_user_status(
            ["C6", "C7"], UserVerificationStatus.VERIFIED
        )

        assert panel.get_health_percentage() == 70
        panel.close()


class TestAutoCheckIndependence:
    """Auto-check column remains unchanged when user review is set."""

    def test_auto_check_unchanged_after_user_verified(self):
        panel = VerifyPanel()
        comps = _make_components(3, mpn_count=0)  # All missing MPN
        statuses = _make_statuses(comps)  # All RED

        panel.set_results(comps, statuses)
        panel.set_user_status(["C1"], UserVerificationStatus.VERIFIED)

        # MPN Status column (index 3) should still show "Missing MPN" for C1
        mpn_status_col = VERIFY_COLUMNS.index("MPN Status")
        for row in range(panel.table.rowCount()):
            ref_item = panel.table.item(row, 0)
            if ref_item and ref_item.text() == "C1":
                status_item = panel.table.item(row, mpn_status_col)
                assert status_item.text() == "Missing MPN"
                break
        panel.close()
