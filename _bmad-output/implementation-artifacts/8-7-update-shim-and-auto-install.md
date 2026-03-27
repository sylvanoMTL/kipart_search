# Story 8.7: Update Shim and Auto-Install

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want the app to close, install the update silently, and relaunch automatically,
so that updating is seamless — like VS Code or Discord.

## Acceptance Criteria

1. **Given** the installer has been downloaded and verified (Story 8.6), **when** the download completes in the UpdateDialog, **then** an "Install Now" button replaces the current "Open Folder" / "Close" post-download buttons.

2. **Given** the user clicks "Install Now", **when** the dialog prepares for install, **then** a pre-close warning is shown: "Windows will ask for permission to install. Click Yes to continue."

3. **Given** the user confirms the install, **when** the app writes the update shim, **then** an `update.bat` file is written to `%TEMP%` that: (1) waits for `kipart-search.exe` to exit (max 30s polling loop), (2) runs the installer with `/VERYSILENT /SUPPRESSMSGBOXES`, (3) checks the exit code, (4) if success → relaunches `kipart-search.exe` from the install path, (5) if failure → relaunches the old exe with `--update-failed` flag.

4. **Given** the shim `.bat` is written, **when** the app launches it, **then** the app launches the shim via `subprocess.Popen()` (detached, no wait), and exits via `QApplication.quit()`.

5. **Given** the shim runs the Inno Setup installer with `/VERYSILENT /SUPPRESSMSGBOXES`, **when** Windows UAC prompts, **then** the installer runs silently (no wizard UI), upgrades Program Files, and the shim relaunches the app.

6. **Given** the app launches with `--update-failed` flag, **when** the main window appears, **then** a non-modal info dialog shows: "Update could not be completed. The installer may need administrator permission." with [Try Again] and [Download Manually] buttons.

7. **Given** macOS/Linux platforms, **when** the shim logic is called, **then** documented placeholder stubs exist as comments describing the future `.sh`-based approach (not implemented, just documented).

## Tasks / Subtasks

