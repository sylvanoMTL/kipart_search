"""Tests for build_nuitka.py — GPL firewall, version parsing, and packaging."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
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
# _split_license_tokens tests
# ---------------------------------------------------------------------------

class TestSplitLicenseTokens:
    def test_single_license(self):
        assert build_nuitka._split_license_tokens("MIT") == ["MIT"]

    def test_and_combinator(self):
        tokens = build_nuitka._split_license_tokens("LGPL-2.1 AND GPL-2.0")
        assert tokens == ["LGPL-2.1", "GPL-2.0"]

    def test_or_combinator(self):
        tokens = build_nuitka._split_license_tokens("MIT OR APACHE-2.0")
        assert tokens == ["MIT", "APACHE-2.0"]

    def test_semicolon_separator(self):
        tokens = build_nuitka._split_license_tokens("BSD; GPL-3.0")
        assert tokens == ["BSD", "GPL-3.0"]


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
        # Actual pyproject.toml has 0.1.0 → must produce exactly 0.1.0.0
        assert version == "0.1.0.0"

    def test_rejects_non_numeric_version(self, tmp_path):
        """Pre-release tags like 1.0.0rc1 raise ValueError."""
        toml_file = tmp_path / "pyproject.toml"
        toml_file.write_text('[project]\nversion = "1.0.0rc1"\n')
        with patch.object(Path, "__truediv__", return_value=toml_file):
            # __truediv__ is used by Path(__file__).parent / "pyproject.toml"
            pass
        # Simpler: just write a real toml and point read_version at it
        import tomllib
        with patch("builtins.open", return_value=open(toml_file, "rb")):
            with pytest.raises(ValueError, match="not a non-negative integer"):
                build_nuitka.read_version()


# ---------------------------------------------------------------------------
# check_licenses tests
# ---------------------------------------------------------------------------

def _make_piplicenses_output(packages: list[dict]) -> str:
    return json.dumps(packages)


class TestCheckLicenses:
    def test_passes_with_clean_packages(self):
        """No GPL packages -> function returns normally."""
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

    def test_dual_license_with_gpl_detected(self):
        """A dual-license like 'LGPL-2.1 AND GPL-2.0' must flag the GPL token."""
        fake_output = _make_piplicenses_output([
            {"Name": "dual-lib", "License": "LGPL-2.1 AND GPL-2.0"},
        ])
        with patch("build_nuitka.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=fake_output)
            with pytest.raises(SystemExit) as exc_info:
                build_nuitka.check_licenses()
            assert exc_info.value.code == 1

    def test_agpl_detected_when_not_excluded(self):
        """An AGPL package not in BUILD_ONLY triggers the firewall."""
        fake_output = _make_piplicenses_output([
            {"Name": "some-agpl-lib", "License": "AGPL-3.0-only"},
        ])
        with patch("build_nuitka.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=fake_output)
            with pytest.raises(SystemExit) as exc_info:
                build_nuitka.check_licenses()
            assert exc_info.value.code == 1

    def test_piplicenses_failure_gives_clear_error(self):
        """When piplicenses is not installed, error message is actionable."""
        with patch("build_nuitka.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "piplicenses", stderr="No module named piplicenses"
            )
            with pytest.raises(SystemExit) as exc_info:
                build_nuitka.check_licenses()
            assert exc_info.value.code == 1


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

    def test_fallback_sets_keyring_in_compiled_mode(self):
        """When __compiled__ is in module globals, keyring backend is set."""
        import kipart_search.__main__ as main_mod

        mock_keyring = MagicMock()
        mock_backend = MagicMock()

        with patch.dict(main_mod.__dict__, {"__compiled__": True}):
            with patch.dict("sys.modules", {
                "keyring": mock_keyring,
                "keyring.backends.Windows": MagicMock(WinVaultKeyring=mock_backend),
            }):
                with patch.object(main_mod, "keyring", mock_keyring, create=True):
                    # Re-import to pick up the patched modules
                    main_mod._init_keyring_compiled()
                    mock_keyring.set_keyring.assert_called_once()


# ---------------------------------------------------------------------------
# read_base_version tests
# ---------------------------------------------------------------------------

class TestReadBaseVersion:
    def test_returns_raw_version(self):
        """Base version should be the raw string from pyproject.toml (no quad)."""
        version = build_nuitka.read_base_version()
        assert version == "0.1.0"

    def test_matches_init_version(self):
        """Base version from pyproject.toml must match __init__.py __version__."""
        from kipart_search import __version__
        assert build_nuitka.read_base_version() == __version__


# ---------------------------------------------------------------------------
# package() tests — use tmp_path to simulate dist layout
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_dist(tmp_path):
    """Create a fake Nuitka dist folder with a dummy exe."""
    nuitka_dir = tmp_path / "__main__.dist"
    nuitka_dir.mkdir()
    exe = nuitka_dir / "kipart-search.exe"
    exe.write_bytes(b"FAKE_EXE_CONTENT")
    # Add a fake DLL to simulate real output
    (nuitka_dir / "python310.dll").write_bytes(b"FAKE_DLL")
    return tmp_path


class TestPackage:
    def test_creates_zip_with_correct_name(self, fake_dist):
        """Zip file name includes base version."""
        build_nuitka.package(output_dir=str(fake_dist))
        version = build_nuitka.read_base_version()
        zip_path = fake_dist / f"kipart-search-{version}-windows.zip"
        assert zip_path.exists()

    def test_zip_contains_top_level_folder(self, fake_dist):
        """All files in zip are under kipart-search/ prefix."""
        build_nuitka.package(output_dir=str(fake_dist))
        version = build_nuitka.read_base_version()
        zip_path = fake_dist / f"kipart-search-{version}-windows.zip"
        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                assert name.startswith("kipart-search/"), f"Unexpected path: {name}"

    def test_zip_contains_exe(self, fake_dist):
        """kipart-search.exe is at kipart-search/kipart-search.exe in zip."""
        build_nuitka.package(output_dir=str(fake_dist))
        version = build_nuitka.read_base_version()
        zip_path = fake_dist / f"kipart-search-{version}-windows.zip"
        with zipfile.ZipFile(zip_path) as zf:
            assert "kipart-search/kipart-search.exe" in zf.namelist()

    def test_zip_contains_readme(self, fake_dist):
        """README.txt is included in the zip."""
        build_nuitka.package(output_dir=str(fake_dist))
        version = build_nuitka.read_base_version()
        zip_path = fake_dist / f"kipart-search-{version}-windows.zip"
        with zipfile.ZipFile(zip_path) as zf:
            assert "kipart-search/README.txt" in zf.namelist()

    def test_readme_content(self, fake_dist):
        """README.txt has quick start, system requirements, and docs link."""
        build_nuitka.package(output_dir=str(fake_dist))
        readme = fake_dist / "kipart-search" / "README.txt"
        content = readme.read_text(encoding="utf-8")
        assert "Double-click kipart-search.exe" in content
        assert "Windows 10" in content
        assert "github.com/sylvanoMTL/kipart-search" in content

    def test_readme_contains_version(self, fake_dist):
        """README.txt header includes the version."""
        build_nuitka.package(output_dir=str(fake_dist))
        readme = fake_dist / "kipart-search" / "README.txt"
        content = readme.read_text(encoding="utf-8")
        version = build_nuitka.read_base_version()
        assert f"v{version}" in content

    def test_preserves_nuitka_dist(self, fake_dist):
        """__main__.dist/ is NOT modified or deleted by packaging."""
        build_nuitka.package(output_dir=str(fake_dist))
        assert (fake_dist / "__main__.dist" / "kipart-search.exe").exists()

    def test_package_dir_is_separate_copy(self, fake_dist):
        """kipart-search/ folder is created as a copy, not a rename."""
        build_nuitka.package(output_dir=str(fake_dist))
        assert (fake_dist / "__main__.dist").exists()
        assert (fake_dist / "kipart-search").exists()

    def test_prints_zip_size(self, fake_dist, capsys):
        """Zip file size is printed to stdout."""
        build_nuitka.package(output_dir=str(fake_dist))
        captured = capsys.readouterr()
        assert "Zip size:" in captured.out
        assert "MB" in captured.out

    def test_fails_without_build_output(self, tmp_path):
        """package() exits with error if __main__.dist/ doesn't exist."""
        with pytest.raises(SystemExit) as exc_info:
            build_nuitka.package(output_dir=str(tmp_path))
        assert exc_info.value.code == 1

    def test_idempotent_repackage(self, fake_dist):
        """Running package() twice succeeds (cleans up previous kipart-search/)."""
        build_nuitka.package(output_dir=str(fake_dist))
        build_nuitka.package(output_dir=str(fake_dist))
        version = build_nuitka.read_base_version()
        zip_path = fake_dist / f"kipart-search-{version}-windows.zip"
        assert zip_path.exists()


# ---------------------------------------------------------------------------
# main() argument handling tests
# ---------------------------------------------------------------------------

class TestMainArgs:
    def test_package_only_skips_build(self, fake_dist):
        """--package-only runs packaging without calling build()."""
        with patch("build_nuitka.build") as mock_build, \
             patch("build_nuitka.check_licenses") as mock_check:
            sys.argv = ["build_nuitka.py", "--package-only",
                        "--output-dir", str(fake_dist)]
            result = build_nuitka.main()
            assert result == 0
            mock_build.assert_not_called()
            mock_check.assert_not_called()

    def test_package_flag_calls_both(self):
        """--package calls build() then package()."""
        with patch("build_nuitka.build") as mock_build, \
             patch("build_nuitka.package") as mock_package, \
             patch("build_nuitka.check_licenses"):
            sys.argv = ["build_nuitka.py", "--package", "--skip-license-check"]
            result = build_nuitka.main()
            assert result == 0
            mock_build.assert_called_once()
            mock_package.assert_called_once()
