"""Update shim: launch the downloaded installer and exit the app.

Replaces: src/kipart_search/core/update_shim.py

Cross-Platform Update Architecture
====================================

This module handles the "install" step of the in-app update flow: after the
user downloads an installer/package from GitHub Releases, this module launches
it via the OS shell and lets the installer handle the rest.

Design Decision (2026-03-30) — Why os.startfile() instead of a .bat shim
-------------------------------------------------------------------------
The original Windows implementation used a 4-layer chain:

    Python app → cmd.exe /c → .bat shim (tasklist loop) → PowerShell → Inno Setup

This caused three bugs:

  1. **Visible CMD window on Windows 11**: Windows Terminal intercepts console
     process creation and opens a window despite the CREATE_NO_WINDOW flag.
     The ``tasklist`` command printed "INFO: No tasks are running which match
     the specified criteria." into that visible window.

  2. **Silent installer failure**: PowerShell ``Start-Process -Verb RunAs``
     could fail due to execution policy, nested quoting issues, or UAC
     interactions — with no feedback to the user.

  3. **Redundant process management**: The .bat shim polled ``tasklist`` for
     30 seconds waiting for the app to exit, but Inno Setup already handles
     this via its ``CloseApplications=yes`` setting and the Windows Restart
     Manager.

The fix adopts the same pattern as the working MATLAB reference implementation
(sylvanoMTL/Matlab-Github-New-Release-Checker), which uses a single call to
``winopen(filepath)`` — MATLAB's wrapper around the Win32 ``ShellExecuteW``
API.  Python's equivalent is ``os.startfile()``.

Per-Platform Strategy
---------------------
Each platform uses its native "open this file" mechanism:

+----------+-------------------+---------------------------+------------------------+
| Platform | Python API        | Underlying OS API         | What it does           |
+==========+===================+===========================+========================+
| Windows  | os.startfile()    | ShellExecuteW("open")     | Launches Inno Setup    |
|          |                   |                           | .exe; UAC handled by   |
|          |                   |                           | installer manifest     |
+----------+-------------------+---------------------------+------------------------+
| macOS    | subprocess "open" | NSWorkspace/LaunchServices| Mounts .dmg or opens   |
| (future) |                   |                           | .pkg installer         |
+----------+-------------------+---------------------------+------------------------+
| Linux    | subprocess        | xdg-open / direct replace | Opens .AppImage or     |
| (future) | "xdg-open"        |                           | replaces in place      |
+----------+-------------------+---------------------------+------------------------+

On all platforms, the app then calls ``QApplication.quit()`` to exit
cooperatively.  The installer (or the user) is responsible for closing any
remaining processes and relaunching.

What Inno Setup's Restart Manager Does (Windows)
-------------------------------------------------
The .iss script has ``CloseApplications=yes`` and
``CloseApplicationsFilter=kipart-search.exe``.  When the installer starts:

  1. Inno Setup calls ``RmStartSession()`` + ``RmRegisterResources()`` for
     all files it will replace.
  2. The Restart Manager identifies processes holding those files.
  3. It sends ``WM_CLOSE`` / ``WM_QUERYENDSESSION`` to those processes.
  4. PySide6/Qt handles ``WM_CLOSE`` via ``QApplication.quit()``.
  5. After the process exits, Inno Setup replaces the files.

This works in both interactive and ``/VERYSILENT`` mode.

Removed Components
------------------
The following were present in the original and have been removed:

  - ``_SHIM_TEMPLATE``: ~30-line batch script (tasklist + powershell + relaunch)
  - ``write_update_shim()``: generated .bat file in %TEMP%
  - ``launch_shim_and_exit()``: launched .bat via cmd.exe with CREATE_NO_WINDOW
  - ``get_app_exe_path()``: returned sys.executable (only needed by the shim)
  - ``_CREATE_NEW_PROCESS_GROUP``, ``_DETACHED_PROCESS``, ``_CREATE_NO_WINDOW``:
    Windows process creation flags (no subprocess is created anymore)
  - ``import subprocess``: only ``os`` is needed now (on Windows)
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Partial-download cleanup (runs on every startup)
# ---------------------------------------------------------------------------

_PARTIAL_GLOB = "kipart-search-update-*.partial"
_STALE_SECONDS = 86400  # 24 hours


def cleanup_stale_partial_downloads(temp_dir: Path | None = None) -> None:
    """Delete stale ``.partial`` download files from the temp directory.

    Called once on every startup from ``__main__.py``.  Scans for files
    matching ``kipart-search-update-*.partial`` that are older than 24 hours
    and removes them silently.
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


# ---------------------------------------------------------------------------
# Build detection
# ---------------------------------------------------------------------------


def is_compiled_build() -> bool:
    """Return True if running as a compiled Nuitka/frozen binary.

    Nuitka sets ``__compiled__`` in the module globals.  PyInstaller and
    similar tools set ``sys.frozen``.  Either indicates a standalone binary
    where in-app install via ``launch_installer()`` is meaningful.

    In a source/development build (``python -m kipart_search``),
    ``sys.executable`` points to ``python.exe``, so in-app install makes no
    sense — the user should use pip instead.
    """
    return "__compiled__" in globals() or getattr(sys, "frozen", False)


# ---------------------------------------------------------------------------
# Installer launch — cross-platform
# ---------------------------------------------------------------------------


