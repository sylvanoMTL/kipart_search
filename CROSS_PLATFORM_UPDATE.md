# KiPart Search — Update Mechanism Fix & Cross-Platform Architecture

## Date: 2026-03-30

---

## Table of Contents

1. [Problem Description](#1-problem-description)
2. [Root Cause Analysis](#2-root-cause-analysis)
3. [Reference Implementation (MATLAB)](#3-reference-implementation-matlab)
4. [Solution: os.startfile()](#4-solution-osstartfile)
5. [Files Changed](#5-files-changed)
6. [Copy Instructions](#6-copy-instructions)
7. [How Inno Setup Restart Manager Works](#7-how-inno-setup-restart-manager-works)
8. [Cross-Platform Strategy](#8-cross-platform-strategy)
9. [Build System Cross-Platform Architecture](#9-build-system-cross-platform-architecture)
10. [CI/CD Multi-Platform Pipeline](#10-cicd-multi-platform-pipeline)
11. [What Can Break on Other Platforms](#11-what-can-break-on-other-platforms)
12. [Recommended Order of Work](#12-recommended-order-of-work)
13. [Testing Checklist](#13-testing-checklist)

---

## 1. Problem Description

### Symptoms

When the user accepts an update in the compiled KiPart Search app:

1. The update downloads successfully.
2. User clicks "Install Now" and confirms.
3. The app closes.
4. A **CMD window pops up** displaying:
   ```
   INFO: No tasks are running which match the specified criteria.
   ```
5. The installer does **not** run (or fails silently).
6. This happens **even with antivirus off and running as administrator**.

### Environment

- App: KiPart Search (Python 3.10+, PySide6)
- Compiler: Nuitka (standalone .exe)
- Installer: Inno Setup 6
- OS: Windows 11
- Terminal: Windows Terminal (default on Windows 11)

---

## 2. Root Cause Analysis

### The original update flow

```
User clicks "Install Now"
    │
    ▼
Python: write_update_shim()          ← Generates a .bat file in %TEMP%
    │
    ▼
Python: launch_shim_and_exit()       ← subprocess.Popen(["cmd.exe", "/c", shim.bat])
    │                                   with CREATE_NO_WINDOW flag
    ▼
Python: QApplication.quit()          ← App exits cooperatively
    │
    ▼
.bat shim: tasklist polling loop     ← Polls every 1s for 30s
    │                                   "Is kipart-search.exe still running?"
    │                                   → App already exited, so tasklist prints:
    │                                     "INFO: No tasks are running which
    │                                      match the specified criteria."
    ▼
.bat shim: powershell Start-Process  ← Launches installer with -Verb RunAs
    │
    ▼
Inno Setup installer                 ← May or may not actually run
```

### Three distinct bugs

#### Bug 1: Visible CMD window on Windows 11

The shim was launched with `CREATE_NO_WINDOW` (flag `0x08000000`):

```python
# File: src/kipart_search/core/update_shim.py, lines 155-159 (ORIGINAL)
subprocess.Popen(
    ["cmd.exe", "/c", str(shim_path)],
    creationflags=_CREATE_NEW_PROCESS_GROUP | _CREATE_NO_WINDOW,
    close_fds=True,
)
```

**Why it fails on Windows 11:**

Windows 11 ships with **Windows Terminal** as the default terminal application.
Windows Terminal hooks into console process creation at the OS level.  When
`cmd.exe` is launched — even with `CREATE_NO_WINDOW` — Windows Terminal may
intercept the creation and open a visible window anyway.

#### Bug 2: "INFO: No tasks are running" message

The .bat shim polls for the app process:

```batch
:: File: update_shim.py _SHIM_TEMPLATE, lines 34-38 (ORIGINAL)
for /L %%i in (1,1,30) do (
    tasklist /FI "IMAGENAME eq kipart-search.exe" 2>NUL | find /I "kipart-search.exe" >NUL
    if ERRORLEVEL 1 goto :install
    timeout /t 1 /nobreak >NUL
)
```

Because the CMD window is visible (Bug 1), the user sees `tasklist`'s output
when no process matches the filter.

#### Bug 3: PowerShell installer launch can fail silently

```batch
:: File: update_shim.py _SHIM_TEMPLATE, line 53 (ORIGINAL)
powershell -NoProfile -Command "Start-Process -FilePath '%INSTALLER%' -ArgumentList '/VERYSILENT /SUPPRESSMSGBOXES /SP-' -Verb RunAs -Wait"
```

This can fail due to PowerShell execution policy, nested quoting issues with
paths containing special characters, or UAC interactions when already elevated.

#### Bug 4 (design): The shim was redundant

The Inno Setup installer script already has:

```ini
CloseApplications=yes
CloseApplicationsFilter=kipart-search.exe
```

These use the **Windows Restart Manager** to close the running app — even in
`/VERYSILENT` mode.  The shim's tasklist polling duplicated this.

---

## 3. Reference Implementation (MATLAB)

### Repository: sylvanoMTL/Matlab-Github-New-Release-Checker

The MATLAB implementation works correctly because it uses a single call:

```matlab
winopen(filepath)    % calls Win32 ShellExecuteW — same as double-clicking
```

No batch script, no PowerShell, no process polling, no CMD window.

### What winopen() / ShellExecuteW does

1. Windows looks up the file association for `.exe`
2. Checks the embedded manifest for `requestedExecutionLevel`
3. Shows UAC prompt if the manifest requests `requireAdministrator`
4. Starts the process with the requested privileges
5. Returns immediately (non-blocking)

### Python equivalent

```python
os.startfile(filepath)  # → Win32 ShellExecuteW("open", filepath, ...)
```

Identical to MATLAB's `winopen()` at the Win32 API level.

---

## 4. Solution: os.startfile()

### Before (4 layers of indirection)

```
Python → cmd.exe /c → .bat shim (tasklist + powershell) → Inno Setup
5 processes, 2 script files, 1 visible CMD window
```

### After (1 layer)

```
Python → os.startfile() → Windows ShellExecuteW → Inno Setup
2 processes, 0 script files, 0 visible windows
```

### The key code change

**Old** (`update_dialog.py`, `_on_install_now()`):
```python
installer = Path(self._downloaded_path)
app_exe = get_app_exe_path()
try:
    shim = write_update_shim(installer, app_exe)
    ok = launch_shim_and_exit(shim)
except Exception:
    ok = False
```

**New** (`update_dialog.py`, `_on_install_now()`):
```python
installer = Path(self._downloaded_path)
ok = launch_installer(installer)
```

**Old** (`update_shim.py`, ~80 lines):
```python
_SHIM_TEMPLATE = r"""@echo off
...30 lines of batch script...
"""
def write_update_shim(...): ...
def launch_shim_and_exit(...): ...
def get_app_exe_path(...): ...
```

**New** (`update_shim.py`, ~15 lines of code):
```python
def launch_installer(installer_path: Path) -> bool:
    if sys.platform == "win32":
        os.startfile(str(installer))
    elif sys.platform == "darwin":
        # future: subprocess.Popen(["open", str(installer)])
        return False
    elif sys.platform == "linux":
        # future: _linux_replace_appimage(installer)
        return False
    return True
```

---

## 5. Files Changed

| Proposed file | Replaces | Key changes |
|---|---|---|
| `update_shim.py` | `src/kipart_search/core/update_shim.py` | Removed .bat shim, added `launch_installer()` with cross-platform stubs |
| `update_dialog.py` | `src/kipart_search/gui/update_dialog.py` | Rewrote `_on_install_now()`, simplified imports |
| `__main__.py` | `src/kipart_search/__main__.py` | Removed `--update-failed` flag handling |
| `kipart-search.iss` | `installer/kipart-search.iss` | Added `[Run]` section, documented Restart Manager |
| `update_check.py` | `src/kipart_search/core/update_check.py` | Expanded cross-platform asset filter stubs |
| `build_nuitka.py` | `build_nuitka.py` | Platform-aware build/package/install, macOS/Linux stubs |
| `build-release.yml` | `.github/workflows/build-windows.yml` | Commented matrix build for future multi-platform CI |

---

## 6. Copy Instructions

To apply these changes to the kipart_search repo:

```bash
# From the SoftwareUpdateMechanismCheck/ directory:

# Core fix (update mechanism)
cp proposed_fix/update_shim.py   kipart_search/src/kipart_search/core/update_shim.py
cp proposed_fix/update_dialog.py kipart_search/src/kipart_search/gui/update_dialog.py
cp proposed_fix/__main__.py      kipart_search/src/kipart_search/__main__.py

# Installer
cp proposed_fix/kipart-search.iss kipart_search/installer/kipart-search.iss

# Update check (cross-platform asset filters)
cp proposed_fix/update_check.py  kipart_search/src/kipart_search/core/update_check.py

# Build system (cross-platform stubs)
cp proposed_fix/build_nuitka.py  kipart_search/build_nuitka.py

# CI/CD (renamed workflow with matrix stubs)
cp proposed_fix/build-release.yml kipart_search/.github/workflows/build-release.yml
# Optionally remove old workflow:
# rm kipart_search/.github/workflows/build-windows.yml
```

### Optional cleanup in main_window.py

The `_show_update_failed_dialog()` method and `run_app(update_failed=...)` parameter
are no longer triggered.  They can be safely removed but are not breaking if left.

---

## 7. How Inno Setup Restart Manager Works

This is the key insight that makes the simplification possible.

### Settings in the .iss file

```ini
CloseApplications=yes
CloseApplicationsFilter=kipart-search.exe
```

### What happens step by step

1. Inno Setup starts (launched by `os.startfile()` / ShellExecuteW).
2. Calls `RmStartSession()` to create a Restart Manager session.
3. Calls `RmRegisterResources()` for all files it needs to replace.
4. Restart Manager queries the OS for processes holding those files.
5. If `kipart-search.exe` is found:
   - **Interactive mode**: Shows "close applications" dialog.
   - **Silent/VerySilent mode**: Sends `WM_CLOSE` automatically.
6. PySide6/Qt receives `WM_CLOSE` → graceful shutdown.
7. After the process exits, Inno Setup replaces the files.

### Why the .bat shim was redundant

| Shim did this | Inno Setup already does this |
|---|---|
| Wait for app to exit (tasklist loop) | Restart Manager WM_CLOSE |
| Kill app if timeout | Restart Manager handles this |
| Run installer with elevation | os.startfile() triggers UAC via manifest |
| Relaunch app on success | [Run] section in .iss |
| Signal failure to app | Not needed — user runs installer again |

---

## 8. Cross-Platform Strategy

### Installer technology per platform

| Platform | Installer | Output format | How update_shim launches it |
|---|---|---|---|
| **Windows** | Inno Setup 6 | `-setup.exe` | `os.startfile()` → ShellExecuteW |
| **macOS** | Native DMG | `.dmg` | `subprocess.Popen(["open", path])` |
| **Linux** | AppImage | `.AppImage` | Replace binary + `os.execv()` |

### Why Inno Setup can't be used on macOS/Linux

Inno Setup compiles Windows PE executables only.  There is no macOS or Linux
support, and no roadmap from the developer (Jordan Russell).

### macOS update flow (future)

```
1. update_check.py matches asset ending in ".dmg"
2. User downloads .dmg to temp
3. launch_installer() calls: subprocess.Popen(["open", path])
4. Finder mounts the .dmg
5. User drags "KiPart Search.app" to /Applications (standard macOS UX)
6. User relaunches from /Applications
```

No "installer" runs — macOS convention is drag-and-drop.

### Linux update flow (future)

```
1. update_check.py matches asset ending in ".AppImage"
2. User downloads .AppImage to temp
3. launch_installer() calls _linux_replace_appimage():
   a. Rename current binary → .bak
   b. Copy new AppImage → current path
   c. chmod +x
   d. os.execv() to relaunch (replaces current process)
```

AppImages are self-contained — no installer needed.

---

## 9. Build System Cross-Platform Architecture

### Current state (Windows only)

```
build_nuitka.py
  ├── build()              → Nuitka --standalone + Windows PE flags
  ├── package()            → ZIP with README
  └── compile_installer()  → Inno Setup .exe

build-windows.yml (CI)
  └── windows-latest only
```

### Proposed state (cross-platform ready, Windows active)

```
build_nuitka.py
  ├── build()
  │   ├── Windows: --windows-console-mode, --windows-company-name, etc.  [ACTIVE]
  │   ├── macOS:   --macos-create-app-bundle, --macos-app-name, etc.     [COMMENTED]
  │   └── Linux:   no special flags                                       [COMMENTED]
  │
  ├── package()
  │   ├── Windows: _package_windows_zip()    [ACTIVE]
  │   ├── macOS:   _package_macos_dmg()      [COMMENTED STUB]
  │   └── Linux:   _package_linux_appimage() [COMMENTED STUB]
  │
  └── compile_installer()
      ├── Windows: Inno Setup iscc           [ACTIVE]
      └── Others:  "Inno Setup is Windows-only. Skipping."

build-release.yml (CI)
  ├── build-windows job                      [ACTIVE]
  └── matrix build (win + mac + linux)       [COMMENTED STUB]
```

### Nuitka flags per platform

**Windows** (active):
```
--windows-console-mode=disable
--windows-company-name=MecaFrog
--windows-product-name=KiPart Search
--windows-file-version=X.X.X.X
--windows-product-version=X.X.X.X
--windows-file-description=...
```

**macOS** (future — commented in build_nuitka.py):
```
--macos-create-app-bundle
--macos-app-name=KiPart Search
--macos-app-version=X.Y.Z
--macos-disable-console
--macos-sign-identity=...          (requires Apple Developer ID)
--macos-sign-notarization          (requires Apple notarization)
```

**Linux** (future — no special flags):
```
(no platform-specific flags — --standalone is sufficient)
(packaging into AppImage is done by _package_linux_appimage)
```

---

## 10. CI/CD Multi-Platform Pipeline

### Current: Single Windows job

```yaml
# .github/workflows/build-windows.yml
jobs:
  build-windows:
    runs-on: windows-latest
    # ... all steps are Windows-specific
```

### Future: Matrix build (commented in build-release.yml)

```yaml
# .github/workflows/build-release.yml
jobs:
  build:
    strategy:
      matrix:
        include:
          - os: windows-latest    # Inno Setup installer
          - os: macos-latest      # DMG disk image
          - os: ubuntu-latest     # AppImage
    runs-on: ${{ matrix.os }}
```

### Platform-specific CI steps

| Step | Windows | macOS | Linux |
|---|---|---|---|
| Install tooling | `choco install innosetup` | (none — hdiutil built-in) | Download appimagetool |
| Build | `build_nuitka.py --installer` | `build_nuitka.py --package` | `build_nuitka.py --package` |
| Output artifact | `-setup.exe` | `-macos.dmg` | `-linux.AppImage` |
| Checksums | SHA256 | SHA256 | SHA256 |
| Code signing | EV certificate (future) | Apple Developer ID (future) | N/A |

---

## 11. What Can Break on Other Platforms

### Runtime (user's machine)

| Code location | macOS/Linux behavior | Risk level |
|---|---|---|
| `update_check.py`: asset filter is `win32`-only | `asset_url` stays "". Button disabled. "No installer available." | **Low** — graceful |
| `update_shim.py`: `launch_installer()` platform guard | Returns False, logs warning. Error dialog shown. | **Low** — graceful |
| `is_compiled_build()`: checks `__compiled__` / `sys.frozen` | Works correctly on all platforms | **None** |
| `cleanup_stale_partial_downloads()`: uses `Path` / `tempfile` | Fully cross-platform | **None** |
| `__main__.py`: `_init_keyring_compiled()` imports `WinVaultKeyring` | Protected by `try/except ImportError` | **None** |

### Build system (developer's machine)

| Code location | macOS/Linux behavior | Risk level |
|---|---|---|
| `build_nuitka.py`: `--windows-*` flags | **Would crash Nuitka** — now guarded by `sys.platform` | **Fixed** |
| `build_nuitka.py`: `compile_installer()` | **Would fail** (no iscc) — now prints message and returns | **Fixed** |
| `build_nuitka.py`: `read_version()` quad format | Windows PE only — macOS/Linux should use `read_base_version()` | **Fixed** |

---

## 12. Recommended Order of Work

### Phase 1: Fix Windows update (NOW)

1. Copy the proposed files into the kipart_search repo (see Section 6)
2. Build with Nuitka + Inno Setup
3. Test the update flow on Windows 11
4. Verify no CMD window appears, installer runs correctly

### Phase 2: Add macOS support (WHEN READY)

1. In `build_nuitka.py`: Uncomment `--macos-*` flags in `build()`
2. In `build_nuitka.py`: Uncomment `_package_macos_dmg()` and its call
3. In `update_check.py`: Uncomment the `.dmg` asset filter
4. In `update_shim.py`: Uncomment the `subprocess.Popen(["open", ...])` call
5. In `build-release.yml`: Add `macos-latest` to the matrix
6. Optional: Apple code signing + notarization

### Phase 3: Add Linux support (WHEN READY)

1. In `build_nuitka.py`: Uncomment `_package_linux_appimage()` and its call
2. In `update_check.py`: Uncomment the `.AppImage` asset filter
3. In `update_shim.py`: Uncomment `_linux_replace_appimage()` and its call
4. In `build-release.yml`: Add `ubuntu-latest` to the matrix
5. Create `.desktop` file and icon for AppImage

### Phase 4: Convert CI to matrix build

1. In `build-release.yml`: Uncomment the matrix strategy block
2. Remove the single `build-windows` job
3. Test all three platforms in CI

---

## 13. Testing Checklist

### Windows update flow (Phase 1)

- [ ] Build compiled app with Nuitka + Inno Setup
- [ ] Trigger update check (Help > Check for Updates)
- [ ] Click "Update Now" — download completes
- [ ] Click "Install Now":
  - [ ] Confirmation dialog appears
  - [ ] UAC prompt appears (if not already admin)
  - [ ] App closes
  - [ ] **No CMD window appears**
  - [ ] **No "INFO: No tasks" message**
  - [ ] Inno Setup runs and installs
  - [ ] Files in Program Files are updated
- [ ] Relaunch from Start Menu / Desktop shortcut
- [ ] Verify new version is running

### Edge cases

- [ ] Windows Terminal as default terminal (Windows 11)
- [ ] Windows Console Host as default terminal (older Windows)
- [ ] App running as standard user (UAC should prompt)
- [ ] App running as administrator
- [ ] Antivirus enabled (quarantine detection)
- [ ] Spaces in temp path (user profile with spaces)
- [ ] SmartScreen blocked (Zone.Identifier removal)

### Regression

- [ ] `cleanup_stale_partial_downloads()` works on startup
- [ ] `is_compiled_build()` returns True for Nuitka, False for source
- [ ] "Install Now" button only appears for compiled builds
- [ ] Download size verification works
- [ ] Skip version persists to config.json
- [ ] 24h cache prevents excessive GitHub API calls
- [ ] "Open Folder" button opens Explorer to temp dir
- [ ] "Open Release Page" opens GitHub in browser

### Cross-platform safety (no action needed yet)

- [ ] Source build on macOS: app runs, update check shows "No installer available"
- [ ] Source build on Linux: app runs, update check shows "No installer available"
- [ ] `build_nuitka.py` on macOS: prints "macOS-specific flags not yet configured"
- [ ] `build_nuitka.py --installer` on macOS: prints "Inno Setup is Windows-only"
