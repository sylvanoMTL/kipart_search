# Source Tree Analysis

**Generated:** 2026-03-17 | **Scan level:** Exhaustive

## Directory Structure

```
kipart-search/
├── CLAUDE.md                          # Project instructions & architecture decisions
├── README.md                          # Minimal install instructions
├── pyproject.toml                     # Build config (hatchling), dependencies, entry point
├── .gitignore                         # Python, venv, IDE, DB files
│
├── src/
│   └── kipart_search/
│       ├── __init__.py                # Package root, __version__ = "0.1.0"
│       ├── __main__.py                # ★ Entry point: python -m kipart_search
│       │
│       ├── core/                      # ★ Zero GUI dependencies
│       │   ├── __init__.py
│       │   ├── models.py             # PartResult, ParametricValue, PriceBreak, ParamField, PARAM_TEMPLATES
│       │   ├── sources.py            # DataSource ABC + JLCPCBSource (SQLite FTS5, chunked download)
│       │   ├── search.py             # SearchOrchestrator (multi-source, dedup, MPN verification)
│       │   ├── units.py              # Engineering value parsing & equivalent generation
│       │   ├── query_transform.py    # Pre-search EE unit normalisation & footprint expansion
│       │   └── cache.py              # QueryCache (SQLite-backed, per-source TTL)
│       │
│       ├── gui/                       # ★ PySide6 standalone app
│       │   ├── __init__.py
│       │   ├── main_window.py        # MainWindow, SearchWorker, ScanWorker, run_app()
│       │   ├── search_bar.py         # SearchBar (input + transform preview + symbol buttons)
│       │   ├── results_table.py      # ResultsTable (filters, detail view, context menu)
│       │   ├── verify_panel.py       # VerifyPanel (BOM health dashboard, colour-coded status)
│       │   ├── kicad_bridge.py       # KiCadBridge + BoardComponent (IPC API, field write-back)
│       │   ├── log_panel.py          # LogPanel (timestamped activity log)
│       │   ├── download_dialog.py    # DownloadDialog (DB download with progress + update check)
│       │   └── assign_dialog.py      # AssignDialog (preview + mismatch detection before write-back)
│       │
│       ├── vendored/                  # Third-party code with attribution
│       │   ├── __init__.py
│       │   └── units.py              # KiBoM units.py (MIT, value comparison & normalisation)
│       │
│       └── cli/                       # Optional CLI (placeholder)
│           └── __init__.py
│
├── tests/
│   └── __init__.py                    # Test package (empty, pytest not yet configured)
│
├── ExistingWorksOn/                   # Reference materials
│   ├── compass_artifact_*.md          # Open-source landscape research report
│   ├── Sample-BOM-*.xlsx (x2)         # Sample BOM files with supplier part numbers
│   ├── Sample-BOM_JLCSMT.xlsx        # Sample JLCPCB SMT BOM
│   └── Sample_BOM_PCBWay.xlsx         # Sample PCBWay BOM
│
├── _bmad-output/                      # BMAD workflow outputs
│   ├── project-context.md
│   ├── brainstorming/
│   └── planning-artifacts/
│       ├── prd.md
│       ├── prd-validation-report.md
│       ├── architecture.md
│       ├── ux-design-specification.md
│       ├── product-brief-*.md
│       └── research/
│
├── _bmad/                             # BMAD method installation (v6.1.0)
├── .claude/                           # Claude Code skills & config
├── .env/                              # Python virtual environment (gitignored)
└── docs/                              # ★ Generated project documentation (this folder)
```

## Critical Folders

| Folder | Purpose | Key Files |
|--------|---------|-----------|
| `src/kipart_search/core/` | Business logic, zero GUI deps | `models.py`, `sources.py`, `search.py`, `units.py` |
| `src/kipart_search/gui/` | PySide6 UI layer | `main_window.py`, `kicad_bridge.py`, `verify_panel.py` |
| `src/kipart_search/vendored/` | Vendored third-party code | `units.py` (from KiBoM) |
| `tests/` | Test suite (empty placeholder) | — |
| `_bmad-output/planning-artifacts/` | Design specs & research | PRD, architecture, UX spec |

## Entry Points

| Entry Point | Command | Module |
|-------------|---------|--------|
| GUI app | `python -m kipart_search` | `__main__.py` → `gui.main_window.run_app()` |
| GUI app (installed) | `kipart-search` | Same via `[project.scripts]` in pyproject.toml |

## Source File Statistics

| Package | Files | Total Lines (approx) |
|---------|-------|---------------------|
| `core/` | 6 source files | ~610 lines |
| `gui/` | 8 source files | ~1,070 lines |
| `vendored/` | 1 source file | ~185 lines |
| `cli/` | 1 file (placeholder) | 1 line |
| **Total** | **16 source files** | **~1,870 lines** |
