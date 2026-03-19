"""Tests for dynamic FilterRow widget (Story 3.1)."""

from __future__ import annotations

import sys

import pytest

PySide6 = pytest.importorskip("PySide6", reason="PySide6 required for GUI tests")

from PySide6.QtWidgets import QApplication

# Ensure a QApplication exists before any widget tests
app = QApplication.instance() or QApplication(sys.argv)

from kipart_search.core.models import PartResult
from kipart_search.gui.results_table import FilterRow, ResultsTable, FILTERABLE_FIELDS


# ── Helpers ──

def _make_parts(*specs: tuple[str, str, str]) -> list[PartResult]:
    """Create PartResult list from (manufacturer, package, category) tuples."""
    return [
        PartResult(mpn=f"MPN-{i}", manufacturer=m, package=p, category=c)
        for i, (m, p, c) in enumerate(specs)
    ]


VARIED_PARTS = _make_parts(
    ("Murata", "0805", "Capacitors"),
    ("Murata", "0402", "Capacitors"),
    ("Samsung", "0805", "Resistors"),
    ("TDK", "0603", "Inductors"),
)

SAME_MFR_PARTS = _make_parts(
    ("Murata", "0805", "Capacitors"),
    ("Murata", "0402", "Resistors"),
)


# ── FilterRow unit tests ──

class TestFilterRowCreation:
    """Test FilterRow creates correct dropdowns from varied PartResult data."""

    def test_creates_dropdowns_for_fields_with_multiple_values(self):
        row = FilterRow()
        row.update_filters(VARIED_PARTS)

        # All three fields have ≥2 unique values
        assert "manufacturer" in row._combos
        assert "package" in row._combos
        assert "category" in row._combos

    def test_dropdown_values_sorted_with_all_default(self):
        row = FilterRow()
        row.update_filters(VARIED_PARTS)

        combo = row._combos["manufacturer"]
        items = [combo.itemText(i) for i in range(combo.count())]
        assert items[0] == "All"
        assert items[1:] == ["Murata", "Samsung", "TDK"]

    def test_excludes_fields_with_less_than_two_unique_values(self):
        row = FilterRow()
        row.update_filters(SAME_MFR_PARTS)

        # Only one manufacturer (Murata) — should not create a dropdown
        assert "manufacturer" not in row._combos
        # Two packages (0805, 0402) — should create dropdown
        assert "package" in row._combos


class TestFilterRowVisibility:
    """Test FilterRow hides when no results / shows when results arrive."""

    def test_hidden_when_no_results(self):
        row = FilterRow()
        row.update_filters([])
        assert row.isHidden()

    def test_visible_when_results_have_filterable_fields(self):
        row = FilterRow()
        row.update_filters(VARIED_PARTS)
        # Use isHidden() — isVisible() requires parent to be shown
        assert not row.isHidden()

    def test_hidden_when_no_field_has_multiple_values(self):
        parts = _make_parts(("Murata", "0805", "Capacitors"))
        row = FilterRow()
        row.update_filters(parts)
        # Single part — no field has ≥2 unique values
        assert row.isHidden()


class TestFilterRowEmptyStrings:
    """Test empty-string values are excluded from dropdown options."""

    def test_empty_values_excluded(self):
        parts = _make_parts(
            ("Murata", "0805", ""),
            ("Samsung", "", ""),
            ("TDK", "0402", ""),
        )
        row = FilterRow()
        row.update_filters(parts)

        # Manufacturer has 3 unique non-empty values → dropdown
        assert "manufacturer" in row._combos
        # Package has 2 unique non-empty values (0805, 0402) → dropdown
        assert "package" in row._combos
        # Category has 0 non-empty values → no dropdown
        assert "category" not in row._combos

    def test_empty_not_in_dropdown_items(self):
        parts = _make_parts(
            ("Murata", "0805", "Caps"),
            ("", "0402", "Res"),
            ("TDK", "", "Caps"),
        )
        row = FilterRow()
        row.update_filters(parts)

        mfr_combo = row._combos["manufacturer"]
        items = [mfr_combo.itemText(i) for i in range(mfr_combo.count())]
        assert "" not in items


