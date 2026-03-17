---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
lastStep: 8
status: 'complete'
completedAt: '2026-03-17'
inputDocuments:
  - planning-artifacts/product-brief-kipart-search-2026-03-15.md
  - planning-artifacts/prd.md
  - planning-artifacts/prd-validation-report.md
  - planning-artifacts/ux-design-specification.md
  - planning-artifacts/research/technical-kipart-search-stack-research-2026-03-17.md
  - project-context.md
  - ExistingWorksOn/compass_artifact_wf-af099856-fd25-4fc1-bcd0-66648f118144_text_markdown.md
workflowType: 'architecture'
project_name: 'kipart-search'
user_name: 'Sylvain'
date: '2026-03-17'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
35 FRs across 8 capability groups:
- **Search & Discovery** (FR1-6): Parametric search with query transformation, filterable results, detail view
- **JLCPCB Database** (FR7-9): Offline database download, refresh, sub-2s FTS5 search
- **KiCad Integration** (FR10-15): IPC API connect, scan, click-to-highlight, write-back with safety guards
- **Verification Dashboard** (FR16-20): Color-coded status, health bar, guided search from context
- **MPN Assignment** (FR21-23): Assign from search or manual entry, preview dialog
- **BOM Export** (FR24-29): PCBWay format, grouping by MPN, footprint-to-package mapping, SMD/THT detection, coverage gate
- **Caching** (FR30-31): Local cache with per-source TTL, offline serving
- **Configuration** (FR32-35): API key management, offline mode, Help/About, data mode indicator

Architecturally, these map to 4 layers: GUI -> Core (orchestration + verification) -> Data Source Adapters -> Infrastructure (cache, credentials, units).

**Non-Functional Requirements:**
15 NFRs driving key architectural decisions:
- **Performance** (NFR1-5): FTS5 < 2s, scan < 10s, no GUI freezes, export < 5s, cold start < 3s — mandates background threading for all I/O
- **Security** (NFR6-7): OS-native secret storage, no telemetry — mandates keyring integration
- **Integration** (NFR8-10): Auto-detect KiCad, standalone fallback, single IPC abstraction layer — mandates kicad_bridge isolation
- **Reliability** (NFR11-13): No crashes in core workflow, DB corruption recovery, atomic writes — mandates defensive error handling per adapter
- **Portability** (NFR14-15): Windows/Linux/macOS, no hardcoded paths — mandates pathlib everywhere, Qt for platform abstraction

**Scale & Complexity:**
- Primary domain: Desktop application with external API integration
- Complexity level: Low-medium
- Estimated architectural components: ~15 modules across 4 layers
- Data volume: ~1M parts in local DB, search results typically 10-500 parts, BOM typically 30-200 components

### Technical Constraints & Dependencies

| Constraint | Impact |
|-----------|--------|
| Python 3.10+ | Union syntax `X \| Y`, `from __future__ import annotations` |
| PySide6 (LGPL-3.0) | GUI framework choice locked; QThread for threading |
| KiCad IPC API (PCB only in v9) | No schematic API — must use cross-probe chain via PCB selection |
| kicad-python v0.6.0 field write-back uncertain | May need fallback file manipulation |
| `digikey-api` GPL-3.0 vs MIT project | Must write own thin httpx adapter to avoid copyleft |
| JLCPCB DB uses mixed ASCII/Unicode units | Query transform pipeline must handle uF vs µF, kOhm vs kohm |
| MPN field has 8+ aliases in KiCad | kicad_bridge must search all aliases via `MPN_FIELD_NAMES` set |
| Solo developer, manual testing workflow | Architecture must be simple, debuggable, not over-engineered |

### Cross-Cutting Concerns Identified

1. **Graceful Degradation**: Every external dependency (KiCad, each distributor API, internet, JLCPCB DB) fails independently. The app always launches and offers maximum functionality with whatever is available.

2. **Core/GUI Separation**: The foundational architectural constraint. `core/` is importable by CLI, tests, or future KiCad wxPython shim. Zero PySide6 imports in core.

3. **Multi-Source Data Normalization**: Each adapter normalizes its API response to `PartResult`. The orchestrator deduplicates by MPN+manufacturer and merges offers from multiple sources.

