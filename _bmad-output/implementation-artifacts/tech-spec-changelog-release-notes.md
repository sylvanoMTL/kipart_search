---
title: 'CHANGELOG-based release notes'
slug: 'changelog-release-notes'
created: '2026-03-26'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['python', 'github-actions', 'softprops/action-gh-release@v2']
files_to_modify: ['release.py', '.github/workflows/build-windows.yml', 'tests/test_release.py']
files_to_create: ['CHANGELOG.md']
code_patterns: ['root-level scripts (not packages)', 'subprocess.run for git ops', 'read_base_version() for version string']
test_patterns: ['pytest + unittest.mock', 'patch/MagicMock for subprocess and httpx', 'tests/test_release.py mirrors release.py']
---

# Tech-Spec: CHANGELOG-based release notes

**Created:** 2026-03-26

## Overview

### Problem Statement

GitHub Releases currently show only auto-generated commit lists (`generate_release_notes: true`), which are noisy and not user-facing. There is no structured changelog and no way for users to quickly see what changed in a release.

### Solution

Add a `CHANGELOG.md` in Keep a Changelog format. A CI step extracts the section matching the tagged version and writes it to `dist/release-notes.md` (empty file if no entry found). `softprops/action-gh-release@v2` reads it via `body_path`, appending GitHub's auto-generated commit notes below. `release.py` validates that a CHANGELOG entry exists before tagging (warning only).

### Scope

**In Scope:**
- Create `CHANGELOG.md` with Keep a Changelog format
- CI step to extract the current version's section from `CHANGELOG.md` into `dist/release-notes.md`
- `softprops/action-gh-release@v2` uses `body_path` to include the extracted notes
- `release.py` warns if no CHANGELOG entry exists for the current version
- Python function `extract_changelog()` for extraction logic (used by both release.py validation and CI)
- Tests for extraction logic and warning behavior

**Out of Scope:**
- Fully automatic changelog generation from stories or commits
- Changelog linting or validation tools
- Retroactive changelog entries for past development

## Context for Development

### Codebase Patterns

- `release.py` is a standalone root-level script (not a package) — imported via `sys.path.insert(0, ROOT)`
- CI workflow at `.github/workflows/build-windows.yml` uses `softprops/action-gh-release@v2` with `generate_release_notes: true`
- Version is read via `build_nuitka.read_base_version()` — returns string like `"0.1.0"`
- `tag_and_push()` in `release.py` does git tag + push but does NOT create the GitHub Release — CI does
- `softprops/action-gh-release@v2` supports `body_path` — when set alongside `generate_release_notes: true`, the body appears above auto-generated notes
- Tests use `pytest` + `unittest.mock` with heavy `patch`/`MagicMock` usage
- The workflow shell is `bash` (set in job defaults)

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `release.py` | Release orchestration — `tag_and_push()`, `print_checklist()`, CLI args |
| `.github/workflows/build-windows.yml` | CI workflow — `softprops/action-gh-release@v2` upload step (line 115-122) |
| `build_nuitka.py` | `read_base_version()` for version string |
| `tests/test_release.py` | Existing tests: version gate, checksums, CLI flags, pipeline order |

### Technical Decisions

- **CHANGELOG format**: Keep a Changelog — `## [X.Y.Z] - YYYY-MM-DD` headers with `### Added / Changed / Fixed / Removed` subsections
- **CI extracts notes**: A Python one-liner in the workflow calls `extract_changelog()` from `release.py` and writes the result to `dist/release-notes.md`. The file is always created (empty if no entry) to avoid `body_path` failure on missing file. `softprops/action-gh-release@v2` reads it via `body_path`.
- **Version passed via sys.argv**: The CI step passes the version as a command-line argument to the Python one-liner instead of shell variable interpolation inside a Python string, avoiding quoting/escaping issues.
- **release.py validates**: Both `--tag` and full-build modes warn if no CHANGELOG entry exists. Warning only — not blocking.
- **Extraction logic in Python, not bash**: Keeps the logic testable and avoids fragile sed/awk.
- **`changelog_path` is relative to CWD**: Default `"CHANGELOG.md"` works in CI (CWD = repo root) and locally. Document this in the function docstring.

## Implementation Plan

### Tasks

