"""Shared test fixtures."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _skip_welcome_dialog():
    """Prevent the welcome dialog from blocking during MainWindow tests."""
    with patch(
        "kipart_search.gui.main_window.MainWindow._check_welcome",
        return_value=None,
    ):
        yield
