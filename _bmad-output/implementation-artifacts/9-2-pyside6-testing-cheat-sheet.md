# Story 9.2: PySide6 Testing Cheat Sheet

Status: ready-for-dev

## Story

As a developer (human or AI agent),
I want a documented set of proven PySide6 testing patterns referenced in project-context.md, with all pre-existing GUI test failures fixed or marked xfail,
so that every future GUI story starts with correct testing patterns and the test suite runs clean without "pre-existing failure" disclaimers.

## Acceptance Criteria

1. **Given** a developer looks at `project-context.md`, **when** they search for testing guidance, **then** they find a reference to `docs/testing-pyside6.md` with a summary of key rules inline.

2. **Given** `docs/testing-pyside6.md` exists, **when** a developer reads it, **then** it documents at minimum: QApplication lifecycle, widget fixture cleanup, QThread `closeEvent` + `wait()`, QSettings isolation, modal dialog testing, eventFilter testing, and the `MainWindow.__new__()` pattern.

3. **Given** the pre-existing GUI test failures in `test_context_menus.py` (VerifyPanel init crash / access violation in `TestStatusBarAccessibleNames`), **when** the developer fixes or marks them `xfail`, **then** `pytest tests/` produces zero unexpected failures on Windows.

4. **Given** the pre-existing GUI test failures in `test_assign_dialog.py` and `test_kicad_bridge.py`, **when** the developer investigates each, **then** each is either fixed or marked `@pytest.mark.xfail(reason="...")` with a clear explanation.

5. **Given** `tests/conftest.py`, **when** the developer adds a QSettings isolation fixture, **then** no GUI test writes to the real Windows registry or pollutes state for subsequent tests.

6. **Given** all changes are complete, **when** `pytest tests/` runs, **then** all tests pass (or xfail cleanly) with no access violations, segfaults, or unexplained failures. Run twice in a row to verify no test-order dependency.

7. **Given** the cheat sheet is referenced in `project-context.md`, **when** a dev agent loads context for a future GUI story, **then** the testing patterns are available in its context window without needing to be told.

## Tasks / Subtasks

