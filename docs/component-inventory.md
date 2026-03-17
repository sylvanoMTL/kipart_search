# Component Inventory — KiPart Search

**Generated:** 2026-03-17 | **Scan level:** Exhaustive

## GUI Components (PySide6 Widgets)

### Layout Components

| Component | File | Type | Purpose |
|-----------|------|------|---------|
| `MainWindow` | `gui/main_window.py` | `QMainWindow` | Top-level window: toolbar, horizontal splitter (BOM/Search), log panel, status bar |
| Root Splitter | `gui/main_window.py` | `QSplitter(Horizontal)` | BOM verification (left, 60%) / Search panel (right, 40%) |

### Form / Input Components

| Component | File | Type | Purpose |
|-----------|------|------|---------|
| `SearchBar` | `gui/search_bar.py` | `QWidget` | Two-row: raw input + symbol buttons + search btn / transformed preview |
| Symbol buttons | `gui/search_bar.py` | `QPushButton` | Insert Ω, ±, µ at cursor |
| Query preview | `gui/search_bar.py` | `QLineEdit` | Editable transformed query (italic, blue background) |

### Display Components

| Component | File | Type | Purpose |
|-----------|------|------|---------|
| `ResultsTable` | `gui/results_table.py` | `QWidget` | Search results: filter dropdowns + sortable table + HTML detail browser |
| `VerifyPanel` | `gui/verify_panel.py` | `QWidget` | BOM dashboard: summary bar + health bar + colour-coded table + detail browser |
| `LogPanel` | `gui/log_panel.py` | `QWidget` | Timestamped monospace activity log |
| Detail browsers | multiple | `QTextBrowser` | HTML rendering of part details (specs, pricing, fields) |
| Status bar | `gui/main_window.py` | `QStatusBar` | DB status, KiCad connection, mode badge |

### Dialog Components

| Component | File | Type | Purpose |
|-----------|------|------|---------|
| `DownloadDialog` | `gui/download_dialog.py` | `QDialog` | DB download: location picker + update check + progress bar |
| `AssignDialog` | `gui/assign_dialog.py` | `QDialog` | Preview write-back: field comparison table + mismatch warnings |

### Background Workers (QThread)

| Worker | File | Signals | Purpose |
|--------|------|---------|---------|
| `SearchWorker` | `gui/main_window.py` | `results_ready`, `error`, `log` | Background search across all sources |
| `ScanWorker` | `gui/main_window.py` | `scan_complete`, `error`, `log` | Read KiCad BOM + verify MPNs |
| `DownloadWorker` | `gui/download_dialog.py` | `progress`, `finished`, `error` | Download JLCPCB database chunks |
| `UpdateCheckWorker` | `gui/download_dialog.py` | `result` | Check if DB update is available |

## Core Components (Non-GUI)

### Data Models

| Class | File | Purpose |
|-------|------|---------|
| `PartResult` | `core/models.py` | Universal component search result (17 fields) |
| `ParametricValue` | `core/models.py` | Single parametric spec (name, raw_value, numeric, unit) |
| `PriceBreak` | `core/models.py` | Price tier (quantity, unit_price, currency) |
| `Confidence` | `core/models.py` | Enum: GREEN, AMBER, RED |
| `ParamField` | `core/models.py` | Parameter template field (name, priority, description) |
| `EngineeringValue` | `core/units.py` | Parsed engineering value (number, prefix, base_unit, base_value) |
| `BoardComponent` | `gui/kicad_bridge.py` | KiCad component (reference, value, footprint, mpn, datasheet, extra_fields) |

### Services / Adapters

| Class | File | Purpose |
|-------|------|---------|
| `DataSource` (ABC) | `core/sources.py` | Abstract base for all distributor adapters |
| `JLCPCBSource` | `core/sources.py` | SQLite FTS5 search + chunked DB download + update check |
| `SearchOrchestrator` | `core/search.py` | Multi-source search coordinator + MPN verification |
| `QueryCache` | `core/cache.py` | SQLite-backed cache with per-type TTL |
| `KiCadBridge` | `gui/kicad_bridge.py` | IPC API connection, component read, select, field write |

### Utility Functions

| Function | File | Purpose |
|----------|------|---------|
| `transform_query()` | `core/query_transform.py` | EE unit normalisation + footprint expansion |
| `strip_quotes()` | `core/query_transform.py` | Remove protective quotes before API calls |
| `parse_value()` | `core/units.py` | Parse "100nF" → EngineeringValue |
| `equivalent_values()` | `core/units.py` | Generate all SI prefix variants |
| `generate_query_variants()` | `core/units.py` | Replace value token in query with equivalents |
| `_extract_ref_prefix()` | `gui/kicad_bridge.py` | "C3" → "C", "SW2" → "SW" |
| `_extract_package_from_footprint()` | `gui/kicad_bridge.py` | "Capacitor_SMD:C_0805_2012Metric" → "0805" |
| `_infer_value_with_unit()` | `gui/kicad_bridge.py` | "10u" + "C" → "10uF" |
| `_check_mismatches()` | `gui/assign_dialog.py` | Detect type/package mismatches before assignment |
| `_natural_sort_collation()` | `core/sources.py` | SQLite collation for C1 < C2 < C10 ordering |

## Signal/Slot Connections

| Signal | Source | Slot | Target |
|--------|--------|------|--------|
| `search_requested(str)` | SearchBar | `_on_search` | MainWindow |
| `results_ready(list)` | SearchWorker | `_on_results` | MainWindow |
| `part_selected(int)` | ResultsTable | `_on_part_selected` | MainWindow |
| `component_clicked(str)` | VerifyPanel | `_on_component_clicked` | MainWindow |
| `search_for_component(int)` | VerifyPanel | `_on_guided_search` | MainWindow |
| `scan_complete(list, dict)` | ScanWorker | `_on_scan_complete` | MainWindow |
| `download_complete(str)` | DownloadDialog | `_on_db_downloaded` | MainWindow |

## Configuration Constants

| Constant | File | Value | Purpose |
|----------|------|-------|---------|
| `JLCPCB_COLUMNS` | `core/sources.py` | 10 column names | Database schema mapping |
| `MPN_FIELD_NAMES` | `gui/kicad_bridge.py` | 8 variants | Common KiCad MPN field names |
| `PARAM_TEMPLATES` | `core/models.py` | 3 categories | Per-category parameter definitions |
| `_REF_PREFIX_MAP` | `gui/kicad_bridge.py` | 10 entries | Reference prefix → component type |
| `_REF_CATEGORY_HINTS` | `gui/assign_dialog.py` | 12 entries | Type → category keyword lists |
| `ASSIGNABLE_FIELDS` | `gui/assign_dialog.py` | 4 fields | Fields that can be written to KiCad |
| `TTL_PRICING/PARAMETRIC/DATASHEET` | `core/cache.py` | 4h/7d/∞ | Cache expiry times |
