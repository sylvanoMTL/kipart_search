# Story 8.3: Automated Release Build Script

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want a single release script that chains all build steps (tests → GPL check → Nuitka → ZIP → Inno Setup → checksums),
so that releases are reproducible, complete, and can't miss a step.

## Acceptance Criteria

1. **Given** the developer runs `python release.py`, **when** the script executes, **then** it runs the test suite and fails fast if any test fails.

2. **Given** the release script runs, **when** the test suite passes, **then** it runs the GPL firewall check and fails fast if GPL deps are detected.

3. **Given** the GPL check passes, **when** execution continues, **then** it executes the Nuitka build via `build_nuitka.py`.

4. **Given** the Nuitka build completes, **when** it succeeds, **then** it produces the ZIP package (`kipart-search-{version}-windows.zip`).

5. **Given** the ZIP is created, **when** execution continues, **then** it compiles the Inno Setup installer (`kipart-search-{version}-setup.exe`).

6. **Given** all build artifacts are produced, **when** the script finalises, **then** it generates SHA256 checksums for all output files.

7. **Given** the script starts, **when** it reads the version from `pyproject.toml`, **then** it checks the latest GitHub release tag and refuses to build if the version is unchanged (version gate).

8. **Given** the full pipeline succeeds, **when** all steps complete, **then** it prints a human checklist: upload files to GitHub Release, tag commit, write release notes.

9. **Given** any step fails, **when** the failure is detected, **then** the script fails fast — no partial builds left in ambiguous state.

## Tasks / Subtasks

