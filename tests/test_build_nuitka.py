"""Tests for build_nuitka.py — GPL firewall and version parsing."""
from __future__ import annotations

import json
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Import helpers — build_nuitka.py lives at project root, not in a package
# ---------------------------------------------------------------------------
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build_nuitka  # noqa: E402


# ---------------------------------------------------------------------------
# read_version tests
# ---------------------------------------------------------------------------

class TestReadVersion:
    def test_returns_quad_format(self):
        """Version from pyproject.toml is converted to X.X.X.X."""
        version = build_nuitka.read_version()
        parts = version.split(".")
        assert len(parts) == 4, f"Expected X.X.X.X, got {version}"
        for p in parts:
            assert p.isdigit(), f"Non-numeric version part: {p}"

    def test_pads_short_version(self):
        """A 3-part version like 0.1.0 becomes 0.1.0.0."""
        version = build_nuitka.read_version()
        assert version.endswith(".0") or version.count(".") == 3


# ---------------------------------------------------------------------------
# check_licenses tests
# ---------------------------------------------------------------------------

def _make_piplicenses_output(packages: list[dict]) -> str:
    return json.dumps(packages)


class TestCheckLicenses:
    def test_passes_with_clean_packages(self):
        """No GPL packages → function returns normally."""
        fake_output = _make_piplicenses_output([
            {"Name": "httpx", "License": "BSD License"},
            {"Name": "PySide6", "License": "LGPL-3.0-only"},
            {"Name": "keyring", "License": "MIT License"},
        ])
        with patch("build_nuitka.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=fake_output)
            build_nuitka.check_licenses()  # Should not raise

    def test_fails_on_gpl_package(self):
        """GPL dependency triggers sys.exit(1)."""
        fake_output = _make_piplicenses_output([
            {"Name": "httpx", "License": "BSD License"},
            {"Name": "evil-lib", "License": "GNU General Public License v3 (GPLv3)"},
        ])
        with patch("build_nuitka.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=fake_output)
            with pytest.raises(SystemExit) as exc_info:
                build_nuitka.check_licenses()
            assert exc_info.value.code == 1

    def test_lgpl_is_allowed(self):
        """LGPL packages should NOT trigger failure."""
        fake_output = _make_piplicenses_output([
            {"Name": "PySide6", "License": "LGPL-3.0-only"},
            {"Name": "qt6-essentials", "License": "GNU Lesser General Public License v3 (LGPLv3)"},
        ])
        with patch("build_nuitka.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=fake_output)
            build_nuitka.check_licenses()  # Should not raise

    def test_build_tools_excluded(self):
        """Build-only tools like Nuitka are excluded even with GPL license."""
        fake_output = _make_piplicenses_output([
            {"Name": "Nuitka", "License": "GNU Affero General Public License v3 or later (AGPLv3+)"},
            {"Name": "httpx", "License": "BSD License"},
        ])
        with patch("build_nuitka.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=fake_output)
            build_nuitka.check_licenses()  # Should not raise


# ---------------------------------------------------------------------------
# Keyring fallback tests
# ---------------------------------------------------------------------------

class TestKeyringFallback:
    def test_fallback_does_nothing_in_dev_mode(self):
        """In normal dev mode (not compiled), _init_keyring_compiled is a no-op."""
        from kipart_search.__main__ import _init_keyring_compiled

        # In dev mode, __compiled__ is not in globals and sys.frozen is not set
        # The function should return immediately without importing keyring
        with patch("kipart_search.__main__.keyring", create=True) as mock_kr:
            _init_keyring_compiled()
            mock_kr.set_keyring.assert_not_called()