def launch_installer(installer_path: Path) -> bool:
    """Launch the platform-appropriate installer via the OS shell.

    This is the single entry point for all platforms.  It uses each OS's
    native "open a file" mechanism — the same thing that happens when the
    user double-clicks the file in their file manager.

    Parameters
    ----------
    installer_path : Path
        Absolute path to the downloaded installer/package.
        - Windows: ``kipart-search-X.Y.Z-setup.exe`` (Inno Setup)
        - macOS (future): ``kipart-search-X.Y.Z-macos.dmg``
        - Linux (future): ``kipart-search-X.Y.Z-linux.AppImage``

    Returns
    -------
    bool
        True if the OS accepted the launch request.  Note that this does NOT
        mean the install succeeded — ``os.startfile()`` and ``open`` return
        immediately.  The installer runs asynchronously.

    After this returns True, the caller should call ``QApplication.quit()``
    to exit the app cooperatively.  On Windows, Inno Setup's Restart Manager
    will also close the app if it hasn't exited in time.

    Platform Details
    ----------------
    **Windows** (active):
        ``os.startfile()`` calls ``ShellExecuteW("open", ...)``.  This is the
        exact equivalent of MATLAB's ``winopen()``.  Windows reads the Inno
        Setup .exe's embedded manifest (``requestedExecutionLevel=
        requireAdministrator``) and shows the UAC prompt.  No PowerShell or
        CMD window is involved.

    **macOS** (future):
        ``subprocess.Popen(["open", path])`` uses macOS LaunchServices to
        mount a .dmg (user drags .app to /Applications) or open a .pkg
        (macOS Installer.app runs).

    **Linux** (future):
        ``subprocess.Popen(["xdg-open", path])`` opens the file with the
        desktop-registered handler.  For AppImage files, the user may
        instead need to chmod +x and replace the old binary directly —
        see _linux_replace_appimage() stub below.
    """
    installer = Path(installer_path)
    if not installer.exists():
        log.error("Installer not found: %s", installer)
        return False

    try:
        if sys.platform == "win32":
            # os.startfile() → Win32 ShellExecuteW → same as double-clicking
            # the .exe in Explorer.  This is what MATLAB's winopen() does.
            # UAC elevation is handled by the installer's embedded manifest.
            os.startfile(str(installer))

        elif sys.platform == "darwin":
            # ---------------------------------------------------------------
            # macOS — FUTURE IMPLEMENTATION
            # ---------------------------------------------------------------
            # "open" is the macOS equivalent of ShellExecuteW.
            # For .dmg: Finder mounts the disk image, user drags .app to
            #   /Applications.  No automated install — standard macOS UX.
            # For .pkg: macOS Installer.app opens and walks user through
            #   the install.  No elevation wrapper needed — the .pkg
            #   installer requests admin privileges itself.
            #
            # To enable:
            #   subprocess.Popen(["open", str(installer)])
            #   log.info("Installer opened via 'open': %s", installer)
            #   return True
            # ---------------------------------------------------------------
            log.warning("macOS installer launch not yet implemented")
            return False

        elif sys.platform == "linux":
            # ---------------------------------------------------------------
            # Linux — FUTURE IMPLEMENTATION
            # ---------------------------------------------------------------
            # AppImage: AppImages are self-contained executables, not
            #   installers.  The "update" means replacing the file:
            #     1. Rename current binary → .bak
            #     2. Copy new AppImage → current path
            #     3. chmod +x
            #     4. Relaunch via os.execv()
            #   See _linux_replace_appimage() stub below.
            #
            # .deb/.rpm: xdg-open opens the package manager GUI.
            #   subprocess.Popen(["xdg-open", str(installer)])
            #
            # To enable:
            #   _linux_replace_appimage(installer)
            #   return True
            # ---------------------------------------------------------------
            log.warning("Linux installer launch not yet implemented")
            return False

        else:
            log.warning("Unsupported platform for installer launch: %s", sys.platform)
            return False

        log.info("Installer launched via OS shell: %s", installer)
        return True

    except OSError:
        log.exception("Failed to launch installer")
        return False


# ---------------------------------------------------------------------------
# Linux AppImage replacement — FUTURE STUB
# ---------------------------------------------------------------------------
#
# def _linux_replace_appimage(new_appimage: Path) -> None:
#     """Replace the running AppImage with the new version.
#
#     Linux AppImages are self-contained — there's no installer.
#     The update strategy is: replace the file and relaunch.
#
#     Steps:
#       1. Resolve the path of the currently running binary.
#       2. Rename current → current.bak (so we can roll back on failure).
#       3. Copy new AppImage → current path.
#       4. Set executable permission (chmod +x).
#       5. Relaunch via os.execv() which replaces the current process.
#
#     Note: os.execv() does NOT return — it replaces the process image.
#     If the new binary is corrupt, the user must manually restore the
#     .bak file.  A more robust approach would verify the new binary
#     before replacing (e.g. run it with --version and check exit code).
#     """
#     import shutil
#
#     current_exe = Path(sys.executable).resolve()
#     backup = current_exe.with_suffix(".bak")
#
#     current_exe.rename(backup)
#     shutil.copy2(new_appimage, current_exe)
#     current_exe.chmod(current_exe.stat().st_mode | 0o755)
#
#     # Relaunch — replaces the current process entirely
#     os.execv(str(current_exe), sys.argv)


# ---------------------------------------------------------------------------
# macOS DMG handling — FUTURE STUB
# ---------------------------------------------------------------------------
#
# def _macos_install_dmg(dmg_path: Path) -> bool:
#     """Mount a .dmg and guide the user to drag-install.
#
#     macOS convention: .dmg contains a .app bundle and a symlink to
#     /Applications.  The user drags the .app onto the symlink.
#     This can be automated with:
#       1. hdiutil attach dmg_path → mount point
#       2. cp -R "mount_point/KiPart Search.app" /Applications/
#       3. hdiutil detach mount_point
#     But this bypasses macOS Gatekeeper checks.  It's better to let
#     the user drag-install (Finder handles Gatekeeper naturally) or
#     use a .pkg installer which requests admin privileges.
#     """
#     subprocess.Popen(["open", str(dmg_path)])
#     return True
