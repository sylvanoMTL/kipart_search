# Brainstorming Context: Multi-API Search UX Rethink

**Date:** 2026-03-25
**Author:** Sylvain
**Purpose:** Pre-reading for a brainstorming session on how the search interface should work across multiple APIs (JLCPCB, DigiKey, Mouser, Nexar/Octopart, etc.)

## Problem Statement

The current UX spec (ux-design-specification.md) defines a **source selector dropdown + shared search box** with two modes (Specific Source vs. All Sources). As more APIs are added, this design may not scale well because each API has fundamentally different capabilities:

- **JLCPCB**: Offline FTS5 database, category-based, LCSC part numbers
- **DigiKey**: OAuth2, parametric filters by category (voltage, tolerance, temp coefficient)
- **Mouser**: Keyword-only, no parametric filtering
- **Nexar/Octopart**: GraphQL, aggregated across 100+ distributors, rich filters
- **Element14/Farnell**: API key, prefix-based parametric search
- **TME**: HMAC auth, specs data

A single search box + generic filter row may not expose each API's strengths.

## Sylvain's Proposed Direction (to explore)

### Core idea: Tabbed per-source search

1. **Main search box** at the top — user types or double-click populates it from component metadata (this part stays the same)
2. **Tabs below the search box**, one per configured API — visible/hidden based on which APIs the user has enabled
3. **Each tab has its own corrected/refined search UI** — the main query gets "translated" for that specific API, and the user can further adjust filters specific to that source
4. **Query translation engine** — the main search query is automatically adapted per API (e.g., "100nF 0805 MLCC" → JLCPCB FTS5 query vs. DigiKey parametric category + filters vs. Mouser keyword string)
5. Results per tab, with ability to compare across tabs

### Open Questions for Brainstorming

- Should results from all tabs be visible simultaneously (split view) or only the active tab?
- How to handle "All Sources" unified search — a separate tab, or a merged view above the tabs?
- Should the main search box show the "raw" user intent and each tab show the translated query (editable)?
- How does tab-per-source interact with the filter row (story 3-1)? Does each tab get its own dynamic filters?
- What happens when only 1 source is configured (typical for hobbyists with just JLCPCB)? Does the tab bar even appear?
- How to surface cross-source comparison (same MPN found in JLCPCB at $0.02 vs DigiKey at $0.15)?
- Mobile/small-screen: tabs take horizontal space. Dropdown fallback? Vertical tab bar?

## Current Implementation State

### What exists (implemented):
- `SearchBar` widget: source selector dropdown (QComboBox) + QLineEdit + symbol buttons + search button
- `query_transform.py`: source-agnostic query transformation (strip quotes, KiCad conventions → search terms)
- Dynamic filter row (story 3-1): manufacturer + package dropdowns populated from results
- Two-mode search architecture (story 3-2): "All Sources" vs specific source via dropdown
- Results table with Source column

### What would change:
- Source selector dropdown → tab bar (QTabWidget or QTabBar)
- Single filter row → per-tab filter panels
- `query_transform.py` → per-source transform methods
- Results table may need per-tab instances or a tab-aware model

### Reference: Current search flow
```
[Source: JLCPCB ▼] [Search: "100nF 0805"] [Ω] [±] [µ] [Search]
[Transformed: "100nF 0805 capacitor"]
[Filter: Manufacturer ▼] [Package ▼]
────────────────────────────────────
Results table (shared across all modes)
```

### Reference: Proposed search flow (rough sketch)
```
[Search: "100nF 0805"]   ← main search box (shared)
[Ω] [±] [µ] [Search]
┌─────────┬──────────┬─────────┬──────────┐
│ JLCPCB  │ DigiKey  │ Mouser  │ All      │  ← tabs (visible per config)
├─────────┴──────────┴─────────┴──────────┤
│ [Corrected: "100nF 0805 MLCC"]          │  ← per-tab translated query
│ [Category: Capacitors ▼] [Pkg: 0805 ▼]  │  ← per-tab specific filters
│ ──────────────────────────────────────── │
│ Results for this source                  │
└─────────────────────────────────────────┘
```

## Key References

- UX spec search section: `ux-design-specification.md` lines 210-268 (two-mode search architecture)
- Architecture: `architecture.md` (DataSource ABC pattern)
- Story 3-1: Dynamic filter row (implemented)
- Story 3-2: Two-mode search architecture (implemented)
- CLAUDE.md: Data source plugin pattern, per-source capabilities
