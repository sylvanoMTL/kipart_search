# Story 8.4: Extend CI for Inno Setup and Release Assets

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want the GitHub Actions CI pipeline to compile the Inno Setup installer and upload both ZIP and installer as release assets,
so that the full release package is built automatically on every tagged release.

## Acceptance Criteria

1. **Given** the existing `.github/workflows/build-windows.yml` from Story 7.5, **when** a version tag (`v*.*.*`) is pushed, **then** the pipeline installs Inno Setup on the Windows runner.

2. **Given** Inno Setup is installed, **when** the Nuitka build and ZIP packaging complete, **then** the Inno Setup `.iss` script is compiled to produce `kipart-search-{version}-setup.exe`.

3. **Given** both ZIP and installer are built, **when** the release upload step runs, **then** both `kipart-search-{version}-windows.zip` and `kipart-search-{version}-setup.exe` are uploaded as GitHub Release assets.

4. **Given** all release artifacts are built, **when** the pipeline generates checksums, **then** SHA256 checksums are generated and uploaded as a separate `checksums-{version}-sha256.txt` file (or included in release notes).

5. **Given** the workflow file, **when** reviewing the job matrix, **then** macOS and Linux build jobs exist as commented-out stubs in the workflow matrix, ready to enable.

6. **Given** the full pipeline runs, **when** all steps complete, **then** the pipeline still completes in under 30 minutes.

## Tasks / Subtasks