- [x] Task 1: Create `core/update_shim.py` — shim generation and launch logic (AC: #3, #4, #7)
  - [x] 1.1 Create `write_update_shim(installer_path: Path, app_exe: Path) -> Path` function that generates `update.bat` in `%TEMP%` with: process wait loop (30s timeout, `tasklist` polling for `kipart-search.exe`), silent installer invocation (`/VERYSILENT /SUPPRESSMSGBOXES`), exit code check, relaunch logic (success → new exe, failure → old exe with `--update-failed`)
  - [x] 1.2 Create `launch_shim_and_exit(shim_path: Path) -> None` function that launches the `.bat` via `subprocess.Popen()` with `CREATE_NEW_PROCESS_GROUP` and `DETACHED_PROCESS` creation flags, then calls `QApplication.quit()` — import QApplication lazily inside this function to keep core/ GUI-free... WAIT — this must stay GUI-free. The `QApplication.quit()` call must happen in the GUI layer, not here. Instead, have this function just launch the subprocess and return True/False.
  - [x] 1.3 Create `get_app_exe_path() -> Path` that returns the path to the running `kipart-search.exe` — use `sys.executable` for compiled builds, or construct from install dir for source builds
  - [x] 1.4 Add platform stubs as comments for macOS (`.sh` replacing `.app` bundle) and Linux (`.sh` replacing AppImage)

- [x] Task 2: Wire "Install Now" into `gui/update_dialog.py` (AC: #1, #2, #4)
  - [x] 2.1 In `_on_download_finished()`, replace the "Open Folder" / "Close" buttons with "Install Now" and "Open Folder" (keep as fallback) and "Close"
  - [x] 2.2 Add `_on_install_now()` method: show confirmation `QMessageBox.information()` with the UAC warning text, then call `write_update_shim()` and `launch_shim_and_exit()`, then call `QApplication.quit()`
  - [x] 2.3 Handle shim write/launch failure: if either fails, show error with "Open Folder" fallback so user can run installer manually

- [x] Task 3: Handle `--update-failed` flag in `__main__.py` and `main_window.py` (AC: #6)
  - [x] 3.1 In `__main__.py`, detect `--update-failed` in `sys.argv` and pass it through to `run_app()` as a parameter
  - [x] 3.2 In `main_window.py`, if the flag is set, show a non-modal `QMessageBox` after the window is shown with failure message and two buttons: "Try Again" (opens UpdateDialog if update info cached) and "Download Manually" (opens release page in browser)

- [x] Task 4: Generate the `.bat` shim content (AC: #3, #5)
  - [x] 4.1 Write the batch script content with proper escaping. Key elements:
    - `@echo off`
    - Timeout loop: `for /L %%i in (1,1,30) do (tasklist /FI "IMAGENAME eq kipart-search.exe" | find /I "kipart-search.exe" >nul || goto :install) & timeout /t 1 /nobreak >nul`
    - Installer invocation: `"{installer_path}" /VERYSILENT /SUPPRESSMSGBOXES`
    - Exit code check: `if %ERRORLEVEL% NEQ 0 goto :failed`
    - Success relaunch: `start "" "{install_dir}\kipart-search.exe"`
    - Failed relaunch: `start "" "{old_exe}" --update-failed`
    - The `/VERYSILENT` flag suppresses all wizard pages; `/SUPPRESSMSGBOXES` suppresses message boxes. UAC prompt still appears (Windows, not Inno Setup).

- [x] Task 5: Tests (AC: #1-#7)
  - [x] 5.1 Unit test `write_update_shim()` — verify the generated `.bat` file exists, contains expected commands (`/VERYSILENT`, tasklist, installer path, `--update-failed`)
  - [x] 5.2 Unit test `get_app_exe_path()` — verify returns a Path, handles both compiled and source scenarios
  - [x] 5.3 Unit test `launch_shim_and_exit()` — mock `subprocess.Popen`, verify it's called with correct args and creation flags
  - [x] 5.4 Unit test `--update-failed` flag detection in `__main__.py` (or wherever it's parsed)

## Dev Notes

### Architecture: New Core Module + Dialog Extension

This story adds a new `core/update_shim.py` module for the platform-specific shim generation (zero GUI imports) and extends `gui/update_dialog.py` with the install trigger. The `__main__.py` entry point gets `--update-failed` flag detection.

**Core/GUI separation is critical:** The shim generation and subprocess launch live in `core/update_shim.py`. Only the `QApplication.quit()` call and dialog UI changes live in `gui/`.

### Inno Setup Silent Install Flags

The existing `installer/kipart-search.iss` already has `CloseApplications=yes` with `CloseApplicationsFilter=kipart-search.exe`. However, `/VERYSILENT` mode bypasses the Inno Setup UI including the close-apps prompt — so the `.bat` shim must handle process termination timing itself (hence the wait loop).

Key Inno Setup flags:
- `/VERYSILENT` — no installer UI at all (no wizard, no progress bar)
- `/SUPPRESSMSGBOXES` — suppress any message boxes (combined with VERYSILENT)
- Exit code 0 = success. Non-zero = failure (UAC denial returns non-zero).
- The installer uses `AppId={{62ac5603-5867-4e62-9bdf-30df22d7bc2c}` for upgrade detection — it will detect the existing install and upgrade in-place.
- Default install dir: `{autopf}\KiPart Search` → `C:\Program Files\KiPart Search\`

### The .bat Shim Strategy

The shim is a temporary `.bat` file written to `%TEMP%` that orchestrates: wait → install → relaunch. The key challenge is that the app must fully exit before the installer can overwrite its files.

**Process flow:**
```
App writes update.bat to %TEMP%
App launches update.bat (detached subprocess)
App calls QApplication.quit() → process exits
   ↓
update.bat polls for kipart-search.exe exit (max 30s)
update.bat runs installer /VERYSILENT
   ↓ (UAC prompt appears — this is Windows, not Inno Setup)
If installer succeeds → relaunch from install dir
If installer fails → relaunch old exe with --update-failed
update.bat deletes itself (del "%~f0")
```

### Subprocess Launch (Detached)

On Windows, use `subprocess.Popen()` with `CREATE_NEW_PROCESS_GROUP` and `DETACHED_PROCESS` flags so the `.bat` survives the Python process exiting:

```python
import subprocess
import sys

CREATE_NEW_PROCESS_GROUP = 0x00000200
DETACHED_PROCESS = 0x00000008

subprocess.Popen(
    ["cmd.exe", "/c", str(shim_path)],
    creationflags=CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS,
    close_fds=True,
)
```

### get_app_exe_path()

For compiled Nuitka builds: `sys.executable` points to the `.exe` itself (e.g., `C:\Program Files\KiPart Search\kipart-search.exe`).

For source/dev builds: `sys.executable` points to `python.exe`. In this case, the update shim doesn't make sense (dev builds aren't installed via Inno Setup), but the function should still return something reasonable. Use a guard: only enable the Install Now button when `"__compiled__" in globals() or getattr(sys, "frozen", False)`.

### Modifying UpdateDialog Post-Download State

Currently in `update_dialog.py`, `_on_download_finished()` (line 210) hides the initial buttons and shows "Open Folder" + "Close". This story changes it to show "Install Now" + "Open Folder" + "Close", where:
- "Install Now" — triggers the shim flow (only enabled for compiled builds)
- "Open Folder" — kept as fallback for manual install
- "Close" — dismiss dialog

### --update-failed Flag Handling

The `__main__.py` currently only checks for `--version`. Add detection of `--update-failed`:

```python
def main():
    _check_version_flag()
    _migrate_data()
    _init_keyring_compiled()
    update_failed = "--update-failed" in sys.argv
    from kipart_search.gui.main_window import run_app
    return run_app(update_failed=update_failed)
```

In `main_window.py`, `run_app()` currently takes no args. Add the `update_failed` parameter, pass to `MainWindow`, and show a non-modal dialog after `window.show()`:

```python
def run_app(update_failed: bool = False) -> int:
    ...
    window = MainWindow()
    window.show()
    if update_failed:
        window._show_update_failed_dialog()
    return app.exec()
```

### .bat Shim Content Template

```batch
@echo off
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

:: Success — relaunch
start "" "%APP_EXE%"
goto :cleanup

:failed
:: Failure — relaunch old exe with error flag
start "" "%OLD_EXE%" --update-failed
goto :cleanup

:cleanup
:: Self-delete
del "%~f0"
```

### What NOT to Do

- Do NOT use `os.system()` or `subprocess.run()` to launch the shim — must use `subprocess.Popen()` with detached flags so it outlives the parent process.
- Do NOT attempt to kill the app process from the shim — just wait for it to exit naturally (the app calls `QApplication.quit()`).
- Do NOT add SHA256 checksum verification of the installer — that's Story 8.8 scope.
- Do NOT add retry logic for failed installs — that's Story 8.8 scope. The `--update-failed` dialog in this story just shows the error and offers manual download.
- Do NOT use PowerShell for the shim — `.bat` is simpler, more universally available, and doesn't have execution policy issues.
- Do NOT import PySide6 in `core/update_shim.py` — keep it GUI-free.
- Do NOT block the main thread during shim write — it's a tiny file write, but keep the pattern clean.
- Do NOT assume the install directory — read it from `sys.executable` path for compiled builds.

### Existing Patterns to Reuse

| Pattern | Source | What to copy |
|---------|--------|-------------|
| `_DownloadWorker` signals pattern | `gui/update_dialog.py:24-76` | Worker pattern (though shim launch is synchronous, not threaded) |
| Detached subprocess | `gui/update_dialog.py:247` (subprocess.Popen for explorer) | `subprocess.Popen` with creation flags |
| Config read-merge-write | `core/update_check.py:114-128` | `save_update_cache()` pattern if any config persistence needed |
| `__compiled__` check | `__main__.py:20` | `_init_keyring_compiled()` compiled-build detection |
| Dialog post-download buttons | `gui/update_dialog.py:140-153` | Post-download button management to modify |

### Project Structure Notes

**New file:**
- `src/kipart_search/core/update_shim.py` — shim generation, app exe detection, subprocess launch (zero GUI deps)

**Modified files:**
- `src/kipart_search/gui/update_dialog.py` — add "Install Now" button to post-download state, wire to shim
- `src/kipart_search/__main__.py` — detect `--update-failed` flag, pass to `run_app()`
- `src/kipart_search/gui/main_window.py` — accept `update_failed` param in `run_app()`, show failure dialog

**New test file:**
- `tests/core/test_update_shim.py` — shim generation, exe path detection, subprocess launch

### Previous Story Intelligence

**From Story 8.6 (Update Dialog with Download):**
- `UpdateDialog` has a working download-then-show-buttons flow in `_on_download_finished()` — extend this with "Install Now"
- `_downloaded_path` stores the installer file path after download — reuse for shim generation
- The `_DownloadWorker` verifies file size — we can trust the file is valid when `_on_download_finished` fires
- `subprocess.Popen` is already imported in `update_dialog.py` (line 5, used for explorer)
- `update_dialog.py` already imports `tempfile` (line 7) — reuse for shim path

**From Story 8.2 (Inno Setup Installer):**
- Installer is at `installer/kipart-search.iss` with `CloseApplications=yes` and `CloseApplicationsFilter=kipart-search.exe`
- `/VERYSILENT` mode bypasses the close-apps prompt, so our shim must handle timing
- Install dir default: `{autopf}\KiPart Search` → `C:\Program Files\KiPart Search\`
- `AppId` is fixed — upgrades are detected automatically by Inno Setup

**From Story 8.5 (Version Check):**
- `_UpdateCheckWorker` in `main_window.py` (line 213) handles background update checks
- Cached `UpdateInfo` can be reused by the `--update-failed` dialog's "Try Again" button

### Git Intelligence

Recent commits show:
- `ceded7b` — Story 8.5 (version check) committed — `core/update_check.py` is the base module
- `4ec7ab2` — version 0.1.5 — this is the current version string
- Story 8.6 changes are staged but not yet committed (visible in git status)

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.7 — acceptance criteria]
- [Source: src/kipart_search/gui/update_dialog.py — dialog to extend with Install Now]
- [Source: src/kipart_search/core/update_check.py — UpdateInfo dataclass, skip/cache functions]
- [Source: src/kipart_search/gui/main_window.py:213-241 — _UpdateCheckWorker]
- [Source: src/kipart_search/gui/main_window.py:447-456 — eventFilter for update dialog]
- [Source: src/kipart_search/__main__.py — entry point to add --update-failed detection]
- [Source: installer/kipart-search.iss — Inno Setup config, silent install flags, AppId]
- [Source: _bmad-output/implementation-artifacts/8-6-update-dialog-with-download.md — previous story]
- [Source: _bmad-output/project-context.md — coding standards and architecture rules]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

None — clean implementation, no issues encountered.

### Completion Notes List

- Created `core/update_shim.py` with `write_update_shim()`, `launch_shim_and_exit()`, `get_app_exe_path()`, and `is_compiled_build()`. Zero GUI imports, strict core/GUI separation maintained.
- The `.bat` shim template includes: 30s tasklist polling loop, `/VERYSILENT /SUPPRESSMSGBOXES` installer invocation, exit code check, success relaunch from install dir, failure relaunch with `--update-failed` flag, and self-deletion.
- Extended `UpdateDialog._on_download_finished()` to show "Install Now" button (only for compiled builds) alongside existing "Open Folder" and "Close".
- Added `_on_install_now()` with UAC warning confirmation, shim write, shim launch, and `QApplication.quit()`. Failure falls back to "Open Folder" for manual install.
- Added `--update-failed` flag detection in `__main__.py`, passed through to `run_app()`.
- Added `_show_update_failed_dialog()` in `MainWindow` — non-modal warning with "Try Again" (opens UpdateDialog with cached info) and "Download Manually" (opens GitHub releases).
- Platform stubs for macOS (.sh/.app) and Linux (.sh/AppImage) documented as comments in `core/update_shim.py`.
- 12 unit tests: shim content validation, exe path detection, subprocess launch mocking, flag detection. All pass.
- 252 core tests pass with no regressions.

### Change Log

- 2026-03-27: Implemented Story 8.7 — update shim and auto-install (all 5 tasks, 12 tests)

### File List

**New files:**
- `src/kipart_search/core/update_shim.py`
- `tests/core/test_update_shim.py`

**Modified files:**
- `src/kipart_search/gui/update_dialog.py`
- `src/kipart_search/__main__.py`
- `src/kipart_search/gui/main_window.py`
