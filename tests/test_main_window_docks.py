"""Tests for QDockWidget migration in MainWindow (Story 1.1)."""

from __future__ import annotations

import sys

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDockWidget, QWidget

# Ensure a QApplication exists before any widget tests
app = QApplication.instance() or QApplication(sys.argv)

from kipart_search.gui.main_window import MainWindow


@pytest.fixture
def window():
    w = MainWindow()
    yield w
    w.close()


class TestDockWidgetStructure:
    """AC #1: Each panel wrapped in QDockWidget with unique objectName."""

    def test_dock_verify_exists(self, window: MainWindow):
        assert isinstance(window.dock_verify, QDockWidget)

    def test_dock_search_exists(self, window: MainWindow):
        assert isinstance(window.dock_search, QDockWidget)

    def test_dock_log_exists(self, window: MainWindow):
        assert isinstance(window.dock_log, QDockWidget)

    def test_dock_verify_object_name(self, window: MainWindow):
        assert window.dock_verify.objectName() == "dock_verify"

    def test_dock_search_object_name(self, window: MainWindow):
        assert window.dock_search.objectName() == "dock_search"

    def test_dock_log_object_name(self, window: MainWindow):
        assert window.dock_log.objectName() == "dock_log"

    def test_unique_object_names(self, window: MainWindow):
        names = {
            window.dock_verify.objectName(),
            window.dock_search.objectName(),
            window.dock_log.objectName(),
        }
        assert len(names) == 3


class TestDefaultDockPositions:
    """AC #2: Verify docked left, Search docked right, Log docked bottom."""

    def test_verify_docked_left(self, window: MainWindow):
        area = window.dockWidgetArea(window.dock_verify)
        assert area == Qt.DockWidgetArea.LeftDockWidgetArea

    def test_search_docked_right(self, window: MainWindow):
        area = window.dockWidgetArea(window.dock_search)
        assert area == Qt.DockWidgetArea.RightDockWidgetArea

    def test_log_docked_bottom(self, window: MainWindow):
        area = window.dockWidgetArea(window.dock_log)
        assert area == Qt.DockWidgetArea.BottomDockWidgetArea


class TestSplitterRemoved:
    """AC #4: QSplitter fully replaced by QDockWidget containers."""

    def test_no_splitter_attribute(self, window: MainWindow):
        assert not hasattr(window, "_splitter")

    def test_no_search_panel_attribute(self, window: MainWindow):
        assert not hasattr(window, "_search_panel")

    def test_central_widget_is_hidden_placeholder(self, window: MainWindow):
        cw = window.centralWidget()
        assert cw is not None
        assert cw.maximumWidth() == 0
        assert cw.maximumHeight() == 0


class TestPanelWidgetsPreserved:
    """AC #5: Panel widgets remain functionally unchanged."""

    def test_verify_panel_inside_verify_dock(self, window: MainWindow):
        # verify_panel is inside a container widget inside the dock
        assert window.verify_panel.parent() is not None
        assert window.verify_panel.parent().parent() is window.dock_verify

    def test_search_bar_exists(self, window: MainWindow):
        assert window.search_bar is not None

    def test_results_table_exists(self, window: MainWindow):
        assert window.results_table is not None

    def test_log_panel_is_dock_child(self, window: MainWindow):
        assert window.dock_log.widget() is window.log_panel

    def test_scan_btn_in_verify_dock(self, window: MainWindow):
        """Scan Project button is inside the verify dock, not search dock."""
        assert window.scan_btn is not None
        # Walk up parents to find the dock
        parent = window.scan_btn.parent()
        while parent and not isinstance(parent, QDockWidget):
            parent = parent.parent()
        assert parent is window.dock_verify

    def test_db_btn_in_search_dock(self, window: MainWindow):
        """Download Database button is inside the search dock."""
        assert window.db_btn is not None
        parent = window.db_btn.parent()
        while parent and not isinstance(parent, QDockWidget):
            parent = parent.parent()
        assert parent is window.dock_search

    def test_search_target_label_exists(self, window: MainWindow):
        assert window._search_target_label is not None

    def test_status_bar_exists(self, window: MainWindow):
        assert window.status_bar is not None


class TestMenuStructure:
    """File, View, Help menus with correct ordering."""

    def test_menu_order_file_view_help(self, window: MainWindow):
        menus = [a.text() for a in window.menuBar().actions()]
        assert menus == ["File", "View", "Help"]

    def test_file_menu_has_scan_and_download(self, window: MainWindow):
        file_action = [a for a in window.menuBar().actions() if a.text() == "File"][0]
        file_menu = file_action.menu()
        labels = [a.text() for a in file_menu.actions() if not a.isSeparator()]
        assert "Scan Project" in labels
        assert "Download Database" in labels

    def test_file_menu_has_close(self, window: MainWindow):
        file_action = [a for a in window.menuBar().actions() if a.text() == "File"][0]
        file_menu = file_action.menu()
        labels = [a.text() for a in file_menu.actions() if not a.isSeparator()]
        assert "Close" in labels

    def test_help_menu_is_last(self, window: MainWindow):
        menus = [a.text() for a in window.menuBar().actions()]
        assert menus[-1] == "Help"

    def test_view_menu_has_three_toggle_actions(self, window: MainWindow):
        view_action = [a for a in window.menuBar().actions() if a.text() == "View"][0]
        view_menu = view_action.menu()
        actions = [a for a in view_menu.actions() if not a.isSeparator()]
        assert len(actions) == 3

    def test_toggle_action_can_reshow_closed_dock(self, window: MainWindow):
        action = window.dock_search.toggleViewAction()
        window.dock_search.close()
        assert not action.isChecked()
        action.trigger()
        assert action.isChecked()
        assert not window.dock_search.isHidden()


class TestCreateDockHelper:
    """Test the _create_dock() factory method."""

    def test_creates_dock_with_correct_title(self, window: MainWindow):
        widget = QWidget()
        dock = window._create_dock("Test Panel", widget, Qt.DockWidgetArea.LeftDockWidgetArea)
        assert dock.windowTitle() == "Test Panel"
        window.removeDockWidget(dock)

    def test_creates_dock_with_correct_object_name(self, window: MainWindow):
        widget = QWidget()
        dock = window._create_dock("My Widget", widget, Qt.DockWidgetArea.RightDockWidgetArea)
        assert dock.objectName() == "dock_my_widget"
        window.removeDockWidget(dock)

    def test_dock_contains_widget(self, window: MainWindow):
        widget = QWidget()
        dock = window._create_dock("Test", widget, Qt.DockWidgetArea.LeftDockWidgetArea)
        assert dock.widget() is widget
        window.removeDockWidget(dock)
