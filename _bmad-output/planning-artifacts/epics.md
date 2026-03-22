---
stepsCompleted: [step-01-validate-prerequisites, step-02-design-epics, step-03-create-stories, step-04-final-validation]
inputDocuments:
  - planning-artifacts/prd.md
  - planning-artifacts/architecture.md
  - planning-artifacts/ux-design-specification.md
---

# KiPart Search - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for KiPart Search, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: Designer can search for electronic components by keyword, value, package, or parametric specs across the local JLCPCB database
FR2: Designer can view search results in a filterable table showing MPN, manufacturer, package, description, stock, and pricing
FR3: Designer can filter search results by manufacturer and package type
FR4: Designer can view detailed part information (specs, datasheet link, price breaks, stock) for any search result
FR5: Designer can have search queries automatically transformed from KiCad conventions to effective search terms (e.g., R_0805 -> "0805 resistor", 100n -> 100nF)
FR6: Designer can edit the transformed query before executing the search
FR7: Designer can download the JLCPCB parts database (~1M parts) on first run with progress indication
FR8: Designer can refresh the local database to get updated part data
FR9: System can perform full-text search on the local database in under 2 seconds
FR10: Designer can connect to a running KiCad 9+ instance via IPC API
FR11: Designer can scan all components from the active KiCad PCB project
FR12: Designer can click a component in the app to highlight/select it in KiCad's PCB editor (triggering schematic cross-probe)
FR13: Designer can write back MPN, manufacturer, and description fields to a KiCad component
FR14: System prevents overwriting non-empty component fields without explicit confirmation
FR15: System warns when assigned part has type or package mismatch with the target component
FR16: Designer can view a verification dashboard showing all board components colour-coded by status (green/amber/red)
FR17: Designer can see per-component verification status: MPN present, MPN verified in database, footprint match
FR18: Designer can view a health bar showing overall BOM readiness percentage
FR19: Designer can double-click a missing-MPN component to open search pre-filled with that component's value and package
FR20: Designer can re-run verification after making changes
FR21: Designer can assign an MPN from search results to a KiCad component via a preview dialog
FR22: Designer can manually enter an MPN, manufacturer, and description for components not found in the database
FR23: Designer can preview all field changes before confirming a write-back to KiCad
FR24: Designer can export a production-ready BOM in PCBWay Excel/CSV format
FR25: System groups components by MPN with combined designators and correct quantities (e.g., R14,R18 -> qty 2)
FR26: System maps KiCad footprint names to standard package names (e.g., C_0805_2012Metric -> 0805)
FR27: System detects and labels components as SMD or THT based on footprint
FR28: System warns or refuses BOM export when MPN coverage is below 100%
FR29: BOM export includes all required PCBWay columns: Item #, Designator, Qty, Manufacturer, Mfg Part #, Description/Value, Package, Type
FR30: System caches search results and part data locally with configurable expiration per source
FR31: System serves cached results for repeat queries without network access
FR32: Designer can store and manage API keys for distributor adapters (DigiKey, Mouser) via OS-native secret storage (enables Phase 2 multi-source search)
FR33: Designer can use the application fully offline after initial database download
FR34: Designer can access a Help/About dialog with app name, version, author, and license information
FR35: Designer can see a clear status indicator showing current data mode (e.g., "Local DB" vs "Online - 3 sources active")
FR36: Developer can compile the application into a standalone binary (no Python installation required) using Nuitka
FR37: Compiled binary retains full functionality: PySide6 GUI, keyring, httpx, openpyxl, SQLite, and optional kicad-python
FR38: Application supports a license key system with revised free/paid tier split: free tier includes JLCPCB search, KiCad scan/highlight, basic verification, single-component write-back, CSV export; paid tier gates multi-distributor search, CM BOM exports, full verification, batch write-back, Excel export
FR39: License validation works both online (LemonSqueezy/Gumroad API) and offline (signed JWT fallback), with one-time license fee (not subscription)
FR40: Compiled binary distributed as a Windows zip package (standalone folder with .exe); installer (NSIS/Inno Setup) deferred to later story
FR41: Build pipeline produces platform-specific packages for Linux AppImage and macOS .app bundle (deferred to future Epic 8)

### NonFunctional Requirements

NFR1: Full-text search queries return results in < 2 seconds on a ~1M part database, as measured by end-to-end timing from query submission to results displayed
NFR2: Full board scan (70 components) completes in < 10 seconds, as measured by scan start to dashboard populated
NFR3: GUI remains responsive (no freezes) during all search, scan, and export operations, as verified by UI interaction during background tasks
NFR4: BOM export for a 70-component board completes in < 5 seconds, as measured by export button click to file written
NFR5: Application cold start to usable state in < 3 seconds (excluding database download), as measured by launch to main window interactive
NFR6: API keys (DigiKey, Mouser) stored via OS-native secret storage, never in plaintext config files
NFR7: No telemetry, no analytics, no data sent to external servers beyond explicit API calls initiated by the user
NFR8: KiCad IPC API connection auto-detected; no manual socket configuration required for standard installs
NFR9: Application functions fully without KiCad running - all features except highlight/select and write-back work standalone
NFR10: IPC API calls isolated behind a single abstraction layer to accommodate KiCad API changes across versions
NFR11: No crashes or data loss during the scan -> search -> assign -> export workflow
NFR12: Database corruption recovery: if the JLCPCB parts database is corrupted, the user can re-download it without losing configuration or cached data
NFR13: Write-back operations are atomic per component - a failed write to one component does not affect others
NFR14: Application runs on Windows 10/11, Linux (Ubuntu 22.04+, Fedora 38+), and macOS 12+ without platform-specific code paths in core logic
NFR15: All file paths use platform-agnostic handling (no hardcoded separators or OS-specific paths)
NFR16: No GPL-licensed dependencies may be added to the project (GPL firewall) — enforced by build pipeline check
NFR17: PySide6 LGPL compliance maintained — Qt DLLs must remain dynamically linked in compiled builds
NFR18: Nuitka build includes all dynamic imports (keyring backends, httpx transports) without runtime import errors
NFR19: Compiled binary cold start remains under 5 seconds (consistent with NFR5)

### Additional Requirements

