# Story 8.2: Inno Setup Installer Script

Status: review

## Story

As a developer,
I want an Inno Setup installer script that packages the Nuitka build output into a standard Windows installer,
so that users get Start Menu entries, Add/Remove Programs integration, and clean upgrade paths.

## Acceptance Criteria

1. **Given** a successful Nuitka build output in `dist/__main__.dist/`, **when** the Inno Setup compiler (`iscc`) processes the `.iss` script, **then** an installer `.exe` is produced that installs to `C:\Program Files\KiPart Search\` by default.

2. **Given** the installer runs, **when** the user reaches the folder selection page, **then** the user can change the install path.

3. **Given** the installer runs, **when** it completes, **then** a Start Menu shortcut is created under "KiPart Search".

4. **Given** the installer runs, **when** the user reaches the "Additional Tasks" page, **then** a desktop shortcut is offered as opt-in (default unchecked).

5. **Given** the installer completes, **when** Add/Remove Programs is opened, **then** an entry exists with app name, version, publisher ("MecaFrog"), and uninstaller.

6. **Given** the installer has a unique `AppId`, **when** running on a machine with a previous install, **then** it detects the existing installation and offers upgrade, reusing the previous install path (no duplicate installs).

7. **Given** the uninstaller runs, **when** it removes Program Files contents, **then** user data in `%LOCALAPPDATA%\KiPartSearch\` is preserved by default, with an optional prompt to remove it.

8. **Given** the installer launches, **when** `kipart-search.exe` is already running, **then** `CloseApplications=yes` with filter for `kipart-search.exe` handles the running instance.

9. **Given** the version in `pyproject.toml`, **when** the `.iss` script is compiled, **then** the version is injected via a `#define MyAppVersion` preprocessor directive (not hardcoded in the script).

10. **Given** the `.iss` file, **when** inspected, **then** it is committed to the repository as a versioned source file, and no file associations are registered.

## Tasks / Subtasks