4. **Thread Safety**: All network I/O and database queries run in QThread workers. GUI model updates only via signal-to-slot on the GUI thread with proper begin/endInsertRows.

5. **Credential Lifecycle**: Three auth patterns (OAuth2 client credentials, OAuth2 authorization code, API key) with proactive token refresh and validation-on-entry.

6. **Rate Limiting**: Per-source token bucket. Exponential backoff on 429/503. Daily counter for DigiKey's 1,000/day limit.

7. **Engineering Value Normalization**: The `units.py` module and `generate_query_variants()` ensure that 0.1uF, 100nF, and 100000pF all match the same parts across all sources.

## Starter Template Evaluation

### Primary Technology Domain

**Python desktop application** (PySide6/Qt6) with external API integration and KiCad IPC API bridge.

### Starter Options Considered

Not applicable — this is a brownfield project. The codebase is functional with Tier 1 MVP complete (search, scan, verify, assign). The `src/` layout, build system, dependency set, and module structure are established and working.

### Established Foundation (In Lieu of Starter)

**Language & Runtime:**
- Python 3.10+ with `from __future__ import annotations` in every file
- Type hints with `X | Y` union syntax (not `Optional` or `Union`)
- `@dataclass` for all data models, `Enum` for constrained value sets

**Build & Packaging:**
- `pyproject.toml` with hatchling build backend
- `src/` layout (current Python best practice)
- Entry point: `python -m kipart_search`
- Target distribution: PyPI, future KiCad Plugin and Content Manager

**GUI Framework:**
- PySide6-Essentials (LGPL-3.0) — lighter than full PySide6
- QThread workers with Signal/Slot for background I/O
- QAbstractTableModel + QSortFilterProxyModel for results
- QDockWidget panels (per UX spec, migrating from current QSplitter)

**Dependencies (MIT-compatible):**

| Package | Purpose | License | Required |
|---------|---------|---------|----------|
| `httpx` | HTTP client | BSD-3 | Yes |
| `keyring` | OS-native secrets | MIT | Yes |
| `PySide6-Essentials` | Qt6 GUI | LGPL-3.0 | Yes (GUI) |
| `kicad-python` | KiCad IPC API | MIT | Optional |
| `openpyxl` | Excel BOM export | MIT | Yes (Phase 1) |

**Code Organization:**
- `core/` — zero GUI imports, importable by CLI/tests/future KiCad shim
- `gui/` — all PySide6 code
- `vendored/` — third-party code with MIT attribution headers (e.g., units.py from KiBoM)
- `cli/` — optional CLI entry point

**Testing Framework:**
- pytest (dev dependency, not yet active — manual testing workflow)
- Test files in `tests/` mirroring `src/kipart_search/` structure

**Note:** No initialization story needed — codebase is already functional.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Cache storage design (separate SQLite DB)
- BOM export template engine (declarative dict-based mappings)
- KiCad write-back strategy (investigate existing capabilities first)
- Multi-source deduplication (merge by MPN+manufacturer)

**Important Decisions (Shape Architecture):**
- GUI migration to QDockWidget panels (Phase 1)

**Deferred Decisions (Post-MVP):**
- Standalone BOM import format (Phase 2)
- DigiKey 3-legged OAuth flow (Phase 2 — 2-legged sufficient for search)
- Nexar adapter (Phase 2 — only for Pro-tier users)

### Data Architecture

**ADR-01: Separate Cache Database**
- **Decision:** Cache stored in `~/.kipart-search/cache.db`, separate from the JLCPCB parts database
- **Rationale:** The JLCPCB database is a downloaded artifact replaced on refresh. The cache is user-generated data (API results, verification state) that must survive DB updates.
- **Schema:** Single `cache_entries` table: `key TEXT PRIMARY KEY, source TEXT, query_type TEXT, data TEXT (JSON), created_at REAL, ttl_seconds INTEGER`
- **Cache key format:** `{source}:{query_type}:{sha256(normalized_query)}`
- **TTLs:** Pricing/stock: 4 hours. Parametric data: 7-30 days. Datasheets: indefinite.
- **Affects:** `core/cache.py`, all DataSource adapters, search orchestrator