- **Brownfield project**: No starter template needed. Tier 1 MVP (search, scan, verify, assign) is already built and functional. Phase 1 adds BOM export and supporting infrastructure.
- **ADR-01 Cache DB**: Separate SQLite cache in `~/.kipart-search/cache.db` with WAL journal mode, `cache_entries` table (key, source, query_type, data JSON, created_at, ttl_seconds). Survives JLCPCB DB refreshes.
- **ADR-02 BOM Export Engine**: Declarative dict-based BOMTemplate dataclass with BOMColumn definitions. Preset templates (PCBWay, JLCPCB, Newbury Electronics) as constants in `core/bom_export.py`. Custom templates stored as JSON in `~/.kipart-search/templates/`.
- **ADR-04 DigiKey Adapter**: Own httpx implementation (avoids GPL dependency). 2-legged OAuth client credentials for Phase 1. Token refresh when < 60s remaining.
- **ADR-05 Multi-Source Deduplication**: Merge by `(mpn.upper(), manufacturer.upper())`. Aggregate offers from all sources into single PartResult. Parametric data priority: Nexar > DigiKey > Mouser > JLCPCB.
- **ADR-06 Rate Limiting**: Per-source token bucket. Exponential backoff with jitter on 429/503. DigiKey 2 req/sec + 1,000/day. Mouser 1 req/sec. LCSC 1 req/sec.
- **ADR-07 QDockWidget Migration**: Migrate from QSplitter to QDockWidget panels. Default layout: Verify (left) | Search (center) | Detail (right) | Log (bottom). Layout persistence via saveState/restoreState. View > Reset Layout.
- **ADR-08 Write-Back Strategy**: Investigate existing kicad_bridge.py capabilities first. If field write-back works in kicad-python v0.6.0, use it. If not, defer to Phase 2.
- **ADR-09 Standalone BOM Import**: Deferred to Phase 2. Connected mode (KiCad IPC API) is the only input path for Phase 1.
- **New dependency**: `openpyxl` required for Excel BOM export.
- **ComponentData enrichment**: Model needs supplier P/Ns, package, SMD/THT type fields for BOM export.
- **Package extraction**: `_extract_package_from_footprint()` may need to move from kicad_bridge.py to core/ for bom_export.py access.
- **New files for Phase 1**: `core/bom_export.py`, `gui/export_dialog.py`, `gui/detail_panel.py`, `tests/core/test_bom_export.py`.
- **Implementation priority from Architecture**: (1) QDockWidget migration, (2) Cache DB, (3) BOM export engine, (4) Deduplication (Phase 2), (5) DigiKey adapter (Phase 2), (6) Write-back investigation (parallel).
- **Nuitka compilation**: Standalone binary build via `nuitka --standalone --enable-plugin=pyside6`. Requires `--include-package=keyring.backends` for dynamic backend discovery. `kicad-python` remains optional with graceful ImportError handling.
- **GPL firewall**: All new dependencies must be MIT/BSD/Apache-compatible. DigiKey adapter uses own httpx client (ADR-04). Never vendor code from GPL projects (Ki-nTree, peeter123/digikey-api).
- **License gating architecture**: `core/license.py` module with feature flags. Free tier always available (JLCPCB search, BOM export). Paid features gated behind `license.has("pro")`. Online validation via LemonSqueezy/Gumroad with offline signed-JWT fallback.
- **Installer packaging**: Windows via NSIS or Inno Setup wrapping Nuitka `--standalone` output. Linux via AppImage. macOS via .app bundle. CI pipeline for all 3 platforms.
- **PySide6 LGPL compliance**: Nuitka standalone mode keeps Qt DLLs as separate shared libraries (dynamic linking), satisfying LGPL requirements for proprietary distribution.
- **License gating pattern**: Use class-level capability checks (`raise FeatureNotAvailable("pro")` in `__init__`), not bare `if not license.has()` conditionals. Harder to patch in compiled binary without over-engineering.
- **Pricing model**: One-time license fee ($30-50 range), not subscription. KiCad community culture strongly resists SaaS/subscription tooling.
- **Distribution strategy**: Windows zip first (Nuitka `--standalone` output folder). Installer (Start Menu, file associations) as a follow-up story. Cross-platform (Linux, macOS) deferred to Epic 8.
- **Revised free/paid tier split (War Room consensus)**: Free tier must be genuinely useful (search + scan + basic verify + single write-back). Pro tier gates productivity-at-scale features (batch ops, multi-distributor, CM exports). Upgrade trigger: when 70+ component boards make one-by-one clicking painful.

### UX Design Requirements

UX-DR1: Migrate main window from QSplitter to QDockWidget panel architecture with 4 dockable panels: Verify (left), Search (center), Detail (right), Log (bottom). Each panel gets a unique objectName for saveState/restoreState persistence.
UX-DR2: Implement a fixed QToolBar with 4 primary actions: Scan Project / Open BOM, Export BOM, Push to KiCad (grayed in standalone), Preferences.
UX-DR3: Implement a QStatusBar with 3 zones: left = mode badge (green "Connected to KiCad" pill / gray "Standalone" pill), center = active source names, right = last action or idle state.
UX-DR4: Implement a View menu with toggle visibility for each panel (via dock.toggleViewAction()) and a "Reset Layout" action to restore default arrangement.
UX-DR5: Build a Detail Panel (QDockWidget, right dock) showing selected part specs, pricing, datasheet link, and assign button. Appears when a search result is selected.
UX-DR6: Build a BOM Export Window (non-modal QDialog) with: template selector (PCBWay, JLCPCB, Newbury, custom), live preview of columns/grouping/sample rows, DNP handling toggle (include marked / exclude), file format selection (Excel/CSV), export button with file path selector, and health < 100% warning banner.
UX-DR7: Build a Source Preferences Dialog (modal QDialog) with: list of all available sources, per-source enable/disable toggle, API key input field with "Test Connection" button, default source selector, JLCPCB database management (download/update/path). Status indicators: green (configured), amber (key missing), red (key invalid).
UX-DR8: Build a Welcome / First-Run Dialog (modal QDialog, shown once) with 3 options: (1) Download JLCPCB Database (no key needed, progress bar), (2) Configure API Source (opens Source Preferences), (3) Skip for now. Only shown when no sources are configured.
UX-DR9: Build a Dynamic Filter Row (composite widget in search panel) with horizontally arranged QComboBox dropdowns that are created/removed dynamically based on search result data fields. Common filters: Manufacturer, Package, Category. Result count label: "X of Y results". In Specific mode: local filter. In Unified mode: cascade back to APIs.
UX-DR10: Build a Health Summary Bar (composite widget above verify table) with QProgressBar (color-coded: red <50%, amber 50-99%, green 100%) and summary text: "Components: N total | Valid MPN: X | Needs attention: Y | Missing MPN: Z". Updates live after each assignment.
UX-DR11: Implement two-mode search architecture: Specific (single source, no Source column, local filters) and Unified (all enabled sources in parallel, Source column visible, filter cascade back to APIs). Source selector dropdown in search bar controls the mode.
UX-DR12: Implement consistent empty states for all panels with centered guidance text: Verify panel "Scan a project or open a BOM to begin", Search panel "Search for components using the query bar above". Never show blank panels.
UX-DR13: Implement right-click context menus on table rows with actions: "Search for this component", "Assign MPN", "Copy MPN".
UX-DR14: Implement layout persistence using QSettings: save geometry and window state on close, restore on open. Key: "kipart-search" / "kipart-search".
UX-DR15: Ensure all status indicators use color + text label (never color-only): "Verified", "Missing MPN", "Not Found", "Needs attention", "Unverified". Accessibility: setAccessibleName() and setAccessibleDescription() on custom composite widgets.
UX-DR16: Implement stale data indicators: components carry "last verified" timestamp. After database update, stale components show amber with "Last verified: [date] - database updated since. Re-scan recommended."
UX-DR17: Implement write-back safety system: silent timestamped backups before any write session in `~/.kipart-search/backups/{project}/{YYYY-MM-DD_HHMM}/`, undo log as CSV (timestamp, reference, field, old value, new value), add-never-overwrite policy, cancel/revert capability.
UX-DR18: Implement live dashboard updates: health bar and per-component status update immediately after each MPN assignment without requiring a full re-scan.

