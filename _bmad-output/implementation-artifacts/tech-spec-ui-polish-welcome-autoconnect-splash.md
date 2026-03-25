---
title: 'UI Polish — Welcome, Auto-connect, Splash Screen'
slug: 'ui-polish-welcome-autoconnect-splash'
created: '2026-03-25'
status: 'ready-for-dev'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python 3.10+', 'PySide6']
files_to_modify: ['src/kipart_search/gui/main_window.py', 'src/kipart_search/gui/__main__.py', 'src/kipart_search/core/source_config.py']
code_patterns: ['QThread background work', 'showEvent deferred init', 'SourceConfigManager JSON config']
test_patterns: []
---

# Tech-Spec: UI Polish — Welcome, Auto-connect, Splash Screen

**Created:** 2026-03-25

## Overview

### Problem Statement

Four UI polish issues reduce perceived quality and first-run experience:

1. **Welcome dialog not shown on compiled binary**: The `welcome_shown` flag is stored in `~/.kipart-search/config.json`, which is shared between source installs and compiled binaries. A user who previously ran from source will never see the welcome dialog when switching to the compiled binary.

2. **KiCad connection shows "Standalone" until first scan**: `_bridge.connect()` is only called when the user clicks Scan. The status bar shows "Standalone" even when KiCad is running, which looks broken.

3. **Cold start time ~5s with no feedback**: Heavy operations (JLCPCB database integrity check, source initialization) run during `MainWindow.__init__()` with no visual feedback. The user sees nothing for ~5 seconds.

### Solution

1. Add a `welcome_version` field to config instead of a boolean — reset welcome on major version changes (e.g. first compiled binary release)
2. Attempt KiCad connection in a background thread during `showEvent()` — non-blocking, updates status bar when done
3. Add a `QSplashScreen` shown immediately after `QApplication()` creation, closed when `MainWindow.show()` completes

### Scope

**In Scope:**
- Version-aware welcome dialog trigger
- Background KiCad auto-connect on first show
- Splash screen with app name/version during startup
- Status bar update when auto-connect succeeds/fails

**Out of Scope:**
- Actual startup time optimization (lazy loading, deferred DB init)
- Connection retry/reconnect logic
- Welcome dialog content changes
- Freshness column removal (moved to Spec A)

## Context for Development

### Codebase Patterns

- `MainWindow.__init__()` calls `_check_welcome()` at line 328 — blocks UI with modal dialog
- `showEvent()` already exists (lines 345-350) with `_first_show` guard and deferred dock sizing
- `_bridge.connect()` returns `(bool, str)` — safe to call from any thread (no Qt calls inside)
- `run_app()` in `main_window.py` (lines 1576-1585) creates `QApplication`, then `MainWindow`, then `window.show()`, then `app.exec()`
- `SourceConfigManager.get_welcome_shown()` / `set_welcome_shown()` read/write `~/.kipart-search/config.json`
- Status bar badge update: `_update_connection_badge()` updates left zone with "Connected" (green) or "Standalone" (gray) — called from `_on_scan()` after successful connect

### Files to Reference

| File | Purpose | Key Lines |
| ---- | ------- | --------- |
| `src/kipart_search/gui/main_window.py` | App entry (`run_app`), MainWindow init, `_check_welcome()`, `showEvent()`, connection badge | `run_app()` L1576-1585, `_check_welcome()` L511-544, `showEvent()` L345-350, `_on_scan()` L751-770 |
| `src/kipart_search/__main__.py` | CLI entry point, `_init_keyring_compiled()` | L31-39 |
| `src/kipart_search/core/source_config.py` | `get_welcome_shown()`, `set_welcome_shown()`, config JSON path | L76-84 (path), L100-120 (get/set) |
| `src/kipart_search/gui/welcome_dialog.py` | Welcome dialog with 3 options (download DB, configure API, skip) | L24-208 |
| `src/kipart_search/gui/kicad_bridge.py` | `connect()` method, `is_connected` property | `connect()` L32-53 |

### Technical Decisions