**ADR-02: BOM Export Template Engine — Declarative Dict Mappings**
- **Decision:** Each CM template is a Python dataclass defining column names, column order, field mappings, grouping rules, and DNP handling. No Jinja2 or string-template dependency.
- **Rationale:** BOM export is structured tabular data (rows and columns), not freeform text. Declarative mappings are simpler, more debuggable, and sufficient for Excel/CSV output.
- **Preset templates:** Ship as constants in `core/bom_export.py` (PCBWay, JLCPCB, Newbury Electronics)
- **Custom templates:** Stored as JSON in `~/.kipart-search/templates/`
- **Affects:** New `core/bom_export.py` module, new `gui/export_dialog.py` panel

### Authentication & Security

**ADR-03: Credential Storage — keyring with Environment Variable Fallback**
- **Decision:** Already established. All API credentials stored via `keyring` (OS-native). Environment variable overrides: `KIPART_DIGIKEY_CLIENT_ID`, `KIPART_MOUSER_API_KEY`, `KIPART_NEXAR_CLIENT_ID`, etc.
- **Rationale:** Never store secrets in plaintext config. `keyring` uses Windows Credential Manager / macOS Keychain / Linux Secret Service.
- **Affects:** `gui/settings_dialog.py`, all DataSource adapters

**ADR-04: DigiKey Adapter — Own httpx Implementation, 2-Legged OAuth**
- **Decision:** Write a thin httpx-based DigiKey adapter directly against the REST API v4. Use 2-legged OAuth (client credentials) for Phase 1. Defer 3-legged flow to Phase 2.
- **Rationale:** Avoids GPL-3.0 dependency (`digikey-api`). 2-legged flow is simpler (no browser popup) and sufficient for parametric search. Token lifetime 10 min — proactive refresh when < 60s remaining.
- **Affects:** New DigiKey adapter in `core/sources.py`

### API & Communication Patterns

**ADR-05: Multi-Source Deduplication — Merge by MPN+Manufacturer**
- **Decision:** When the same MPN appears from multiple sources in unified search, merge into a single `PartResult` with aggregated `offers` from all sources.
- **Rationale:** Users want to see one row per part with all sourcing options, not duplicate rows. Matches the UX spec and the `PartResult.offers: list[Offer]` model.
- **Parametric data priority:** Nexar > DigiKey > Mouser > JLCPCB (based on data richness)
- **Merge key:** `(mpn.upper(), manufacturer.upper())` — case-insensitive
- **Affects:** `core/search.py` (SearchOrchestrator), ResultsModel

**ADR-06: Rate Limiting — Per-Source Token Bucket**
- **Decision:** Already established. Token bucket rate limiter per source. Exponential backoff with jitter on 429/503 (2s, 4s, 8s, max 30s).
- **Limits:** DigiKey 2 req/sec burst + 1,000/day counter. Mouser 1 req/sec (conservative). LCSC enrichment 1 req/sec. JLCPCB local DB: no limit.
- **Affects:** Infrastructure layer, all API-based adapters

### Frontend (GUI) Architecture

**ADR-07: QDockWidget Panel Migration — Phase 1**
- **Decision:** Migrate from QSplitter to QDockWidget panels in Phase 1 (BOM export milestone).
- **Rationale:** The BOM Export Window is new work that benefits from the dockable panel architecture. Multi-monitor support (float search on monitor 2) is a significant productivity gain for the target user. Qt handles all dock/undock/tab behavior natively.
- **Default layout:** Verify (left) | Search (center) | Detail (right) | Log (bottom) | Toolbar (top, fixed)
- **Layout persistence:** `QMainWindow.saveState()` / `restoreState()` between sessions. "View > Reset Layout" to restore defaults.
- **Migration approach:** Wrap existing panel widgets (VerifyPanel, SearchBar, ResultsTable, LogPanel) in QDockWidget containers. Panel code unchanged — only the container changes.
- **Affects:** `gui/main_window.py` (major refactor), all panel modules (minor — container change only)

### KiCad Integration

**ADR-08: Write-Back Strategy — Investigate First, Defer if Needed**
- **Decision:** Investigate what the existing kicad_bridge.py code can actually do with kicad-python v0.6.0 before making a fallback decision. If field write-back works: use it. If not: defer write-back to Phase 2 (wait for API expansion), and Phase 1 assigns to local state only (BOM export still works).
- **Rationale:** The existing code may already have working write-back. No point designing a fallback for a problem that may not exist. Direct .kicad_sch file manipulation is explicitly against project rules.
- **Affects:** `gui/kicad_bridge.py`, assign dialog behavior