### FR Coverage Map

FR1: Epic 3 - Component search by keyword/value/package
FR2: Epic 3 - Filterable results table
FR3: Epic 3 - Filter by manufacturer and package
FR4: Epic 3 - Detailed part information view
FR5: Epic 3 - Query transformation from KiCad conventions
FR6: Epic 3 - Edit transformed query before search
FR7: Epic 4 - JLCPCB database download with progress
FR8: Epic 4 - Refresh local database
FR9: Epic 3 - FTS5 search < 2 seconds
FR10: Epic 5 - Connect to KiCad 9+ via IPC API
FR11: Epic 5 - Scan all components from active KiCad project
FR12: Epic 5 - Click-to-highlight in KiCad PCB editor
FR13: Epic 5 - Write back MPN/manufacturer/description fields
FR14: Epic 5 - Prevent overwriting non-empty fields
FR15: Epic 5 - Type/package mismatch warning
FR16: Epic 3 - Verification dashboard with color-coded status
FR17: Epic 3 - Per-component verification status
FR18: Epic 3 - Health bar showing BOM readiness %
FR19: Epic 3 - Double-click to guided search
FR20: Epic 3 - Re-run verification after changes
FR21: Epic 5 - Assign MPN from search results via preview
FR22: Epic 5 - Manual MPN entry
FR23: Epic 5 - Preview field changes before write-back
FR24: Epic 2 - Export BOM in PCBWay Excel/CSV format
FR25: Epic 2 - Group components by MPN with quantities
FR26: Epic 2 - Map footprint names to standard packages
FR27: Epic 2 - Detect SMD/THT from footprint
FR28: Epic 2 - Warn/refuse export when coverage < 100%
FR29: Epic 2 - Include all required PCBWay columns
FR30: Epic 4 - Cache search results with configurable TTL
FR31: Epic 4 - Serve cached results offline
FR32: Epic 6 - Store/manage API keys via OS-native storage
FR33: Epic 4 - Full offline use after database download
FR34: Epic 1, 6 - Help/About dialog
FR35: Epic 1, 6 - Data mode status indicator
FR36: Epic 7 - Nuitka standalone binary compilation
FR37: Epic 7 - Compiled binary full functionality verification
FR38: Epic 7 - License key system (revised free/paid tier split)
FR39: Epic 7 - Online + offline license validation (one-time fee)
FR40: Epic 7 - Windows zip distribution package
FR41: Epic 8 (future) - Cross-platform builds (Linux, macOS)

## Epic List

### Epic 1: GUI Modernization & Panel Architecture
Designers can dock, undock, float, and rearrange panels to customize their workspace, including multi-monitor setups. Layout persists between sessions. Includes detail panel for part inspection, toolbar, status bar, View menu, and Help/About dialog.
**FRs covered:** FR34, FR35
**UX-DRs covered:** UX-DR1, UX-DR2, UX-DR3, UX-DR4, UX-DR5, UX-DR12, UX-DR13, UX-DR14, UX-DR15
**NFRs addressed:** NFR3, NFR5, NFR14, NFR15

### Epic 2: Production-Ready BOM Export
Designers can export a CM-ready BOM file (PCBWay, JLCPCB, Newbury Electronics format) with components grouped by MPN, standard package names, SMD/THT labeling, and coverage validation. The export is the finish line of the scan-verify-assign workflow.
**FRs covered:** FR24, FR25, FR26, FR27, FR28, FR29
**UX-DRs covered:** UX-DR6, UX-DR10, UX-DR18
**NFRs addressed:** NFR4, NFR11

### Epic 3: Search & Verification Enhancements
Designers get dynamic filters that adapt to search results, two-mode search (Specific source vs Unified across all sources), live dashboard updates after assignments, and stale data indicators for re-verification awareness.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR9, FR16, FR17, FR18, FR19, FR20
**UX-DRs covered:** UX-DR9, UX-DR10, UX-DR11, UX-DR16, UX-DR18
**NFRs addressed:** NFR1, NFR2, NFR3

### Epic 4: Caching & Offline Resilience
Designers get faster repeat searches via local cache, offline access to previously-fetched results, and database corruption recovery - making the tool reliable for daily production use.
**FRs covered:** FR7, FR8, FR30, FR31, FR33
**UX-DRs covered:** None (infrastructure)
**NFRs addressed:** NFR1, NFR9, NFR12

### Epic 5: Safe KiCad Write-Back & Assignment
Designers can assign MPNs to KiCad components with full safety guarantees: silent backups before write sessions, undo log, add-never-overwrite policy, type/package mismatch warnings, and atomic writes per component.
**FRs covered:** FR10, FR11, FR12, FR13, FR14, FR15, FR21, FR22, FR23
**UX-DRs covered:** UX-DR17
**NFRs addressed:** NFR8, NFR10, NFR11, NFR13

### Epic 6: Source Configuration & First-Run Experience
Designers can configure which data sources are active, enter and validate API keys, set a default source, and get guided through first-launch setup - enabling multi-source workflows in future phases.
**FRs covered:** FR32, FR34, FR35
**UX-DRs covered:** UX-DR7, UX-DR8
**NFRs addressed:** NFR6, NFR7

### Epic 7: Build Pipeline & Distribution (Windows)
Developers can compile KiPart Search into a standalone Windows binary using Nuitka, enforce dependency license compliance, and gate premium features behind a one-time license key — enabling closed-source distribution and monetization without requiring end-users to install Python. Free tier remains genuinely useful (JLCPCB search, scan, basic verify, single write-back). Pro tier gates productivity-at-scale features (multi-distributor, CM exports, batch write-back, full verification).
**FRs covered:** FR36, FR37, FR38, FR39, FR40
**NFRs addressed:** NFR14, NFR16, NFR17, NFR18, NFR19

---

## Epic 1: GUI Modernization & Panel Architecture

Designers can dock, undock, float, and rearrange panels to customize their workspace, including multi-monitor setups. Layout persists between sessions. Includes detail panel for part inspection, toolbar, status bar, View menu, and Help/About dialog.

### Story 1.1: Migrate Main Window to QDockWidget Panel Architecture

As a designer,
I want the application panels (verify, search, log) to be dockable, floatable, and rearrangeable,
So that I can customize my workspace and use multiple monitors efficiently.

**Acceptance Criteria:**

**Given** the application launches with the existing verify, search, and log panels
**When** the main window initializes
**Then** each panel is wrapped in a QDockWidget with a unique objectName (dock_verify, dock_search, dock_log)
**And** the default layout places Verify on the left, Search in the center, and Log at the bottom
**And** each panel can be dragged to a different dock position, floated as a separate window, or tabbed with another panel
**And** the QSplitter-based layout is fully replaced by QDockWidget containers
**And** existing panel widget code (VerifyPanel, SearchBar, ResultsTable, LogPanel) remains functionally unchanged

### Story 1.2: Toolbar, Status Bar, and View Menu

As a designer,
I want a toolbar with primary actions, a status bar showing connection/source state, and a View menu to control panel visibility,
So that I can access key actions quickly and always know what mode the app is in.

**Acceptance Criteria:**

