# Architecture — KiPart Search

**Generated:** 2026-03-17 | **Scan level:** Exhaustive

## Executive Summary

KiPart Search is a standalone PySide6 desktop application that provides parametric electronic component search and BOM verification with KiCad 9+ integration via IPC API. The architecture enforces strict core/GUI separation — all business logic runs without GUI dependencies and can be used by CLI tools or tests independently.

## Architecture Pattern

**Layered architecture with plugin-based data sources:**

```
┌─────────────────────────────────────────────────┐
│  GUI Layer (PySide6)                            │
│  main_window, search_bar, results_table,        │
│  verify_panel, log_panel, download_dialog,      │
│  assign_dialog, kicad_bridge                    │
├─────────────────────────────────────────────────┤
│  Core Layer (zero GUI dependencies)             │
│  SearchOrchestrator, DataSource ABC,            │
│  JLCPCBSource, QueryCache, units, models        │
├─────────────────────────────────────────────────┤
│  External Services                              │
│  JLCPCB SQLite DB, KiCad IPC API,              │
│  Future: DigiKey API, Mouser API, Nexar/Octopart│
└─────────────────────────────────────────────────┘
```

## Core Layer (`core/`)

### Data Models (`models.py`)

Central data structures — all plain dataclasses, no ORM:

- **`PartResult`** — Universal component representation returned by all data sources. Fields: mpn, manufacturer, description, package, category, datasheet_url, lifecycle, source, source_part_id, source_url, specs (list), price_breaks (list), stock, confidence.
- **`ParametricValue`** — A single parametric spec with raw_value, numeric_value, and unit. Attached to PartResult.specs.
- **`PriceBreak`** — quantity/unit_price/currency tuple.
- **`Confidence`** — Enum (GREEN/AMBER/RED) for verification status.
- **`ParamField`** + **`PARAM_TEMPLATES`** — Per-category parameter templates (capacitor, resistor, inductor) defining required/important/optional fields.

### Data Source Plugin Pattern (`sources.py`)

Abstract base class `DataSource` with:
- `search(query, filters, limit) -> list[PartResult]`
- `get_part(mpn, manufacturer) -> PartResult | None`
- `is_configured() -> bool`
- `name: str`, `needs_key: bool`, `key_fields: list[str]`

**Implemented adapters:**
- **`JLCPCBSource`** — Offline SQLite FTS5 database (~1M+ JLCPCB/LCSC parts). Zero API keys needed. Features: chunked download from GitHub Pages, update checking via HTTP headers, metadata tracking, natural sort collation. Handles short query terms (<3 chars) via `instr()` instead of FTS5 MATCH to work around UTF-8 bugs. Converts between ASCII/Unicode unit conventions (µ↔u, Ω↔ohm).

**Planned adapters** (from CLAUDE.md):
- DigiKey API v4 (OAuth2, 1,000 req/day free, parametric filters)
- Mouser API (API key, keyword/MPN only)
- Nexar/Octopart (OAuth2/GraphQL, expensive)
- Element14/Farnell, TME, TrustedParts

### Search Orchestrator (`search.py`)

`SearchOrchestrator` coordinates searches across all registered data sources:
- Generates unit-equivalent query variants (via `units.py`)
- Searches each variant across each source
- Deduplicates by (MPN, source) tuple
- `verify_mpn()` — looks up MPN across all sources for BOM verification

Currently synchronous (sequential per-source). TODO: parallel QThread workers.

### Unit Equivalence (`units.py`)

Parses engineering values ("100nF", "0.1µF", "1kΩ") and generates all reasonable equivalent representations for search. Uses SI prefix tables and preferred prefix tiers per unit family. The `generate_query_variants()` function replaces the value token in a query string with each equivalent, preserving surrounding text.

### Query Transformation (`query_transform.py`)

Pre-search pipeline ported from Sylvain's earlier prototype:
1. Preserves double-quoted segments unchanged
2. Expands KiCad footprint prefixes: `R_0805` → `0805 resistor`, `C_0402` → `0402 capacitor`
3. Normalises EE units: `uF` → `µF`, `kohm` → `kΩ`, `Ohm` → `Ω`
4. Inserts space between number and unit: `100nF` → `100 nF`

### Caching (`cache.py`)

`QueryCache` — SQLite-backed with per-source TTL:
- Pricing/stock: 4 hours
- Parametric data: 7 days
- Datasheets: indefinite (TTL=0)
- Keys: SHA-256 of `{source}:{query_type}:{query}`

## GUI Layer (`gui/`)

### Main Window (`main_window.py`)

Central orchestrator for the GUI:
- **Layout:** Toolbar (Scan, Download DB, Search toggle) → Horizontal splitter (BOM verification left, Search panel right) → Log panel bottom
- **Search panel** is collapsible — hidden by default, shown when user clicks "Search Parts" or double-clicks a BOM component
- **Workers:** `SearchWorker` (QThread for search) and `ScanWorker` (QThread for BOM scanning + MPN verification)
- **Flow:** Scan Project → connect to KiCad → read BOM → verify MPNs → display in VerifyPanel → double-click component → guided search → select result → AssignDialog → write back to KiCad

