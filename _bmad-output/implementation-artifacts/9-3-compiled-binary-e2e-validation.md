# Story 9.3: Compiled Binary End-to-End Validation

Status: done

## Story

As a developer,
I want a structured smoke test that validates the full install/update lifecycle on real compiled artifacts,
so that distribution features (installer, update check, download, auto-install) are proven to work end-to-end before shipping to users.

## Acceptance Criteria

1. **Given** a Nuitka-compiled binary and Inno Setup installer have been built, **when** the smoke test suite runs, **then** it covers: fresh install, version display, update detection, download, skip version, remind me later, UAC denial recovery, install failure fallback, offline graceful degradation, partial download cleanup, Inno Setup upgrade, uninstall with data preservation, cache TTL, manual update check, and release script validation.

2. **Given** the smoke test runner, **when** executed via `python tests/smoke_test_epic8.py`, **then** it presents an interactive test-by-test checklist with Pass/Fail/Skip options, saves timestamped results to `tests/smoke-test-results/`, and reports a summary on exit.

3. **Given** all critical user-facing flows, **when** tested on real compiled artifacts (not mocked), **then** all critical flows pass — any remaining items are documented with reasons.

4. **Given** bugs found during smoke testing, **when** they are fixed, **then** the fixes are committed, tested again, and merged.

5. **Given** the smoke test plan, **when** reviewed, **then** it is stored as a planning artifact for future release validation.

## Tasks / Subtasks