**Given** the main window with dockable panels from Story 1.1
**When** the application starts
**Then** a fixed QToolBar displays 4 actions: "Scan Project", "Export BOM" (disabled until implemented), "Push to KiCad" (grayed in standalone), "Preferences" (disabled until implemented)
**And** a QStatusBar shows 3 zones: left = mode badge (green "Connected to KiCad" pill or gray "Standalone" pill), center = active source names (e.g. "JLCPCB"), right = last action or "Ready"
**And** a View menu lists toggle actions for each panel (via dock.toggleViewAction()) plus a "Reset Layout" action that restores the default panel arrangement
**And** a Help menu contains an "About" dialog showing app name, version, author (Sylvain Boyer / MecaFrog), and MIT license (FR34)
**And** the data mode indicator in the status bar reflects the current state (FR35)

### Story 1.3: Detail Panel for Part Inspection

As a designer,
I want a detail panel that shows full specs, pricing, datasheet link, and an assign button for the selected search result,
So that I can inspect a part thoroughly before deciding to assign it.

**Acceptance Criteria:**

**Given** the dockable panel architecture from Story 1.1
**When** a search result is selected (single-click) in the results table
**Then** a Detail Panel (QDockWidget, right dock) displays: part MPN, manufacturer, description, package, stock, price breaks, and a clickable datasheet URL
**And** the detail panel includes an "Assign to [reference]" button (active when a verify-panel component is also selected)
**And** when no search result is selected, the detail panel shows centered guidance text: "Select a search result to view details" (UX-DR12)

### Story 1.4: Layout Persistence and Empty States

As a designer,
I want my panel arrangement to be saved between sessions and every panel to show helpful guidance when empty,
So that I don't have to reconfigure my layout each time and I always know what to do next.

**Acceptance Criteria:**

**Given** the user has customized the panel layout (moved, resized, or hidden panels)
**When** the application closes
**Then** window geometry and dock state are saved via QSettings (organization="kipart-search", app="kipart-search") (UX-DR14)
**And** when the application reopens, the saved layout is restored exactly

**Given** the application launches with no project scanned and no search performed
**When** the verify panel is empty
**Then** it shows centered text: "Scan a project or open a BOM to begin" (UX-DR12)
**And** the search results area shows: "Search for components using the query bar above"
**And** the log panel shows: "Ready"

### Story 1.5: Context Menus and Accessibility Labels

As a designer,
I want right-click context menus on table rows and accessible status labels,
So that I can quickly access actions and rely on text labels (not just colors) for component status.

**Acceptance Criteria:**

**Given** the verification table or results table has rows displayed
**When** the user right-clicks a row in the verification table
**Then** a context menu appears with: "Search for this component", "Assign MPN", "Copy MPN" (UX-DR13)
**And** right-clicking a results table row shows: "Assign to [reference]", "Copy MPN", "Open Datasheet"

**Given** the verification table shows color-coded component status
**When** any component row is displayed
**Then** every status indicator includes a text label alongside the color: "Verified", "Missing MPN", "Not Found", "Needs attention", "Unverified" (UX-DR15)
**And** custom composite widgets (Health Summary Bar, Dynamic Filter Row when added later) set setAccessibleName() and setAccessibleDescription() (UX-DR15)

---

## Epic 2: Production-Ready BOM Export

Designers can export a CM-ready BOM file (PCBWay, JLCPCB, Newbury Electronics format) with components grouped by MPN, standard package names, SMD/THT labeling, and coverage validation. The export is the finish line of the scan-verify-assign workflow.

### Story 2.1: BOM Export Engine with PCBWay Template

As a designer,
I want a core BOM export engine that transforms my verified component data into a PCBWay-format Excel file,
So that I can generate a production BOM my CM accepts without manual spreadsheet work.

**Acceptance Criteria:**

**Given** a list of ComponentData objects with MPN, manufacturer, description, footprint, and designator fields
**When** the export engine is invoked with the PCBWay template
**Then** it produces an Excel file (.xlsx via openpyxl) with columns: Item #, Designator, Qty, Manufacturer, Mfg Part #, Description/Value, Package, Type (FR29)
**And** components with the same MPN and manufacturer are grouped into a single row with combined designators (e.g. "R14,R18") and correct quantity (e.g. 2) (FR25)
**And** KiCad footprint names are mapped to standard package names (e.g. C_0805_2012Metric -> 0805, R_0402_1005Metric -> 0402) via a mapping function in core/ (FR26)
**And** each component is labeled SMD or THT based on footprint analysis (FR27)
**And** the export engine lives in `core/bom_export.py` with zero GUI dependencies
**And** `openpyxl` is added to pyproject.toml dependencies
**And** the BOMTemplate and BOMColumn dataclasses follow the architecture spec (ADR-02)

### Story 2.2: Preset CM Templates (JLCPCB, Newbury Electronics)

As a designer,
I want preset BOM templates for JLCPCB and Newbury Electronics in addition to PCBWay,
So that I can export in the right format for whichever CM I'm using without building templates manually.

**Acceptance Criteria:**

**Given** the BOM export engine from Story 2.1
**When** the JLCPCB SMT template is selected
**Then** the export produces columns matching the JLCPCB SMT assembly format (from Sample-BOM_JLCSMT.xlsx reference file) including LCSC part number column
**And** when the Newbury Electronics template is selected, it produces columns matching the Newbury format (from pcb-bom-sample-file-newbury-electronics.xlsx reference file)
**And** all preset templates are defined as constants in `core/bom_export.py` (PCBWAY_TEMPLATE, JLCPCB_TEMPLATE, NEWBURY_TEMPLATE)
**And** CSV export is supported as an alternative to Excel for all templates

### Story 2.3: Health Summary Bar with Live Updates

As a designer,
I want a health summary bar above the verification table that shows BOM readiness at a glance and updates live after each assignment,
So that I can see my progress without re-scanning and know when the BOM is ready for export.

**Acceptance Criteria:**

**Given** a board has been scanned with components in the verification table
**When** the health summary bar is displayed
**Then** it shows a QProgressBar color-coded by percentage (red <50%, amber 50-99%, green 100%) (UX-DR10)
**And** summary text reads: "Components: N total | Valid MPN: X | Needs attention: Y | Missing MPN: Z"

**Given** a designer assigns an MPN to a component
**When** the assignment is confirmed
**Then** the health bar percentage, color, and summary counts update immediately without a full re-scan (UX-DR18)
**And** the component row color updates from red/amber to green immediately

### Story 2.4: BOM Export Dialog with Template Selection and Preview

As a designer,
I want an export dialog where I select a CM template, preview the output, configure DNP handling, and export the file,
So that I can verify the BOM looks correct before generating the file.

**Acceptance Criteria:**

**Given** the designer clicks "Export BOM" in the toolbar
**When** the BOM export dialog opens (non-modal, so the user can go back to fix issues)
**Then** a template selector shows all preset templates (PCBWay, JLCPCB, Newbury) plus any custom templates (UX-DR6)
**And** selecting a template shows a live preview table with the actual BOM data in the selected column layout and grouping
**And** a DNP handling toggle lets the user choose "Include marked" or "Exclude entirely"
**And** a file format selector offers Excel (.xlsx) or CSV (.csv)