### Standalone Mode

**ADR-09: Standalone BOM Import — Deferred to Phase 2**
- **Decision:** No standalone BOM file import in Phase 1. Connected mode (KiCad IPC API) is the primary and only input path for MVP.
- **Rationale:** PRD explicitly lists CSV BOM import as out of scope for MVP. The primary user (Sylvain) always has KiCad running. Phase 2 adds KiCad BOM XML/CSV import for standalone use.
- **Affects:** Scope control — no `core/bom_import.py` in Phase 1

### Decision Impact Analysis

**Implementation Sequence:**
1. ADR-07 (QDockWidget migration) — restructures the GUI shell, all new panels build on this
2. ADR-01 (Cache DB) — enables offline serving and repeat query optimization
3. ADR-02 (BOM export engine) — the Phase 1 deliverable
4. ADR-05 (Deduplication) — needed when Phase 2 adds multi-source search
5. ADR-04 (DigiKey adapter) — Phase 2
6. ADR-08 (Write-back investigation) — can happen in parallel with any step

**Cross-Component Dependencies:**
- BOM export (ADR-02) depends on the verification data model — components must carry MPN, manufacturer, supplier P/Ns, footprint, and package data
- Cache (ADR-01) sits between adapters and network — all adapters must call through it
- Deduplication (ADR-05) happens in the SearchOrchestrator after cache lookup, before model insertion
- QDockWidget migration (ADR-07) is a GUI-only change — does not affect core/ at all

## Implementation Patterns & Consistency Rules

### Already Established (from project-context.md)

These patterns are settled and documented — not repeated here:
- Python naming: snake_case files, PascalCase classes, UPPER_SNAKE_CASE constants, leading underscore for private
- Import ordering: stdlib, third-party, project (blank line separated)
- `from __future__ import annotations` in every file
- `@dataclass` for models, `Enum` for constrained sets
- `logging.getLogger(__name__)` — never `print()`
- `pathlib.Path` — never string concatenation for paths
- Core/GUI separation (zero PySide6 in `core/`)
- QThread worker pattern with Signal for results
- DataSource ABC adapter pattern
- Query transform 3-stage pipeline

### New Patterns for Phase 1 Work

#### Database & Cache Patterns

**SQLite connection management:**
```python
# Always use context manager for connections
with sqlite3.connect(self.db_path) as conn:
    conn.execute("PRAGMA journal_mode=WAL")  # WAL for concurrent reads
    cursor = conn.execute(query, params)
```
- One connection per operation (no long-lived connections across threads)
- WAL journal mode for the cache DB (allows concurrent reads from GUI + worker threads)
- Parameterized queries only — never f-strings or format() in SQL

**Cache module contract:**
```python
class QueryCache:
    def get(self, key: str) -> CacheEntry | None: ...
    def put(self, key: str, data: str, source: str, query_type: str, ttl: int) -> None: ...
    def invalidate(self, source: str | None = None) -> None: ...
    def is_expired(self, entry: CacheEntry) -> bool: ...
```
- Cache stores JSON strings (not pickled objects) — human-readable, debuggable
- `CacheEntry` is a `@dataclass` with `key, source, query_type, data, created_at, ttl_seconds`
- Adapters call `cache.get()` before API calls and `cache.put()` after

#### BOM Export Patterns

**Template dataclass:**
```python
@dataclass
class BOMTemplate:
    name: str                           # "PCBWay", "JLCPCB SMT", "Custom"
    columns: list[BOMColumn]            # ordered column definitions
    group_by: str                       # "mpn" — group components with same MPN
    dnp_handling: str                   # "include_marked" | "exclude"
    file_format: str                    # "xlsx" | "csv"

@dataclass
class BOMColumn:
    header: str                         # column header in output file
    field: str                          # source field name from component data
    transform: str | None               # optional transform: "package_extract", "smd_tht_detect"
```
- Preset templates: module-level constants `PCBWAY_TEMPLATE`, `JLCPCB_TEMPLATE`, etc.
- Custom templates: serialized as JSON, loaded from `~/.kipart-search/templates/*.json`
- The export engine (`core/bom_export.py`) takes a `BOMTemplate` + `list[ComponentData]` and returns bytes (Excel) or str (CSV)
- Export engine has zero GUI dependencies — testable standalone