class TestFilterRowSignal:
    """Test filters_changed signal emits when dropdown selection changes."""

    def test_signal_emits_on_selection_change(self):
        row = FilterRow()
        row.update_filters(VARIED_PARTS)

        received = []
        row.filters_changed.connect(lambda: received.append(True))

        row._combos["manufacturer"].setCurrentIndex(1)
        assert len(received) == 1

    def test_no_signal_during_update_filters(self):
        row = FilterRow()
        received = []
        row.filters_changed.connect(lambda: received.append(True))

        row.update_filters(VARIED_PARTS)
        assert len(received) == 0


class TestGetActiveFilters:
    """Test get_active_filters returns correct dict."""

    def test_returns_empty_when_all_selected(self):
        row = FilterRow()
        row.update_filters(VARIED_PARTS)
        assert row.get_active_filters() == {}

    def test_returns_selected_filter(self):
        row = FilterRow()
        row.update_filters(VARIED_PARTS)
        row._combos["manufacturer"].setCurrentText("Murata")

        active = row.get_active_filters()
        assert active == {"manufacturer": "Murata"}

    def test_returns_multiple_active_filters(self):
        row = FilterRow()
        row.update_filters(VARIED_PARTS)
        row._combos["manufacturer"].setCurrentText("Murata")
        row._combos["package"].setCurrentText("0805")

        active = row.get_active_filters()
        assert active == {"manufacturer": "Murata", "package": "0805"}


# ── ResultsTable integration tests ──

class TestResultsTableFiltering:
    """Test _apply_filters hides/shows correct rows with multi-field filtering."""

    def test_filter_hides_non_matching_rows(self):
        widget = ResultsTable()
        widget.set_results(VARIED_PARTS)

        # Select Murata → should show 2 of 4
        widget._filter_row._combos["manufacturer"].setCurrentText("Murata")

        visible = sum(
            not widget.table.isRowHidden(r)
            for r in range(widget.table.rowCount())
        )
        assert visible == 2

    def test_additive_filters(self):
        widget = ResultsTable()
        widget.set_results(VARIED_PARTS)

        # Murata + 0805 → only 1 match
        widget._filter_row._combos["manufacturer"].setCurrentText("Murata")
        widget._filter_row._combos["package"].setCurrentText("0805")

        visible = sum(
            not widget.table.isRowHidden(r)
            for r in range(widget.table.rowCount())
        )
        assert visible == 1

    def test_all_filter_shows_all_rows(self):
        widget = ResultsTable()
        widget.set_results(VARIED_PARTS)

        # Filter then reset
        widget._filter_row._combos["manufacturer"].setCurrentText("Murata")
        widget._filter_row._combos["manufacturer"].setCurrentText("All")

        visible = sum(
            not widget.table.isRowHidden(r)
            for r in range(widget.table.rowCount())
        )
        assert visible == 4

    def test_count_label_updates(self):
        widget = ResultsTable()
        widget.set_results(VARIED_PARTS)

        # All visible initially
        assert widget._filter_row._count_label.text() == "4 results"

        # Filter to 2
        widget._filter_row._combos["manufacturer"].setCurrentText("Murata")
        assert widget._filter_row._count_label.text() == "2 of 4 results"

    def test_count_label_zero_visible(self):
        widget = ResultsTable()
        widget.set_results(VARIED_PARTS)

        # Murata + 0603 → no match (Murata has 0805/0402, TDK has 0603)
        widget._filter_row._combos["manufacturer"].setCurrentText("Murata")
        widget._filter_row._combos["package"].setCurrentText("0603")
        assert widget._filter_row._count_label.text() == "0 of 4 results"

    def test_filter_row_resets_on_new_results(self):
        widget = ResultsTable()
        widget.set_results(VARIED_PARTS)

        # Apply a filter
        widget._filter_row._combos["manufacturer"].setCurrentText("Murata")

        # New search results → filters should reset
        new_parts = _make_parts(
            ("Vishay", "0603", "Resistors"),
            ("Yageo", "0402", "Resistors"),
        )
        widget.set_results(new_parts)

        # Old filter gone, new dropdowns created
        assert "manufacturer" in widget._filter_row._combos
        assert widget._filter_row._combos["manufacturer"].currentText() == "All"
        # Category only has 1 unique value → no dropdown
        assert "category" not in widget._filter_row._combos

    def test_clear_results_hides_filter_row(self):
        widget = ResultsTable()
        widget.set_results(VARIED_PARTS)
        # Use isHidden() — isVisible() requires parent to be shown
        assert not widget._filter_row.isHidden()

        widget.clear_results()
        assert widget._filter_row.isHidden()
        assert widget._filter_row._count_label.text() == ""