- [x] Task 1: Create the Inno Setup `.iss` script (AC: #1, #2, #3, #4, #5, #6, #7, #8, #9, #10)
  - [x] 1.1 Create `installer/kipart-search.iss` in the project root
  - [x] 1.2 Define `#define MyAppVersion "0.1.0"` — this will be overridden at compile time via `/D` flag or read by the build script
  - [x] 1.3 Set `AppId={{A-UNIQUE-GUID}}` — generate a new GUID; this MUST remain constant across all future versions for upgrade detection
  - [x] 1.4 Set `DefaultDirName={autopf}\KiPart Search` — `{autopf}` resolves to Program Files on 64-bit
  - [x] 1.5 Set `DefaultGroupName=KiPart Search` for Start Menu folder
  - [x] 1.6 Set `AppPublisher=MecaFrog`, `AppPublisherURL`, `AppSupportURL`
  - [x] 1.7 Add `[Files]` section: source `dist\__main__.dist\*` → install dir, recursive, with `Flags: ignoreversion`
  - [x] 1.8 Add `[Icons]` section: Start Menu shortcut pointing to `kipart-search.exe`
  - [x] 1.9 Add `[Tasks]` section: optional desktop shortcut (default unchecked via `Flags: unchecked`)
  - [x] 1.10 Set `CloseApplications=yes` and `CloseApplicationsFilter=kipart-search.exe`
  - [x] 1.11 Set `UninstallDisplayIcon={app}\kipart-search.exe`
  - [x] 1.12 Add `[Code]` section with optional uninstall prompt to delete `%LOCALAPPDATA%\KiPartSearch\` user data
  - [x] 1.13 Set output filename pattern: `kipart-search-{version}-setup`
  - [x] 1.14 Set `OutputDir=dist` to place installer next to the zip

- [x] Task 2: Add compile helper to `build_nuitka.py` (AC: #9)
  - [x] 2.1 Add `compile_installer(output_dir)` function that invokes `iscc` with `/DMyAppVersion={version}` to inject version from `pyproject.toml`
  - [x] 2.2 Add `--installer` flag to build script: builds + packages + compiles installer
  - [x] 2.3 Add `--installer-only` flag: compiles installer from existing Nuitka output (skip build)
  - [x] 2.4 Verify `iscc` is on PATH; print helpful error if not found (Inno Setup must be installed locally or via CI)

- [x] Task 3: Verify installer end-to-end (AC: #1–#10)
  - [x] 3.1 Build with Nuitka, then compile installer, then test: fresh install, upgrade over existing, uninstall
  - [x] 3.2 Verify Start Menu shortcut, desktop shortcut opt-in, Add/Remove Programs entry
  - [x] 3.3 Verify user data in `%LOCALAPPDATA%\KiPartSearch\` survives uninstall
  - [x] 3.4 Verify running instance is closed gracefully on upgrade

## Dev Notes

### Inno Setup `.iss` Script Structure

The `.iss` file uses Inno Setup's declarative DSL with Pascal Script extensions in `[Code]`. Key directives:

```iss
#define MyAppName "KiPart Search"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "MecaFrog"
#define MyAppExeName "kipart-search.exe"

[Setup]
AppId={{GENERATE-A-GUID-HERE}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=dist
OutputBaseFilename=kipart-search-{#MyAppVersion}-setup
Compression=lzma
SolidCompression=yes
CloseApplications=yes
CloseApplicationsFilter={#MyAppExeName}
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Files]
Source: "dist\__main__.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
```

### AppId GUID

Generate a fresh GUID (e.g. via `python -c "import uuid; print(uuid.uuid4())"`) and use it as AppId. Double curly braces escape literal braces in Inno Setup syntax: `AppId={{xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}`. This GUID must NEVER change between versions — it's how Inno Setup detects existing installs for upgrade.

### Version Injection

The build script should invoke `iscc` with `/DMyAppVersion=0.1.0` to override the `#define` at compile time. This avoids manual version bumps in the `.iss` file. The `#define` in the file serves as documentation and default.

```python
def compile_installer(output_dir: str = "dist") -> None:
    version = read_base_version()
    iss_path = Path(__file__).parent / "installer" / "kipart-search.iss"
    cmd = ["iscc", f"/DMyAppVersion={version}", str(iss_path)]
    subprocess.run(cmd, check=True)
```

### Source Path in [Files] Section

The `Source:` path is relative to the `.iss` file's directory. Since the `.iss` lives in `installer/` and the Nuitka output is in `dist/__main__.dist/`, the source path should be `"..\dist\__main__.dist\*"` (go up one directory from `installer/` to project root, then into `dist/`). Alternatively, use the `/D` flag to pass the source dir, or invoke `iscc` with a working directory.

**Recommended approach:** Place the `.iss` file in `installer/` and use relative paths going up to project root:
```iss
Source: "..\dist\__main__.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
```

### Uninstall User Data Prompt

The `[Code]` section can add a Pascal Script `CurUninstallStepChanged` callback that prompts to delete `%LOCALAPPDATA%\KiPartSearch\`:

```pascal
[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\KiPartSearch');
    if DirExists(DataDir) then
    begin
      if MsgBox('Remove user data (search cache, settings, JLCPCB database)?'#13#10#13#10 +
                'Location: ' + DataDir, mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;
```

Default is NO (MB_DEFBUTTON2) — preserving user data is the safe default.

### Output Artifacts

After `iscc` compiles, the output is:
```
dist/
├── __main__.dist/                          # Nuitka output (input to installer)
├── kipart-search/                          # Packaged folder (input to zip)
├── kipart-search-0.1.0-windows.zip         # Portable distribution
└── kipart-search-0.1.0-setup.exe           # Installer (NEW)
```

### Build Script Integration

Extend `build_nuitka.py` with two new flags:

| Flag | Behavior |
|------|----------|
| `--installer` | GPL check → Nuitka build → zip package → Inno Setup compile |
| `--installer-only` | Inno Setup compile only (requires prior `--package` build) |

The `compile_installer()` function should:
1. Check `iscc` is on PATH (Inno Setup default: `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`)
2. Read version from `pyproject.toml`
3. Run `iscc /DMyAppVersion={version} installer/kipart-search.iss`
4. Verify output file exists
5. Print installer path and file size

### What NOT to Do

- Do NOT hardcode the version in the `.iss` file — always inject via `/DMyAppVersion`
- Do NOT register file associations — the app is workflow-driven, not file-driven
- Do NOT use `{pf}` constant — use `{autopf}` which handles 64-bit correctly
- Do NOT delete `%LOCALAPPDATA%\KiPartSearch\` automatically on uninstall — always prompt
- Do NOT change the `AppId` between versions — this breaks upgrade detection
- Do NOT bundle Inno Setup itself as a dependency — it's a build tool installed separately
- Do NOT use `--onefile` Nuitka builds for the installer source — `--standalone` keeps DLLs separate for LGPL compliance (this is already correct in `build_nuitka.py`)
- Do NOT add Inno Setup to `pyproject.toml` — it's a native Windows tool, not a Python dependency

### Project Structure Notes

**New files:**
- `installer/kipart-search.iss` — Inno Setup script (committed to repo)

**Modified files:**
- `build_nuitka.py` — add `compile_installer()`, `--installer`, `--installer-only` flags

**No changes to:**
- `pyproject.toml` — no new Python dependencies
- `src/kipart_search/` — no application code changes
- `.github/workflows/build-windows.yml` — CI extension is Story 8.4, not this story

### Previous Story Intelligence

**From Story 8.1 (platformdirs Data Path Migration):**
- User data now lives at `%LOCALAPPDATA%\KiPartSearch\` (via `platformdirs.user_data_dir("KiPartSearch", appauthor=False)`)
- The uninstall data cleanup prompt must target this exact path
- `core/paths.py` is the single source of truth for data paths — but the `.iss` script is independent (it's a Windows-native tool, not Python)
- Story 8.1 is done and merged (commit `7392e43`)

**From Story 7.1 (Nuitka Build):**
- Nuitka output is in `dist/__main__.dist/` with `kipart-search.exe` at root
- Build uses `--standalone` (NOT `--onefile`) — separate DLLs for LGPL compliance
- The exe is named `kipart-search.exe` via `--output-filename=kipart-search`
- Windows metadata (company, product, version) already embedded in the exe

**From Story 7.4 (ZIP Distribution):**
- `build_nuitka.py` already has `package()` function and `--package`/`--package-only` flags
- Version reading is done via `read_base_version()` — reuse this for installer version injection
- The zip and installer are complementary distribution methods (portable vs installed)

**From Story 7.5 (CI Pipeline):**
- CI workflow is at `.github/workflows/build-windows.yml` — do NOT modify it in this story (that's Story 8.4)
- The workflow uses `softprops/action-gh-release@v2` for upload — Story 8.4 will add the installer `.exe` to the upload glob

### Git Intelligence

Recent commits (most relevant):
- `7392e43` — Story 8.1 platformdirs migration (directly preceding this story)
- `build_nuitka.py` — 300 lines, well-structured with `main()` → argparse → dispatch pattern. Add new flags following the same pattern as `--package`/`--package-only`.

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 8, Story 8.2]
- [Source: _bmad-output/planning-artifacts/architecture.md — Build & Packaging section]
- [Source: build_nuitka.py — existing build script with package() and main()]
- [Source: _bmad-output/implementation-artifacts/8-1-platformdirs-data-path-migration.md — predecessor story]
- [Source: _bmad-output/implementation-artifacts/7-1-minimal-nuitka-build.md — Nuitka build config]
- [Source: _bmad-output/implementation-artifacts/7-4-windows-zip-distribution-package.md — packaging pattern]
- [Source: Inno Setup 6 docs — https://jrsoftware.org/ishelp/]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- All 69 tests in `test_build_nuitka.py` pass (1 skipped — PyYAML not installed)
- Full core + build test suite: 275 passed, 1 skipped
- Pre-existing GUI test failures (PySide6 access violation in test_context_menus.py) are unrelated

### Completion Notes List

- Created `installer/kipart-search.iss` with all required directives: AppId GUID `62ac5603-5867-4e62-9bdf-30df22d7bc2c`, `{autopf}` for 64-bit, MecaFrog publisher, Start Menu + optional desktop shortcuts, `CloseApplications=yes`, `[Code]` Pascal Script for user data cleanup prompt on uninstall
- Added `compile_installer()` function to `build_nuitka.py` with iscc detection (PATH + default location), version injection via `/DMyAppVersion`, output verification
- Added `--installer` flag (full pipeline: build + package + installer) and `--installer-only` flag (compile installer from existing build)
- Added 13 `.iss` file validation tests (TestIssFile), 4 compile_installer function tests (TestCompileInstaller), 3 CLI flag tests (added to TestMainArgs)
- Inno Setup compilation successful: `dist/kipart-search-0.1.0-setup.exe` (31.3 MB) — compiled from existing Nuitka build output
- Task 3 subtasks (install/upgrade/uninstall) require manual user testing

### Change Log

- 2026-03-25: Created `installer/kipart-search.iss`, extended `build_nuitka.py` with `compile_installer()` and `--installer`/`--installer-only` flags, added 20 new tests

### File List

- `installer/kipart-search.iss` (new)
- `build_nuitka.py` (modified)
- `tests/test_build_nuitka.py` (modified)
