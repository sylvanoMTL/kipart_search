# Story 8.6: Update Dialog with Download

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to see release notes and choose how to handle an available update (install now, remind later, or skip this version),
so that I control when and whether updates are applied.

## Acceptance Criteria

1. **Given** the version check from Story 8.5 detects a newer release, **when** the update notification is shown in the status bar, **then** clicking it opens an update dialog (not just a browser link).

2. **Given** the update dialog opens, **when** the user reads it, **then** it displays: the new version number, release notes summary (from GitHub release body rendered as plain text or simple markdown), and three buttons: [Update Now] / [Remind Me Later] / [Skip This Version].

3. **Given** the user clicks "Remind Me Later", **when** the dialog closes, **then** no persistent state changes — the check runs again on next launch as normal.

4. **Given** the user clicks "Skip This Version", **when** the dialog closes, **then** the skipped version string is persisted in config.json under `update_check.skipped_version` — future checks only alert for versions newer than the skipped one.

5. **Given** the user clicks "Update Now", **when** the download begins, **then** the dialog shows a progress bar downloading the correct platform asset (`.exe` installer for Windows) from the GitHub release assets.

6. **Given** the download is in progress, **when** the asset is being fetched, **then** the file is saved to `%TEMP%\kipart-search-update-v{version}.exe` using a `.partial` extension during download, renamed to the final name after completion.

7. **Given** the download completes, **when** the file is fully written, **then** the downloaded file size is verified against the GitHub release asset `size` field.

8. **Given** the download fails or the file is missing after download (e.g. AV quarantine), **when** the error is detected, **then** a fallback message is shown: "Download may have been blocked. Download manually from GitHub." with a clickable link to the release page.

9. **Given** the dialog needs to select the correct asset, **when** it parses the GitHub release assets list, **then** it selects the asset matching `*-setup.exe` for `sys.platform == "win32"` (framework-ready for future multi-platform with elif stubs for darwin/linux).

## Tasks / Subtasks