**Given** the health bar is below 100%
**When** the export dialog opens
**Then** a warning banner appears: "X components still missing MPNs" with an option to proceed anyway or go back (FR28)

**Given** the user confirms export
**When** the file is written
**Then** a success message shows the file path with an "Open File" button
**And** export completes in < 5 seconds for a 70-component board (NFR4)

---

## Epic 3: Search & Verification Enhancements

Designers get dynamic filters that adapt to search results, two-mode search (Specific source vs Unified across all sources), live dashboard updates after assignments, and stale data indicators for re-verification awareness.

### Story 3.1: Dynamic Filter Row

As a designer,
I want search result filters that automatically adapt to the data returned by each search,
So that I can narrow results by manufacturer, package, category, or other fields without guessing what's available.

**Acceptance Criteria:**

**Given** a search has returned results in the results table
**When** the results are displayed
**Then** a horizontal row of QComboBox dropdowns appears above the results table, with one dropdown per filterable field found in the data (e.g. Manufacturer, Package, Category) (UX-DR9)
**And** each dropdown is populated with unique values from the returned results for that field, plus an "All" default option
**And** a result count label shows "X of Y results" reflecting current filter state
**And** selecting a filter value narrows the displayed results immediately (local filtering)
**And** clearing a filter (selecting "All") restores results without re-searching
**And** filters are additive — applying Package: 0805 AND Manufacturer: Murata shows only matching rows (FR3)

**Given** no search has been performed yet
**When** the search panel is displayed
**Then** the filter row is hidden (no empty dropdowns shown)

### Story 3.2: Two-Mode Search Architecture (Specific vs Unified)

As a designer,
I want to choose between searching a single source or all enabled sources at once,
So that I get fast results when I know which source to use, and comprehensive results when I'm discovering parts.

**Acceptance Criteria:**

**Given** the search panel with a source selector dropdown
**When** a specific source is selected (e.g. "JLCPCB")
**Then** the search query is sent only to that source (Specific mode) (UX-DR11)
**And** the results table does not show a "Source" column
**And** filters apply locally to the returned results

**Given** "All Sources" is selected in the source selector
**When** a search is executed
**Then** the query is sent to all enabled sources in parallel (Unified mode) (UX-DR11)
**And** a "Source" column appears in the results table showing which source each result came from
**And** results from multiple sources are displayed as they arrive (incremental, no blocking)

**Given** only one source is configured (e.g. JLCPCB only)
**When** the source selector is displayed
**Then** it shows "JLCPCB" and "All Sources" (which behaves identically to JLCPCB-only in this case)

### Story 3.3: Verification Dashboard Enhancements

As a designer,
I want the verification dashboard to show clear per-component status with text labels, support re-verification, and provide guided search from context,
So that I can quickly triage all components and fix issues efficiently.

**Acceptance Criteria:**

**Given** a board has been scanned
**When** the verification table is displayed
**Then** each component row is color-coded by status (green/amber/red) with a text label: "Verified", "Missing MPN", "Not Found", "Needs attention", "Unverified" (FR16, FR17)
**And** per-component status shows: MPN present, MPN verified in database, footprint match (FR17)
**And** components are sorted by status (red first, then amber, then green) by default

**Given** a component has a missing or unverified MPN (red/amber status)
**When** the designer double-clicks that component row
**Then** the search panel opens with a pre-filled query using the component's value and package (e.g. "100nF 0805 capacitor") (FR19)
**And** the query is transformed using the existing query transform pipeline (FR5)
**And** the designer can edit the transformed query before executing (FR6)

**Given** the designer has made changes (assigned MPNs, edited fields)
**When** they click a "Re-verify" button in the verify panel
**Then** verification re-runs against the current component state and the dashboard updates (FR20)

### Story 3.4: Stale Data Indicators

As a designer,
I want to see which components were verified against an older database version,
So that I know what to re-check after a database update.

**Acceptance Criteria:**

**Given** components were verified against the JLCPCB database at a certain timestamp
**When** the database is refreshed/updated to a newer version
**Then** previously verified components are flagged with an amber stale indicator (UX-DR16)
**And** the stale indicator shows: "Last verified: [date] — database updated since. Re-scan recommended."
**And** the health summary bar reflects stale components in the "Needs attention" count

**Given** a component was never verified (freshly scanned)
**When** it is displayed in the verification table
**Then** no stale indicator is shown — only its normal verification status

---

## Epic 4: Caching & Offline Resilience

Designers get faster repeat searches via local cache, offline access to previously-fetched results, and database corruption recovery — making the tool reliable for daily production use.

### Story 4.1: SQLite Query Cache

As a designer,
I want search results and part data cached locally with configurable expiration,
So that repeat searches are instant and I can work offline after initial queries.

**Acceptance Criteria:**

**Given** the application is running
**When** a search query returns results from any source
**Then** the results are stored in `~/.kipart-search/cache.db` (separate from the JLCPCB parts database) with the cache key format `{source}:{query_type}:{sha256(normalized_query)}` (ADR-01)
**And** each cache entry stores: key, source, query_type, data (JSON string), created_at (Unix timestamp), ttl_seconds

**Given** the same search query is executed again
**When** a valid (non-expired) cache entry exists
**Then** cached results are served immediately without a network call (FR31)
**And** the log panel shows a cache hit indicator (e.g. "JLCPCB: served from cache")

**Given** a cache entry exists but has expired
**When** the query is executed
**Then** a fresh API/database query is made and the cache entry is updated

**Given** default TTL values
**When** cache entries are created
**Then** pricing/stock data expires after 4 hours, parametric data after 7-30 days, datasheet URLs are cached indefinitely (FR30)

**And** the cache database uses WAL journal mode for concurrent read access from GUI and worker threads
**And** `core/cache.py` exposes: `get(key)`, `put(key, data, source, query_type, ttl)`, `invalidate(source=None)`, `is_expired(entry)` — zero GUI dependencies

### Story 4.2: JLCPCB Database Download and Refresh

As a designer,
I want to download the JLCPCB parts database on first run with progress indication and refresh it when needed,
So that I have offline search capabilities without manual file management.

**Acceptance Criteria:**

**Given** the application launches and no JLCPCB database exists locally
**When** the user is prompted to download
**Then** a progress dialog shows download progress (chunked download from GitHub Pages hosting, ~500 MB) (FR7)
**And** the download can be cancelled without corrupting local state
**And** on completion the database is stored at `~/.kipart-search/parts-fts5.db` and the JLCPCB source becomes available

**Given** the JLCPCB database already exists locally
**When** the user clicks a "Refresh Database" action
**Then** the database is re-downloaded with progress indication (FR8)
**And** the old database is replaced only after the new download completes successfully
**And** the cache database (`cache.db`) and configuration are not affected by the refresh (NFR12)

**Given** the local database file is corrupted or unreadable
**When** the application detects the corruption (e.g. SQLite open fails)
**Then** the user is prompted to re-download with a clear message: "Database corrupted — download a fresh copy?" (NFR12)
**And** configuration, cache, and API keys are preserved

### Story 4.3: Full Offline Operation

As a designer,
I want the application to work fully offline after the initial database download,
So that I can search, verify, and export BOMs without an internet connection.

