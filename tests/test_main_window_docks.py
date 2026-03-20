"""Tests for QDockWidget migration in MainWindow (Story 1.1)."""

from __future__ import annotations

import sys

import pytest

PySide6 = pytest.importorskip("PySide6", reason="PySide6 required for GUI tests")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QDockWidget, QSizePolicy, QToolBar, QWidget

# Ensure a QApplication exists before any widget tests
app = QApplication.instance() or QApplication(sys.argv)

from kipart_search.core.search import SearchOrchestrator
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

    def test_dock_detail_exists(self, window: MainWindow):
        assert isinstance(window.dock_detail, QDockWidget)

    def test_dock_detail_object_name(self, window: MainWindow):
        assert window.dock_detail.objectName() == "dock_detail"

    def test_dock_log_object_name(self, window: MainWindow):
        assert window.dock_log.objectName() == "dock_log"

    def test_unique_object_names(self, window: MainWindow):
        names = {
            window.dock_verify.objectName(),
            window.dock_search.objectName(),
            window.dock_detail.objectName(),
            window.dock_log.objectName(),
        }
        assert len(names) == 4


class TestDefaultDockPositions:
    """AC #2: Verify docked left, Search docked right, Log docked bottom."""

    def test_verify_docked_left(self, window: MainWindow):
        area = window.dockWidgetArea(window.dock_verify)
        assert area == Qt.DockWidgetArea.LeftDockWidgetArea

    def test_search_docked_right(self, window: MainWindow):
        area = window.dockWidgetArea(window.dock_search)
        assert area == Qt.DockWidgetArea.RightDockWidgetArea

    def test_detail_docked_right_hidden(self, window: MainWindow):
        area = window.dockWidgetArea(window.dock_detail)
        assert area == Qt.DockWidgetArea.RightDockWidgetArea
        assert window.dock_detail.isHidden()

    def test_log_docked_bottom(self, window: MainWindow):
        area = window.dockWidgetArea(window.dock_log)
        assert area == Qt.DockWidgetArea.BottomDockWidgetArea


class TestSplitterRemoved:
    """AC #4: QSplitter fully replaced by QDockWidget containers."""

    def test_no_splitter_attribute(self, window: MainWindow):
        assert not hasattr(window, "_splitter")

    def test_no_search_panel_attribute(self, window: MainWindow):
        assert not hasattr(window, "_search_panel")

    def test_central_widget_is_shrinkable_placeholder(self, window: MainWindow):
        cw = window.centralWidget()
        assert cw is not None
        assert cw.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
        assert cw.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Ignored


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

    def test_scan_btn_removed(self, window: MainWindow):
        """Scan button removed from verify dock — now a toolbar action."""
        assert not hasattr(window, "scan_btn")

    def test_db_btn_removed(self, window: MainWindow):
        """Download Database button removed from search dock — now a menu action."""
        assert not hasattr(window, "db_btn")

    def test_search_target_label_exists(self, window: MainWindow):
        assert window._search_target_label is not None

    def test_status_bar_exists(self, window: MainWindow):
        assert window.status_bar is not None


class TestMenuStructure:
    """File, View, Tools, Help menus with correct ordering."""

    def test_menu_order_file_view_tools_help(self, window: MainWindow):
        menus = [a.text() for a in window.menuBar().actions()]
        assert menus == ["File", "View", "Tools", "Help"]

    def test_file_menu_has_scan_and_download(self, window: MainWindow):
        file_action = [a for a in window.menuBar().actions() if a.text() == "File"][0]
        file_menu = file_action.menu()
        labels = [a.text() for a in file_menu.actions() if not a.isSeparator()]
        assert "Scan Project" in labels
        assert "Download / Refresh Database" in labels

    def test_file_menu_has_close(self, window: MainWindow):
        file_action = [a for a in window.menuBar().actions() if a.text() == "File"][0]
        file_menu = file_action.menu()
        labels = [a.text() for a in file_menu.actions() if not a.isSeparator()]
        assert "Close" in labels

    def test_help_menu_is_last(self, window: MainWindow):
        menus = [a.text() for a in window.menuBar().actions()]
        assert menus[-1] == "Help"

    def test_view_menu_has_toggles_and_reset(self, window: MainWindow):
        view_action = [a for a in window.menuBar().actions() if a.text() == "View"][0]
        view_menu = view_action.menu()
        actions = [a for a in view_menu.actions() if not a.isSeparator()]
        assert len(actions) == 5  # 4 toggles + Reset Layout
        labels = [a.text() for a in actions]
        assert "Reset Layout" in labels

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


