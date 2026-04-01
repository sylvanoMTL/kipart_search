"""Tests for two-mode search architecture (Story 3.2)."""

from __future__ import annotations

import sys

import pytest

PySide6 = pytest.importorskip("PySide6", reason="PySide6 required for GUI tests")

from PySide6.QtWidgets import QApplication

# Ensure a QApplication exists before any widget tests
app = QApplication.instance() or QApplication(sys.argv)

from kipart_search.core.models import PartResult
from kipart_search.core.search import SearchOrchestrator
from kipart_search.core.sources import DataSource
from kipart_search.gui.results_table import COLUMNS, FILTERABLE_FIELDS, ResultsTable
from kipart_search.gui.search_bar import SearchBar


# ── Helpers ──

def _make_parts(*specs: tuple[str, str, str, str]) -> list[PartResult]:
    """Create PartResult list from (mpn, manufacturer, package, source) tuples."""
    return [
        PartResult(mpn=mpn, manufacturer=m, package=p, source=s)
        for mpn, m, p, s in specs
    ]


class FakeSource(DataSource):
    """Minimal DataSource for testing."""

    def __init__(self, source_name: str, parts: list[PartResult] | None = None):
        self.name = source_name
        self._parts = parts or []
        self._configured = True

    def search(self, query, filters=None, limit=50):
        return self._parts[:limit]

    def get_part(self, mpn, manufacturer=""):
        return next((p for p in self._parts if p.mpn == mpn), None)

    def is_configured(self):
        return self._configured


JLCPCB_PARTS = _make_parts(
    ("C0805C104K5RAC", "KEMET", "0805", "JLCPCB"),
    ("GRM21BR71C104KA01", "Murata", "0805", "JLCPCB"),
)

DIGIKEY_PARTS = _make_parts(
    ("C0805C104K5RAC", "KEMET", "0805", "DigiKey"),
    ("CL21B104KBCNNNC", "Samsung", "0805", "DigiKey"),
)


# ── SearchBar source selector tests ──

class TestSearchBarSourceSelector:
    """Test source selector QComboBox in SearchBar."""

    def test_default_contains_all_sources(self):
        bar = SearchBar()
        assert bar._source_selector.count() == 1
        assert bar._source_selector.itemText(0) == "All Sources"

    def test_set_sources_populates_dropdown(self):
        bar = SearchBar()
        bar.set_sources(["JLCPCB", "DigiKey"])

        items = [bar._source_selector.itemText(i) for i in range(bar._source_selector.count())]
        assert items == ["All Sources", "JLCPCB", "DigiKey"]

    def test_set_sources_preserves_selection(self):
        bar = SearchBar()
        bar.set_sources(["JLCPCB", "DigiKey"])
        bar._source_selector.setCurrentText("DigiKey")

        # Re-set sources (e.g. after DB download) — selection should persist
        bar.set_sources(["JLCPCB", "DigiKey", "Mouser"])
        assert bar.selected_source == "DigiKey"

    def test_set_sources_resets_to_all_if_removed(self):
        bar = SearchBar()
        bar.set_sources(["JLCPCB", "DigiKey"])
        bar._source_selector.setCurrentText("DigiKey")

        # DigiKey removed from sources
        bar.set_sources(["JLCPCB"])
        assert bar.selected_source == "All Sources"

    def test_selected_source_returns_current(self):
        bar = SearchBar()
        bar.set_sources(["JLCPCB"])
        bar._source_selector.setCurrentText("JLCPCB")
        assert bar.selected_source == "JLCPCB"

    def test_selected_source_default_is_all(self):
        bar = SearchBar()
        assert bar.selected_source == "All Sources"


class TestSearchBarSignal:
    """Test SearchBar emits (query, source) on search."""

    def test_emits_query_and_source(self):
        bar = SearchBar()
        bar.set_sources(["JLCPCB"])
        bar._source_selector.setCurrentText("JLCPCB")

        received = []
        bar.search_requested.connect(lambda q, s: received.append((q, s)))

        bar.query_input.setText("100nF")
        bar._on_search()

        assert len(received) == 1
        assert received[0][1] == "JLCPCB"

    def test_emits_all_sources_by_default(self):
        bar = SearchBar()

        received = []
        bar.search_requested.connect(lambda q, s: received.append((q, s)))

        bar.query_input.setText("100nF")
        bar._on_search()

        assert len(received) == 1
        assert received[0][1] == "All Sources"


