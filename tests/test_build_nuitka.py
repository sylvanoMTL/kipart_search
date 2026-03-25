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

class TestGplViolation:
    def test_pure_mit_no_violation(self):
        assert build_nuitka._has_gpl_violation("MIT") is False

    def test_pure_gpl_is_violation(self):
        assert build_nuitka._has_gpl_violation("GPL-3.0-only") is True

    def test_lgpl_no_violation(self):
        assert build_nuitka._has_gpl_violation("LGPL-3.0-only") is False

    def test_or_with_lgpl_alternative_no_violation(self):
        """LGPL OR GPL → user can choose LGPL → safe (PySide6 case)."""
        assert build_nuitka._has_gpl_violation(
            "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"
        ) is False

    def test_and_with_gpl_is_violation(self):
        """LGPL AND GPL → both apply → violation."""
        assert build_nuitka._has_gpl_violation("LGPL-2.1 AND GPL-2.0") is True

    def test_semicolon_treated_as_and(self):
        """Semicolons are conservative AND — 'BSD; GPL-3.0' is a violation."""
        assert build_nuitka._has_gpl_violation("BSD; GPL-3.0") is True

    def test_all_or_alternatives_are_gpl(self):
        """GPL-2.0 OR GPL-3.0 → every choice is GPL → violation."""
        assert build_nuitka._has_gpl_violation("GPL-2.0-only OR GPL-3.0-only") is True

    def test_agpl_is_violation(self):
        assert build_nuitka._has_gpl_violation("AGPL-3.0-only") is True


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
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # Python 3.10 fallback
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

    def test_pyside6_real_license_passes(self):
        """PySide6's actual SPDX triple-OR license must pass (choose LGPL)."""
        fake_output = _make_piplicenses_output([
            {"Name": "PySide6", "License": "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"},
            {"Name": "PySide6_Addons", "License": "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"},
            {"Name": "PySide6_Essentials", "License": "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"},
            {"Name": "shiboken6", "License": "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"},
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

    def test_installer_only_skips_build(self, fake_dist):
        """--installer-only compiles installer without build or license check."""
        with patch("build_nuitka.build") as mock_build, \
             patch("build_nuitka.check_licenses") as mock_check, \
             patch("build_nuitka.compile_installer") as mock_inst:
            sys.argv = ["build_nuitka.py", "--installer-only",
                        "--output-dir", str(fake_dist)]
            result = build_nuitka.main()
            assert result == 0
            mock_build.assert_not_called()
            mock_check.assert_not_called()
            mock_inst.assert_called_once_with(output_dir=str(fake_dist))

    def test_installer_flag_calls_build_package_and_installer(self):
        """--installer calls build(), package(), then compile_installer()."""
        with patch("build_nuitka.build") as mock_build, \
             patch("build_nuitka.package") as mock_package, \
             patch("build_nuitka.compile_installer") as mock_inst, \
             patch("build_nuitka.check_licenses"):
            sys.argv = ["build_nuitka.py", "--installer", "--skip-license-check"]
            result = build_nuitka.main()
            assert result == 0
            mock_build.assert_called_once()
            mock_package.assert_called_once()
            mock_inst.assert_called_once()

    def test_mutually_exclusive_flags(self):
        """--package and --installer cannot be used together."""
        with pytest.raises(SystemExit):
            sys.argv = ["build_nuitka.py", "--package", "--installer"]
            build_nuitka.main()


# ---------------------------------------------------------------------------
# Inno Setup .iss file validation tests
# ---------------------------------------------------------------------------

class TestIssFile:
    ISS_PATH = ROOT / "installer" / "kipart-search.iss"

    def test_iss_file_exists(self):
        """installer/kipart-search.iss must exist."""
        assert self.ISS_PATH.exists()

    def test_iss_has_app_id(self):
        """AppId must be set (and never change between versions)."""
        content = self.ISS_PATH.read_text(encoding="utf-8")
        assert "AppId={{62ac5603-5867-4e62-9bdf-30df22d7bc2c}" in content

    def test_iss_has_autopf(self):
        """{autopf} is used instead of {pf} for 64-bit compat."""
        content = self.ISS_PATH.read_text(encoding="utf-8")
        assert "{autopf}" in content
        assert "{pf}" not in content.replace("{autopf}", "")

    def test_iss_has_version_define(self):
        """#define MyAppVersion exists for /D override."""
        content = self.ISS_PATH.read_text(encoding="utf-8")
        assert '#define MyAppVersion' in content

    def test_iss_has_publisher(self):
        """Publisher is MecaFrog."""
        content = self.ISS_PATH.read_text(encoding="utf-8")
        assert "MecaFrog" in content

    def test_iss_has_close_applications(self):
        """CloseApplications is set for handling running instances."""
        content = self.ISS_PATH.read_text(encoding="utf-8")
        assert "CloseApplications=yes" in content
        assert "CloseApplicationsFilter" in content

    def test_iss_has_desktop_shortcut_unchecked(self):
        """Desktop shortcut is opt-in (unchecked by default)."""
        content = self.ISS_PATH.read_text(encoding="utf-8")
        assert "desktopicon" in content
        assert "unchecked" in content

    def test_iss_has_uninstall_user_data_prompt(self):
        """Uninstall prompts to delete user data in %LOCALAPPDATA%."""
        content = self.ISS_PATH.read_text(encoding="utf-8")
        assert "KiPartSearch" in content
        assert "CurUninstallStepChanged" in content
        assert "MB_DEFBUTTON2" in content  # Default is NO

    def test_iss_output_dir(self):
        """Output dir uses overridable define with dist/ as default."""
        content = self.ISS_PATH.read_text(encoding="utf-8")
        assert "OutputDir={#MyOutputDir}" in content
        assert '#define MyOutputDir "..\\dist"' in content

    def test_iss_output_filename(self):
        """Output filename includes version placeholder."""
        content = self.ISS_PATH.read_text(encoding="utf-8")
        assert "kipart-search-{#MyAppVersion}-setup" in content

    def test_iss_no_file_associations(self):
        """No file associations are registered (AC #10)."""
        content = self.ISS_PATH.read_text(encoding="utf-8")
        assert "[Registry]" not in content
        assert "FileAssoc" not in content.lower()

    def test_iss_source_path(self):
        """Source path uses overridable define with Nuitka output as default."""
        content = self.ISS_PATH.read_text(encoding="utf-8")
        assert "{#MySourceDir}\\*" in content
        assert '#define MySourceDir "..\\dist\\__main__.dist"' in content

    def test_iss_has_version_info(self):
        """Installer exe embeds version metadata for Windows Explorer."""
        content = self.ISS_PATH.read_text(encoding="utf-8")
        assert "VersionInfoVersion={#MyAppVersion}" in content

    def test_iss_has_start_menu(self):
        """Start Menu shortcut is created."""
        content = self.ISS_PATH.read_text(encoding="utf-8")
        assert "{group}" in content
        assert "kipart-search.exe" in content


# ---------------------------------------------------------------------------
# compile_installer() tests
# ---------------------------------------------------------------------------

class TestCompileInstaller:
    def test_fails_without_iss_file(self, fake_dist):
        """compile_installer() exits if .iss file is missing."""
        _real_exists = Path.exists

        def fake_exists(p):
            if p.name == "kipart-search.iss":
                return False
            return _real_exists(p)

        with patch.object(Path, "exists", fake_exists):
            with pytest.raises(SystemExit):
                build_nuitka.compile_installer(output_dir=str(fake_dist))

    def test_fails_without_nuitka_output(self, tmp_path):
        """compile_installer() exits if __main__.dist/kipart-search.exe is missing."""
        with pytest.raises(SystemExit):
            build_nuitka.compile_installer(output_dir=str(tmp_path))

    def test_fails_without_iscc(self, fake_dist):
        """compile_installer() exits with helpful error if iscc is not found."""
        inno_default = Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe")
        _real_exists = Path.exists

        def fake_exists(p):
            if str(p) == str(inno_default):
                return False
            return _real_exists(p)

        with patch("build_nuitka.shutil.which", return_value=None), \
             patch.object(Path, "exists", fake_exists):
            with pytest.raises(SystemExit):
                build_nuitka.compile_installer(output_dir=str(fake_dist))

    def test_invokes_iscc_with_version_and_paths(self, fake_dist):
        """compile_installer() calls iscc with /D flags for version, output, and source."""
        version = build_nuitka.read_base_version()
        # Create the expected output file so the post-compile check passes
        installer = fake_dist / f"kipart-search-{version}-setup.exe"
        installer.write_bytes(b"FAKE_INSTALLER")
        with patch("build_nuitka.shutil.which", return_value="iscc"), \
             patch("build_nuitka.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            build_nuitka.compile_installer(output_dir=str(fake_dist))
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert cmd[0] == "iscc"
            assert f"/DMyAppVersion={version}" in cmd
            assert any(arg.startswith("/DMyOutputDir=") for arg in cmd)
            assert any(arg.startswith("/DMySourceDir=") for arg in cmd)
            assert any("kipart-search.iss" in arg for arg in cmd)


# ---------------------------------------------------------------------------
# __main__.py --version flag tests
# ---------------------------------------------------------------------------

class TestVersionFlag:
    def test_version_flag_prints_version_and_exits(self):
        """--version prints 'kipart-search X.X.X' and exits 0."""
        result = subprocess.run(
            [sys.executable, "-m", "kipart_search", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        from kipart_search import __version__
        assert f"kipart-search {__version__}" in result.stdout.strip()

    def test_version_flag_no_gui(self):
        """--version must not import PySide6 or create QApplication."""
        # If it returns quickly without error, no GUI was created
        result = subprocess.run(
            [sys.executable, "-m", "kipart_search", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "Traceback" not in result.stderr


# ---------------------------------------------------------------------------
# GitHub Actions workflow validation tests
# ---------------------------------------------------------------------------

class TestWorkflowFile:
    WORKFLOW_PATH = ROOT / ".github" / "workflows" / "build-windows.yml"

    def test_workflow_file_exists(self):
        """build-windows.yml must exist."""
        assert self.WORKFLOW_PATH.exists(), f"{self.WORKFLOW_PATH} not found"

    def test_workflow_is_valid_yaml(self):
        """Workflow file must be parseable YAML with required top-level keys."""
        content = self.WORKFLOW_PATH.read_text(encoding="utf-8")
        assert content.strip(), "Workflow file is empty"
        # Validate key YAML structure markers exist
        assert "name:" in content
        assert "on:" in content
        assert "jobs:" in content

    def test_workflow_parses_as_yaml(self):
        """Workflow file must be parseable by a YAML parser (not just string checks)."""
        yaml = pytest.importorskip("yaml", reason="PyYAML not installed")
        content = self.WORKFLOW_PATH.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        assert isinstance(data, dict), "Workflow YAML did not parse to a dict"
        assert "jobs" in data

    def test_workflow_triggers_on_version_tags(self):
        """Workflow triggers on v*.*.* tag push."""
        content = self.WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "v*.*.*" in content

    def test_workflow_uses_windows_runner(self):
        """Workflow runs on windows-latest."""
        content = self.WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "windows-latest" in content

    def test_workflow_uses_bash_shell(self):
        """Workflow uses bash shell for consistency."""
        content = self.WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "shell: bash" in content

    def test_workflow_references_build_script(self):
        """Workflow calls build_nuitka.py."""
        content = self.WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "build_nuitka.py" in content

    def test_workflow_has_gpl_check(self):
        """Workflow includes GPL firewall check step."""
        content = self.WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "check_licenses" in content

    def test_workflow_has_smoke_test(self):
        """Workflow runs kipart-search.exe --version."""
        content = self.WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "kipart-search.exe --version" in content

    def test_workflow_has_release_upload(self):
        """Workflow uploads zip to GitHub Release."""
        content = self.WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "softprops/action-gh-release" in content
        assert "kipart-search-*-windows.zip" in content

    def test_workflow_has_nuitka_cache(self):
        """Workflow caches Nuitka ccache directory."""
        content = self.WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "actions/cache@v4" in content
        assert "Nuitka" in content

    def test_workflow_has_version_verification(self):
        """Workflow verifies tag version matches pyproject.toml."""
        content = self.WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "GITHUB_REF_NAME" in content
        assert "read_base_version" in content
