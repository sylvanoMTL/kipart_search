"""Tests for DetailPanel widget (Story 1.3)."""

from __future__ import annotations

import sys

import pytest

PySide6 = pytest.importorskip("PySide6", reason="PySide6 required for GUI tests")

from PySide6.QtWidgets import QApplication

# Ensure a QApplication exists before any widget tests
app = QApplication.instance() or QApplication(sys.argv)

from kipart_search.core.models import PartResult, PriceBreak, ParametricValue
from kipart_search.gui.detail_panel import DetailPanel, render_part_html


@pytest.fixture
def panel():
    p = DetailPanel()
    yield p
    p.close()


@pytest.fixture
def sample_part():
    return PartResult(
        mpn="GRM188R71C104KA01D",
        manufacturer="Murata",
        description="100nF 16V X7R 0603",
        package="0603",
        category="Capacitors",
        datasheet_url="https://example.com/datasheet.pdf",
        source="JLCPCB",
        source_part_id="C14663",
        stock=50000,
        specs=[ParametricValue(name="Capacitance", raw_value="100nF")],
        price_breaks=[PriceBreak(quantity=10, unit_price=0.0052, currency="EUR")],
    )


class TestDetailPanelEmptyState:
    """AC #3: Empty state shows guidance text."""

    def test_empty_state_shows_guidance(self, panel: DetailPanel):
        html = panel._browser.toHtml()
        assert "Select a search result to view details" in html

    def test_set_part_none_shows_guidance(self, panel: DetailPanel, sample_part):
        panel.set_part(sample_part)
        panel.set_part(None)
        html = panel._browser.toHtml()
        assert "Select a search result to view details" in html


class TestDetailPanelPartDisplay:
    """AC #1: Detail panel shows part info."""

    def test_set_part_shows_detail(self, panel: DetailPanel, sample_part):
        panel.set_part(sample_part)
        html = panel._browser.toHtml()
        assert "GRM188R71C104KA01D" in html

    def test_set_part_shows_manufacturer(self, panel: DetailPanel, sample_part):
        panel.set_part(sample_part)
        html = panel._browser.toHtml()
        assert "Murata" in html

    def test_set_part_shows_datasheet(self, panel: DetailPanel, sample_part):
        panel.set_part(sample_part)
        html = panel._browser.toHtml()
        assert "https://example.com/datasheet.pdf" in html

    def test_set_part_shows_stock(self, panel: DetailPanel, sample_part):
        panel.set_part(sample_part)
        html = panel._browser.toHtml()
        assert "50,000" in html

    def test_set_part_shows_pricing(self, panel: DetailPanel, sample_part):
        panel.set_part(sample_part)
        html = panel._browser.toHtml()
        assert "0.0052" in html

    def test_set_part_shows_specs(self, panel: DetailPanel, sample_part):
        panel.set_part(sample_part)
        html = panel._browser.toHtml()
        assert "Capacitance" in html
        assert "100nF" in html

    def test_current_part_property(self, panel: DetailPanel, sample_part):
        assert panel.current_part is None
        panel.set_part(sample_part)
        assert panel.current_part is sample_part
        panel.set_part(None)
        assert panel.current_part is None


class TestAssignButton:
    """AC #2: Assign button behaviour."""

    def test_assign_button_hidden_no_target(self, panel: DetailPanel):
        # Widget isn't shown, so check the visibility flag directly
        assert not panel._assign_btn.isVisibleTo(panel)

    def test_assign_button_shows_reference(self, panel: DetailPanel):
        panel.set_assign_target("R14")
        assert panel._assign_btn.isVisibleTo(panel)
        assert panel._assign_btn.text() == "Assign to R14"

    def test_assign_button_hides_on_clear(self, panel: DetailPanel):
        panel.set_assign_target("R14")
        panel.set_assign_target(None)
        assert not panel._assign_btn.isVisibleTo(panel)

    def test_assign_signal_emitted(self, panel: DetailPanel):
        panel.set_assign_target("C1")
        received = []
        panel.assign_requested.connect(lambda: received.append(True))
        panel._assign_btn.click()
        assert len(received) == 1


class TestRenderPartHtml:
    """Unit tests for the render_part_html function."""

    def test_minimal_part(self):
        part = PartResult(mpn="TEST-001")
        html = render_part_html(part)
        assert "TEST-001" in html

    def test_datasheet_link(self, sample_part):
        html = render_part_html(sample_part)
        assert '<a href="https://example.com/datasheet.pdf">' in html

    def test_price_table(self, sample_part):
        html = render_part_html(sample_part)
        assert "Pricing" in html
        assert "0.0052" in html

    def test_specs_table(self, sample_part):
        html = render_part_html(sample_part)
        assert "Parameters" in html