- [x] Task 1: Add `extract_changelog()` function to `release.py`
  - File: `release.py`
  - Action: Add function `extract_changelog(version: str, changelog_path: str = "CHANGELOG.md") -> str | None` that reads `CHANGELOG.md`, finds the `## [X.Y.Z]` section matching `version`, and returns the `.strip()`ped content between that header and the next `## [` header (or EOF). Returns `None` if the file doesn't exist or the version isn't found.
  - Matching rule: `line.startswith(f"## [{version}]")` — strict prefix match, no v-prefix, no fuzzy matching.
  - Notes: Use simple line-by-line parsing. Include the subsection headers (`### Added`, etc.) but not the `## [X.Y.Z]` header itself. Strip leading/trailing whitespace from the returned content. Open file with `encoding="utf-8"` explicitly (Windows defaults to cp1252, which breaks on non-ASCII characters). Docstring should note that `changelog_path` is relative to CWD.

- [x] Task 2: Add CHANGELOG validation to `release.py` pipeline
  - File: `release.py`
  - Action: In `main()`, add a changelog check after the version gate. Call `extract_changelog(version)` — if `None`, print a visually prominent warning with blank lines before/after: `\nWARNING: No CHANGELOG.md entry found for version {version}\n`. Do this in both `--tag` mode and full-build mode. Warning only, not `sys.exit(1)`.
  - Insertion points:
    - **`--tag` mode**: After the version gate `if/else` block (around line 186) and before `print("Step 2/2: Tag and push")`. Add the changelog check as a standalone print, not inside a numbered step.
    - **Full-build mode**: After the version gate `if/else` block (around line 201) and before the `# Step 2: Test suite` comment. Add as a continuation of Step 1 output.
  - Notes: The warning must be visible — blank lines and clear prefix prevent it from being lost in terminal output. Do not renumber existing steps.

- [x] Task 3: Create `CHANGELOG.md` with initial entry
  - File: `CHANGELOG.md` (new)
  - Action: Create file with Keep a Changelog header, an empty `## [Unreleased]` section (no placeholder subsections — just the header and a blank line), followed by an entry for the current version from `pyproject.toml` (use `read_base_version()` — currently `0.1.0`) with today's date. Include `### Added` subsection with key features.
  - Notes: Format reference: https://keepachangelog.com/en/1.1.0/. The `## [Unreleased]` section is intentionally empty — users add to it as they work. Use the actual version from `pyproject.toml`, not a hardcoded value — if the version has been bumped by implementation time, the CHANGELOG entry must match.

- [x] Task 4: Add CI step to extract release notes
  - File: `.github/workflows/build-windows.yml`
  - Action: Add a step after "Generate SHA256 checksums" and before "Upload release" that extracts the changelog section for the tagged version into `dist/release-notes.md`. Always create the file (empty if no entry found):
    ```yaml
    - name: Extract release notes
      run: |
        VERSION="${GITHUB_REF_NAME#v}"
        python -c "import sys; from release import extract_changelog; notes=extract_changelog(sys.argv[1]); f=open('dist/release-notes.md','w'); f.write(notes or ''); f.close(); print(('Release notes extracted for '+sys.argv[1]) if notes else 'No CHANGELOG entry -- auto-generated notes only')" "$VERSION"
    ```
  - Notes: Single-line `python -c` avoids YAML/Python indentation clashes. Version is passed via `sys.argv[1]` (not shell interpolation inside Python string) to avoid quoting issues. The file is always created so `body_path` never references a missing file. The `from release import` works because CWD is the repo root (Python adds CWD to `sys.path` for `-c` commands). The `dist/` directory already exists at this point — created by the "Build and package" step. Note: importing `release` triggers the full import chain (`httpx`, `build_nuitka`) — this is acceptable since all deps are installed, but if `extract_changelog` is ever moved to its own module, the import would be lighter.

- [x] Task 5: Update `softprops/action-gh-release` to use `body_path`
  - File: `.github/workflows/build-windows.yml`
  - Action: Add `body_path: dist/release-notes.md` to the Upload release step:
    ```yaml
    - name: Upload release
      uses: softprops/action-gh-release@v2
      with:
        body_path: dist/release-notes.md
        files: |
          dist/kipart-search-*-windows.zip
          dist/kipart-search-*-setup.exe
          dist/checksums-*-sha256.txt
        generate_release_notes: true
    ```
  - Notes: The file is always created by Task 4 (empty if no changelog entry), so `body_path` will never reference a missing file. An empty `body_path` file results in no custom body — only auto-generated notes appear.