#### QDockWidget Patterns

**Panel registration in main_window.py:**
```python
def _create_dock(self, title: str, widget: QWidget, area: Qt.DockWidgetArea) -> QDockWidget:
    dock = QDockWidget(title, self)
    dock.setWidget(widget)
    dock.setObjectName(f"dock_{title.lower().replace(' ', '_')}")  # for saveState
    self.addDockWidget(area, dock)
    return dock
```
- Every QDockWidget gets a unique `objectName` — required for `saveState()`/`restoreState()` to work
- Object names follow pattern: `dock_verify`, `dock_search`, `dock_detail`, `dock_log`
- View menu dynamically lists all docks with `dock.toggleViewAction()`
- Panel widgets (VerifyPanel, etc.) are unchanged — only wrapped in QDockWidget

**Layout save/restore:**
```python
# On close
settings = QSettings("kipart-search", "kipart-search")
settings.setValue("geometry", self.saveGeometry())
settings.setValue("windowState", self.saveState())

# On open
settings = QSettings("kipart-search", "kipart-search")
self.restoreGeometry(settings.value("geometry"))
self.restoreState(settings.value("windowState"))
```

#### Signal & Worker Patterns

**Signal naming convention for new workers:**
```python
class ExportWorker(QThread):
    progress = Signal(int, str)         # (percent, message)
    finished = Signal(str)              # file_path on success
    error = Signal(str)                 # error message

class CacheWorker(QThread):
    result_ready = Signal(str, list)    # (source, [PartResult])
    cache_hit = Signal(str)             # source name — for log
    error = Signal(str, str)            # (source, error_message)
```
- Signal names: `snake_case`, descriptive of what they carry
- Signals emit plain Python types only — never Qt objects, never dataclasses (serialize first if needed)
- Every worker has an `error` signal — GUI connects it to the log panel

#### Error Handling Patterns

**Adapter error handling:**
```python
def search(self, query, filters, limit):
    try:
        results = self._api_call(query, filters, limit)
        return results
    except httpx.TimeoutException:
        log.warning("DigiKey timeout for query: %s", query)
        return []  # empty results, not crash
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            log.warning("DigiKey rate limited, backing off")
            raise RateLimitError(source="digikey", retry_after=self._backoff())
        log.error("DigiKey HTTP %d: %s", e.response.status_code, e.response.text)
        return []
```
- Adapters never crash the app — return empty results on failure
- `RateLimitError` is a custom exception the orchestrator handles (backoff + retry)
- All other errors: log + return empty + GUI shows "Source X: error" in log panel
- GUI-level errors (write-back failed, export failed): `QMessageBox.warning()` with plain-language message

#### JSON & Serialization Patterns

- Config files (`config.json`, template JSON): `snake_case` keys
- Cache data: JSON strings via `json.dumps()`/`json.loads()` — not pickle
- No custom JSON encoders — dataclasses serialized via `dataclasses.asdict()`
- Dates in cache: Unix timestamps (float) — `time.time()`

### Anti-Patterns (What Agents Must NOT Do)

| Anti-Pattern | Correct Pattern |
|-------------|----------------|
| Import PySide6 in `core/` | Keep core GUI-free — import only in `gui/` |
| Use `print()` for debugging | Use `logging.getLogger(__name__)` |
| Hardcode file paths with backslashes | Use `pathlib.Path` |
| Store API keys in config.json | Use `keyring` with env var fallback |
| Block GUI thread with I/O | Use QThread worker + Signal |
| Use `pickle` for cache | Use `json.dumps()`/`json.loads()` |
| Modify .kicad_sch files directly | Use IPC API via kicad_bridge.py only |
| Create deeply nested widget hierarchies | QDockWidget with flat panel widget |
| Overwrite non-empty KiCad fields silently | Always confirm via preview dialog |
| Use f-strings in SQL queries | Use parameterized queries with `?` |

### Enforcement

- project-context.md is the authoritative source for agent rules — update it when patterns change
- This architecture document provides rationale and examples that project-context.md rules reference
- Pattern violations caught during code review — no automated linting for architectural rules in MVP

## Project Structure & Boundaries

### Complete Project Directory Structure

