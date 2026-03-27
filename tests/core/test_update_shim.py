"""Tests for core/update_shim.py — shim generation, exe path, subprocess launch."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from kipart_search.core.update_shim import (
    cleanup_stale_partial_downloads,
    get_app_exe_path,
    launch_shim_and_exit,
    write_update_shim,
)


class TestWriteUpdateShim:
    """Test write_update_shim() generates a valid .bat file."""

    def test_shim_file_created(self, tmp_path):
        installer = tmp_path / "setup.exe"
        installer.touch()
        app_exe = Path(r"C:\Program Files\KiPart Search\kipart-search.exe")

        with patch("kipart_search.core.update_shim.tempfile") as mock_temp:
            mock_temp.gettempdir.return_value = str(tmp_path)
            shim = write_update_shim(installer, app_exe)

        assert shim.exists()
        assert shim.suffix == ".bat"

    def test_shim_contains_verysilent(self, tmp_path):
        installer = tmp_path / "setup.exe"
        installer.touch()
        app_exe = Path(r"C:\Program Files\KiPart Search\kipart-search.exe")

        with patch("kipart_search.core.update_shim.tempfile") as mock_temp:
            mock_temp.gettempdir.return_value = str(tmp_path)
            shim = write_update_shim(installer, app_exe)

        content = shim.read_text(encoding="utf-8")
        assert "/VERYSILENT" in content
        assert "/SUPPRESSMSGBOXES" in content

    def test_shim_contains_tasklist_polling(self, tmp_path):
        installer = tmp_path / "setup.exe"
        installer.touch()
        app_exe = Path(r"C:\Program Files\KiPart Search\kipart-search.exe")

        with patch("kipart_search.core.update_shim.tempfile") as mock_temp:
            mock_temp.gettempdir.return_value = str(tmp_path)
            shim = write_update_shim(installer, app_exe)

        content = shim.read_text(encoding="utf-8")
        assert "tasklist" in content
        assert "kipart-search.exe" in content

    def test_shim_contains_installer_path(self, tmp_path):
        installer = tmp_path / "my-installer.exe"
        installer.touch()
        app_exe = Path(r"C:\Program Files\KiPart Search\kipart-search.exe")

        with patch("kipart_search.core.update_shim.tempfile") as mock_temp:
            mock_temp.gettempdir.return_value = str(tmp_path)
            shim = write_update_shim(installer, app_exe)

        content = shim.read_text(encoding="utf-8")
        assert str(installer) in content

    def test_shim_contains_update_failed_flag(self, tmp_path):
        installer = tmp_path / "setup.exe"
        installer.touch()
        app_exe = Path(r"C:\Program Files\KiPart Search\kipart-search.exe")

        with patch("kipart_search.core.update_shim.tempfile") as mock_temp:
            mock_temp.gettempdir.return_value = str(tmp_path)
            shim = write_update_shim(installer, app_exe)

        content = shim.read_text(encoding="utf-8")
        assert "--update-failed" in content


class TestGetAppExePath:
    """Test get_app_exe_path() returns a Path."""

    def test_returns_path(self):
        result = get_app_exe_path()
        assert isinstance(result, Path)

    def test_returns_sys_executable(self):
        result = get_app_exe_path()
        assert result == Path(sys.executable).resolve()


class TestLaunchShimAndExit:
    """Test launch_shim_and_exit() calls subprocess.Popen correctly."""

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only shim")
    def test_calls_popen_with_correct_args(self, tmp_path):
        shim = tmp_path / "update.bat"
        shim.write_text("@echo off", encoding="utf-8")

        with patch("kipart_search.core.update_shim.subprocess.Popen") as mock_popen:
            result = launch_shim_and_exit(shim)

        assert result is True
        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        assert args[0] == ["cmd.exe", "/c", str(shim)]
        # Check creation flags include DETACHED_PROCESS and CREATE_NEW_PROCESS_GROUP
        assert kwargs["creationflags"] == (0x00000200 | 0x00000008)
        assert kwargs["close_fds"] is True

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only shim")
    def test_returns_false_on_os_error(self, tmp_path):
        shim = tmp_path / "update.bat"
        shim.write_text("@echo off", encoding="utf-8")

        with patch(
            "kipart_search.core.update_shim.subprocess.Popen",
            side_effect=OSError("mock"),
        ):
            result = launch_shim_and_exit(shim)

        assert result is False

    def test_returns_false_on_non_windows(self, tmp_path):
        shim = tmp_path / "update.bat"
        shim.write_text("@echo off", encoding="utf-8")

        with patch("kipart_search.core.update_shim.sys") as mock_sys:
            mock_sys.platform = "linux"
            result = launch_shim_and_exit(shim)

        assert result is False


class TestUpdateFailedFlag:
    """Test --update-failed flag detection in __main__.py main()."""

    def test_flag_passed_to_run_app(self):
        with (
            patch("sys.argv", ["kipart-search", "--update-failed"]),
            patch("kipart_search.__main__._check_version_flag"),
            patch("kipart_search.__main__._migrate_data"),
            patch("kipart_search.__main__._init_keyring_compiled"),
            patch("kipart_search.gui.main_window.run_app", return_value=0) as mock_run,
        ):
            from kipart_search.__main__ import main
            main()
            mock_run.assert_called_once_with(update_failed=True)

    def test_flag_not_passed_when_absent(self):
        with (
            patch("sys.argv", ["kipart-search"]),
            patch("kipart_search.__main__._check_version_flag"),
            patch("kipart_search.__main__._migrate_data"),
            patch("kipart_search.__main__._init_keyring_compiled"),
            patch("kipart_search.gui.main_window.run_app", return_value=0) as mock_run,
        ):
            from kipart_search.__main__ import main
            main()
            mock_run.assert_called_once_with(update_failed=False)


class TestCleanupStalePartialDownloads:
    """Test cleanup_stale_partial_downloads() removes old .partial files."""

    def test_deletes_stale_partial_file(self, tmp_path):
        """A .partial file older than 24h should be deleted."""
        import time

        stale = tmp_path / "kipart-search-update-v1.0.0.exe.partial"
        stale.write_bytes(b"data")
        # Backdate mtime to 25 hours ago
        old_time = time.time() - 25 * 3600
        import os
        os.utime(stale, (old_time, old_time))

        cleanup_stale_partial_downloads(tmp_path)

        assert not stale.exists()

    def test_keeps_fresh_partial_file(self, tmp_path):
        """A .partial file less than 24h old should be left alone."""
        fresh = tmp_path / "kipart-search-update-v2.0.0.exe.partial"
        fresh.write_bytes(b"data")

        cleanup_stale_partial_downloads(tmp_path)

        assert fresh.exists()

    def test_ignores_non_matching_files(self, tmp_path):
        """Files not matching the pattern should be left alone."""
        import time

        unrelated = tmp_path / "other-file.partial"
        unrelated.write_bytes(b"data")
        old_time = time.time() - 25 * 3600
        import os
        os.utime(unrelated, (old_time, old_time))

        cleanup_stale_partial_downloads(tmp_path)

        assert unrelated.exists()

    def test_no_crash_on_permission_error(self, tmp_path):
        """Should not raise even if deletion fails."""
        import time

        stale = tmp_path / "kipart-search-update-v1.0.0.exe.partial"
        stale.write_bytes(b"data")
        old_time = time.time() - 25 * 3600
        import os
        os.utime(stale, (old_time, old_time))

        with patch("pathlib.Path.unlink", side_effect=PermissionError("locked")):
            # Should not raise
            cleanup_stale_partial_downloads(tmp_path)

    def test_no_crash_on_empty_dir(self, tmp_path):
        """Empty temp dir should work fine."""
        cleanup_stale_partial_downloads(tmp_path)
