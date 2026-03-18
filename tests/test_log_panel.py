"""Tests for LogPanel widget (Story 1.6)."""

from __future__ import annotations

import sys

import pytest

PySide6 = pytest.importorskip("PySide6", reason="PySide6 required for GUI tests")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

# Ensure a QApplication exists before any widget tests
app = QApplication.instance() or QApplication(sys.argv)

from kipart_search.gui.log_panel import LogPanel


@pytest.fixture
def panel():
    p = LogPanel()
    yield p
    p.close()


def test_log_appends_timestamped_entry(panel):
    """log() should append a line containing [HH:MM:SS] and the message."""
    panel.clear()  # remove the initial "Ready" entry
    panel.log("hello world")
    text = panel._text.toPlainText()
    assert "hello world" in text
    # Timestamp pattern: [HH:MM:SS]
    assert "[" in text and "]" in text


def test_section_appends_separator(panel):
    """section() should append a separator containing the title."""
    panel.clear()
    panel.section("Search")
    text = panel._text.toPlainText()
    assert "Search" in text
    assert "──" in text


def test_clear_removes_all_entries(panel):
    """clear() should empty the log."""
    panel.log("first")
    panel.log("second")
    panel.clear()
    assert panel._text.toPlainText() == ""


def test_log_preserves_previous_entries(panel):
    """Multiple log() calls should accumulate, not overwrite."""
    panel.clear()
    panel.log("alpha")
    panel.log("beta")
    text = panel._text.toPlainText()
    assert "alpha" in text
    assert "beta" in text


def test_context_menu_has_clear_action(panel):
    """The custom context menu should include a 'Clear Log' action."""
    assert (
        panel._text.contextMenuPolicy()
        == Qt.ContextMenuPolicy.CustomContextMenu
    )
    menu = panel._build_context_menu()
    action_texts = [a.text() for a in menu.actions()]
    assert "Clear Log" in action_texts
    menu.deleteLater()