**Acceptance Criteria:**

**Given** the JLCPCB database has been downloaded and cached results exist
**When** the application launches with no internet connection
**Then** the application starts normally and all local functionality works: FTS5 search, board scan, verification, MPN assignment, BOM export (FR33)
**And** the status bar shows "Local DB" as the data mode (FR35)
**And** API-based sources (DigiKey, Mouser) show as unavailable without errors or crashes (NFR9)
**And** previously cached API results are still served from cache.db

**Given** the application is offline and a search returns no results from the local database
**When** the user sees 0 results
**Then** the log panel notes that online sources are unavailable: "DigiKey: offline — cached results only"
**And** the manual MPN entry workflow remains fully functional

---

## Epic 5: Safe KiCad Write-Back & Assignment

Designers can assign MPNs to KiCad components with full safety guarantees: silent backups before write sessions, undo log, add-never-overwrite policy, type/package mismatch warnings, and atomic writes per component.

### Story 5.1: KiCad Connection and Board Scan

As a designer,
I want the application to auto-detect a running KiCad instance and scan all board components into the verification dashboard,
So that I can start the BOM workflow without manual configuration.

**Acceptance Criteria:**

**Given** KiCad 9+ is running with IPC API enabled
**When** the application launches or the user clicks "Scan Project"
**Then** the app auto-detects the KiCad IPC API socket (via `KICAD_API_SOCKET` env var or default path) without manual configuration (FR10, NFR8)
**And** all components are read from the active PCB project: reference, value, footprint, and existing field data (MPN, manufacturer, description, supplier P/Ns) (FR11)
**And** the verification dashboard populates with all components and their status
**And** the scan completes in < 10 seconds for a 70-component board (NFR2)
**And** all IPC API calls are isolated in `gui/kicad_bridge.py` behind a single abstraction layer (NFR10)

**Given** KiCad is not running or the IPC API is unavailable
**When** the application launches
**Then** the status bar shows "Standalone" (gray pill) and KiCad-specific actions (highlight, Push to KiCad) are grayed out (NFR9)
**And** all other functionality (search, verify against local data, export) works normally

### Story 5.2: Click-to-Highlight Cross-Probe

As a designer,
I want to click a component in the app and have it highlighted in KiCad's PCB editor,
So that I can visually locate components on the board while working through verification.

**Acceptance Criteria:**

**Given** the app is connected to KiCad and the verification table shows scanned components
**When** the designer single-clicks a component row in the verification table
**Then** the corresponding footprint is selected/highlighted in KiCad's PCB editor (FR12)
**And** KiCad's internal cross-probe automatically highlights the component in the schematic editor

**Given** the app is in standalone mode (no KiCad connection)
**When** the designer clicks a component row
**Then** the detail panel updates normally but no KiCad highlight occurs
**And** no error is shown — the feature is silently unavailable

### Story 5.3: MPN Assignment with Preview Dialog

As a designer,
I want to assign an MPN from search results or manually enter one, with a clear preview of all field changes before confirming,
So that I know exactly what will be written and can catch mistakes before they happen.

**Acceptance Criteria:**

**Given** a search result is selected and a target component is selected in the verification table
**When** the designer clicks "Assign" (from detail panel, context menu, or double-click on search result)
**Then** an assign dialog opens showing plain-language confirmation: "Add MPN: [value] to [reference]?" (FR21)
**And** the dialog previews all field changes: MPN, Manufacturer, Description, and any supplier P/Ns (FR23)
**And** the designer can confirm or cancel

**Given** the designer needs to assign a part not found in any database
**When** they choose "Manual Entry" in the assign dialog
**Then** editable fields appear for MPN, Manufacturer, and Description (FR22)
**And** the preview updates to show the manually-entered values before confirmation

**Given** the designer confirms the assignment
**When** the write-back executes
**Then** in connected mode: fields are written to the KiCad component via IPC API (FR13)
**And** in standalone mode: fields are stored in local state for BOM export
**And** the verification table row updates immediately (green status)

### Story 5.4: Write-Back Safety Guards

As a designer,
I want the tool to prevent accidental overwrites and warn about mismatches,
So that my existing correct data is never silently destroyed and I catch assignment errors early.

**Acceptance Criteria:**

**Given** a target component already has a non-empty MPN field
**When** the designer attempts to assign a different MPN
**Then** the assign dialog shows an explicit warning: "MPN field already contains [existing value]. Overwrite?" with separate Overwrite / Cancel buttons (FR14)
**And** the default button is Cancel (not Overwrite)

**Given** the assigned part has a different package or type than the target component
**When** the assign dialog opens
**Then** a mismatch warning is displayed: "Warning: Part package [QFN-24] does not match footprint [SOIC-8]" (FR15)
**And** the designer can still proceed but must explicitly acknowledge the mismatch

**Given** a write-back to KiCad fails for one component (e.g. IPC API error)
**When** the error occurs
**Then** the failure is logged and the user is notified, but other components are not affected (NFR13)
**And** the failed component remains in its previous state (not partially written)
**And** no crash or data loss occurs (NFR11)

### Story 5.5: Backup System and Undo Log

As a designer,
I want automatic backups before any write session and a persistent undo log,
So that I can always recover if something goes wrong, even beyond KiCad's undo stack.

**Acceptance Criteria:**

**Given** the designer is about to confirm the first write-back of a session (connected mode)
**When** the write-back is initiated
**Then** a silent timestamped backup is created at `~/.kipart-search/backups/{project}/{YYYY-MM-DD_HHMM}/` before any fields are written (UX-DR17)
**And** subsequent writes in the same session do not create additional backups (one backup per session)
**And** no user action is required — backups are automatic and silent

**Given** any write-back is performed (connected or standalone)
**When** the field change is committed
**Then** an entry is appended to an undo log CSV file: timestamp, reference, field name, old value, new value (UX-DR17)
**And** the undo log persists across application sessions

**Given** the designer wants to view or restore from a backup
**When** they access the backup browser (via menu or settings)
**Then** a list of available backups is shown with project name and timestamp
**And** the designer can restore any previous backup

### Story 5.6: Schematic File Parser Module

As a designer,
I want KiPart Search to read and write fields in my `.kicad_sch` files,
So that MPN assignments persist in my KiCad project files.

**Acceptance Criteria:**

**Given** a `.kicad_sch` file with symbol blocks containing `(property ...)` entries
**When** `read_symbols(sch_path)` is called
**Then** it returns a list of symbols with all their properties (Reference, Value, Footprint, MPN, Manufacturer, etc.)
**And** the parser handles nested S-expressions correctly (depth-counting, not regex)

**Given** a symbol identified by reference designator (e.g. "C12")
**When** `set_field(sch_path, reference, field_name, value)` is called with a field that doesn't exist
**Then** a new `(property ...)` entry is inserted into the symbol block with the correct format
**And** the field is hidden by default (`(effects (font (size 1.27 1.27)) hide)`)
**And** the rest of the file is preserved byte-for-byte (no reformatting)

**Given** a symbol with an existing field
**When** `set_field()` is called with `allow_overwrite=False` (default)
**Then** the field is NOT modified and the method returns False
**And** with `allow_overwrite=True`, the field value is updated in-place

