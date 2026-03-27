"""Update shim: generates a .bat script to install updates and relaunch the app."""

from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
import time
from pathlib import Path

log = logging.getLogger(__name__)

# Windows process creation flags for detached subprocess
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_DETACHED_PROCESS = 0x00000008

_SHIM_TEMPLATE = r"""@echo off
setlocal

set "INSTALLER={installer_path}"
set "APP_EXE={install_dir}\kipart-search.exe"
set "OLD_EXE={old_exe_path}"

:: Wait for the app to exit (max 30 seconds)
for /L %%i in (1,1,30) do (
    tasklist /FI "IMAGENAME eq kipart-search.exe" 2>NUL | find /I "kipart-search.exe" >NUL
    if ERRORLEVEL 1 goto :install
    timeout /t 1 /nobreak >NUL
)

:install
:: Run installer silently
"%INSTALLER%" /VERYSILENT /SUPPRESSMSGBOXES
if %ERRORLEVEL% NEQ 0 goto :failed

:: Success - relaunch
start "" "%APP_EXE%"
goto :cleanup

:failed
:: Failure - relaunch old exe with error flag
start "" "%OLD_EXE%" --update-failed
goto :cleanup

:cleanup
:: Self-delete
del "%~f0"
"""


_PARTIAL_GLOB = "kipart-search-update-*.partial"
_STALE_SECONDS = 86400  # 24 hours


def cleanup_stale_partial_downloads(temp_dir: Path | None = None) -> None:
    """Delete stale .partial download files from the temp directory.

    Scans for files matching ``kipart-search-update-*.partial`` that are
    older than 24 hours and removes them silently.
    """
    if temp_dir is None:
        temp_dir = Path(tempfile.gettempdir())
    try:
        for p in temp_dir.glob(_PARTIAL_GLOB):
            try:
                age = time.time() - p.stat().st_mtime
                if age > _STALE_SECONDS:
                    p.unlink()
                    log.info("Deleted stale partial download: %s", p)
            except OSError:
                log.debug("Could not remove partial file: %s", p, exc_info=True)
    except OSError:
        log.debug("Could not scan temp dir for partial files", exc_info=True)


def is_compiled_build() -> bool:
    """Return True if running as a compiled Nuitka/frozen binary."""
    return "__compiled__" in globals() or getattr(sys, "frozen", False)


def get_app_exe_path() -> Path:
    """Return the path to the running application executable.

    For compiled builds, sys.executable is the .exe itself.
    For source builds, sys.executable is python.exe (shim not useful).
    """
    return Path(sys.executable).resolve()


def write_update_shim(installer_path: Path, app_exe: Path) -> Path:
    """Generate update.bat in %TEMP% that installs the update and relaunches.

    The shim: (1) waits for kipart-search.exe to exit, (2) runs the installer
    silently, (3) relaunches on success or relaunches with --update-failed on
    failure, (4) deletes itself.
    """
    install_dir = app_exe.parent
    content = _SHIM_TEMPLATE.format(
        installer_path=str(installer_path),
        install_dir=str(install_dir),
        old_exe_path=str(app_exe),
    )
    shim_path = Path(tempfile.gettempdir()) / "kipart-search-update.bat"
    shim_path.write_text(content, encoding="utf-8")
    log.info("Update shim written to %s", shim_path)
    return shim_path


def launch_shim_and_exit(shim_path: Path) -> bool:
    """Launch the update shim as a detached process.

    Returns True if the subprocess was launched successfully.
    The caller (GUI layer) is responsible for calling QApplication.quit().
    """
    if sys.platform != "win32":
        log.warning("Update shim is only supported on Windows")
        return False
    try:
        subprocess.Popen(
            ["cmd.exe", "/c", str(shim_path)],
            creationflags=_CREATE_NEW_PROCESS_GROUP | _DETACHED_PROCESS,
            close_fds=True,
        )
        log.info("Update shim launched: %s", shim_path)
        return True
    except OSError:
        log.exception("Failed to launch update shim")
        return False


# --- Platform stubs (future) ---
# macOS: Generate a .sh script that replaces the .app bundle contents and
#   relaunches via `open -a "KiPart Search"`. The .sh would use `lsof` or
#   `pgrep` to wait for the app process to exit before copying.
# Linux: Generate a .sh script that replaces the AppImage file and relaunches.
#   The .sh would wait for the process to exit, then `chmod +x` the new
#   AppImage and execute it.
