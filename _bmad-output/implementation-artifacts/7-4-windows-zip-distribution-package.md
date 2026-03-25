# Story 7.4: Windows Zip Distribution Package

Status: done

## Story

As a developer,
I want to package the compiled binary as a distributable zip file for Windows,
so that end-users can download, unzip, and run KiPart Search without installing Python.

## Acceptance Criteria

1. **Given** a successful Nuitka build from Story 7.1, **when** the developer runs the packaging step in the build script, **then** a `kipart-search-{version}-windows.zip` file is produced containing the standalone folder.

2. **Given** the zip file, **when** extracted, **then** the zip includes a top-level `kipart-search/` folder with `kipart-search.exe` at its root (not `__main__.dist/`).

3. **Given** the zip file, **when** extracted, **then** a `README.txt` is present inside the top-level folder with: quick start instructions, system requirements (Windows 10/11), and link to documentation.

4. **Given** the zip file, **when** produced, **then** the zip file size is printed to stdout as a baseline for tracking bloat.

5. **Given** a fresh Windows machine (no Python installed), **when** the user unzips and runs `kipart-search.exe`, **then** the application launches and is fully functional.

6. **Given** the build script, **when** the developer runs `python build_nuitka.py --package`, **then** it compiles via Nuitka first, then produces the zip after compilation.

7. **Given** the version number in `pyproject.toml`, **when** the zip is produced, **then** the version is embedded in the zip filename (e.g., `kipart-search-0.1.0-windows.zip`) **and** the app's About dialog already displays this version (via `__version__` in `__init__.py` — already implemented, just verify consistency).

## Tasks / Subtasks