**Given** a KiCad project directory
**When** `find_schematic_files(project_dir)` is called
**Then** it discovers the root `.kicad_sch` and all sub-sheets referenced via `(sheet ...)` blocks
**And** `find_symbol_sheet(project_dir, reference)` returns the path to the sheet containing the given reference

**Technical constraints:**
- Zero GUI dependencies — lives in `core/`
- Proper S-expression depth-counting parser (not regex for block extraction)
- Preserves file formatting, comments, and whitespace outside modified blocks
- UTF-8 encoding throughout
- Uses `pathlib.Path` for all file operations

### Story 5.7: File-Based Write-Back via Push to KiCad

As a designer,
I want to push my MPN assignments from KiPart Search into my KiCad schematic files,
So that my KiCad project carries all manufacturing references and future BOM exports from KiCad are already complete.

**Acceptance Criteria:**

**Given** the designer has made local MPN assignments (`_local_assignments` is non-empty)
**When** they click "Push to KiCad"
**Then** the system checks if KiCad's eeschema process has the schematic files open

**Given** the schematic files are open in KiCad
**When** the open-file check detects this
**Then** the system shows a warning: "Close the schematic editor in KiCad before pushing changes. File-based write cannot proceed while the schematic is open."
**And** the write is blocked — no file modification occurs

**Given** the schematic files are NOT open in KiCad (or KiCad is not running)
**When** the designer confirms the push
**Then** all `.kicad_sch` files in the project are backed up to `~/.kipart-search/backups/{project}/{YYYY-MM-DD_HHMM}/` (extends Story 5.5)
**And** each local assignment is written to the correct schematic file via `core/kicad_sch.py`
**And** each write is logged to the undo CSV (timestamp, reference, field, old value, new value)
**And** the add-never-overwrite policy is enforced (non-empty fields are not modified without explicit confirmation)

**Given** the push completes successfully
**When** the success dialog is shown
**Then** it displays: "Written N fields to M components. Run 'Update PCB from Schematic' (F8) in KiCad to sync the board."
**And** `_local_assignments` is cleared for the successfully written fields
**And** the log panel records: "Pushed N field(s) to .kicad_sch — run Update PCB from Schematic to sync"

**Given** a write fails for any component
**When** the error is caught
**Then** the system continues writing remaining components (non-atomic across components, atomic per component)
**And** failed writes remain in `_local_assignments` for retry
**And** the error is logged with the specific component reference and reason

**Safety constraints:**
- KiCad-open detection is mandatory — refuse to write if schematic is open
- Backup is mandatory — no writes without a successful backup first
- Add-never-overwrite is the default — matches existing UX-DR17 spec
- Undo log records every change for auditability

### Story 5.8: Dual-Source Scan (Schematic + PCB)

As a designer,
I want the scan to read component data from both my `.kicad_sch` schematic files and the PCB via IPC API,
So that I see all components (including unplaced ones), get the most up-to-date field values, and get warned when the PCB is out of sync with the schematic.

**Acceptance Criteria:**

**Given** the app is connected to KiCad and a board scan is initiated
**When** the scan reads components from the PCB via IPC API
**Then** the system also reads symbol properties from all `.kicad_sch` files in the project directory via `core/kicad_sch.py`
**And** for each component, the scan merges data from both sources: schematic fields take priority over PCB fields for MPN, Manufacturer, and other custom properties (schematic is the source of truth)

**Given** a component exists in the schematic but has no footprint placed on the PCB
**When** the verification dashboard displays results
**Then** that component appears in the table with a distinct "Not on PCB" status indicator
**And** click-to-highlight is unavailable for that component (no footprint to select)
**And** the health summary bar counts these components under "Needs attention"
**And** the log panel reports: "N component(s) found in schematic but not placed on PCB"

**Given** a component's schematic symbol has field values (e.g. MPN) that differ from the PCB footprint fields
**When** the verification dashboard displays results
**Then** that component shows an amber "PCB out of sync" indicator
**And** a tooltip or detail text reads: "Schematic has MPN '[value]' but PCB does not — run Update PCB from Schematic (F8) in KiCad"

**Given** one or more components are detected as out of sync or not on PCB
**When** the scan completes
**Then** a banner or log message warns: "N component(s) need attention — run Update PCB from Schematic (F8) in KiCad, then re-scan."

**Given** all components have matching fields between PCB and schematic and all are placed
**When** the scan completes
**Then** no sync warning is shown — the scan proceeds as normal

**Given** the app cannot locate the `.kicad_sch` project files (e.g. standalone mode, project directory not resolvable)
**When** the scan runs
**Then** schematic reading is silently skipped — the scan works exactly as before (PCB-only)
**And** no error is shown (graceful degradation)

**Technical constraints:**
- Merge logic lives in `core/` (zero GUI dependencies) — e.g. `merge_pcb_sch(pcb_components: list[BoardComponent], sch_symbols: list[SchSymbol]) -> list[MergedComponent]`
- A new `MergedComponent` dataclass or extended `BoardComponent` carries a `source` flag indicating: `both`, `pcb_only`, `sch_only`, and a `sync_mismatches: list[str]` for differing fields
- Schematic file discovery reuses `kicad_sch.find_schematic_files()` and `read_symbols()`
- The scan worker thread handles schematic reads in background (no GUI blocking)
- Schematic lock files do NOT prevent read access — only writes are blocked by locks
- This is read-only — no `.kicad_sch` file modification occurs

---

## Epic 6: Source Configuration & First-Run Experience

Designers can configure which data sources are active, enter and validate API keys, set a default source, and get guided through first-launch setup — enabling multi-source workflows in future phases.

### Story 6.1: Source Preferences Dialog

As a designer,
I want a preferences dialog where I can enable/disable data sources, enter API keys, and test connections,
So that I control which distributors the tool queries and can validate my credentials before searching.

**Acceptance Criteria:**

**Given** the designer clicks "Preferences" in the toolbar or menu
**When** the Source Preferences Dialog opens (modal)
**Then** it lists all available sources: JLCPCB (offline DB), DigiKey, Mouser, Octopart (UX-DR7)
**And** each source has: an enable/disable toggle, a status indicator (green = configured, amber = key missing, red = key invalid after test), and source-specific configuration

**Given** a source requires an API key (DigiKey, Mouser, Octopart)
**When** the source is enabled
**Then** an API key input field appears with a "Test Connection" button
**And** clicking "Test" validates the credentials against the API and shows green checkmark (valid) or red X with error message (invalid)
**And** valid API keys are stored via `keyring` (OS-native secret storage), never in plaintext config files (FR32, NFR6)
**And** environment variable overrides are supported: `KIPART_DIGIKEY_CLIENT_ID`, `KIPART_MOUSER_API_KEY`, etc.

**Given** the JLCPCB source row is displayed
**When** the designer views its configuration
**Then** it shows database status (downloaded / not downloaded / stale), database path, file size, and a "Download" or "Refresh" button
**And** a default source selector lets the user choose which source is pre-selected in the search bar

**Given** no telemetry requirement (NFR7)
**When** any source configuration is saved
**Then** no data is sent to external servers — only explicit user-initiated API calls contact distributor APIs