### Search Bar (`search_bar.py`)

Two-row input:
1. Raw query input + special symbol buttons (Ω, ±, µ) + Search button
2. Live-transformed query preview (editable) showing the result of `transform_query()`

The transformed query is what gets sent to the search engine.

### Results Table (`results_table.py`)

Columns: MPN, Manufacturer, Description, Package, Category, Source. Features:
- Manufacturer and Package dropdown filters
- Vertical splitter: table (top) + HTML detail view (bottom, collapsible)
- Sort-safe: stores original result index in UserRole data
- Context menu with "Assign to component"
- Double-click emits `part_selected` signal for assignment workflow

### Verification Panel (`verify_panel.py`)

BOM health dashboard:
- Summary bar with counts (total, valid MPN, needs attention, missing MPN)
- Health progress bar (percentage of verified components)
- Colour-coded table: Reference, Value, MPN, MPN Status, Footprint
- Click → emits `component_clicked` (highlights in KiCad via bridge)
- Double-click → emits `search_for_component` (opens guided search)
- Detail view showing all component fields

### KiCad Bridge (`kicad_bridge.py`)

**`BoardComponent`** dataclass: reference, value, footprint, mpn, datasheet, extra_fields. Features:
- `build_search_query()` — smart query builder: infers unit suffix from reference prefix (C→F, R→Ohm, L→H), extracts package from footprint (0805, SOIC-8, SOT-23), adds component type keyword
- Package extraction handles both passive sizes (imperial codes) and IC packages (SOT, SOIC, QFN, BGA, etc.)

**`KiCadBridge`** class:
- `connect()` — uses `kipy.KiCad()` to connect to running KiCad 9+ IPC API
- `get_components()` — reads all footprints from board, extracts reference, value, footprint, MPN (searching common field names), datasheet, extra fields
- `select_component()` — selects footprint in PCB editor → KiCad cross-probes to schematic
- `write_field()` — writes field values back to KiCad (safety: refuses to overwrite non-empty fields)
- `get_diagnostics()` — gathers platform, kipy version, env vars, socket paths for debugging

### Assign Dialog (`assign_dialog.py`)

Preview and confirm write-back:
- Shows table: Field | Current Value | New Value | Action
- Only writes to empty fields (non-empty fields show "Skip" with amber background)
- **Mismatch detection:** checks component type (reference prefix vs part category), package (footprint vs part package), and cross-type warnings
- Covers 12 component types with category keyword lists

### Download Dialog (`download_dialog.py`)

Database management:
- Background update check (`UpdateCheckWorker`) using HTTP Last-Modified header
- Background download (`DownloadWorker`) with progress bar
- Configurable database location with browse dialog
- Handles: no DB, update available, up to date states

### Log Panel (`log_panel.py`)

Timestamped activity log (monospace, read-only, 30-90px height range).

## State Management

The application uses Qt's signal/slot mechanism for state flow:

```
SearchBar.search_requested → MainWindow._on_search → SearchWorker (QThread)
    → SearchWorker.results_ready → ResultsTable.set_results

VerifyPanel.component_clicked → MainWindow._on_component_clicked → KiCadBridge.select_component
VerifyPanel.search_for_component → MainWindow._on_guided_search → SearchBar.set_query → search flow

ResultsTable.part_selected → MainWindow._on_part_selected → AssignDialog → KiCadBridge.write_field
```

State is held in:
- `MainWindow._orchestrator` — SearchOrchestrator with registered sources
- `MainWindow._bridge` — KiCadBridge (connection, footprint cache)
- `MainWindow._assign_target` — BoardComponent being assigned to
- `VerifyPanel._components` / `._mpn_statuses` — scan results
- `ResultsTable._results` — search results

## Vendored Code

`vendored/units.py` — KiBoM's value comparison module (MIT, Oliver Henry Walters). Handles locale-aware decimal parsing, SI prefix resolution, and component value comparison including mid-string units like "0R05" = 0.05Ω. Currently not integrated into the main search flow (the project uses its own `core/units.py` instead) but available for BOM grouping.

## Cross-Probe Chain

```
KiPart Search selects footprint in PCB
    → KiCad PCB editor highlights it
    → KiCad internal cross-probe highlights in schematic
```

No schematic API needed. PCB → schematic link is handled by KiCad internally.

## Key Design Decisions

1. **Standalone process** — runs as independent PySide6 app, NOT inside KiCad's wxPython interpreter
2. **Core/GUI separation** — `core/` has zero PySide6 imports; all Qt code lives in `gui/`
3. **JLCPCB as zero-config baseline** — offline SQLite FTS5 database, no API keys needed
4. **Graceful degradation** — KiCad features disabled when not connected, search works standalone
5. **Safety-first write-back** — refuses to overwrite non-empty fields, shows mismatch warnings
6. **Query transformation pipeline** — raw input → footprint expansion → unit normalisation → unit equivalence variants → FTS5 search