```
kipart-search/
├── pyproject.toml                      # Package metadata, deps, entry points (hatchling)
├── README.md
├── CLAUDE.md                           # Project instructions for AI agents
├── LICENSE                             # MIT
├── .gitignore
│
├── src/
│   └── kipart_search/
│       ├── __init__.py                 # Package version
│       ├── __main__.py                 # Entry point: python -m kipart_search
│       │
│       ├── core/                       # *** ZERO GUI DEPENDENCIES ***
│       │   ├── __init__.py
│       │   ├── models.py              # PartResult, ParametricValue, PriceBreak, Offer, ComponentData
│       │   ├── sources.py             # DataSource ABC + JLCPCB adapter (+ future DigiKey, Mouser, Nexar)
│       │   ├── search.py             # SearchOrchestrator — fan-out, collect, deduplicate
│       │   ├── cache.py              # QueryCache — SQLite cache with per-source TTL
│       │   ├── units.py              # Engineering value normalization, generate_query_variants()
│       │   ├── query_transform.py    # 3-stage query pipeline: prefix → EE units → SI normalization
│       │   ├── bom_export.py         # [NEW] BOM export engine: BOMTemplate + ComponentData → Excel/CSV
│       │   └── verify.py            # [FUTURE] BOM verification engine
│       │
│       ├── gui/                       # *** ALL PySide6 CODE ***
│       │   ├── __init__.py
│       │   ├── main_window.py        # QMainWindow + QDockWidget panel management + toolbar
│       │   ├── search_bar.py         # Search input, source selector, query preview
│       │   ├── results_table.py      # QTableView + ResultsModel + FilterProxyModel
│       │   ├── verify_panel.py       # Component table, health bar, status colors
│       │   ├── log_panel.py          # Timestamped activity log (QTextEdit, read-only)
│       │   ├── assign_dialog.py      # MPN assignment with preview, manual entry
│       │   ├── download_dialog.py    # JLCPCB database download with progress
│       │   ├── export_dialog.py      # [NEW] BOM export: template selector, preview, file output
│       │   ├── settings_dialog.py    # [FUTURE] Source preferences, API key management
│       │   ├── detail_panel.py       # [NEW] Selected part specs, pricing, datasheet, assign button
│       │   └── kicad_bridge.py       # KiCad IPC API: connect, scan, select, write-back
│       │
│       ├── vendored/                  # Third-party code with MIT attribution
│       │   ├── __init__.py
│       │   └── units.py             # KiBoM units.py (MIT, SchrodingersGat)
│       │
│       └── cli/                       # Optional CLI entry point
│           └── __init__.py
│
├── tests/                             # Mirrors src/kipart_search/ structure
│   ├── core/
│   │   ├── test_bom_export.py        # [NEW] Template mapping, grouping, package extraction
│   │   ├── test_cache.py             # [FUTURE] Cache get/put/invalidate/TTL
│   │   └── test_units.py             # [FUTURE] Unit normalization, query variants
│   └── conftest.py                   # Shared fixtures (small test DB, mock components)
│
├── docs/                              # Project documentation (if needed)
│
└── ExistingWorksOn/                   # Reference BOM templates from CMs
    ├── Sample_BOM_PCBWay.xlsx
    ├── Sample-BOM_JLCSMT.xlsx
    ├── pcb-bom-sample-file-newbury-electronics.xlsx
    ├── Sample-BOM-With-Supplier-Part-Number-Example.xlsx
    └── Sample-BOM-With-Supplier-Part-Number-Example-V2.xlsx
```

**Legend:** `[NEW]` = to be created in Phase 1. `[FUTURE]` = Phase 2+. Unmarked = already exists.

### Architectural Boundaries

**Layer 1: GUI (PySide6) — `gui/`**
- Depends on: `core/`, PySide6, kicad-python (optional)
- Exposes: QMainWindow, user interactions
- Forbidden: direct HTTP calls, direct SQLite access, direct file manipulation of KiCad files

**Layer 2: Core (zero GUI deps) — `core/`**
- Depends on: `vendored/`, stdlib, httpx
- Exposes: DataSource adapters, SearchOrchestrator, QueryCache, BOM export engine, models
- Forbidden: PySide6 imports, Qt types, GUI concepts

**Layer 3: Vendored — `vendored/`**
- Depends on: stdlib only
- Exposes: Unit normalization utilities
- Forbidden: any project imports