- [x] Task 6: Add tests for `extract_changelog()` and warning behavior
  - File: `tests/test_release.py`
  - Action: Add `TestExtractChangelog` class with tests:
    - `test_extracts_matching_version` — parses a multi-version CHANGELOG, returns correct section
    - `test_returns_none_for_missing_version` — version not in file returns `None`
    - `test_returns_none_for_missing_file` — file doesn't exist returns `None`
    - `test_excludes_version_header` — returned text does not include the `## [X.Y.Z]` line
    - `test_handles_unreleased_section` — `## [Unreleased]` is skipped, correct version still found
    - `test_extracts_last_version` — works when version is the last section (no next `## [` after it)
    - `test_strips_whitespace` — returned content has no leading/trailing blank lines
    - `test_tag_mode_warns_on_missing_changelog` — use `monkeypatch` to set `sys.argv` to `["release.py", "--tag", "--skip-version-gate"]`, mock `extract_changelog` to return `None`, mock `tag_and_push`, mock `read_base_version` (return `"0.1.0"`), verify WARNING is printed via `capsys`
  - Notes: Use `tmp_path` fixture to create test CHANGELOG files. No mocking needed for extraction tests. The warning test requires mocks for `extract_changelog`, `tag_and_push`, and `read_base_version` (follow the pattern in existing `TestCLIFlags` tests which mock all pipeline functions). Use `--skip-version-gate` to avoid needing to mock `check_version_gate`.

### Acceptance Criteria

- [ ] AC 1: Given a `CHANGELOG.md` with a `## [0.1.0] - 2026-03-26` section containing `### Added` items, when `extract_changelog("0.1.0")` is called, then it returns the section content without the `## [0.1.0]` header line.
- [ ] AC 2: Given no `CHANGELOG.md` file exists, when `extract_changelog("0.1.0")` is called, then it returns `None`.
- [ ] AC 3: Given a `CHANGELOG.md` without an entry for `0.2.0`, when `extract_changelog("0.2.0")` is called, then it returns `None`.
- [ ] AC 4: Given `release.py --tag` is run and no CHANGELOG entry exists for the current version, when the version gate step runs, then a WARNING is printed but the tag is still created.
- [ ] AC 5: Given a tagged release triggers CI and `CHANGELOG.md` has an entry for the version, when the workflow runs, then the GitHub Release body contains the CHANGELOG content above the auto-generated commit notes.
- [ ] AC 6: Given a tagged release triggers CI and `CHANGELOG.md` has no entry for the version, when the workflow runs, then the GitHub Release is created with auto-generated notes only (no error).
- [ ] AC 7: Given `CHANGELOG.md` exists, when reviewing its format, then it follows Keep a Changelog convention with `## [X.Y.Z] - YYYY-MM-DD` headers and `### Added / Changed / Fixed / Removed` subsections.

## Additional Context

### Dependencies

- No new external libraries needed
- `softprops/action-gh-release@v2` already in use — just adding `body_path` parameter
- `release.py` already importable from tests via `sys.path` hack

### Testing Strategy

- **Unit tests**: `TestExtractChangelog` in `tests/test_release.py` — 8 tests (7 extraction + 1 warning behavior)
- **Manual test**: Run `python -c "from release import extract_changelog; print(extract_changelog('0.1.0'))"` after creating `CHANGELOG.md`
- **CI integration test**: Push a test tag, verify the GitHub Release body contains the CHANGELOG content, then clean up with `python clear_release.py`

### Notes

- The `extract_changelog()` function should be kept simple (line-by-line parsing) — no regex or CHANGELOG-specific libraries.
- Future enhancement: `release.py` could auto-populate an `## [Unreleased]` section from git log, but that's out of scope.
- **Empty body_path verification**: During the CI integration test, verify that an empty `dist/release-notes.md` does not produce a visible empty body section in the GitHub Release. If it does, change Task 4 to skip writing the file when no changelog entry exists, and update Task 5 to conditionally set `body_path` only when the file has content (e.g., `if: hashFiles('dist/release-notes.md') != ''` or a step output flag).
- **gitignore**: `dist/release-notes.md` is a CI-generated file. If `.gitignore` exists and includes `dist/`, it's already covered. If not, consider adding `dist/release-notes.md` to prevent accidental commits during local testing.

## Review Notes
- Adversarial review completed
- Findings: 9 total, 4 fixed, 3 noise/dismissed, 2 skipped (undecided/by-design)
- Resolution approach: auto-fix
- F1+F2+F9 (High): Rewrote CI step — proper file handling, conditional body_path via step output flag
- F3+F8 (Medium): Dismissed — `]` bracket in startswith makes matching exact, not prefix-based
- F4 (Medium): Dismissed — actions/checkout defaults to repo root, CWD is reliable
- F5 (Medium): Skipped — dist/ created by build step, ordering is stable
- F6 (Medium): Fixed — documented empty-section-returns-None in docstring
- F7 (Medium): Fixed — removed extra blank lines, indented warning under step output
