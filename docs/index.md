# KiPart Search — Documentation Index

**Generated:** 2026-03-17 | **Scan level:** Exhaustive | **Mode:** Initial scan

## Project Overview

- **Type:** Monolith desktop application
- **Primary Language:** Python 3.10+
- **Architecture:** Layered — Core/GUI separation with data source plugin pattern
- **GUI Framework:** PySide6 (Qt6)
- **KiCad Integration:** IPC API via kicad-python (KiCad 9+, optional)

## Quick Reference

- **Entry Point:** `python -m kipart_search` → `src/kipart_search/__main__.py`
- **Build System:** Hatchling (`pyproject.toml`)
- **Dependencies:** httpx, keyring, PySide6 (core) + kicad-python (optional)
- **License:** MIT
- **Author:** Sylvain Boyer (MecaFrog)
- **Version:** 0.1.0

## Generated Documentation

- [Project Overview](./project-overview.md) — Purpose, tech stack, architecture summary, current status
- [Architecture](./architecture.md) — Full architecture: layers, data models, services, state management, design decisions
- [Source Tree Analysis](./source-tree-analysis.md) — Annotated directory tree, critical folders, entry points, file statistics
- [Component Inventory](./component-inventory.md) — All GUI widgets, core classes, utilities, signals, constants
- [Development Guide](./development-guide.md) — Setup, conventions, build, testing, common tasks

## Existing Documentation

- [CLAUDE.md](../CLAUDE.md) — Project identity, architecture decisions, data source details, coding style (primary project reference)
- [README.md](../README.md) — Minimal install instructions

## Existing Planning Artifacts

- [Product Brief](../_bmad-output/planning-artifacts/product-brief-kipart-search-2026-03-15.md) — Project vision and scope
- [PRD](../_bmad-output/planning-artifacts/prd.md) — Product Requirements Document
- [PRD Validation Report](../_bmad-output/planning-artifacts/prd-validation-report.md) — PRD review findings
- [Architecture (planning)](../_bmad-output/planning-artifacts/architecture.md) — Architecture design spec
- [UX Design Specification](../_bmad-output/planning-artifacts/ux-design-specification.md) — UX patterns and design spec
- [Technical Research](../_bmad-output/planning-artifacts/research/technical-kipart-search-stack-research-2026-03-17.md) — Stack research report

## Research & Reference Materials

- [Open-Source Landscape Research](../ExistingWorksOn/compass_artifact_wf-af099856-fd25-4fc1-bcd0-66648f118144_text_markdown.md) — Comprehensive survey of existing tools, APIs, and code to reuse
- [Sample BOM files](../ExistingWorksOn/) — JLCPCB, PCBWay, and supplier BOM samples (`.xlsx`)

## Getting Started

```bash
# Clone, install, and run
git clone https://github.com/sylvanoMTL/kipart-search.git
cd kipart-search
python -m venv .env
.env\Scripts\activate          # Windows
pip install -e .
python -m kipart_search

# First run: click "Download Database" to get the JLCPCB parts database (~500MB)
```

For KiCad integration: install `pip install -e ".[kicad]"` and ensure KiCad 9+ is running with IPC API enabled.