**Boundary enforcement:** If `from PySide6` appears in any `core/` file, the architecture is broken.

### Data Flow

```
[KiCad IPC API]                    [JLCPCB SQLite DB]     [DigiKey/Mouser/Nexar APIs]
       |                                  |                         |
       v                                  v                         v
  kicad_bridge.py              sources.py (JLCPCB adapter)   sources.py (API adapters)
       |                                  |                         |
       v                                  v                         v
  verify_panel.py              search.py (SearchOrchestrator)  cache.py (QueryCache)
       |                                  |                         |
       |                                  v                         |
       |                          results_table.py  <───────────────┘
       |                                  |
       v                                  v
  [Component selection]          assign_dialog.py
       |                                  |
       v                                  v
  [KiCad cross-probe]           kicad_bridge.py (write-back)
                                          |
                                          v
                                    bom_export.py
                                          |
                                          v
                                    [Excel/CSV file]
```

### FR-to-Module Mapping

| FR Category | Core Module | GUI Module |
|-------------|------------|------------|
| **Search & Discovery** (FR1-6) | `sources.py`, `search.py`, `query_transform.py`, `units.py` | `search_bar.py`, `results_table.py` |
| **JLCPCB Database** (FR7-9) | `sources.py` (JLCPCBSource) | `download_dialog.py` |
| **KiCad Integration** (FR10-15) | — | `kicad_bridge.py`, `verify_panel.py` |
| **Verification Dashboard** (FR16-20) | `models.py` (ComponentData) | `verify_panel.py` |
| **MPN Assignment** (FR21-23) | — | `assign_dialog.py`, `kicad_bridge.py` |
| **BOM Export** (FR24-29) | `bom_export.py` | `export_dialog.py` |
| **Caching** (FR30-31) | `cache.py` | — |
| **Configuration** (FR32-35) | — | `settings_dialog.py`, `main_window.py` |

### New Files for Phase 1

| File | Purpose | Dependencies |
|------|---------|-------------|
| `core/bom_export.py` | BOM export engine: template + components → file | `models.py`, `openpyxl`, stdlib `csv` |
| `gui/export_dialog.py` | Template selector, preview table, DNP options, export button | `core/bom_export.py`, PySide6 |
| `gui/detail_panel.py` | Selected part specs, pricing, datasheet link, assign button | `core/models.py`, PySide6 |
| `tests/core/test_bom_export.py` | Template mapping, grouping, package extraction tests | `core/bom_export.py`, pytest |

### User Data Files

```
~/.kipart-search/
├── config.json                # App settings (window state is in QSettings, not here)
├── parts-fts5.db             # JLCPCB database (downloaded artifact)
├── cache.db                  # [NEW] Query cache (user-generated, survives DB refresh)
├── templates/                # [NEW] Custom BOM templates (JSON)
│   └── my_cm_template.json
└── backups/                  # [FUTURE] KiCad write-back backups
    └── {project}/
        └── {YYYY-MM-DD_HHMM}/
```

## Architecture Validation Results

### Coherence Validation

**Decision Compatibility:**
All 9 ADRs are mutually compatible. Cache DB (ADR-01) is separate from JLCPCB DB — no conflict with database refresh. BOM export engine (ADR-02) operates on ComponentData from the verification model — clean data flow. DigiKey adapter (ADR-04) uses httpx (already a project dependency). QDockWidget migration (ADR-07) wraps existing panel code — no core/ changes needed. No version conflicts across the stack.

**Pattern Consistency:**
All naming follows project-context.md conventions. All new modules follow established core/GUI separation. Cache, export, and worker patterns use the same QThread + Signal approach. Error handling pattern (log + return empty + never crash) is consistent across all adapters.

**Structure Alignment:**
Project tree maps cleanly to the 4-layer architecture (GUI → Core → Adapters → Infrastructure). Every FR category has a clear module owner. Boundaries are enforceable.

**No contradictions found.**

### Requirements Coverage Validation

**Functional Requirements:**