- [x] Task 1: Create `release.py` at project root (AC: #1–#9)
  - [x] 1.1 Create `release.py` with `main()` entry point and argparse for `--skip-tests`, `--skip-version-gate`, `--output-dir`
  - [x] 1.2 Implement version gate: read version from `pyproject.toml` via `build_nuitka.read_base_version()`, query GitHub API for latest release tag, refuse if version is not newer
  - [x] 1.3 Implement test step: run `pytest` via `subprocess.run([sys.executable, "-m", "pytest", "tests/", "-x", "-q"])` and fail fast on non-zero exit
  - [x] 1.4 Implement GPL firewall step: call `build_nuitka.check_licenses()` directly (it already calls `sys.exit(1)` on failure)
  - [x] 1.5 Implement Nuitka build step: call `build_nuitka.build(output_dir)`
  - [x] 1.6 Implement ZIP packaging step: call `build_nuitka.package(output_dir)`
  - [x] 1.7 Implement Inno Setup step: call `build_nuitka.compile_installer(output_dir)`
  - [x] 1.8 Implement SHA256 checksum generation: compute checksums for `.zip` and `-setup.exe`, write `checksums-{version}-sha256.txt` to `dist/`
  - [x] 1.9 Print final human checklist on success

- [x] Task 2: Add tests for `release.py` (AC: #1–#9)
  - [x] 2.1 Create `tests/test_release.py`
  - [x] 2.2 Test version gate: mock GitHub API response, verify build refused when version matches latest tag
  - [x] 2.3 Test version gate: verify build proceeds when version is newer
  - [x] 2.4 Test fail-fast: mock test failure, verify script exits before GPL check
  - [x] 2.5 Test checksum generation: create dummy files, verify SHA256 output file content
  - [x] 2.6 Test `--skip-tests` and `--skip-version-gate` flags

- [ ] Task 3: Verify end-to-end (manual)
  - [ ] 3.1 Run `python release.py --skip-version-gate` (to bypass GitHub check in dev)
  - [ ] 3.2 Verify all artifacts produced in `dist/`: `.zip`, `-setup.exe`, `checksums-*-sha256.txt`
  - [ ] 3.3 Verify checksums match actual files

## Dev Notes

### Architecture: Reuse `build_nuitka.py` Functions Directly

The release script should import and call functions from `build_nuitka.py` — do NOT duplicate any logic. The existing functions are:

| Function | Module | What it does |
|----------|--------|-------------|
| `read_base_version()` | `build_nuitka` | Reads version string from `pyproject.toml` (e.g., `"0.1.0"`) |
| `check_licenses()` | `build_nuitka` | GPL firewall — calls `sys.exit(1)` on violation |
| `build(output_dir)` | `build_nuitka` | Runs Nuitka standalone build |
| `package(output_dir)` | `build_nuitka` | Creates ZIP from Nuitka output |
| `compile_installer(output_dir)` | `build_nuitka` | Compiles Inno Setup `.iss` script |

Import pattern:
```python
from build_nuitka import (
    read_base_version,
    check_licenses,
    build,
    package,
    compile_installer,
)
```

### Version Gate Implementation

Use the unauthenticated GitHub API (60 req/hr per IP, no token needed):

```python
import httpx

def check_version_gate(version: str) -> None:
    """Refuse to build if version matches the latest GitHub release tag."""
    url = "https://api.github.com/repos/sylvanoMTL/kipart-search/releases/latest"
    try:
        resp = httpx.get(url, timeout=10, follow_redirects=True)
        if resp.status_code == 404:
            print("No previous releases found — version gate passed.")
            return
        resp.raise_for_status()
        latest_tag = resp.json().get("tag_name", "")
        latest_version = latest_tag.lstrip("v")
        if latest_version == version:
            print(f"ERROR: Version {version} matches latest release {latest_tag}.")
            print("Bump version in pyproject.toml before building a release.")
            sys.exit(1)
        print(f"Version gate passed: {version} (latest release: {latest_tag})")
    except httpx.HTTPError as exc:
        print(f"WARNING: Could not check GitHub releases: {exc}")
        print("Proceeding without version gate check.")
```

Notes:
- 404 means no releases yet — pass the gate
- Network errors are warnings, not blockers (developer may be offline)
- Compare raw version strings, not semantic versions (the project only uses simple `X.Y.Z`)

### SHA256 Checksum Generation

```python
import hashlib

def generate_checksums(output_dir: str, version: str) -> None:
    """Generate SHA256 checksums for all release artifacts."""
    dist = Path(output_dir)
    artifacts = [
        dist / f"kipart-search-{version}-windows.zip",
        dist / f"kipart-search-{version}-setup.exe",
    ]
    checksum_file = dist / f"checksums-{version}-sha256.txt"
    lines = []
    for artifact in artifacts:
        if artifact.exists():
            sha256 = hashlib.sha256(artifact.read_bytes()).hexdigest()
            lines.append(f"{sha256}  {artifact.name}")
            print(f"  {sha256}  {artifact.name}")
    checksum_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Checksums written to {checksum_file}")
```

The format `{hash}  {filename}` (two spaces) is compatible with `sha256sum --check`.

### Pipeline Step Order

```
1. Version gate         → httpx GET GitHub API (skippable with --skip-version-gate)
2. Run test suite       → pytest tests/ -x -q (skippable with --skip-tests)
3. GPL firewall         → build_nuitka.check_licenses()
4. Nuitka build         → build_nuitka.build(output_dir)
5. ZIP packaging        → build_nuitka.package(output_dir)
6. Inno Setup compile   → build_nuitka.compile_installer(output_dir)
7. SHA256 checksums     → hashlib over .zip and -setup.exe
8. Print checklist      → human-readable next steps
```

Each step must succeed before the next begins. Functions from `build_nuitka` already call `sys.exit(1)` on failure, which is the correct fail-fast behaviour.

### Human Checklist (printed on success)

```
============================================================
Release v{version} build complete!
============================================================

Output files:
  dist/kipart-search-{version}-windows.zip
  dist/kipart-search-{version}-setup.exe
  dist/checksums-{version}-sha256.txt

Next steps:
  1. git tag v{version}
  2. git push origin v{version}
     → CI will build and upload to GitHub Release automatically
  3. Or upload manually: gh release create v{version} dist/kipart-search-{version}-*
  4. Write release notes (or use --generate-release-notes on gh release)
============================================================
```

### CLI Arguments

| Flag | Default | Purpose |
|------|---------|---------|
| `--skip-tests` | False | Skip pytest step (for quick rebuilds during debugging) |
| `--skip-version-gate` | False | Skip GitHub version check (for offline use or re-building same version) |
| `--output-dir` | `dist` | Output directory (passed to all `build_nuitka` functions) |

### What NOT to Do

- Do NOT duplicate `build_nuitka.py` functions — import and call them
- Do NOT use `--onefile` for Nuitka — the existing config uses `--standalone` for LGPL compliance
- Do NOT modify `build_nuitka.py` — this story creates a new orchestrator on top of it
- Do NOT modify the CI workflow — that's Story 8.4
- Do NOT add complex semantic version comparison — simple string equality is sufficient for the version gate
- Do NOT add automatic git tagging or pushing — the script prints a checklist; the developer decides when to tag
- Do NOT catch `SystemExit` from `build_nuitka` functions — let them propagate for fail-fast behaviour
- Do NOT add `release.py` to `pyproject.toml` entry points — it's a developer tool, not a user-facing command

### Project Structure Notes

**New files:**
- `release.py` — release orchestrator script (project root, next to `build_nuitka.py`)
- `tests/test_release.py` — tests for release script

**No changes to:**
- `build_nuitka.py` — all functions reused as-is
- `installer/kipart-search.iss` — already correct from Story 8.2
- `pyproject.toml` — no new dependencies (`httpx` and `hashlib` already available)
- `.github/workflows/build-windows.yml` — CI extension is Story 8.4
- `src/kipart_search/` — no application code changes

### Previous Story Intelligence

**From Story 8.2 (Inno Setup Installer Script):**
- `compile_installer()` in `build_nuitka.py` handles iscc detection (PATH + default location), version injection via `/DMyAppVersion`, output verification
- `--installer` flag already chains build → package → installer, but without tests, version gate, or checksums
- The installer output is `dist/kipart-search-{version}-setup.exe`
- Tests for build_nuitka are in `tests/test_build_nuitka.py` — follow same patterns for `test_release.py`

**From Story 8.1 (platformdirs Migration):**
- User data paths now use `platformdirs` (`%LOCALAPPDATA%\KiPartSearch\`)
- No impact on release script, but the installer's uninstall prompt targets this path

**From Story 7.4 (ZIP Distribution):**
- `package()` creates `dist/kipart-search-{version}-windows.zip`
- `read_base_version()` reads from `pyproject.toml` — reuse this for version gate

**From Story 7.5 (CI Pipeline):**
- CI at `.github/workflows/build-windows.yml` uses `softprops/action-gh-release@v2`
- CI triggers on `v*.*.*` tags and verifies tag matches `pyproject.toml` version
- The release script's checklist should reference this: "push the tag → CI builds and uploads automatically"

### Git Intelligence

Recent commits:
- `3dd27c6` — Story 8.2 (Inno Setup installer) — directly preceding this story
- `bcd4735` — Fix migration edge case (Story 8.1 follow-up)
- `7392e43` — Story 8.1 platformdirs migration

`build_nuitka.py` is 385 lines with clean `main()` → argparse → dispatch pattern. The release script follows the same argparse pattern but orchestrates a superset pipeline.

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 8, Story 8.3]
- [Source: _bmad-output/planning-artifacts/architecture.md — Build & Packaging section]
- [Source: build_nuitka.py — functions to reuse: read_base_version, check_licenses, build, package, compile_installer]
- [Source: .github/workflows/build-windows.yml — CI pipeline that release artifacts feed into]
- [Source: _bmad-output/implementation-artifacts/8-2-inno-setup-installer-script.md — predecessor story]
- [Source: _bmad-output/implementation-artifacts/7-4-windows-zip-distribution-package.md — packaging pattern]

## Change Log

- 2026-03-25: Created release.py orchestrator and tests/test_release.py (12 tests, all passing)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- Fixed httpx import: moved from lazy import inside `check_version_gate()` to module-level so tests can patch `release.httpx`

### Completion Notes List

- Created `release.py` at project root — orchestrates the full 7-step release pipeline (version gate, tests, GPL check, Nuitka build, ZIP, Inno Setup, checksums) with human checklist on completion
- All `build_nuitka` functions imported and called directly — zero logic duplication
- Version gate uses unauthenticated GitHub API; network errors are warnings not blockers
- SHA256 checksum output is `sha256sum --check` compatible (two-space separator)
- CLI flags: `--skip-tests`, `--skip-version-gate`, `--output-dir`
- Created `tests/test_release.py` with 12 tests covering: version gate (4 tests), fail-fast (1 test), checksums (3 tests), CLI flags (4 tests including full pipeline order verification)
- All 12 new tests pass; 288 non-GUI tests pass with zero regressions
- Task 3 (manual end-to-end verification) left unchecked — requires Nuitka + Inno Setup installed to run

### File List

- `release.py` (new) — release orchestrator script
- `tests/test_release.py` (new) — 12 unit tests for release script
