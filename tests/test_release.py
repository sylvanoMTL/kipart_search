"""Tests for release.py — version gate, fail-fast, checksums, CLI flags."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import helper — release.py lives at project root, not in a package
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import release  # noqa: E402


# ---------------------------------------------------------------------------
# Version gate tests
# ---------------------------------------------------------------------------

class TestVersionGate:
    def test_refuses_when_version_matches_latest_tag(self):
        """Build should be refused when version matches latest GitHub release."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tag_name": "v0.1.0"}
        mock_response.raise_for_status = MagicMock()

        with patch("release.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            mock_httpx.HTTPError = Exception
            with pytest.raises(SystemExit) as exc_info:
                release.check_version_gate("0.1.0")
            assert exc_info.value.code == 1

    def test_passes_when_version_is_newer(self):
        """Build should proceed when version differs from latest release."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tag_name": "v0.1.0"}
        mock_response.raise_for_status = MagicMock()

        with patch("release.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            mock_httpx.HTTPError = Exception
            # Should not raise
            release.check_version_gate("0.2.0")

    def test_passes_when_no_releases_exist(self):
        """404 from GitHub means no releases — version gate passes."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("release.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            mock_httpx.HTTPError = Exception
            # Should not raise
            release.check_version_gate("0.1.0")

    def test_warns_on_network_error(self, capsys):
        """Network errors are warnings, not blockers."""
        with patch("release.httpx") as mock_httpx:
            mock_httpx.HTTPError = Exception
            mock_httpx.get.side_effect = Exception("Connection refused")
            # Should not raise — just warn
            release.check_version_gate("0.1.0")
            captured = capsys.readouterr()
            assert "WARNING" in captured.out


# ---------------------------------------------------------------------------
# Fail-fast tests
# ---------------------------------------------------------------------------

class TestFailFast:
    def test_test_failure_exits_before_gpl_check(self, monkeypatch):
        """If pytest fails, release.py exits before reaching GPL check."""
        monkeypatch.setattr("sys.argv", ["release.py", "--skip-version-gate"])
        with patch("release.subprocess.run") as mock_run, \
             patch("release.check_version_gate"), \
             patch("release.check_licenses") as mock_gpl, \
             patch("release.read_base_version", return_value="0.1.0"):
            mock_run.return_value = MagicMock(returncode=1)
            with pytest.raises(SystemExit) as exc_info:
                release.main()
            assert exc_info.value.code == 1
            mock_gpl.assert_not_called()


# ---------------------------------------------------------------------------
# Checksum generation tests
# ---------------------------------------------------------------------------

class TestChecksums:
    def test_generates_correct_checksums(self, tmp_path):
        """SHA256 checksums match actual file content."""
        import hashlib

        version = "1.2.3"
        zip_file = tmp_path / f"kipart-search-{version}-windows.zip"
        exe_file = tmp_path / f"kipart-search-{version}-setup.exe"
        zip_file.write_bytes(b"ZIP_CONTENT_HERE")
        exe_file.write_bytes(b"EXE_CONTENT_HERE")

        release.generate_checksums(str(tmp_path), version)

        checksum_file = tmp_path / f"checksums-{version}-sha256.txt"
        assert checksum_file.exists()
        content = checksum_file.read_text(encoding="utf-8")

        # Verify each line has correct format and hash
        lines = content.strip().split("\n")
        assert len(lines) == 2

        for line in lines:
            sha256_hash, filename = line.split("  ")
            filepath = tmp_path / filename
            expected_hash = hashlib.sha256(filepath.read_bytes()).hexdigest()
            assert sha256_hash == expected_hash

    def test_checksum_format_sha256sum_compatible(self, tmp_path):
        """Output format uses two-space separator compatible with sha256sum --check."""
        version = "1.0.0"
        zip_file = tmp_path / f"kipart-search-{version}-windows.zip"
        zip_file.write_bytes(b"CONTENT")

        release.generate_checksums(str(tmp_path), version)

        checksum_file = tmp_path / f"checksums-{version}-sha256.txt"
        content = checksum_file.read_text(encoding="utf-8")
        # Each line: 64-char hex + two spaces + filename
        for line in content.strip().split("\n"):
            parts = line.split("  ")
            assert len(parts) == 2
            assert len(parts[0]) == 64  # SHA256 hex digest length

    def test_handles_missing_artifacts_gracefully(self, tmp_path):
        """No crash when artifacts don't exist — just warns."""
        release.generate_checksums(str(tmp_path), "9.9.9")
        # No checksum file should be created
        assert not (tmp_path / "checksums-9.9.9-sha256.txt").exists()


# ---------------------------------------------------------------------------
# CLI flag tests
# ---------------------------------------------------------------------------

class TestCLIFlags:
    def test_skip_tests_flag(self, monkeypatch):
        """--skip-tests skips the pytest step."""
        monkeypatch.setattr("sys.argv", ["release.py", "--skip-tests", "--skip-version-gate"])
        with patch("release.read_base_version", return_value="0.1.0"), \
             patch("release.check_version_gate"), \
             patch("release.run_tests") as mock_tests, \
             patch("release.check_licenses"), \
             patch("release.build"), \
             patch("release.package"), \
             patch("release.compile_installer"), \
             patch("release.generate_checksums"), \
             patch("release.print_checklist"):
            release.main()
            mock_tests.assert_not_called()

    def test_skip_version_gate_flag(self, monkeypatch):
        """--skip-version-gate skips the GitHub API check."""
        monkeypatch.setattr("sys.argv", ["release.py", "--skip-version-gate"])
        with patch("release.read_base_version", return_value="0.1.0"), \
             patch("release.check_version_gate") as mock_gate, \
             patch("release.run_tests"), \
             patch("release.check_licenses"), \
             patch("release.build"), \
             patch("release.package"), \
             patch("release.compile_installer"), \
             patch("release.generate_checksums"), \
             patch("release.print_checklist"):
            release.main()
            mock_gate.assert_not_called()

    def test_output_dir_passed_to_steps(self, monkeypatch):
        """--output-dir is forwarded to build, package, compile_installer, and checksums."""
        monkeypatch.setattr("sys.argv", ["release.py", "--skip-tests", "--skip-version-gate",
                                         "--output-dir", "my_output"])
        with patch("release.read_base_version", return_value="0.1.0"), \
             patch("release.check_version_gate"), \
             patch("release.run_tests"), \
             patch("release.check_licenses"), \
             patch("release.build") as mock_build, \
             patch("release.package") as mock_package, \
             patch("release.compile_installer") as mock_installer, \
             patch("release.generate_checksums") as mock_checksums, \
             patch("release.print_checklist"):
            release.main()
            mock_build.assert_called_once_with(output_dir="my_output")
            mock_package.assert_called_once_with(output_dir="my_output")
            mock_installer.assert_called_once_with(output_dir="my_output")
            mock_checksums.assert_called_once_with("my_output", "0.1.0")

    def test_full_pipeline_order(self, monkeypatch):
        """All steps execute in correct order when no flags are skipped."""
        monkeypatch.setattr("sys.argv", ["release.py"])
        call_order = []

        def track(name):
            def fn(*args, **kwargs):
                call_order.append(name)
            return fn

        with patch("release.read_base_version", return_value="0.1.0"), \
             patch("release.check_version_gate", side_effect=track("version_gate")), \
             patch("release.run_tests", side_effect=track("tests")), \
             patch("release.check_licenses", side_effect=track("gpl")), \
             patch("release.build", side_effect=track("build")), \
             patch("release.package", side_effect=track("package")), \
             patch("release.compile_installer", side_effect=track("installer")), \
             patch("release.generate_checksums", side_effect=track("checksums")), \
             patch("release.print_checklist", side_effect=track("checklist")):
            release.main()

        assert call_order == [
            "version_gate", "tests", "gpl", "build",
            "package", "installer", "checksums", "checklist",
        ]
