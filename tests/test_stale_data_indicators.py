"""Tests for stale data indicators (Story 3.4)."""

from __future__ import annotations

import time

from kipart_search.core.models import BoardComponent, is_stale

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


