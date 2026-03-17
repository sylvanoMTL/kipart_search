# KiPart Search — Project Overview

**Generated:** 2026-03-17 | **Scan level:** Exhaustive | **Version:** 0.1.0

## Purpose

KiPart Search is a standalone PySide6 desktop application for **parametric electronic component discovery** and **BOM verification** with KiCad integration.

Two main functions:

1. **Parametric component discovery** — Start from specs (voltage, package, capacitance...) and discover MPNs across distributor databases. The opposite of BOM costing tools like KiCost.
2. **BOM verification / design audit** — Connect to a running KiCad instance, read the board BOM, and verify that MPNs exist in distributor databases. Flag missing fields, unresolved values, and package mismatches.

## Quick Reference

- **Type:** Monolith desktop application
- **Primary Language:** Python 3.10+
- **GUI Framework:** PySide6 (Qt6)
- **Architecture Pattern:** Core/GUI separation with data source plugin pattern
- **Entry Point:** `python -m kipart_search` → `src/kipart_search/__main__.py`
- **Build System:** Hatchling (`pyproject.toml`)
- **License:** MIT
- **Author:** Sylvain Boyer (MecaFrog)

## Tech Stack Summary

| Category | Technology | Version | Notes |
|----------|-----------|---------|-------|
| Language | Python | >=3.10 | Type hints, dataclasses, `from __future__ import annotations` |
| GUI | PySide6 | 6.10.2 | Qt6 bindings, standalone desktop app |
| HTTP Client | httpx | 0.28.1 | Async-capable, used for API calls & DB download |
| Credentials | keyring | 25.7.0 | OS-native secret storage |
| KiCad Integration | kicad-python (kipy) | 0.5.0 | Optional, IPC API for KiCad 9+ |
| Spreadsheets | openpyxl | 3.1.5 | BOM file reading |
| Build | hatchling | — | PEP 517 build backend |
| Testing | pytest | — | Optional dev dependency |

## Architecture Summary

The codebase follows strict **core/GUI separation**:

- `core/` — Zero GUI dependencies. Contains data models, search orchestrator, data source adapters, caching, and unit normalisation. Can be imported by CLI, tests, or future plugins.
- `gui/` — PySide6 widgets. Main window, search bar, results table, verification panel, KiCad bridge, download dialog, assign dialog.
- `vendored/` — Third-party code with attribution (KiBoM units.py).
- `cli/` — Placeholder for optional CLI interface.

## Current Status

- Core search engine functional with JLCPCB/LCSC offline database
- PySide6 GUI implemented: search bar, results table, verification panel, log panel
- KiCad IPC API bridge implemented (connect, read BOM, select/highlight, write fields)
- Database download with chunked transfer and update checking
- Unit equivalence search (0.1µF → 100nF → 100000pF)
- Query transformation (EE unit normalisation, footprint expansion)
- Assign dialog with mismatch detection (component type, package)
- SQLite cache with per-source TTL

## Links to Detailed Documentation

- [Architecture](./architecture.md)
- [Source Tree Analysis](./source-tree-analysis.md)
- [Component Inventory](./component-inventory.md)
- [Development Guide](./development-guide.md)

## Existing Planning Artifacts

- [PRD](../_bmad-output/planning-artifacts/prd.md)
- [Architecture (planning)](../_bmad-output/planning-artifacts/architecture.md)
- [UX Design Specification](../_bmad-output/planning-artifacts/ux-design-specification.md)
- [Product Brief](../_bmad-output/planning-artifacts/product-brief-kipart-search-2026-03-15.md)
- [PRD Validation Report](../_bmad-output/planning-artifacts/prd-validation-report.md)
- [Technical Research](../_bmad-output/planning-artifacts/research/technical-kipart-search-stack-research-2026-03-17.md)
- [Open-Source Landscape Research](../ExistingWorksOn/compass_artifact_wf-af099856-fd25-4fc1-bcd0-66648f118144_text_markdown.md)
