# Story 8.5: In-App Version Check

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want the app to check for updates on startup and show me when a new version is available,
so that I know when to update without manually checking GitHub.

## Acceptance Criteria

1. **Given** the application launches, **when** the startup sequence runs, **then** a background thread checks `api.github.com/repos/sylvanoMTL/kipart-search/releases/latest` for the latest release tag.

2. **Given** the version check runs, **when** the background thread completes, **then** it has a 5-second timeout and the app launches immediately regardless of the check result.

3. **Given** the latest tag is newer than the running version, **when** the check completes, **then** a non-blocking notification is shown in the status bar (right-aligned, clickable).

4. **Given** the version check succeeds, **when** the result is returned, **then** the result is cached with a 24-hour TTL — only one check per day.

5. **Given** GitHub is unreachable (firewall, outage, rate limit 403), **when** the check fails, **then** the check is silently skipped with no user-visible error.

6. **Given** the cached "last check" data, **when** it is persisted, **then** the timestamp and result are stored in the config directory (`config.json`).

7. **Given** the API endpoint, **when** the check runs, **then** no authentication is required (unauthenticated GitHub API, 60 req/hr per IP).

## Tasks / Subtasks

- [x] Task 1: Create `core/update_check.py` module (AC: #1, #4, #5, #6, #7)
  - [x] 1.1 Create `UpdateInfo` dataclass: `latest_version: str`, `release_url: str`, `release_notes: str`, `check_time: float`
  - [x] 1.2 Implement `check_for_update(current_version: str) -> UpdateInfo | None` — calls GitHub API, compares versions, returns `UpdateInfo` if newer, `None` if current or error
  - [x] 1.3 Implement `_compare_versions(current: str, latest: str) -> bool` — returns True if latest is newer, using `packaging.version` or simple tuple comparison
  - [x] 1.4 Implement `load_cached_update(config_path: Path) -> UpdateInfo | None` — reads from config.json `update_check` key
  - [x] 1.5 Implement `save_update_cache(config_path: Path, info: UpdateInfo) -> None` — writes to config.json `update_check` key without overwriting other settings
  - [x] 1.6 Implement `should_check(config_path: Path, ttl_hours: int = 24) -> bool` — returns True if no cache or cache is expired

- [x] Task 2: Create `UpdateCheckWorker` QThread in `main_window.py` (AC: #1, #2)
  - [x] 2.1 Add `UpdateCheckWorker(QThread)` with `result = Signal(object)` — emits `UpdateInfo | None`
  - [x] 2.2 Worker calls `should_check()`, exits early if cache is fresh, otherwise calls `check_for_update()` and `save_update_cache()`
  - [x] 2.3 Worker has 5-second timeout on the httpx request

- [x] Task 3: Integrate into startup sequence (AC: #1, #2, #3)
  - [x] 3.1 In `showEvent()`, after the KiCad auto-connect worker starts, create and start `UpdateCheckWorker`
  - [x] 3.2 Connect worker `result` signal to `_on_update_check_result(info)` slot
  - [x] 3.3 In `_on_update_check_result()`: if `info` is not None, show a clickable label in the status bar

- [x] Task 4: Status bar notification (AC: #3)
  - [x] 4.1 Add an `_update_available_label` to the status bar (permanent widget, right-aligned, between license badge and action label)
  - [x] 4.2 Style: amber/highlight text "Update available: v{version}" — clickable (opens GitHub release URL in browser)
  - [x] 4.3 Hidden by default, shown only when update is available
  - [x] 4.4 Use `QDesktopServices.openUrl()` for the click action

- [x] Task 5: Tests (AC: #1-#7)
  - [x] 5.1 Unit tests for `_compare_versions()` — same version, older, newer, pre-release
  - [x] 5.2 Unit tests for `should_check()` — no cache, fresh cache, expired cache
  - [x] 5.3 Unit tests for `load_cached_update()` / `save_update_cache()` — round-trip, missing file, corrupted JSON
  - [x] 5.4 Unit test for `check_for_update()` — mock httpx response for success, 404 (no releases), timeout, 403

## Dev Notes

### Architecture: Core Module + GUI Worker

This follows the established core/GUI separation. The `core/update_check.py` module has **zero GUI dependencies** — it uses `httpx` for the HTTP call and `json` for config persistence. The QThread worker and status bar integration live in `gui/main_window.py`.

### GitHub API Endpoint

Use the **same endpoint and repo constant** as `release.py`:

```python
GITHUB_REPO = "sylvanoMTL/kipart-search"
url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
```

The response JSON has:
- `tag_name`: e.g. `"v0.2.0"` — strip the leading `v` for version comparison
- `html_url`: link to the release page (for the clickable notification)
- `body`: release notes markdown (store for use by Story 8.6's update dialog)

**Rate limit:** Unauthenticated GitHub API allows 60 requests/hour per IP. With 24-hour caching, this is never a concern.

### Version Comparison

Do NOT add `packaging` as a dependency. Use simple tuple comparison:

```python
def _compare_versions(current: str, latest: str) -> bool:
    """Return True if latest is strictly newer than current."""
    def _parse(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in v.split(".") if x.isdigit())
    return _parse(latest) > _parse(current)
```

This handles `"0.1.0"` vs `"0.2.0"` correctly. Pre-release suffixes are stripped by only taking digit segments.

### Config Storage Pattern

Follow the **exact same pattern** as `SourceConfigManager.set_welcome_version()` in `core/source_config.py` (lines 127-139): read existing config.json, update the target key, write back without overwriting other settings.

Store under a new `update_check` key in config.json:

```json
{
  "welcome_version": "0.1",
  "sources": { ... },
  "update_check": {
    "last_check_time": 1711468800.0,
    "latest_version": "0.2.0",
    "release_url": "https://github.com/sylvanoMTL/kipart-search/releases/tag/v0.2.0",
    "release_notes": "### What's New\n- Feature X\n- Bug fix Y"
  }
}
```

Use `paths.config_path()` from `core/paths.py` — do NOT construct the path manually.

### Status Bar Integration

The current status bar layout (from `main_window.py` lines 341-355):
```
[Mode label] [Sources label (stretches)] ... [License badge] [Action label]
```

Add the update notification as a **permanent widget** between the license badge and action label:

```python
self._update_label = QLabel()
self._update_label.setVisible(False)
self._update_label.setCursor(Qt.PointingHandCursor)
self.status_bar.addPermanentWidget(self._update_label)
```

Insert it **before** `self.status_bar.addPermanentWidget(self._action_label)` in the existing code.

### Startup Sequence Integration

In `showEvent()` (line 378), add the update check **after** the KiCad auto-connect worker:

```python
# Auto-check for app updates (non-blocking, cached 24h)
self._update_check_worker = UpdateCheckWorker()
self._update_check_worker.result.connect(self._on_update_check_result)
self._update_check_worker.start()
```

### QThread Worker Pattern

Follow the exact same pattern as `_ConnectWorker` (lines 194-210) and `UpdateCheckWorker` in `download_dialog.py` (lines 23-37):

```python
class UpdateCheckWorker(QThread):
    result = Signal(object)  # UpdateInfo | None

    def run(self):
        from kipart_search.core.update_check import (
            should_check, check_for_update, save_update_cache, load_cached_update
        )
        from kipart_search.core.paths import config_path
        cfg = config_path()
        if not should_check(cfg):
            cached = load_cached_update(cfg)
            self.result.emit(cached)
            return
        info = check_for_update(__version__)
        if info:
            save_update_cache(cfg, info)
        self.result.emit(info)
```

### httpx Request

Use `httpx.get()` with explicit timeout, matching the pattern in `release.py` (line 43):

```python
resp = httpx.get(url, timeout=5.0, follow_redirects=True)
```

Catch `httpx.HTTPError` and `httpx.TimeoutException` — return None on any failure.

### What NOT to Do

- Do NOT add `packaging` as a dependency — use simple tuple version comparison
- Do NOT show a dialog/popup on startup — use the status bar only (Story 8.6 adds the dialog)
- Do NOT block the startup sequence — the check MUST run in a background thread
- Do NOT log errors for network failures — silently skip (the user doesn't care if GitHub is unreachable)
- Do NOT authenticate with GitHub — unauthenticated API is sufficient
- Do NOT store update cache in QSettings — use config.json for consistency with all other config
- Do NOT create a separate config file for update state — add to the existing config.json
- Do NOT import `release.py` — it's a build tool, not a runtime dependency. Copy the repo constant.

### Project Structure Notes

**New file:**
- `src/kipart_search/core/update_check.py` — core module (zero GUI deps)

**Modified files:**
- `src/kipart_search/gui/main_window.py` — add `UpdateCheckWorker`, status bar label, startup hook
- `tests/` — new test file for update_check module

**Alignment with project structure:**
- `core/update_check.py` follows the established pattern of core modules (`core/cache.py`, `core/sources.py`, `core/verify.py`)
- Config persistence follows the `SourceConfigManager` pattern in `core/source_config.py`
- Status bar addition follows the existing permanent widget pattern (license badge)

### Previous Story Intelligence

**From Story 8.4 (CI Pipeline):**
- The CI workflow uploads release assets to GitHub Releases on tagged pushes (`v*.*.*`)
- `release.py` uses `GITHUB_REPO = "sylvanoMTL/kipart-search"` — reuse this exact constant
- The GitHub API `releases/latest` endpoint is already used in `release.py` line 41 for the version gate — proven to work
- SHA256 checksums are generated as release assets (useful for Story 8.6 download verification)

**From Story 8.1 (platformdirs):**
- All config lives in `platformdirs.user_data_dir("KiPartSearch")` via `core/paths.py`
- Config.json read/write pattern: read → merge → write (see `source_config.py` lines 127-139)

**From Epic 6 (Welcome Dialog):**
- The welcome dialog deferred-show pattern in `showEvent()` (line 385) is the exact pattern to follow
- Config.json key pattern: `welcome_version` → add `update_check` at the same level

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.5 — acceptance criteria and epic context]
- [Source: release.py:36-57 — GITHUB_REPO constant, GitHub API pattern, version comparison]
- [Source: src/kipart_search/gui/main_window.py:341-355 — status bar setup]
- [Source: src/kipart_search/gui/main_window.py:378-389 — showEvent startup sequence]
- [Source: src/kipart_search/gui/main_window.py:194-210 — _ConnectWorker QThread pattern]
- [Source: src/kipart_search/core/source_config.py:127-139 — config.json read-merge-write pattern]
- [Source: src/kipart_search/core/paths.py:27-29 — config_path() function]
- [Source: src/kipart_search/__init__.py:3 — __version__ = "0.1.0"]
- [Source: src/kipart_search/gui/download_dialog.py:23-37 — UpdateCheckWorker QThread pattern]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

### Completion Notes List

- ✅ Task 1: Created `core/update_check.py` with `UpdateInfo` dataclass, `check_for_update()`, `_compare_versions()`, `load_cached_update()`, `save_update_cache()`, `should_check()` — all zero GUI deps, uses httpx with 5s timeout
- ✅ Task 2: Created `_UpdateCheckWorker(QThread)` in main_window.py — checks cache freshness, calls GitHub API only if expired, emits `UpdateInfo | None`
- ✅ Task 3: Integrated into `showEvent()` startup sequence — worker starts after KiCad auto-connect, non-blocking
- ✅ Task 4: Added amber clickable `_update_label` in status bar between license badge and action label — hidden by default, opens release URL via `QDesktopServices.openUrl()`
- ✅ Task 5: 21 unit tests covering version comparison, cache round-trip, TTL expiry, corrupted JSON, httpx mocked success/timeout/403/404 — all pass
- ℹ️ Pre-existing crash in `test_context_menus.py::TestAccessibilityLabels::test_status_bar_accessible_names` (access violation in VerifyPanel init) — confirmed present on clean main branch before any changes

### Change Log

- 2026-03-27: Implemented Story 8.5 — in-app version check with GitHub API, 24h cache, status bar notification
- 2026-03-27: Code review — fixed 3 issues (H1: cache staleness on upgrade, M1: monkey-patched mousePressEvent → eventFilter, M2: worker cleanup on close)

### File List

- `src/kipart_search/core/update_check.py` (new)
- `src/kipart_search/gui/main_window.py` (modified)
- `tests/core/test_update_check.py` (new)