- [x] Task 1: Create smoke test plan (AC: #5)
  - [x] 1.1 Document test phases and test cases covering full install/update lifecycle
  - [x] 1.2 Store as `_bmad-output/implementation-artifacts/tests/epic-8-smoke-test-plan.md`

- [x] Task 2: Build smoke test runner (AC: #1, #2)
  - [x] 2.1 Create `tests/smoke_test_epic8.py` — interactive manual test runner
  - [x] 2.2 Organize into 6 phases: Build & Install A, Build B & Update Detection, Alternative Update Flows, Failure & Resilience, Edge Cases, Release Script Validation
  - [x] 2.3 32 test cases with detailed step-by-step instructions (PS>, GUI>, WIN> prefixes)
  - [x] 2.4 Save timestamped results to `tests/smoke-test-results/`
  - [x] 2.5 Handle Ctrl+C gracefully (save partial results)

- [x] Task 3: Execute smoke tests and fix bugs (AC: #3, #4)
  - [x] 3.1 Build Release A (v0.2.3) and Release B (v0.3.0) for two-version update testing
  - [x] 3.2 Run smoke tests — 8 rounds total
  - [x] 3.3 Fix bugs found during testing (see Dev Notes for full list)
  - [x] 3.4 Merge fixes via PR #3 (fix/update-mechanism branch)

- [x] Task 4: Final validation (AC: #3)
  - [x] 4.1 Final smoke test run: 19 pass, 1 fail (cache TTL log — minor), 2 skip (obsolete test paths from old .bat shim architecture)
  - [x] 4.2 All critical user-facing flows validated on real compiled artifacts

## Dev Notes

### Context

This story was identified as a **critical path item** in the Epic 8 retrospective (2026-03-31). The retro found that Epic 8's 8 stories had ~95 unit tests with zero regressions, but the full install/update lifecycle had never been validated on compiled artifacts. When Sylvain ran the smoke tests, **10+ real-world bugs** were found that no unit test caught.

### Bugs Found and Fixed During Smoke Testing

All fixes were committed on the `fix/update-mechanism` branch and merged as PR #3:

| Bug | Commit | Root Cause |
|-----|--------|------------|
| GitHub repo URL wrong (underscore vs hyphen) | `d6f8935` | Config typo |
| `config.json` missing on fresh install | `424216e` | No first-run creation |
| SmartScreen blocked installer (Zone.Identifier ADS) | `e3aef73` | Downloaded files marked as "from internet" |
| CMD window visible during update shim | `dc7ca3f` | Windows Terminal intercepts console process |
| Update shim needed elevated PowerShell for UAC | `af4b570` | Silent installer requires admin |
| **Entire .bat shim replaced with `os.startfile()`** | `cc3b353` | Overengineered — 4-layer chain replaced by 1 Windows API call |
| Skip-version message incorrect | `178114c` | UX text showed wrong status |
| Installer retry on pre-delete failure | `178114c` | Locked files on retry |
| Offline update check crashed | `8e5f26c` | Network error not caught |
| Update cache not saved when already up to date | `6b40509` | Cache write skipped on equality |
| Update check not logging to GUI Log panel | `ba1d96f` | Log messages went to stderr only |

### Key Architectural Change: .bat Shim → os.startfile()

The most significant finding was that the update shim (Story 8.7) was overengineered. The original approach:

```
Python app → cmd.exe /c → .bat shim (tasklist polling loop) → PowerShell → Inno Setup
```

Was replaced by:

```
Python app → os.startfile(installer_path) → Windows ShellExecuteW → UAC → Inno Setup
```

`os.startfile()` is the Python equivalent of double-clicking the .exe in Explorer. Windows handles UAC elevation, Inno Setup's Restart Manager handles closing the running app and replacing files. The entire process management layer was redundant.

**Root cause:** No literature review of how existing Windows apps handle auto-update before designing the solution. A survey of VS Code/Squirrel.Windows/Electron patterns would have found this immediately.

### Smoke Test Results Summary

| Run | Date | Pass | Fail | Skip | Notes |
|-----|------|------|------|------|-------|
| 1 | 2026-03-29 15:23 | 17 | 6 | 0 | First run, many issues found |
| 2 | 2026-03-29 16:47 | — | — | — | Partial run after fixes |
| 3 | 2026-03-29 17:15 | — | — | — | Targeted re-test |
| 4 | 2026-03-29 17:57 | — | — | — | Targeted re-test |
| 5 | 2026-03-31 10:37 | 17 | 6 | 0 | Post os.startfile() rewrite |
| 6 | 2026-03-31 12:01 | — | — | — | Partial re-test |
| 7 | 2026-03-31 13:13 | 19 | 1 | 2 | Near-final: only cache TTL log missing |
| 8 | 2026-03-31 15:23 | 19 | 1 | 2 | Final validation before merge |

### Remaining Minor Items (Non-Blocking)

- **Test 5.4 (Cache TTL log message):** Update check doesn't emit "using cached result" to the GUI log panel. Low priority — cache works correctly, just not visible to user.
- **Tests 4.2, 4.3 (Obsolete paths):** Written for old .bat shim architecture. `--update-failed` flag and explicit fallback dialog are from the old design. With `os.startfile()`, failure recovery is handled differently (exception in Python → error dialog in UpdateDialog).

### Smoke Test Runner Architecture

`tests/smoke_test_epic8.py` (702 lines):
- 6 phases, 32 test cases
- Each test has: name, story references, detailed steps (PS>, GUI>, WIN> prefixes)
- Interactive prompt: P(pass) / F(fail) / S(skip) / Q(quit)
- On fail: prompts for notes, asks Continue/Quit
- Saves timestamped report to `tests/smoke-test-results/`
- Handles Ctrl+C gracefully (saves partial results)
- Configurable: `VER_A`, `VER_B`, `REPO` constants

### Files Created/Modified

**New files:**
- `tests/smoke_test_epic8.py` — Interactive smoke test runner (702 lines)
- `_bmad-output/implementation-artifacts/tests/epic-8-smoke-test-plan.md` — Test plan document
- `_bmad-output/implementation-artifacts/tests/test-summary.md` — Test summary
- `tests/smoke-test-results/*.txt` — 8 timestamped result files
- `tests/clear_update_cache.ps1` — Helper script for cache clearing during testing

**Modified files (bug fixes):**
- `src/kipart_search/core/update_shim.py` — Replaced .bat shim with os.startfile()
- `src/kipart_search/core/update_check.py` — Fixed offline check, cache save, log messages
- `src/kipart_search/gui/update_dialog.py` — Fixed download flow, error handling, button states
- `src/kipart_search/gui/main_window.py` — Added update UI integration, status bar version
- `src/kipart_search/core/paths.py` — Added ensure_config_exists() for fresh install
- `installer/kipart-search.iss` — Updated for silent install compatibility
- `release.py` — Extended with --bump, --tag, CI watch
- `build_nuitka.py` — Extended for installer compilation
- `.github/workflows/build-release.yml` — Extended CI pipeline

### References

- [Source: _bmad-output/implementation-artifacts/epic-8-retro-2026-03-31.md — Significant Discoveries #1, #2]
- [Source: tests/smoke_test_epic8.py — 32 test cases across 6 phases]
- [Source: tests/smoke-test-results/ — 8 result files from 2026-03-29 to 2026-03-31]
- [Source: PR #3 fix/update-mechanism — 20 fix commits, 3661 lines added]

## Dev Agent Record

### Agent Model Used

Manual implementation by Sylvain (Project Lead)

### Debug Log References

See smoke test result files in `tests/smoke-test-results/` for detailed per-test outcomes.

### Completion Notes List

- Created `smoke_test_epic8.py` interactive runner with 32 test cases across 6 phases
- Executed 8 rounds of smoke testing on compiled Nuitka binaries and Inno Setup installers
- Found and fixed 10+ real-world bugs invisible to unit tests
- Replaced overengineered .bat shim with `os.startfile()` (commit cc3b353)
- All fixes merged via PR #3 (fix/update-mechanism branch)
- Final validation: 19 pass, 1 minor fail (cache log), 2 skip (obsolete test paths)
- Epic 8 smoke test plan documented as planning artifact

### Implementation Plan

Work was done directly by Sylvain on the fix/update-mechanism branch, iterating between smoke testing and bug fixes over 2 days (2026-03-29 to 2026-03-31).

### Change Log

- 2026-03-29: Created smoke test runner and plan, first test run (17 pass, 6 fail)
- 2026-03-29 to 2026-03-31: Iterative bug fixing — 20 commits
- 2026-03-31: Replaced .bat shim with os.startfile(), final validation (19 pass)
- 2026-03-31: Merged PR #3 to main

### File List

**New files:**
- `tests/smoke_test_epic8.py`
- `_bmad-output/implementation-artifacts/tests/epic-8-smoke-test-plan.md`
- `_bmad-output/implementation-artifacts/tests/test-summary.md`
- `tests/smoke-test-results/smoke-test-epic8-2026-03-29-1523.txt`
- `tests/smoke-test-results/smoke-test-epic8-2026-03-29-1647.txt`
- `tests/smoke-test-results/smoke-test-epic8-2026-03-29-1715.txt`
- `tests/smoke-test-results/smoke-test-epic8-2026-03-29-1757.txt`
- `tests/smoke-test-results/smoke-test-epic8-2026-03-31-1037.txt`
- `tests/smoke-test-results/smoke-test-epic8-2026-03-31-1201.txt`
- `tests/smoke-test-results/smoke-test-epic8-2026-03-31-1313.txt`
- `tests/smoke-test-results/smoke-test-epic8-2026-03-31-1523.txt`
- `tests/clear_update_cache.ps1`

**Modified files:**
- `src/kipart_search/core/update_shim.py`
- `src/kipart_search/core/update_check.py`
- `src/kipart_search/gui/update_dialog.py`
- `src/kipart_search/gui/main_window.py`
- `src/kipart_search/core/paths.py`
- `installer/kipart-search.iss`
- `release.py`
- `build_nuitka.py`
- `.github/workflows/build-release.yml`