- **Welcome version tracking**: Replace `welcome_shown: bool` with `welcome_version: str` storing the version string (e.g. `"0.3.0"`). Show welcome when `welcome_version` is missing or differs from current major.minor. This handles: (a) first install, (b) upgrade from source to compiled binary if version changes, (c) major feature additions that warrant re-showing welcome.
- **Auto-connect thread**: Use a simple `QThread` worker (same pattern as `ScanWorker`). Fire in `showEvent()` after `_first_show` guard. On completion, emit signal to update status bar badge. If connection fails, silently stay in "Standalone" — no error dialog (user didn't request connection).
- **Splash screen**: Use `QSplashScreen` with a simple pixmap (app name + version text rendered on a colored background). No external image file needed — generate programmatically with `QPainter`. Show before `MainWindow()` construction, close after `window.show()`.

## Implementation Plan

### Tasks

- [ ] Task 1: Create splash screen in `run_app()`
  - File: `src/kipart_search/gui/main_window.py`
  - Action: In `run_app()`, after `QApplication()` creation and before `MainWindow()`, create a `QSplashScreen`. Generate a simple pixmap programmatically: solid background color (#1a1a2e or similar dark theme), app name "KiPart Search" centered, version string below. Call `splash.show()` and `app.processEvents()`. After `MainWindow()` construction, call `splash.finish(window)` which hides splash when the window is shown.
  - Notes: `QSplashScreen.finish(window)` automatically closes the splash when the main window appears. No timer needed. `splash.showMessage()` can display progress text during init if desired.

- [ ] Task 2: Replace `welcome_shown` boolean with `welcome_version` string
  - File: `src/kipart_search/core/source_config.py`
  - Action: Add `get_welcome_version() -> str | None` method that reads `welcome_version` from config JSON (returns None if absent or if only old `welcome_shown` exists). Add `set_welcome_version(version: str)` that writes the version string. Keep `get_welcome_shown()` / `set_welcome_shown()` for backwards compat but have `get_welcome_shown()` also return False when `welcome_version` doesn't match current version.
  - Notes: Import `__version__` from `kipart_search` to compare.

- [ ] Task 3: Update `_check_welcome()` to use version-aware logic
  - File: `src/kipart_search/gui/main_window.py`
  - Action: In `_check_welcome()`, replace `mgr.get_welcome_shown()` check with version comparison: `mgr.get_welcome_version()` vs current app version (compare major.minor only). If different or None, show welcome. After dialog, call `mgr.set_welcome_version(__version__)` instead of `set_welcome_shown(True)`.
  - Notes: Compare only major.minor (e.g. "0.3") so patch releases don't re-trigger welcome. Use `__version__.rsplit('.', 1)[0]` for comparison.

- [ ] Task 4: Add background KiCad auto-connect on first show
  - File: `src/kipart_search/gui/main_window.py`
  - Action: Create a small `_ConnectWorker(QThread)` inner class with a `result = Signal(bool, str)` signal. In its `run()`, call `self.bridge.connect()` and emit the result. In the existing `showEvent()` method, after `_apply_default_dock_sizes`, start a `_ConnectWorker`. Connect its `result` signal to a new `_on_auto_connect_result(ok, msg)` slot that calls `_update_connection_badge()` and logs the result (e.g. "Auto-connected to KiCad" or silent on failure).
  - Notes: In `_on_scan()`, check `self._bridge.is_connected` before calling `connect()` again — this already works (line 754 has `if not self._bridge.is_connected`). No change needed there.

- [ ] Task 5: Update status bar badge after auto-connect
  - File: `src/kipart_search/gui/main_window.py`
  - Action: Ensure `_update_connection_badge()` (or equivalent method that sets the "Connected"/"Standalone" label) is callable from the auto-connect result slot. If this method doesn't exist as a standalone method, extract the badge-update logic from `_on_scan()` into a reusable `_update_connection_badge()` method.
  - Notes: The badge update must run on the main thread. Since Qt signals/slots cross thread boundaries safely, the signal connection handles this automatically.

### Acceptance Criteria

- [ ] AC 1: Given a fresh install (no `~/.kipart-search/config.json`), when the compiled binary launches, then the welcome dialog appears.

- [ ] AC 2: Given an existing config with `welcome_shown: true` but no `welcome_version` field (legacy source install), when the compiled binary launches, then the welcome dialog appears (because version doesn't match).

- [ ] AC 3: Given a config with `welcome_version: "0.3"` matching current version, when the app launches, then the welcome dialog does NOT appear.

- [ ] AC 4: Given KiCad 9+ is running with IPC API enabled, when KiPart Search launches, then within ~2 seconds the status bar changes from "Standalone" to "Connected to KiCad" without the user clicking Scan.

- [ ] AC 5: Given KiCad is NOT running, when KiPart Search launches, then the status bar remains "Standalone" with no error dialog or log spam.

- [ ] AC 6: Given the app is starting up, when the user double-clicks the executable, then a splash screen with "KiPart Search" and the version number appears immediately and remains visible until the main window appears (~5 seconds).

- [ ] AC 7: Given the splash screen is visible, when `MainWindow` finishes initializing and calls `show()`, then the splash screen closes automatically.

## Additional Context

### Dependencies

None — `QSplashScreen` is part of PySide6 (already a dependency).

### Testing Strategy

**Manual smoke test:**
1. Delete `~/.kipart-search/config.json` → launch → verify welcome dialog appears (AC 1)
2. Create config with only `welcome_shown: true` → launch → verify welcome appears (AC 2)
3. Launch normally after welcome → verify welcome doesn't appear again (AC 3)
4. Start KiCad → launch KiPart Search → verify auto-connect within ~2s (AC 4)
5. Close KiCad → launch KiPart Search → verify "Standalone" stays, no error (AC 5)
6. Launch compiled binary → verify splash appears immediately (AC 6-7)

**Edge cases:**
- KiCad started AFTER KiPart Search → auto-connect won't fire (by design, user clicks Scan)
- Very slow disk → splash should still appear fast (it's created before MainWindow)

### Notes

- The splash screen is purely cosmetic — it masks the startup delay without actually reducing it. Actual startup optimization (lazy DB init, deferred source loading) is a separate story.
- Auto-connect is best-effort. If it fails silently, the existing on-demand connection in `_on_scan()` still works exactly as before.
- The `welcome_version` approach is forward-compatible: if we add major features in v0.4, we can re-trigger the welcome to showcase them.