### Story 6.2: Welcome / First-Run Dialog

As a new user,
I want a guided first-launch experience that helps me set up at least one data source,
So that I can start searching immediately without reading documentation.

**Acceptance Criteria:**

**Given** the application launches for the first time (no sources configured, checked via config file)
**When** the main window opens
**Then** a Welcome Dialog (modal) appears with a brief tool description and 3 options (UX-DR8):
1. "Download JLCPCB Database" — no API key needed, shows download progress bar (~500 MB), cancel available
2. "Configure API Source" — opens the Source Preferences Dialog from Story 6.1
3. "Skip for now" — closes dialog, app opens with no sources and limited functionality

**Given** the user selects "Download JLCPCB Database"
**When** the download completes
**Then** the dialog auto-closes, the JLCPCB source is enabled, and the status bar updates to show "JLCPCB" as active
**And** the app is immediately usable for searching

**Given** the user selects "Skip for now"
**When** the dialog closes
**Then** the app opens normally with status bar showing "No sources configured"
**And** the Preferences button in the toolbar is visually emphasized (e.g. subtle highlight) to guide the user back
**And** the Welcome Dialog is not shown again on subsequent launches — the user configures sources via Preferences

**Given** a returning user who has previously configured sources
**When** the application launches
**Then** the Welcome Dialog does not appear — the app opens directly to the main window

---

## Epic 7: Build Pipeline & Distribution (Windows)

Developers can compile KiPart Search into a standalone Windows binary using Nuitka, enforce dependency license compliance, and gate premium features behind a one-time license key — enabling closed-source distribution and monetization without requiring end-users to install Python. Free tier remains genuinely useful (JLCPCB search, scan, basic verify, single write-back). Pro tier gates productivity-at-scale features (multi-distributor, CM exports, batch write-back, full verification).

### Story 7.1: Minimal Nuitka Build

As a developer,
I want to compile KiPart Search into a standalone Windows binary using Nuitka that launches and displays the main window,
So that I have a working build pipeline foundation for closed-source distribution.

**Acceptance Criteria:**

**Given** the project source code with all dependencies installed
**When** the developer runs the Nuitka build script
**Then** a `dist/` folder is produced containing a standalone `kipart-search.exe` and all required DLLs
**And** PySide6 Qt plugins (platforms, imageformats, styles) are correctly included via `--enable-plugin=pyside6`
**And** the compiled binary launches and displays the main window without errors
**And** `keyring.backends` are included via `--include-package` to resolve dynamic import discovery
**And** SSL certificates are bundled for `httpx` HTTPS requests
**And** the build script is a single Python file (`build_nuitka.py`) that can be run reproducibly
**And** a GPL firewall check runs before compilation: parses `pip-licenses` output and fails the build if any GPL dependency is detected (NFR16)
**And** PySide6 Qt DLLs remain as separate shared libraries in the output (dynamic linking, satisfying LGPL — NFR17)

### Story 7.2: Compiled Binary Full Functionality Verification

As a developer,
I want to verify that all application features work correctly in the compiled binary,
So that I can be confident the distributed build matches the development experience.

**Acceptance Criteria:**

**Given** the compiled binary from Story 7.1
**When** the developer runs the smoke test checklist against the compiled binary
**Then** JLCPCB database download completes with progress indication
**And** full-text search returns results in under 5 seconds (NFR19)
**And** KiCad IPC connection works when KiCad is running (kicad-python optional import resolved)
**And** KiCad scan, highlight, and single-component write-back function correctly
**And** BOM export produces valid Excel and CSV files (openpyxl working)
**And** keyring stores and retrieves API keys via the OS-native backend
**And** the verify panel displays component status with colour-coded indicators
**And** all QDockWidget panels dock, float, and persist layout via QSettings
**And** a smoke test script (`tests/smoke_test_build.py`) documents the manual verification checklist with pass/fail recording
**And** any Nuitka `--include-*` flags needed to fix broken features are added to the build script

### Story 7.3: License Module and Feature Gating

As a developer,
I want a license module that validates a one-time license key and gates premium features behind class-level capability checks,
So that free and paid tiers are enforced in both development and compiled builds.

**Acceptance Criteria:**

**Given** the application starts without a license key
**When** the user launches the app
**Then** the free tier is fully functional: JLCPCB search, KiCad scan/highlight, basic verification (MPN present/missing), single-component write-back, CSV export
**And** Pro-gated features show a disabled state with tooltip "Requires Pro license": multi-distributor search, CM BOM export templates, full verification (datasheet/footprint checks), batch write-back, Excel export

**Given** the user enters a valid license key in the Preferences dialog
**When** the key is validated online via LemonSqueezy/Gumroad API
**Then** all Pro features become available immediately without restart
**And** the license key is stored securely via `keyring`
**And** the status bar shows "Pro" badge

**Given** the app has a cached valid license but no internet connection
**When** the user launches the app offline
**Then** the offline signed-JWT fallback validates the cached key
**And** Pro features remain available

**Given** a Pro-gated feature class (e.g., `BatchWriteBack`, `CMBOMExport`)
**When** instantiated without a valid Pro license
**Then** a `FeatureNotAvailable("pro")` exception is raised at `__init__` level (class-level gating, not bare conditionals)
**And** the `core/license.py` module contains the `License` class, feature registry, and validation logic
**And** the pricing model is one-time fee (not subscription) — no expiry check on valid keys

### Story 7.4: Windows Zip Distribution Package

As a developer,
I want to package the compiled binary as a distributable zip file for Windows,
So that end-users can download, unzip, and run KiPart Search without installing Python.

**Acceptance Criteria:**

**Given** a successful Nuitka build from Story 7.1
**When** the developer runs the packaging step in the build script
**Then** a `kipart-search-{version}-windows.zip` file is produced containing the standalone folder
**And** the zip includes a top-level `kipart-search/` folder with `kipart-search.exe` at its root
**And** the zip includes a `README.txt` with: quick start instructions, system requirements (Windows 10/11), and link to documentation
**And** the zip file size is documented (baseline for tracking bloat)
**And** a fresh Windows machine (no Python installed) can unzip and run `kipart-search.exe` successfully
**And** the build script has a `--package` flag that produces the zip after compilation
**And** version number is read from `pyproject.toml` and embedded in the zip filename and the app's About dialog

### Story 7.5: CI Build Pipeline

As a developer,
I want an automated CI pipeline that compiles, tests, and packages the Windows binary on every tagged release,
So that distribution builds are reproducible and not dependent on my local machine.

**Acceptance Criteria:**

**Given** a GitHub Actions workflow file (`.github/workflows/build-windows.yml`)
**When** a version tag (`v*.*.*`) is pushed to the repository
**Then** the pipeline installs Python 3.10+, project dependencies, and Nuitka
**And** the GPL firewall check runs and fails the pipeline if GPL deps are detected
**And** the Nuitka build script executes and produces the standalone binary
**And** the smoke test script runs basic validation (app launches, exits cleanly)
**And** the zip package is produced with correct version in filename
**And** the zip is uploaded as a GitHub Release asset attached to the tag
**And** the pipeline completes in under 30 minutes
**And** build artifacts are cached between runs where possible (Nuitka ccache, pip cache)