- [x] Task 1: Extend `core/update_check.py` with asset resolution and skip logic (AC: #4, #9)
  - [x]1.1 Add `asset_url: str` and `asset_size: int` fields to the `UpdateInfo` dataclass (default empty/0 for backward compat with existing cache)
  - [x]1.2 In `check_for_update()`, parse `data["assets"]` list to find the matching installer asset by name suffix (`-setup.exe` on Windows), extract `browser_download_url` and `size`
  - [x]1.3 Add `save_skipped_version(config_path: Path, version: str) -> None` — writes `update_check.skipped_version` to config.json using the read-merge-write pattern
  - [x]1.4 Add `load_skipped_version(config_path: Path) -> str | None` — reads `update_check.skipped_version` from config.json
  - [x]1.5 Update `check_for_update()` to accept optional `skipped_version: str | None` parameter — if the latest version equals the skipped version, return None

- [x] Task 2: Create `gui/update_dialog.py` with the UpdateDialog class (AC: #1, #2, #3, #4, #5, #6, #7, #8)
  - [x]2.1 Create `UpdateDialog(QDialog)` with constructor taking `info: UpdateInfo` and `parent`
  - [x]2.2 Layout: version header label ("v{version} is available"), release notes in a read-only `QTextEdit` (plain text from `info.release_notes`), three-button row at the bottom
  - [x]2.3 "Remind Me Later" button: simply calls `self.reject()` — no state change
  - [x]2.4 "Skip This Version" button: calls `save_skipped_version()` with the update version, then `self.reject()`
  - [x]2.5 "Update Now" button: disables all three buttons, shows progress bar, starts `_DownloadWorker`
  - [x]2.6 Create `_DownloadWorker(QThread)` inner class with signals: `progress(int, int)` (downloaded bytes, total bytes), `finished(str)` (final file path), `error(str)`
  - [x]2.7 Worker downloads from `info.asset_url` using `httpx.stream()` with `follow_redirects=True`, writes to `{tempdir}/kipart-search-update-v{version}.exe.partial`, renames on completion
  - [x]2.8 After download, verify file size against `info.asset_size` — emit error if mismatch or file missing
  - [x]2.9 On download success: show success message with path, offer "Open Folder" button (opens containing folder in explorer) and "Close" button
  - [x]2.10 On download failure: show fallback message with clickable link to `info.release_url`

- [x] Task 3: Wire update dialog into main_window.py (AC: #1, #4)
  - [x]3.1 Change the `eventFilter` click handler on `_update_label` to open `UpdateDialog` instead of `QDesktopServices.openUrl()`
  - [x]3.2 Store the `UpdateInfo` object from `_on_update_check_result` as `self._update_info` for use by the dialog
  - [x]3.3 In `_UpdateCheckWorker.run()`, integrate `load_skipped_version()` — if cached version equals skipped version, emit None
  - [x]3.4 After dialog closes with skip, if a newer version later becomes available (next launch), the notification reappears

- [x] Task 4: Tests (AC: #1-#9)
  - [x]4.1 Unit test `save_skipped_version` / `load_skipped_version` round-trip
  - [x]4.2 Unit test `check_for_update` with `skipped_version` parameter — skipped returns None, newer-than-skipped returns UpdateInfo
  - [x]4.3 Unit test asset URL resolution — mock GitHub response with assets list, verify correct `-setup.exe` is selected
  - [x]4.4 Unit test asset resolution when no matching asset exists — returns UpdateInfo with empty asset_url
  - [x]4.5 Unit test backward compatibility — `UpdateInfo` loaded from cache without `asset_url`/`asset_size` fields defaults gracefully

## Dev Notes

### Architecture: New Dialog + Core Extensions

This story extends the `core/update_check.py` module (created in Story 8.5) and adds a new `gui/update_dialog.py` dialog. The core/GUI separation is maintained: all GitHub API logic and config persistence stays in `core/`, the dialog and download progress UI lives in `gui/`.

### GitHub Release Assets API

The `releases/latest` endpoint already used by Story 8.5 returns an `assets` array. Each asset has:

```json
{
  "assets": [
    {
      "name": "kipart-search-0.2.0-setup.exe",
      "browser_download_url": "https://github.com/sylvanoMTL/kipart-search/releases/download/v0.2.0/kipart-search-0.2.0-setup.exe",
      "size": 45678912,
      "content_type": "application/x-msdownload"
    },
    {
      "name": "kipart-search-0.2.0-windows.zip",
      "browser_download_url": "...",
      "size": 43210000,
      "content_type": "application/zip"
    }
  ]
}
```

The asset selection logic should match `*-setup.exe` (installer preferred over ZIP). The `size` field is used for post-download verification.

### Extending UpdateInfo Dataclass

Add two new fields with defaults so existing cached data (from 8.5) still loads:

```python
@dataclass
class UpdateInfo:
    latest_version: str
    release_url: str
    release_notes: str
    check_time: float
    asset_url: str = ""
    asset_size: int = 0
```

In `load_cached_update()`, use `.get()` with defaults for the new fields:

```python
return UpdateInfo(
    latest_version=uc["latest_version"],
    release_url=uc["release_url"],
    release_notes=uc.get("release_notes", ""),
    check_time=uc["check_time"],
    asset_url=uc.get("asset_url", ""),
    asset_size=uc.get("asset_size", 0),
)
```

### Asset Resolution in check_for_update()

Add asset parsing after the existing version comparison logic:

```python
import sys

# After creating UpdateInfo...
asset_url = ""
asset_size = 0
for asset in data.get("assets", []):
    name = asset.get("name", "")
    if sys.platform == "win32" and name.endswith("-setup.exe"):
        asset_url = asset.get("browser_download_url", "")
        asset_size = asset.get("size", 0)
        break
    # elif sys.platform == "darwin" and name.endswith(".dmg"):  # future
    # elif sys.platform == "linux" and name.endswith(".AppImage"):  # future
```

### Skip Version Config Pattern

Follow the exact same read-merge-write pattern as `save_update_cache()`:

```python
def save_skipped_version(config_path: Path, version: str) -> None:
    raw: dict = {}
    if config_path.exists():
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            raw = {}
    raw.setdefault("update_check", {})["skipped_version"] = version
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
```

Config.json after skip:

```json
{
  "update_check": {
    "last_check_time": 1711468800.0,
    "latest_version": "0.2.0",
    "release_url": "...",
    "release_notes": "...",
    "asset_url": "...",
    "asset_size": 45678912,
    "skipped_version": "0.2.0"
  }
}
```

### Download Worker Pattern

Follow the `DownloadWorker` pattern from `download_dialog.py` (lines 40-71). Key differences:

- Uses `httpx.stream("GET", url)` for chunked download with progress
- Writes to `.partial` file, renames on completion
- GitHub release asset downloads require `follow_redirects=True` (redirects to S3/CDN)

```python
class _DownloadWorker(QThread):
    progress = Signal(int, int)   # (downloaded_bytes, total_bytes)
    finished = Signal(str)        # final file path
    error = Signal(str)           # error message

    def __init__(self, url: str, dest: Path, expected_size: int):
        super().__init__()
        self.url = url
        self.dest = dest
        self.expected_size = expected_size

    def run(self):
        import httpx
        partial = self.dest.with_suffix(self.dest.suffix + ".partial")
        try:
            with httpx.stream("GET", self.url, timeout=300.0, follow_redirects=True) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0
                with open(partial, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.progress.emit(downloaded, total)
            # Rename .partial → final
            if self.dest.exists():
                self.dest.unlink()
            partial.rename(self.dest)
            # Verify size
            actual = self.dest.stat().st_size
            if self.expected_size > 0 and actual != self.expected_size:
                self.error.emit(f"Size mismatch: expected {self.expected_size}, got {actual}")
                return
            self.finished.emit(str(self.dest))
        except Exception as e:
            # Clean up partial file
            if partial.exists():
                try:
                    partial.unlink()
                except OSError:
                    pass
            self.error.emit(str(e))
```

### Download Destination

Use `tempfile.gettempdir()` for the download path:

```python
import tempfile
dest = Path(tempfile.gettempdir()) / f"kipart-search-update-v{info.latest_version}.exe"
```

This goes to `%TEMP%` on Windows, `/tmp` on Linux — consistent with AC #6.

### Update Dialog Layout

```
+--------------------------------------------------+
| KiPart Search Update Available                   |
+--------------------------------------------------+
|                                                  |
|  Version 0.2.0 is available (you have 0.1.5)    |
|                                                  |
|  +--------------------------------------------+ |
|  | Release Notes                               | |
|  |                                             | |
|  | ### What's New                              | |
|  | - Feature X                                 | |
|  | - Bug fix Y                                 | |
|  |                                             | |
|  +--------------------------------------------+ |
|                                                  |
|  [========== 45% ==========    ]    (download)   |
|                                                  |
|  [Update Now]  [Remind Me Later]  [Skip Version] |
+--------------------------------------------------+
```

- Window title: "KiPart Search Update Available"
- `setMinimumWidth(480)`, `setMinimumHeight(320)`
- Modal dialog (`setModal(True)`)
- Release notes in a `QTextEdit` set to read-only with `setPlainText(info.release_notes)` — do NOT attempt to render markdown as HTML
- Progress bar hidden by default, shown during download

### Wiring Into main_window.py

Replace the current `eventFilter` click behavior (which opens the browser) with opening the dialog:

```python
def eventFilter(self, obj, event):
    if obj is self._update_label and event.type() == event.Type.MouseButtonPress:
        if self._update_info:
            from kipart_search.gui.update_dialog import UpdateDialog
            dlg = UpdateDialog(self._update_info, parent=self)
            dlg.exec()
        return True
    return super().eventFilter(obj, event)
```

In `_on_update_check_result`, store the info object:

```python
def _on_update_check_result(self, info):
    if info is None:
        return
    self._update_info = info
    self._update_release_url = info.release_url
    self._update_label.setText(f"  Update available: v{info.latest_version}  ")
    self._update_label.setVisible(True)
```

### Skip Version Integration in Worker

In `_UpdateCheckWorker.run()`, add skip check after loading cache or getting fresh result:

```python
from kipart_search.core.update_check import load_skipped_version

skipped = load_skipped_version(cfg)
# After getting info (either cached or fresh):
if info and skipped and info.latest_version == skipped:
    self.result.emit(None)
    return
```

### What NOT to Do

- Do NOT render release notes as HTML/rich text — use `setPlainText()` on QTextEdit. The markdown from GitHub is readable as-is.
- Do NOT add a "check for updates" menu item or button — that's not in scope for this story.
- Do NOT auto-start the installer after download — that's Story 8.7.
- Do NOT verify SHA256 checksums of the download — the size check is sufficient for 8.6. Checksum verification can be added in 8.8.
- Do NOT add cancel support during download — keep it simple. The dialog can be closed, which will abandon the worker (same as DownloadDialog pattern).
- Do NOT import `release.py` or `build_nuitka.py` — they are build tools, not runtime.
- Do NOT use `requests` — use `httpx` (project standard HTTP client).
- Do NOT store download state in config.json — the download is ephemeral (temp dir).

### Existing Patterns to Reuse

| Pattern | Source | What to copy |
|---------|--------|-------------|
| QDialog with progress bar | `gui/download_dialog.py` | Dialog structure, progress bar wiring, button state management |
| QThread download worker | `gui/download_dialog.py:40-71` | Worker with progress/finished/error signals |
| Config read-merge-write | `core/update_check.py:88-102` | `save_update_cache()` pattern for skip persistence |
| Status bar click handling | `gui/main_window.py:441-449` | `eventFilter` method (modify, don't duplicate) |
| UpdateInfo dataclass | `core/update_check.py:23-30` | Extend with new fields using defaults |

### Project Structure Notes

**New file:**
- `src/kipart_search/gui/update_dialog.py` — update dialog with download (PySide6)

**Modified files:**
- `src/kipart_search/core/update_check.py` — add `asset_url`/`asset_size` to UpdateInfo, add skip version functions, add asset resolution
- `src/kipart_search/gui/main_window.py` — change status bar click to open dialog instead of browser, store UpdateInfo, integrate skip version in worker
- `tests/core/test_update_check.py` — add tests for skip version, asset resolution, backward compat

**Alignment with project structure:**
- `gui/update_dialog.py` follows the established pattern of dialog modules (`gui/download_dialog.py`, `gui/assign_dialog.py`, `gui/export_dialog.py`)
- Core extensions stay in `core/update_check.py` — no new core modules needed
- Tests extend the existing `tests/core/test_update_check.py` file

### Previous Story Intelligence

**From Story 8.5 (In-App Version Check):**
- `core/update_check.py` already exists with `UpdateInfo`, `check_for_update()`, `load_cached_update()`, `save_update_cache()`, `should_check()`, `_compare_versions()`
- The GitHub API response is already parsed in `check_for_update()` — extend it to also extract assets
- Config.json `update_check` key already exists — add `skipped_version` and `asset_url`/`asset_size` to it
- `_UpdateCheckWorker` in main_window.py already emits `UpdateInfo | None` — no signal change needed
- The `_update_label` click currently opens the browser via `QDesktopServices.openUrl()` — replace with dialog
- 21 existing tests in `tests/core/test_update_check.py` — extend, don't break them
- `_compare_versions()` is imported in the worker for cache invalidation on upgrade — reuse for skip logic

**From Story 8.4 (CI Pipeline):**
- CI uploads both `-setup.exe` and `-windows.zip` as release assets — the asset selection must pick the installer
- Asset naming convention: `kipart-search-{version}-setup.exe`

**From download_dialog.py (JLCPCB Database Download):**
- Proven download-with-progress-bar pattern using QThread worker + progress/finished/error signals
- Button state management during download (disable buttons, rewire cancel)
- `_cancelled` flag pattern for worker cancellation

### Git Intelligence

Recent commits show:
- `52ec8b1` — brainstorming session (no code changes relevant)
- `4ec7ab2` — version bumped to 0.1.5 (current running version)
- `2c1dd84` — license UI improvements (settings dialog pattern)
- `748e2d5` — JWT fix for dev bypass (keyring/license pattern)

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.6 — acceptance criteria]
- [Source: src/kipart_search/core/update_check.py — existing module to extend]
- [Source: src/kipart_search/gui/main_window.py:213-236 — _UpdateCheckWorker]
- [Source: src/kipart_search/gui/main_window.py:377-391 — _update_label setup]
- [Source: src/kipart_search/gui/main_window.py:433-449 — _on_update_check_result and eventFilter]
- [Source: src/kipart_search/gui/download_dialog.py:40-71 — DownloadWorker pattern]
- [Source: src/kipart_search/gui/download_dialog.py:74-228 — DownloadDialog progress/button pattern]
- [Source: src/kipart_search/core/paths.py:27-29 — config_path()]
- [Source: release.py:42 — GITHUB_REPO constant]
- [Source: tests/core/test_update_check.py — existing tests to extend]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

None — clean implementation with no blockers.

### Completion Notes List

- **Task 1**: Extended `UpdateInfo` dataclass with `asset_url`/`asset_size` fields (with defaults for backward compat). Updated `check_for_update()` to parse GitHub release assets and accept `skipped_version` parameter. Added `save_skipped_version()` and `load_skipped_version()` functions using read-merge-write pattern.
- **Task 2**: Created `UpdateDialog` with version header, read-only release notes QTextEdit, progress bar, and three-button row (Update Now / Remind Me Later / Skip This Version). `_DownloadWorker` QThread handles streaming download with `.partial` rename and size verification. Post-download shows Open Folder / Close. Error state shows fallback link to release page.
- **Task 3**: Wired dialog into `main_window.py` — status bar click now opens `UpdateDialog` instead of browser. Stored `_update_info` from check result. Integrated `load_skipped_version()` in `_UpdateCheckWorker` to suppress skipped versions from both cached and fresh checks.
- **Task 4**: Added 13 new tests covering skip version round-trip, skip version with corrupted/missing config, `check_for_update` with skipped version, asset URL resolution (Windows setup.exe selection, no matching asset, no assets array), and backward compatibility (cached data from 8.5 without new fields).

### Change Log

- 2026-03-27: Implemented Story 8.6 — Update dialog with download progress, skip version, asset resolution

### File List

- `src/kipart_search/core/update_check.py` — modified (asset fields, skip version functions, asset resolution)
- `src/kipart_search/gui/update_dialog.py` — new (UpdateDialog + _DownloadWorker)
- `src/kipart_search/gui/main_window.py` — modified (dialog wiring, skip version in worker)
- `tests/core/test_update_check.py` — modified (13 new tests)