class TestToolbar:
    """Story 1.2 AC #1: Fixed QToolBar with 4 actions."""

    def test_toolbar_exists(self, window: MainWindow):
        assert isinstance(window.toolbar, QToolBar)

    def test_toolbar_not_movable(self, window: MainWindow):
        assert not window.toolbar.isMovable()

    def test_toolbar_has_four_actions(self, window: MainWindow):
        actions = window.toolbar.actions()
        assert len(actions) == 4

    def test_toolbar_action_labels(self, window: MainWindow):
        labels = [a.text() for a in window.toolbar.actions()]
        assert labels == ["Scan Project", "Export BOM", "Push to KiCad", "Preferences"]

    def test_export_bom_disabled(self, window: MainWindow):
        assert not window._act_export.isEnabled()

    def test_preferences_enabled(self, window: MainWindow):
        assert window._act_prefs.isEnabled()

    def test_scan_project_enabled(self, window: MainWindow):
        assert window._act_scan.isEnabled()

    def test_push_to_kicad_disabled_standalone(self, window: MainWindow):
        """Push to KiCad disabled when not connected."""
        assert not window._act_push.isEnabled()

    def test_toolbar_has_object_name(self, window: MainWindow):
        """Toolbar needs objectName for QMainWindow::saveState() to work."""
        assert window.toolbar.objectName() == "main_toolbar"


class TestStatusBar3Zones:
    """Story 1.2 AC #2: QStatusBar with 3 zones."""

    def test_mode_label_exists(self, window: MainWindow):
        assert window._mode_label is not None

    def test_sources_label_exists(self, window: MainWindow):
        assert window._sources_label is not None

    def test_action_label_exists(self, window: MainWindow):
        assert window._action_label is not None

    def test_mode_label_standalone_text(self, window: MainWindow):
        assert "Standalone" in window._mode_label.text()

    def test_action_label_default_ready(self, window: MainWindow):
        """Right zone defaults to 'Ready'."""
        # After _update_status in __init__, action_label should still be 'Ready'
        # unless a source was loaded — but the default init sets it
        assert window._action_label.text() == "Ready"

    def test_set_action_status(self, window: MainWindow):
        window._set_action_status("5 results found")
        assert window._action_label.text() == "5 results found"

    def test_sources_label_no_db(self, window: MainWindow):
        """Without a configured source, shows 'No sources configured'."""
        # Force no source — clear both the source reference and the orchestrator
        window._jlcpcb_source = None
        window._orchestrator = SearchOrchestrator(cache=window._cache)
        window._update_status()
        assert window._sources_label.text() == "No sources configured"


class TestResetLayout:
    """Story 1.2 AC #3: Reset Layout restores default dock positions."""

    def test_reset_layout_restores_hidden_dock(self, window: MainWindow):
        window.dock_log.hide()
        assert window.dock_log.isHidden()
        window._reset_layout()
        assert not window.dock_log.isHidden()

    def test_reset_layout_keeps_detail_hidden(self, window: MainWindow):
        """Detail dock is hidden by default, stays hidden after reset."""
        window.dock_detail.show()
        assert not window.dock_detail.isHidden()
        window._reset_layout()
        assert window.dock_detail.isHidden()

    def test_reset_layout_restores_positions(self, window: MainWindow):
        """After reset, docks are in their default areas."""
        window._reset_layout()
        assert window.dockWidgetArea(window.dock_verify) == Qt.DockWidgetArea.LeftDockWidgetArea
        assert window.dockWidgetArea(window.dock_search) == Qt.DockWidgetArea.RightDockWidgetArea
        assert window.dockWidgetArea(window.dock_detail) == Qt.DockWidgetArea.RightDockWidgetArea
        assert window.dockWidgetArea(window.dock_log) == Qt.DockWidgetArea.BottomDockWidgetArea

    def test_reset_layout_unfloats_docks(self, window: MainWindow):
        window.dock_search.setFloating(True)
        window._reset_layout()
        assert not window.dock_search.isFloating()


class TestLayoutPersistence:
    """Story 1.4: QSettings layout persistence."""

    @pytest.fixture(autouse=True)
    def clear_settings(self):
        """Ensure clean QSettings before and after each test."""
        QSettings("kipart-search", "kipart-search").clear()
        yield
        QSettings("kipart-search", "kipart-search").clear()

    def test_close_event_saves_state(self, window: MainWindow):
        """Closing the window saves geometry and windowState to QSettings."""
        window.close()
        settings = QSettings("kipart-search", "kipart-search")
        assert settings.value("geometry") is not None
        assert settings.value("windowState") is not None

    def test_restore_state_on_init(self, window: MainWindow):
        """State saved from one window is restored in a new window."""
        # Save state from current window
        window.close()
        # Create a new window — it should restore without crashing
        w2 = MainWindow()
        settings = QSettings("kipart-search", "kipart-search")
        assert settings.value("geometry") is not None
        w2.close()

    def test_first_launch_no_saved_state(self):
        """With no saved state, window launches with default layout (no crash)."""
        QSettings("kipart-search", "kipart-search").clear()
        w = MainWindow()
        # Default positions should be intact
        assert w.dockWidgetArea(w.dock_verify) == Qt.DockWidgetArea.LeftDockWidgetArea
        assert w.dockWidgetArea(w.dock_search) == Qt.DockWidgetArea.RightDockWidgetArea
        w.close()

    def test_reset_layout_clears_settings(self, window: MainWindow):
        """_reset_layout() clears QSettings so next launch uses defaults."""
        # First, save some state
        window.close()
        settings = QSettings("kipart-search", "kipart-search")
        assert settings.value("geometry") is not None

        # Now create a new window and reset
        w2 = MainWindow()
        w2._reset_layout()
        settings2 = QSettings("kipart-search", "kipart-search")
        assert settings2.value("geometry") is None
        assert settings2.value("windowState") is None
        w2.close()