- [x] Task 1: Add Inno Setup installation step to CI (AC: #1)
  - [x] 1.1 Add a step to install Inno Setup via Chocolatey (`choco install innosetup -y --no-progress`) or the `jrsoftware/iscc` action
  - [x] 1.2 Verify `iscc` is on PATH after installation

- [x] Task 2: Add Inno Setup compile step (AC: #2)
  - [x] 2.1 After the existing "Build and package" step, add a step that runs `python build_nuitka.py --installer-only` (reuses the already-built Nuitka output)
  - [x] 2.2 Verify `dist/kipart-search-{version}-setup.exe` exists after compile

- [x] Task 3: Add SHA256 checksum generation step (AC: #4)
  - [x] 3.1 Add a step that computes SHA256 for both `.zip` and `-setup.exe` and writes `dist/checksums-{version}-sha256.txt`
  - [x] 3.2 Use the same `sha256sum`-compatible format as `release.py` (two-space separator)

- [x] Task 4: Update release upload to include all artifacts (AC: #3, #4)
  - [x] 4.1 Change the `softprops/action-gh-release@v2` `files` glob to `dist/kipart-search-*` to capture both ZIP and installer
  - [x] 4.2 Add the checksums file to the upload glob

- [x] Task 5: Add commented-out macOS/Linux stubs (AC: #5)
  - [x] 5.1 Add a commented-out job matrix with `os: [windows-latest, macos-latest, ubuntu-latest]` as documentation stubs
  - [x] 5.2 Include notes on what each platform would need (e.g., macOS: create `.app` bundle; Linux: AppImage)

- [x] Task 6: Verify pipeline timing (AC: #6)
  - [x] 6.1 Confirm total timeout stays at 30 minutes
  - [x] 6.2 The Inno Setup install + compile should add < 2 minutes to the pipeline

## Dev Notes

### Existing CI Workflow: `.github/workflows/build-windows.yml`

The current workflow (73 lines) triggers on `v*.*.*` tags and does:
1. Checkout → Python 3.10 → `pip install -e ".[dev]"` + nuitka
2. Nuitka ccache (actions/cache@v4)
3. GPL firewall check
4. Tag-vs-pyproject.toml version verification
5. `python build_nuitka.py --package` (Nuitka build + ZIP)
6. Smoke test: run `kipart-search.exe --version`
7. Unit tests: `pytest tests/test_build_nuitka.py`
8. Upload ZIP via `softprops/action-gh-release@v2`

This story extends it — it does NOT replace or rewrite the workflow.

### Inno Setup Installation on GitHub Actions

GitHub's `windows-latest` runners do NOT include Inno Setup. Install via Chocolatey (pre-installed on runners):

```yaml
- name: Install Inno Setup
  run: choco install innosetup -y --no-progress
```

After Chocolatey install, `iscc` is available at `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`. The `build_nuitka.compile_installer()` function already checks both PATH and this default location, so no additional PATH configuration is needed.

### Inno Setup Compile Step

Use `--installer-only` flag — the Nuitka build output in `dist/__main__.dist/` already exists from the "Build and package" step. Do NOT re-run the full build:

```yaml
- name: Compile Inno Setup installer
  run: python build_nuitka.py --installer-only
```

This calls `compile_installer("dist")` which runs:
```
iscc /DMyAppVersion={version} /DMyOutputDir=dist /DMySourceDir=dist/__main__.dist installer/kipart-search.iss
```

Output: `dist/kipart-search-{version}-setup.exe`

### SHA256 Checksum Generation

Use bash (the workflow default shell) for cross-platform compatibility:

```yaml
- name: Generate SHA256 checksums
  run: |
    cd dist
    VERSION=$(python -c "from build_nuitka import read_base_version; print(read_base_version())")
    sha256sum kipart-search-${VERSION}-windows.zip kipart-search-${VERSION}-setup.exe > checksums-${VERSION}-sha256.txt
    cat checksums-${VERSION}-sha256.txt
```

Note: `sha256sum` is available on `windows-latest` runners via Git Bash (the shell is `bash`).

### Release Upload Update

Current:
```yaml
files: dist/kipart-search-*-windows.zip
```

Updated to capture all artifacts:
```yaml
files: |
  dist/kipart-search-*-windows.zip
  dist/kipart-search-*-setup.exe
  dist/checksums-*-sha256.txt
```

### Commented-Out Multi-Platform Stubs

Add as comments at the top of the jobs section or as a separate commented-out job. Purpose is documentation — making it easy to enable macOS/Linux when ready:

```yaml
# --- Future multi-platform builds ---
# To enable, uncomment and add platform-specific steps:
#   macos-latest: create .app bundle, DMG packaging
#   ubuntu-latest: AppImage or .deb packaging
# build-matrix:
#   strategy:
#     matrix:
#       os: [windows-latest, macos-latest, ubuntu-latest]
#   runs-on: ${{ matrix.os }}
```

### What NOT to Do

- Do NOT rewrite the entire workflow — extend the existing one with new steps inserted after "Build and package"
- Do NOT run `release.py` in CI — it's a local developer tool with interactive version gate and test suite. The CI workflow has its own version check and test steps
- Do NOT add `--installer` to the existing "Build and package" step — keep build and installer as separate steps for clarity and independent failure reporting
- Do NOT install Inno Setup via direct download/MSI — Chocolatey is the idiomatic approach for GitHub Actions Windows runners
- Do NOT add new secrets or tokens — all steps use unauthenticated APIs or built-in `GITHUB_TOKEN`
- Do NOT change the trigger from `v*.*.*` tags — the release trigger pattern is correct
- Do NOT add `workflow_dispatch` trigger unless explicitly asked — tagged releases only

### Project Structure Notes

**Modified files:**
- `.github/workflows/build-windows.yml` — add Inno Setup install, compile, checksum, and update upload step

**No new files.** No changes to `build_nuitka.py`, `release.py`, `installer/kipart-search.iss`, or any source code.

### Previous Story Intelligence

**From Story 8.3 (Automated Release Build Script):**
- `release.py` created at project root — orchestrates the full local pipeline
- Human checklist in release.py specifically says "push the tag → CI builds and uploads automatically" — this story makes that true
- SHA256 format: `{hash}  {filename}` (two-space separator, `sha256sum --check` compatible)
- Version reading: `build_nuitka.read_base_version()` returns string like `"0.1.0"`

**From Story 8.2 (Inno Setup Installer Script):**
- `compile_installer()` in `build_nuitka.py` handles `iscc` detection: checks PATH first, then `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`
- Version injected via `/DMyAppVersion={version}` preprocessor directive
- Output naming: `kipart-search-{version}-setup.exe`
- The `.iss` script at `installer/kipart-search.iss` is committed and version-controlled

**From Story 7.5 (CI Pipeline):**
- Uses `softprops/action-gh-release@v2` with `generate_release_notes: true`
- Tag-vs-pyproject.toml version verification already exists
- `permissions: contents: write` already set (needed for release upload)
- Shell is `bash` (set in job defaults)
- Timeout is 30 minutes

### Git Intelligence

Recent commits:
- `067805b` — Story 8.3: `release.py` + `tests/test_release.py`
- `ccc38f3` — Story 8.2 code review fixes
- `3dd27c6` — Story 8.2: Inno Setup installer script + `build_nuitka.py` extensions
- `bcd4735` — Story 8.1 migration fix
- `7392e43` — Story 8.1: platformdirs migration

The CI workflow was last modified in Story 7.5 and has not been touched since. The current workflow is 73 lines with a single `build-windows` job.

### References

- [Source: .github/workflows/build-windows.yml — current CI workflow (73 lines)]
- [Source: _bmad-output/planning-artifacts/epics.md — Epic 8, Story 8.4]
- [Source: build_nuitka.py — compile_installer() function, read_base_version()]
- [Source: installer/kipart-search.iss — Inno Setup script]
- [Source: release.py — SHA256 checksum format reference]
- [Source: _bmad-output/implementation-artifacts/8-3-automated-release-build-script.md — predecessor story]
- [Source: _bmad-output/implementation-artifacts/8-2-inno-setup-installer-script.md — Inno Setup story]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

None — clean implementation with no blockers.

### Completion Notes List

- Extended `.github/workflows/build-windows.yml` from 73 to 122 lines
- Added Inno Setup installation via Chocolatey (`choco install innosetup -y --no-progress`) with `pwsh` shell override (Chocolatey needs PowerShell)
- Added `iscc` verification step checking both PATH and default `C:\Program Files (x86)\Inno Setup 6\ISCC.exe` location
- Added `--installer-only` step to compile the Inno Setup installer from existing Nuitka output (no rebuild)
- Added installer artifact verification step
- Added SHA256 checksum generation using `sha256sum` (available via Git Bash on `windows-latest` runners), two-space separator format matching `release.py`
- Updated `softprops/action-gh-release@v2` upload to include ZIP, setup.exe, and checksums.txt via multi-line glob
- Added commented-out multi-platform build stubs (macOS: .app/DMG, Ubuntu: AppImage/.deb) above the `jobs:` section
- Timeout remains at 30 minutes; new steps estimated to add < 2 minutes
- Added 8 new workflow tests to `tests/test_build_nuitka.py` covering all new CI features
- All 90 tests pass (78 build_nuitka + 12 release), 1 skipped (PyYAML optional)

### Change Log

- 2026-03-25: Implemented Story 8.4 — extended CI workflow with Inno Setup install, compile, SHA256 checksums, multi-artifact upload, and multi-platform stubs

### File List

- `.github/workflows/build-windows.yml` — modified: added Inno Setup install, compile, verify, checksum, updated upload, multi-platform stubs
- `tests/test_build_nuitka.py` — modified: added 8 new tests for CI workflow validation