# ── ResultsTable source column visibility tests ──

class TestResultsTableSourceColumn:
    """Test Source column hide/show in ResultsTable."""

    def test_source_in_columns(self):
        assert "Source" in COLUMNS

    def test_source_in_filterable_fields(self):
        field_names = [attr for _, attr in FILTERABLE_FIELDS]
        assert "source" in field_names

    def test_hide_source_column(self):
        widget = ResultsTable()
        widget.set_source_column_visible(False)
        source_col = COLUMNS.index("Source")
        assert widget.table.isColumnHidden(source_col)

    def test_show_source_column(self):
        widget = ResultsTable()
        widget.set_source_column_visible(True)
        source_col = COLUMNS.index("Source")
        assert not widget.table.isColumnHidden(source_col)

    def test_source_data_stored_when_hidden(self):
        widget = ResultsTable()
        widget.set_source_column_visible(False)
        widget.set_results(JLCPCB_PARTS)

        # Data is still accessible even though column is hidden
        part = widget.get_result(0)
        assert part is not None
        assert part.source == "JLCPCB"

    def test_source_filter_auto_hidden_single_source(self):
        """In Specific mode, all results have same source → filter auto-excluded."""
        widget = ResultsTable()
        widget.set_results(JLCPCB_PARTS)

        # All parts have source="JLCPCB" → < 2 unique values → no Source filter
        assert "source" not in widget._filter_row._combos

    def test_source_filter_shown_multiple_sources(self):
        """In Unified mode with mixed sources, Source filter appears."""
        mixed = JLCPCB_PARTS + DIGIKEY_PARTS
        widget = ResultsTable()
        widget.set_results(mixed)

        # Multiple sources → Source filter should appear
        assert "source" in widget._filter_row._combos


# ── SearchOrchestrator tests ──

class TestSearchOrchestratorSourceRouting:
    """Test SearchOrchestrator.search_source and get_source_names."""

    def test_get_source_names_returns_configured(self):
        orch = SearchOrchestrator()
        orch.add_source(FakeSource("JLCPCB", JLCPCB_PARTS))
        orch.add_source(FakeSource("DigiKey", DIGIKEY_PARTS))

        names = orch.get_source_names()
        assert names == ["JLCPCB", "DigiKey"]

    def test_get_source_names_empty_when_none(self):
        orch = SearchOrchestrator()
        assert orch.get_source_names() == []

    def test_search_source_queries_only_named_source(self, pro_license):
        jlcpcb = FakeSource("JLCPCB", JLCPCB_PARTS)
        digikey = FakeSource("DigiKey", DIGIKEY_PARTS)
        orch = SearchOrchestrator()
        orch.add_source(jlcpcb)
        orch.add_source(digikey)

        results = orch.search_source("100nF", "JLCPCB")
        # Should only return JLCPCB parts
        assert all(r.source == "JLCPCB" for r in results)
        assert len(results) == len(JLCPCB_PARTS)

    def test_search_source_unknown_name_returns_empty(self):
        orch = SearchOrchestrator()
        orch.add_source(FakeSource("JLCPCB", JLCPCB_PARTS))

        results = orch.search_source("100nF", "Mouser")
        assert results == []

    def test_search_all_queries_all_sources(self, pro_license):
        jlcpcb = FakeSource("JLCPCB", JLCPCB_PARTS)
        digikey = FakeSource("DigiKey", DIGIKEY_PARTS)
        orch = SearchOrchestrator()
        orch.add_source(jlcpcb)
        orch.add_source(digikey)

        results = orch.search("100nF")
        # Should have results from both sources
        sources = {r.source for r in results}
        assert "JLCPCB" in sources
        assert "DigiKey" in sources

    def test_get_source_names_excludes_unconfigured(self):
        configured = FakeSource("JLCPCB", JLCPCB_PARTS)
        unconfigured = FakeSource("DigiKey", DIGIKEY_PARTS)
        unconfigured._configured = False

        orch = SearchOrchestrator()
        orch.add_source(configured)
        orch.add_source(unconfigured)

        assert orch.get_source_names() == ["JLCPCB"]