- [ ] Task 1: Create `docs/testing-pyside6.md` (AC: #2)
  - [ ] 1.1 Document QApplication lifecycle pattern (session-scoped fixture, singleton, proper shutdown)
  - [ ] 1.2 Document widget fixture cleanup pattern (yield + close/deleteLater)
  - [ ] 1.3 Document QThread `closeEvent` + `wait(timeout)` pattern with code example from `update_dialog.py` and `main_window.py`
  - [ ] 1.4 Document QSettings isolation (monkeypatch or tmp_path, never write to real registry)
  - [ ] 1.5 Document modal dialog testing with `qtbot`
  - [ ] 1.6 Document eventFilter testing pattern (replacing monkey-patched mousePressEvent)
  - [ ] 1.7 Document `MainWindow.__new__()` minimal-init pattern for testing specific methods
  - [ ] 1.8 Document "things that always fail" anti-patterns list (multiple QApplication, no processEvents, no widget cleanup, accessing QThread after start without wait)
  - [ ] 1.9 Document mock robustness: prefer state-based verification over call-counting

- [ ] Task 2: Fix or xfail pre-existing GUI test failures (AC: #3, #4)
  - [ ] 2.1 Investigate `test_context_menus.py::TestStatusBarAccessibleNames` — currently creates full MainWindow, crashes on VerifyPanel init. Fix by using `MainWindow.__new__()` pattern or mark xfail with reason
  - [ ] 2.2 Investigate `test_assign_dialog.py` failures — check for missing widget cleanup, QThread not waited, or QSettings pollution
  - [ ] 2.3 Investigate `test_kicad_bridge.py` failures — check ScanWorker thread cleanup and signal timing
  - [ ] 2.4 For each: if root cause is clear and fix is safe, fix it. If fix requires refactoring production code, mark `@pytest.mark.xfail(reason="PySide6 widget lifecycle on Windows — tracked in testing-pyside6.md")` instead
  - [ ] 2.5 Run `pytest tests/` twice in a row to confirm no test-order dependencies

- [ ] Task 3: Add QSettings isolation fixture to conftest.py (AC: #5)
  - [ ] 3.1 Add autouse fixture that patches QSettings to use a temp path or in-memory storage
  - [ ] 3.2 Remove manual QSettings cleanup workarounds in `test_context_menus.py` (lines ~287-291) once fixture handles it
  - [ ] 3.3 Verify no GUI test touches real Windows registry after fixture is applied

- [ ] Task 4: Reference cheat sheet in project-context.md (AC: #1, #7)
  - [ ] 4.1 Add a "PySide6 Testing" subsection under the existing testing rules in `project-context.md`
  - [ ] 4.2 Include 3-4 key rules inline (most critical patterns) plus a pointer to the full doc: `docs/testing-pyside6.md`
  - [ ] 4.3 The inline rules must cover: always `wait()` in `closeEvent`, always clean up widgets in fixtures, never write to real QSettings in tests

- [ ] Task 5: Final verification (AC: #6)
  - [ ] 5.1 Run `pytest tests/` — zero unexpected failures
  - [ ] 5.2 Run `pytest tests/` a second time — same result (no order-dependent failures)
  - [ ] 5.3 Verify no new test regressions in core tests

## Dev Notes

### Why This Story Exists

This is a **critical path item from the Epic 8 retrospective** (2026-03-31). The PySide6 testing cheat sheet has been an action item since Epic 1 — 8 epics overdue. Pre-existing GUI test failures have been noted as "unrelated" in 5 of 8 Epic 8 stories. The Epic 7 retro established the rule: "Action items that survive 2+ retros must become stories with acceptance criteria."

The root cause is twofold:
1. **No documented patterns** — Each story rediscovers PySide6 testing gotchas (e.g., QThread cleanup was re-fixed in Stories 8.5, 8.6, 8.7)
2. **No discoverability** — Even if patterns existed, the dev agent wouldn't find them unless they're referenced in `project-context.md`

### Pre-Existing Failure Analysis

From the codebase investigation:

**`test_context_menus.py::TestStatusBarAccessibleNames`**
- Creates full `MainWindow` with mocks, triggers VerifyPanel init
- Access violation / segfault during MainWindow construction on Windows
- Manual QSettings cleanup workaround at lines ~287-291: `settings.remove("geometry")` / `settings.remove("windowState")`
- **Fix approach:** Use `MainWindow.__new__()` to avoid full init, or restructure to test status bar labels without full window construction

**`test_assign_dialog.py`**
- 92 tests, uses `QApplication.instance() or QApplication(sys.argv)` — no teardown
- No `qtbot.waitSignal()` for SearchWorker threads
- **Fix approach:** Add widget cleanup fixtures, ensure threads are waited

**`test_kicad_bridge.py`**
- Uses `qtbot.waitSignal()` correctly in ScanWorker tests (good pattern)
- `TestOnComponentClickedSignalChain` creates MainWindow with `__new__()` and manual mocks — fragile
- **Fix approach:** Verify signal chain tests have proper cleanup, xfail if root cause is deep lifecycle issue

### QThread Cleanup Pattern (Proven in Epic 8)

This pattern was applied in Stories 8.5, 8.6, and 8.7 during code review. It MUST be documented:

```python
# In any QMainWindow or QDialog that creates QThread workers:
def closeEvent(self, event: QCloseEvent):
    """Wait for background workers before destroying the window."""
    if self._worker is not None and self._worker.isRunning():
        self._worker.wait(5000)  # 5-second timeout prevents hang
    super().closeEvent(event)
```

**Real examples in codebase:**
- `gui/update_dialog.py` — waits for `_DownloadWorker`
- `gui/main_window.py:555-567` — waits for `_connect_worker` and `_update_check_worker`

### QSettings Isolation Pattern

The current workaround in `test_context_menus.py`:
```python
finally:
    settings = QSettings("kipart-search", "kipart-search")
    settings.remove("geometry")
    settings.remove("windowState")
    w.close()
```

This should be replaced by a conftest fixture that prevents QSettings from touching the real registry entirely.

### Existing conftest.py Fixtures

`tests/conftest.py` currently has 3 fixtures:
1. `_skip_welcome_dialog` (autouse) — patches `MainWindow._check_welcome`
2. `_reset_license_singleton` (autouse) — resets `License._reset()` with keyring/env mocked
3. `pro_license` — activates Pro tier for specific tests

The QSettings isolation fixture will be the 4th autouse fixture.

### What NOT to Do

- Do NOT add `pytest-qt` as a new dependency if it's not already used — check `pyproject.toml` first. If it IS already used, leverage `qtbot` fixtures.
- Do NOT refactor production GUI code as part of this story — only fix test code and add documentation
- Do NOT create an exhaustive 500-line document — the cheat sheet should be concise, pattern-focused, with code examples. Aim for ~100-150 lines.
- Do NOT change the `closeEvent` implementations in production code — they're already correct from Epic 8. Document them, don't modify them.
- Do NOT add new test infrastructure (CI changes, xvfb, etc.) — scope is documentation + test fixes only

### Exact Files to Modify

| File | Change |
|------|--------|
| `docs/testing-pyside6.md` | **NEW** — Cheat sheet document |
| `_bmad-output/project-context.md` | Add PySide6 testing subsection with inline rules + pointer to cheat sheet |
| `tests/conftest.py` | Add QSettings isolation fixture |
| `tests/test_context_menus.py` | Fix or xfail `TestStatusBarAccessibleNames`, remove manual QSettings cleanup |
| `tests/gui/test_assign_dialog.py` | Fix or xfail failing tests, add widget cleanup |
| `tests/gui/test_kicad_bridge.py` | Fix or xfail failing tests if any |

### Project Structure Notes

- `docs/` already contains `architecture.md`, `development-guide.md`, `index.md` — the cheat sheet fits here as `testing-pyside6.md`
- `project-context.md` lives at `_bmad-output/project-context.md` — this is what the dev agent loads for every story
- Core/GUI separation: this story only touches test files and documentation, no production code changes

### Previous Story Intelligence

**From Story 9.1 (User Verification Status):**
- Added context menu actions to `verify_panel.py` — exactly the kind of GUI code that needs these testing patterns
- Added `core/project_state.py` with atomic JSON writes — core module, no GUI testing issues
- Tests added for project state are pure Python (no PySide6) — good separation

**From Epic 8 Stories 8.5-8.7:**
- QThread `closeEvent` + `wait()` pattern applied 3 times
- eventFilter replaced monkey-patched mousePressEvent (Story 8.5)
- Worker cleanup on dialog close (Story 8.6)
- All three were code review findings, not proactive — proving the pattern needs documentation

### Git Intelligence

Recent commits (fix/update-mechanism branch merged as PR #3) show significant rework of update mechanism. No GUI test changes in that branch — the pre-existing failures are still present on current main.

### References

- [Source: _bmad-output/implementation-artifacts/epic-8-retro-2026-03-31.md — Action Item #1]
- [Source: _bmad-output/implementation-artifacts/epic-7-retro-2026-03-27.md — Action Item #1, #2]
- [Source: _bmad-output/implementation-artifacts/epic-6-retro-2026-03-23.md — PySide6 cheat sheet marked MANDATORY]
- [Source: tests/conftest.py — Current 3 fixtures]
- [Source: tests/test_context_menus.py:287-291 — QSettings manual cleanup workaround]
- [Source: src/kipart_search/gui/update_dialog.py:211-215 — closeEvent + wait pattern]
- [Source: src/kipart_search/gui/main_window.py:555-567 — closeEvent + wait pattern]
- [Source: _bmad-output/project-context.md:59 — Current testing guidance: "GUI testing requires QApplication"]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### Implementation Plan

### Change Log

### File List
