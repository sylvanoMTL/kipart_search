"""Shared test fixtures."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _isolate_qsettings(tmp_path):
    """Redirect QSettings to a temp directory so tests never touch the real
    Windows registry or pollute state for subsequent tests.

    Uses INI format + tmp_path so every test gets a clean slate.
    """
    try:
        from PySide6.QtCore import QSettings
    except ImportError:
        # PySide6 not installed — skip fixture for core-only tests
        yield
        return

    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path),
    )
    yield
    # No cleanup needed — tmp_path is removed by pytest automatically


@pytest.fixture(autouse=True)
def _skip_welcome_dialog():
    """Prevent the welcome dialog from blocking during MainWindow tests."""
    with patch(
        "kipart_search.gui.main_window.MainWindow._check_welcome",
        return_value=None,
    ):
        yield


@pytest.fixture(autouse=True)
def _reset_license_singleton():
    """Reset the License singleton between tests so tier state doesn't leak.

    Blocks keyring and env var reads during reset so a real cached JWT
    (e.g. from manual dev-key testing) doesn't promote the test to Pro.
    """
    from kipart_search.core.license import License
    with patch("kipart_search.core.license._keyring_get", return_value=None), \
         patch.dict("os.environ", {}, clear=False):
        import os
        os.environ.pop("KIPART_LICENSE_KEY", None)
        License._reset()
        yield
        License._reset()


@pytest.fixture
def pro_license(monkeypatch):
    """Activate Pro license for the duration of a test."""
    from kipart_search.core.license import License
    lic = License.instance()
    monkeypatch.setattr(lic, "_tier", "pro")
    return lic
