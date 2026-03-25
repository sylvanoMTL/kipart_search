# Story 7.5: CI Build Pipeline

Status: done

## Story

As a developer,
I want an automated CI pipeline that compiles, tests, and packages the Windows binary on every tagged release,
so that distribution builds are reproducible and not dependent on my local machine.

## Acceptance Criteria

1. **Given** a GitHub Actions workflow file (`.github/workflows/build-windows.yml`), **when** a version tag (`v*.*.*`) is pushed to the repository, **then** the pipeline installs Python 3.10+, project dependencies, and Nuitka.

2. **Given** the pipeline is running, **when** the dependency installation completes, **then** the GPL firewall check runs via `python build_nuitka.py` (the `check_licenses()` function) and fails the pipeline if GPL deps are detected.

3. **Given** the GPL check passes, **when** the Nuitka build step executes, **then** the standalone binary is produced in `dist/__main__.dist/` with `kipart-search.exe`.

4. **Given** a successful build, **when** the smoke test step runs, **then** a headless validation confirms the binary launches and exits cleanly (non-interactive — NOT the interactive `tests/smoke_test_build.py`).

5. **Given** a successful build, **when** the packaging step runs, **then** `kipart-search-{version}-windows.zip` is produced with the correct version from the tag.

6. **Given** the zip is produced, **when** the pipeline completes, **then** the zip is uploaded as a GitHub Release asset attached to the tag.

7. **Given** the pipeline, **when** executed, **then** it completes in under 30 minutes.

8. **Given** repeated pipeline runs, **when** caches are available, **then** pip dependencies and Nuitka ccache are cached between runs to speed up subsequent builds.

## Tasks / Subtasks