| FR Range | Status | Architectural Support |
|----------|--------|----------------------|
| FR1-6 (Search) | Covered | sources.py, search.py, query_transform.py, results_table.py |
| FR7-9 (JLCPCB DB) | Covered | sources.py (JLCPCBSource), download_dialog.py |
| FR10-15 (KiCad) | Covered | kicad_bridge.py; write-back via ADR-08 |
| FR16-20 (Verification) | Covered | verify_panel.py, models.py |
| FR21-23 (Assignment) | Covered | assign_dialog.py |
| FR24-29 (BOM Export) | Covered | bom_export.py [NEW], export_dialog.py [NEW] |
| FR30-31 (Caching) | Covered | cache.py via ADR-01 |
| FR32-35 (Config) | Partial | FR32 deferred to Phase 2; FR33-35 covered |

**Non-Functional Requirements:** 15/15 covered. Performance (QThread workers, FTS5), security (keyring), integration (kicad_bridge isolation), reliability (error handling pattern), portability (PySide6 + pathlib).

**Coverage: 34/35 FRs (FR32 deferred). 15/15 NFRs.**

### Implementation Readiness Validation

**Decision Completeness:** All 9 ADRs documented with decision, rationale, and affected modules.

**Structure Completeness:** Complete project tree with [NEW] and [FUTURE] labels distinguishing Phase 1 from Phase 2.

**Pattern Completeness:** Cache contract, BOM template dataclass, QDockWidget registration, signal conventions, error handling, and JSON serialization all documented with code examples.

### Gap Analysis Results

**Critical Gaps:** None.

**Important Gaps (non-blocking):**
1. `openpyxl` not yet in pyproject.toml — must be added for BOM export
2. `ComponentData` dataclass may need enrichment (supplier P/Ns, package, SMD/THT type) for BOM export
3. `_extract_package_from_footprint()` in kicad_bridge.py may need to move to core/ for use by bom_export.py

**Nice-to-Have Gaps:**
1. No visual architecture diagram — ASCII data flow covers key relationships
2. No formal API contract docs for Phase 2 adapters — deferred

### Architecture Completeness Checklist

**Requirements Analysis**
- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed (low-medium)
- [x] Technical constraints identified (8 constraints)
- [x] Cross-cutting concerns mapped (7 concerns)

**Architectural Decisions**
- [x] Critical decisions documented with rationale (9 ADRs)
- [x] Technology stack fully specified
- [x] Integration patterns defined (adapter, mediator, cache-aside, model-view)
- [x] Performance considerations addressed (QThread, FTS5, WAL mode)

**Implementation Patterns**
- [x] Naming conventions established (via project-context.md)
- [x] Structure patterns defined (cache, export, dock, worker)
- [x] Communication patterns specified (Signal/Slot, JSON serialization)
- [x] Process patterns documented (error handling, rate limiting)

**Project Structure**
- [x] Complete directory structure defined
- [x] Component boundaries established (3 layers + vendored)
- [x] Integration points mapped (data flow diagram)
- [x] Requirements to structure mapping complete (FR-to-Module table)

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** High — brownfield project with working Tier 1 code, well-documented decisions, proven patterns from open-source references.

**Key Strengths:**
- Core/GUI separation already enforced in existing code
- DataSource ABC pattern proven with JLCPCB adapter — adding new sources is mechanical
- All new Phase 1 work (3 new files) builds on established patterns
- Declarative BOM template approach keeps export logic simple and testable

**Areas for Future Enhancement:**
- Phase 2: DigiKey/Mouser adapters, standalone BOM import, settings dialog, multi-source unified search
- Phase 3: Multi-CM template library, cost estimation, stock alerts, KiCad Plugin Manager distribution

### Implementation Handoff

**AI Agent Guidelines:**
- Follow all architectural decisions (ADR-01 through ADR-09) exactly as documented
- Use implementation patterns consistently — especially core/GUI separation and error handling
- Respect project structure boundaries — `from PySide6` in `core/` is forbidden
- Refer to project-context.md for coding rules, this document for architectural decisions

**Phase 1 Implementation Priority:**
1. Add `openpyxl` to pyproject.toml
2. Enrich `ComponentData` model for BOM export fields
3. Move `_extract_package_from_footprint()` to core/ if needed
4. Implement `core/bom_export.py` (BOMTemplate + preset templates)
5. Migrate main_window.py to QDockWidget panels
6. Implement `gui/export_dialog.py`
7. Implement `gui/detail_panel.py`
8. Implement `core/cache.py` (QueryCache with SQLite)
