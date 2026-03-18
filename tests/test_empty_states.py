"""Tests for empty-state guidance text in panels (Story 1.4)."""

from __future__ import annotations

import sys

import pytest

PySide6 = pytest.importorskip("PySide6", reason="PySide6 required for GUI tests")

from PySide6.QtWidgets import QApplication

# Ensure a QApplication exists before any widget tests
app = QApplication.instance() or QApplication(sys.argv)

from kipart_search.gui.verify_panel import VerifyPanel
from kipart_search.gui.results_table import ResultsTable
from kipart_search.gui.log_panel import LogPanel
from kipart_search.gui.detail_panel import DetailPanel


class TestVerifyPanelEmptyState:
    """AC #3: Verify panel shows guidance when empty."""

    def test_initial_guidance_text(self):
        panel = VerifyPanel()
        assert "Scan a project or open a BOM to begin" in panel.summary_label.text()
        panel.close()

    def test_clear_restores_guidance(self):
        panel = VerifyPanel()
        panel.summary_label.setText("Some other text")
        panel.clear()
        assert "Scan a project or open a BOM to begin" in panel.summary_label.text()
        panel.close()


class TestResultsTableEmptyState:
    """AC #3: Results table shows guidance when empty."""

    def test_initial_guidance_html(self):
        table = ResultsTable()
        html = table._detail.toHtml()
        assert "Search for components using the query bar above" in html
        table.close()

    def test_clear_results_restores_guidance(self):
        table = ResultsTable()
        table._detail.setHtml("<p>Something</p>")
        table.clear_results()
        html = table._detail.toHtml()
        assert "Search for components using the query bar above" in html
        table.close()


class TestLogPanelEmptyState:
    """AC #3: Log panel shows 'Ready' as initial entry."""

    def test_initial_ready_entry(self):
        panel = LogPanel()
        text = panel._text.toPlainText()
        assert "Ready" in text
        panel.close()


class TestDetailPanelEmptyState:
    """AC #3: Detail panel guidance — verify existing behaviour still works."""

    def test_initial_guidance(self):
        panel = DetailPanel()
        html = panel._browser.toHtml()
        assert "Select a search result to view details" in html
        panel.close()
