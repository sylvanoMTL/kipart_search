# Development Guide — KiPart Search

**Generated:** 2026-03-17 | **Scan level:** Exhaustive

## Prerequisites

- **Python 3.10+** (uses `X | Y` union syntax, `match` not used but 3.10 is minimum)
- **pip** (for editable install)
- **Git** (for version control)
- **KiCad 9+** (optional, for IPC API integration — must have API enabled in Preferences)

## Environment Setup

### 1. Clone and install

```bash
git clone https://github.com/sylvanoMTL/kipart-search.git
cd kipart-search
python -m venv .env
# Windows:
.env\Scripts\activate
# Linux/macOS:
source .env/bin/activate

pip install -e .
```

This installs in editable mode with dependencies: `httpx`, `keyring`, `PySide6`.

### 2. Optional dependencies

```bash
# KiCad IPC API support (requires KiCad 9+)
pip install -e ".[kicad]"

# Development tools
pip install -e ".[dev]"
```

### 3. Run the application

```bash
python -m kipart_search
# Or after install:
kipart-search
```

## Project Structure

```
src/kipart_search/
├── __main__.py          # Entry point
├── core/                # Business logic (no GUI deps)
│   ├── models.py        # Data models
│   ├── sources.py       # DataSource ABC + JLCPCBSource
│   ├── search.py        # SearchOrchestrator
│   ├── units.py         # Engineering value equivalence
│   ├── query_transform.py  # Query normalisation
│   └── cache.py         # SQLite cache
├── gui/                 # PySide6 widgets
│   ├── main_window.py   # Main window + workers
│   ├── search_bar.py    # Search input
│   ├── results_table.py # Results display
│   ├── verify_panel.py  # BOM verification
│   ├── kicad_bridge.py  # KiCad IPC API
│   ├── log_panel.py     # Activity log
│   ├── download_dialog.py  # DB download
│   └── assign_dialog.py # Part assignment
├── vendored/            # Third-party code
│   └── units.py         # KiBoM units (MIT)
└── cli/                 # CLI (placeholder)
```

## Key Conventions

### Core/GUI separation

The `core/` package must **never** import PySide6 or any GUI module. It should be importable by:
- The GUI app
- The CLI
- Tests
- Future KiCad wxPython plugins

All PySide6 imports live in `gui/`.

### Adding a new data source

1. Create a new class in `core/sources.py` (or a new file) extending `DataSource`
2. Implement `search()`, `get_part()`, `is_configured()`
3. Set `name`, `needs_key`, `key_fields`
4. Register it in `MainWindow.__init__` via `self._orchestrator.add_source()`

### Type hints

Used throughout but not over-annotated. `from __future__ import annotations` is standard in all modules for PEP 604 union syntax (`X | Y`).

### Background work

All network I/O and heavy computation runs in `QThread` workers:
- `SearchWorker` for searches
- `ScanWorker` for BOM scanning
- `DownloadWorker` for database download
- `UpdateCheckWorker` for update checks

Workers communicate via Qt signals (`results_ready`, `error`, `log`, `progress`).

## Build & Package

```bash
# Build wheel
pip install build
python -m build

# The wheel is in dist/
```

Build backend is **hatchling** (configured in `pyproject.toml`).

## Testing

```bash
pip install -e ".[dev]"
pytest
```

Test suite is currently empty (`tests/__init__.py` only). Testing approach: start with manual testing, add pytest later.

## Database Management

The JLCPCB/LCSC offline database is stored at `~/.kipart-search/jlcpcb/parts-fts5.db` by default.

- **Download:** Use the GUI "Download Database" button, or call `JLCPCBSource.download_database()` programmatically
- **Update check:** `JLCPCBSource.check_for_update()` compares local metadata with remote HTTP headers
- **Metadata:** Stored in `~/.kipart-search/jlcpcb/db_meta.json` (chunk count, download date, remote build date)
- **Size:** ~500+ MB (SQLite FTS5 database)

## KiCad Integration

For KiCad features to work:
1. KiCad 9+ must be running
2. A `.kicad_pcb` board must be open in the PCB editor
3. IPC API must be enabled in Preferences → API
4. KiCad must be restarted after enabling the API

The app auto-discovers the KiCad API socket. Environment variables `KICAD_API_SOCKET` and `KICAD_API_TOKEN` are checked first.

## Common Development Tasks

### Adding a GUI widget

1. Create new file in `gui/`
2. Subclass `QWidget` or `QDialog`
3. Connect signals to `MainWindow` slots
4. Import and instantiate in `main_window.py`

### Modifying search behaviour

1. Query transformation: edit `core/query_transform.py`
2. Unit equivalence: edit `core/units.py`
3. Search orchestration: edit `core/search.py`
4. Source-specific search: edit the relevant source in `core/sources.py`

### Adding MPN field name variants

Add to `MPN_FIELD_NAMES` set in `gui/kicad_bridge.py`.

### Adding component type recognition

Add to `_REF_PREFIX_MAP` in `gui/kicad_bridge.py` and `_REF_CATEGORY_HINTS` in `gui/assign_dialog.py`.