- [x] Task 1: Add `--package` flag to `build_nuitka.py` (AC: #1, #6)
  - [x] 1.1 Add `--package` argument to the argparse section (action="store_true")
  - [x] 1.2 When `--package` is set, call the new `package()` function after `build()` completes

- [x] Task 2: Implement folder rename from `__main__.dist/` to `kipart-search/` (AC: #2)
  - [x] 2.1 After Nuitka build, copy/rename `dist/__main__.dist/` → `dist/kipart-search/` using `shutil.copytree` or rename
  - [x] 2.2 Verify `kipart-search.exe` exists at `dist/kipart-search/kipart-search.exe`
  - [x] 2.3 Keep `__main__.dist/` untouched (it's the Nuitka build artifact — don't modify it in place)

- [x] Task 3: Generate `README.txt` inside the package folder (AC: #3)
  - [x] 3.1 Create `dist/kipart-search/README.txt` with quick start, system requirements, and docs link
  - [x] 3.2 Content: "Double-click kipart-search.exe to launch", Windows 10/11 requirement, link to GitHub repo
  - [x] 3.3 Write as plain text (not markdown) — this is for end-users who unzip and look for instructions

- [x] Task 4: Create the zip file with correct structure (AC: #1, #2, #4, #7)
  - [x] 4.1 Read version from pyproject.toml via existing `read_version()` (use base `X.X.X` format, not quad)
  - [x] 4.2 Create `kipart-search-{version}-windows.zip` using `shutil.make_archive` or `zipfile` module
  - [x] 4.3 Zip must contain top-level `kipart-search/` folder (not bare files at root)
  - [x] 4.4 Print zip file size in MB to stdout

- [x] Task 5: Add `--package-only` flag for re-packaging without rebuilding (AC: #6)
  - [x] 5.1 Add `--package-only` argument that skips Nuitka compilation and only runs the packaging step
  - [x] 5.2 Validate that `dist/__main__.dist/kipart-search.exe` exists before packaging
  - [x] 5.3 This allows rapid iteration on packaging without re-running the ~10min Nuitka build

- [x] Task 6: Verify version consistency (AC: #7)
  - [x] 6.1 Confirm version in zip filename matches `pyproject.toml` version
  - [x] 6.2 About dialog already displays `__version__` from `__init__.py` — no code changes needed, just verify `__init__.py` and `pyproject.toml` have the same version string

- [ ] Task 7: Manual verification on clean environment (AC: #5)
  - [ ] 7.1 Unzip on a machine/VM without Python installed
  - [ ] 7.2 Run `kipart-search.exe` and confirm it launches
  - [ ] 7.3 Document zip file size as baseline in completion notes

## Dev Notes

### Build Script Integration

The `--package` flag extends the existing `build_nuitka.py`. The flow is:

```
python build_nuitka.py --package
  1. GPL firewall check (unless --skip-license-check)
  2. Nuitka build → dist/__main__.dist/
  3. Copy __main__.dist/ → dist/kipart-search/
  4. Write README.txt into dist/kipart-search/
  5. Zip dist/kipart-search/ → dist/kipart-search-{version}-windows.zip
  6. Print zip size
```

`--package-only` skips steps 1-2 (useful for iterating on packaging without re-compiling).

### Folder Rename Rationale

Nuitka names the output folder after the entry-point module: `__main__.py` → `__main__.dist`. End-users should see `kipart-search/` when they unzip. Use `shutil.copytree()` to create the clean copy, preserving `__main__.dist/` as the canonical build output.

Do NOT rename `__main__.dist/` in place — that breaks re-running the build script (Nuitka expects to find/overwrite its own output folder).

### Version Format

`read_version()` already exists and returns quad format (`X.X.X.X`). For the zip filename, use the base version from pyproject.toml (e.g., `0.1.0`), NOT the quad format. Add a helper or read the raw version before quad conversion.

Current `read_version()` returns `"0.1.0.0"` — need the raw `"0.1.0"` for the zip filename.

```python
def read_base_version() -> str:
    """Read raw version string from pyproject.toml (e.g., '0.1.0')."""
    pyproject = Path(__file__).parent / "pyproject.toml"
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    return data.get("project", {}).get("version", "0.0.0")
```

Or refactor `read_version()` to return both raw and quad. Either approach is fine — keep it simple.

### README.txt Content

```text
KiPart Search v{version}
========================

Parametric electronic component search with KiCad integration.

QUICK START
-----------
Double-click kipart-search.exe to launch the application.

No Python installation is required.

SYSTEM REQUIREMENTS
-------------------
- Windows 10 or Windows 11
- ~120 MB disk space
- Internet connection for distributor searches (JLCPCB offline database
  works without internet after first download)

KICAD INTEGRATION
-----------------
For KiCad integration, KiCad 9.0+ must be running with IPC API enabled.
Install kicad-python separately: pip install kicad-python

DOCUMENTATION
-------------
https://github.com/sylvanoMTL/kipart-search

LICENSE
-------
MIT License - Copyright (c) 2026 Sylvain Boyer (MecaFrog)
```

### Zip Structure

The final zip must have this structure when extracted:

```
kipart-search-0.1.0-windows.zip
└── kipart-search/
    ├── kipart-search.exe
    ├── README.txt
    ├── python310.dll
    ├── Qt6Core.dll
    ├── Qt6Gui.dll
    ├── Qt6Widgets.dll
    ├── PySide6/
    ├── platforms/
    ├── imageformats/
    ├── styles/
    ├── certifi/
    └── ... (all other Nuitka output files)
```

Use `zipfile.ZipFile` with `zipfile.ZIP_DEFLATED` for compression. Write files with arcnames prefixed by `kipart-search/` to ensure the top-level folder exists in the archive.

Alternatively, `shutil.make_archive(base_name, 'zip', root_dir, base_dir)` can produce the right structure:
```python
shutil.make_archive(
    base_name=str(output_dir / f"kipart-search-{version}-windows"),
    format="zip",
    root_dir=str(output_dir),          # parent of kipart-search/
    base_dir="kipart-search",          # folder to include
)
```

### Current Dist Layout (from Story 7.1/7.2)

```
dist/
├── __main__.build/     # Nuitka intermediate build files
├── __main__.dist/      # Standalone output
│   ├── kipart-search.exe   (47 MB)
│   ├── python310.dll
│   ├── Qt6Core.dll
│   ├── PySide6/
│   ├── certifi/
│   └── ... (~68 files, ~115 MB total)
├── stdout.log
└── stderr.log
```

The zip output goes alongside: `dist/kipart-search-0.1.0-windows.zip`.

### What NOT to Do

- Do NOT use `--onefile` or repackage as a single exe — LGPL compliance requires separate Qt DLLs
- Do NOT create an installer (NSIS/Inno Setup/MSI) — out of scope, may be a future story
- Do NOT add auto-update checks or self-update mechanism
- Do NOT rename or move `__main__.dist/` — copy it instead
- Do NOT add code signing — that requires an EV certificate and is a separate concern
- Do NOT modify any GUI, core, or test code — this story only touches `build_nuitka.py`
- Do NOT add the generated zip to git — `dist/` is already in `.gitignore`

### Project Structure Notes

**Modified files:**
- `build_nuitka.py` — add `--package`, `--package-only` flags, `package()` function, `read_base_version()` helper

**Generated output (not committed):**
- `dist/kipart-search/` — renamed copy of `__main__.dist/` with `README.txt` added
- `dist/kipart-search-{version}-windows.zip` — distributable archive

No new source files. No changes to `pyproject.toml`, `__init__.py`, or any `src/` code.

### Existing Patterns to Follow

- **Build script structure**: `build_nuitka.py` has `main()` → argparse → `check_licenses()` → `build()`. Add `package()` as a third step.
- **Version reading**: `read_version()` already parses `pyproject.toml` via `tomllib`/`tomli`. Refactor or add `read_base_version()`.
- **Path handling**: Use `pathlib.Path` throughout (consistent with project conventions).
- **Error messages**: Print clear messages with paths and sizes (see `build()` summary block).

### Previous Story Intelligence (Story 7.3)

**Key learnings from Story 7.3:**
- `core/license.py` created with singleton License class, feature gating
- Dev bypass key (`dev-pro-unlock`) works in source builds only
- Env var `KIPART_LICENSE_KEY=anything` activates Pro immediately
- 32 tests added for license module
- No changes to build script were needed for license module (it's auto-included via `--include-package=kipart_search`)

**Key learnings from Story 7.1:**
- `dist/__main__.dist/` is the Nuitka output folder name (from `__main__.py` entry point)
- `--output-filename=kipart-search` names the exe but NOT the folder
- Build produces ~68 files, ~115 MB total
- `tomllib` (Python 3.11+) with `tomli` fallback for Python 3.10
- GPL firewall check uses `piplicenses` (no hyphen) as module name

**Key learnings from Story 7.2:**
- kipart-search.exe is 47 MB; total dist folder is ~116 MB
- All features verified working in compiled binary
- Windows Defender may flag the exe (needs code signing later)

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 7, Story 7.4, lines 943-959]
- [Source: build_nuitka.py — existing build script with `read_version()`, `build()`, argparse]
- [Source: _bmad-output/implementation-artifacts/7-1-minimal-nuitka-build.md — dist layout, build flags]
- [Source: _bmad-output/implementation-artifacts/7-3-license-module-and-feature-gating.md — latest story learnings]
- [Source: src/kipart_search/__init__.py — `__version__ = "0.1.0"`]
- [Source: pyproject.toml — `version = "0.1.0"`]
- [Source: src/kipart_search/gui/main_window.py:420 — About dialog uses `__version__`]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

None — clean implementation, no blockers encountered.

### Completion Notes List

- Implemented `read_base_version()` to return raw `X.X.X` version (vs `read_version()` which returns quad `X.X.X.X`)
- Implemented `package()` function: copies `__main__.dist/` → `kipart-search/`, writes `README.txt`, creates zip via `shutil.make_archive`, prints size
- Added `--package` flag (build + package) and `--package-only` flag (package without rebuild)
- `--package-only` validates `dist/__main__.dist/kipart-search.exe` exists before running
- Version consistency verified: `pyproject.toml` = `__init__.py` = `"0.1.0"`
- 15 new tests added (2 for `read_base_version`, 11 for `package()`, 2 for CLI args), all passing
- 263 non-GUI tests pass with zero regressions
- Task 7 (manual verification on clean environment) requires user action — cannot be automated in tests
- Pre-existing GUI test failures (PySide6 access violation in `test_context_menus.py`) are unrelated to this story

### Change Log

- 2026-03-24: Implemented Tasks 1-6 — `--package` and `--package-only` flags, `package()` function, `read_base_version()`, README.txt generation, zip creation with version in filename, 15 new tests
- 2026-03-25: Code review fixes — DRY'd `read_version()` to call `read_base_version()`, removed unused `zipfile` import, made `--package`/`--package-only` mutually exclusive, removed dead test line

### File List

- `build_nuitka.py` — added `read_base_version()`, `package()`, `--package`/`--package-only` args
- `tests/test_build_nuitka.py` — added TestReadBaseVersion, TestPackage, TestMainArgs classes (15 new tests)