- [x] Task 1: Create `.github/workflows/build-windows.yml` (AC: #1, #7, #8)
  - [x] 1.1 Create `.github/workflows/` directory
  - [x] 1.2 Define workflow trigger: `on: push: tags: ['v*.*.*']`
  - [x] 1.3 Configure `runs-on: windows-latest` with `shell: bash`
  - [x] 1.4 Checkout step with `actions/checkout@v4`
  - [x] 1.5 Set up Python 3.10 with `actions/setup-python@v5` and pip cache
  - [x] 1.6 Install project deps: `pip install -e ".[dev]"` + `pip install nuitka`
  - [x] 1.7 Cache Nuitka ccache directory (`%LOCALAPPDATA%\Nuitka\Nuitka\Cache`) with `actions/cache@v4`

- [x] Task 2: Add GPL firewall check step (AC: #2)
  - [x] 2.1 Run `python build_nuitka.py --skip-license-check` is NOT used — the default `build()` path includes `check_licenses()` already
  - [x] 2.2 Alternatively, run `check_licenses()` as an explicit early step: `python -c "from build_nuitka import check_licenses; check_licenses()"` before the full build, so GPL violation fails fast before the 15+ minute Nuitka compilation

- [x] Task 3: Add Nuitka build step (AC: #3)
  - [x] 3.1 Run `python build_nuitka.py --package` — this calls `check_licenses()` → `build()` → `package()`
  - [x] 3.2 Override version from tag: extract version from `${{ github.ref_name }}` (strip `v` prefix), verify it matches `pyproject.toml`

- [x] Task 4: Add headless smoke test step (AC: #4)
  - [x] 4.1 Create a minimal headless smoke test: launch `kipart-search.exe --version` or similar, verify it prints the version and exits 0
  - [x] 4.2 If no `--version` flag exists, add one to `__main__.py`: parse `--version` before QApplication, print `__version__`, `sys.exit(0)` — this avoids needing a display server
  - [x] 4.3 Verify the exe exists at `dist/__main__.dist/kipart-search.exe` before running
  - [x] 4.4 Run existing unit tests: `python -m pytest tests/test_build_nuitka.py -v` to validate build script logic

- [x] Task 5: Upload release asset (AC: #5, #6)
  - [x] 5.1 Use `softprops/action-gh-release@v2` to create the GitHub Release from the tag
  - [x] 5.2 Attach `dist/kipart-search-*-windows.zip` as a release asset
  - [x] 5.3 Auto-generate release notes from commits since last tag (GitHub default)

- [x] Task 6: Add `--version` flag to `__main__.py` (AC: #4)
  - [x] 6.1 In `__main__.py`, before `QApplication` creation, check `sys.argv` for `--version`
  - [x] 6.2 If `--version`, print version string and `sys.exit(0)` — no GUI, no display required
  - [x] 6.3 Add test for `--version` flag in test suite

- [x] Task 7: Run tests and verify (AC: all)
  - [x] 7.1 Run `python -m pytest tests/test_build_nuitka.py -v` — all existing tests pass
  - [x] 7.2 Validate YAML syntax of the workflow file
  - [x] 7.3 Verify workflow references correct paths (`build_nuitka.py`, `dist/` outputs)

## Dev Notes

### GitHub Actions Workflow Structure

The workflow should be a single job on `windows-latest`:

```yaml
name: Build Windows Release
on:
  push:
    tags: ['v*.*.*']

jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
          cache: 'pip'
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
          pip install nuitka
      - name: Build and package
        run: python build_nuitka.py --package
      - name: Smoke test
        run: dist/__main__.dist/kipart-search.exe --version
      - name: Upload release
        uses: softprops/action-gh-release@v2
        with:
          files: dist/kipart-search-*-windows.zip
```

### Version Tag Handling

The tag `v0.1.0` should match `pyproject.toml` version `0.1.0`. The workflow should verify this consistency. The `package()` function in `build_nuitka.py` already reads version from `pyproject.toml` via `read_base_version()` — no need to pass it from the tag. However, a validation step should compare the tag version with pyproject.toml to catch mismatches early.

### Headless Smoke Test Strategy

The existing `tests/smoke_test_build.py` is interactive (prompts for pass/fail) — it CANNOT run in CI. For CI, the simplest headless approach is a `--version` flag:

1. Add `--version` to `__main__.py` — checks `sys.argv` BEFORE creating `QApplication`
2. Prints `kipart-search {version}` to stdout and exits 0
3. This works headless (no display server needed on Windows GHA runners)
4. CI step: `dist/__main__.dist/kipart-search.exe --version` — validates exe loads, imports work, exits cleanly

Do NOT try to launch the full GUI in CI — Windows GHA runners have no display. Do NOT use `xvfb` — that's Linux only. The `--version` flag is the standard approach for headless binary validation.

### Nuitka ccache

Nuitka stores its compilation cache in `%LOCALAPPDATA%\Nuitka\Nuitka\Cache` on Windows. Caching this directory between runs dramatically speeds up subsequent builds (from ~15 min to ~5 min for incremental changes). Use `actions/cache@v4` with a key based on Python version + dependencies hash.

### Build Script Invocation

`build_nuitka.py` already has the complete build pipeline:
- `python build_nuitka.py` — GPL check + Nuitka build
- `python build_nuitka.py --package` — GPL check + build + zip packaging
- `python build_nuitka.py --package-only` — zip only (skip build)

For CI, use `--package` to get the full pipeline in one command. The GPL firewall check runs automatically as the first step inside `build()`.

### Nuitka Installation

Nuitka is NOT in `pyproject.toml` dependencies (it's a build tool, not a runtime dependency). Install it explicitly: `pip install nuitka`. Nuitka auto-downloads MinGW64 compiler on Windows via `--assume-yes-for-downloads` flag (already in `build_nuitka.py`).

### What NOT to Do

- Do NOT use `--onefile` in the build — violates LGPL (already enforced in build script)
- Do NOT run `tests/smoke_test_build.py` in CI — it's interactive, requires human input
- Do NOT try to launch the full GUI in CI — no display server available
- Do NOT add Linux/macOS builds — this epic is Windows-only per Epic 7 scope
- Do NOT add code signing — requires EV certificate, separate future story
- Do NOT add auto-update mechanism — out of scope
- Do NOT modify the Nuitka build flags — they're already correct from Stories 7.1/7.2
- Do NOT add `nuitka` to `pyproject.toml` — it's build-only, installed explicitly in CI
- Do NOT create matrix builds (multiple Python versions) — only 3.10 is supported

### Project Structure Notes

**New files:**
- `.github/workflows/build-windows.yml` — GitHub Actions workflow

**Modified files:**
- `src/kipart_search/__main__.py` — add `--version` flag (early exit before QApplication)

**No changes to:**
- `build_nuitka.py` — already complete from Stories 7.1/7.4
- `pyproject.toml` — no new dependencies needed
- Any `core/` or `gui/` modules

### Existing Patterns to Follow

- **Build script**: `build_nuitka.py` at project root — 287 lines, `main()` → argparse → `check_licenses()` → `build()` → `package()`. The CI workflow calls this directly.
- **Version reading**: `read_base_version()` returns raw `X.X.X` from pyproject.toml. `read_version()` returns Windows PE quad `X.X.X.X`.
- **Dist layout**: `dist/__main__.dist/kipart-search.exe` is the binary. `dist/kipart-search/` is the user-facing copy. `dist/kipart-search-{version}-windows.zip` is the distributable.
- **Entry point**: `src/kipart_search/__main__.py` calls `_init_keyring_compiled()` then `run_app()` from `gui.main_window`. The `--version` check must happen BEFORE these.

### Previous Story Intelligence

**From Story 7.4 (Windows Zip Distribution Package):**
- `--package` flag triggers full pipeline: GPL check → Nuitka build → zip packaging
- `--package-only` repackages without rebuilding
- Zip output: `dist/kipart-search-{version}-windows.zip`
- Version from `read_base_version()` (raw format, not quad)
- 15 new tests in `test_build_nuitka.py`, 263 total non-GUI tests pass

**From Story 7.1 (Minimal Nuitka Build):**
- `dist/__main__.dist/` is Nuitka output folder (from `__main__.py` entry point)
- Build produces ~68 files, ~115 MB total
- `--assume-yes-for-downloads` auto-downloads MinGW64 on Windows
- Nuitka is AGPL but excluded from GPL firewall (build-only tool, not bundled)
- `tomllib` (Python 3.11+) with `tomli` fallback for Python 3.10

**From Story 7.2 (Compiled Binary Verification):**
- kipart-search.exe is 47 MB; total dist ~116 MB
- All features verified working in compiled binary
- Windows Defender may flag exe (code signing is a future concern)

**From Story 7.3 (License Module):**
- No build script changes needed for license module (auto-included via `--include-package=kipart_search`)
- Dev bypass key rejected in compiled binaries (uses `__compiled__` detection)

### GitHub Actions Runner Notes

- `windows-latest` is Windows Server 2022 (compatible with our Windows 10/11 target)
- Python 3.10 available via `actions/setup-python@v5`
- pip cache supported natively by `setup-python` action
- No display server — cannot run GUI apps, hence the `--version` approach
- Default shell is PowerShell; use `shell: bash` for consistency with project conventions
- 7 GB RAM, 2-core CPU — sufficient for Nuitka compilation

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 7, Story 7.5]
- [Source: build_nuitka.py — existing build script with GPL check, build, package functions]
- [Source: tests/test_build_nuitka.py — 30+ existing tests for build pipeline]
- [Source: tests/smoke_test_build.py — interactive smoke test (NOT for CI)]
- [Source: pyproject.toml — v0.1.0, deps, entry point]
- [Source: _bmad-output/implementation-artifacts/7-4-windows-zip-distribution-package.md — packaging learnings]
- [Source: _bmad-output/implementation-artifacts/7-1-minimal-nuitka-build.md — Nuitka flags, dist layout]
- [Source: GitHub Actions docs — windows-latest, setup-python, cache, gh-release]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

None — clean implementation with no blockers.

### Completion Notes List

- **Task 6 (--version flag):** Added `_check_version_flag()` to `__main__.py` that checks `sys.argv` for `--version` before any GUI imports. Prints `kipart-search {version}` and exits 0. Two tests validate: correct output and no GUI/PySide6 dependency.
- **Tasks 1-5 (workflow file):** Created `.github/workflows/build-windows.yml` with all required steps: checkout, Python 3.10 setup with pip cache, dependency installation, Nuitka ccache caching, GPL firewall check (early fail-fast before Nuitka compilation), version tag vs pyproject.toml verification, `python build_nuitka.py --package` for full build+package, headless smoke test (`kipart-search.exe --version`), unit test execution, and GitHub Release upload via `softprops/action-gh-release@v2` with auto-generated release notes.
- **Task 7 (verification):** 49 tests pass in `test_build_nuitka.py` (36 pre-existing + 2 version flag + 11 workflow validation). No regressions introduced. Pre-existing GUI test failures in `test_assign_dialog.py` and `test_kicad_bridge.py` (4 failures) are unrelated to this story.

### Change Log

- 2026-03-25: Story 7.5 CI Build Pipeline — created workflow file, added --version flag, 13 new tests

### File List

- `.github/workflows/build-windows.yml` — NEW: GitHub Actions workflow for Windows release builds
- `src/kipart_search/__main__.py` — MODIFIED: added `_check_version_flag()` for headless `--version` support
- `tests/test_build_nuitka.py` — MODIFIED: added `TestVersionFlag` (2 tests) and `TestWorkflowFile` (11 tests)
- `docs/development-guide.md` — MODIFIED: added Licensing & Dependency Audit section, updated testing section
