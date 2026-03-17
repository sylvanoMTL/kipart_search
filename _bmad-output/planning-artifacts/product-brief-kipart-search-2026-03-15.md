---
stepsCompleted: [1, 2, 3, 4, 5, 6]
status: complete
inputDocuments: ['brainstorming/brainstorming-session-2026-03-14-1730.md', 'CLAUDE.md', 'ExistingWorksOn/compass_artifact_wf-af099856-fd25-4fc1-bcd0-66648f118144_text_markdown.md']
date: 2026-03-15
author: Sylvain
---

# Product Brief: KiPart Search

## Executive Summary

KiPart Search is a free, open-source desktop tool that helps KiCad users build production-ready BOMs by combining parametric component discovery and BOM verification in a single workflow. It connects to a running KiCad instance via the IPC API (KiCad 9+) to scan, search, assign, and verify component data — eliminating the manual back-and-forth between KiCad and distributor websites. Used by designers to build and verify their own BOMs, and by assemblers to audit client BOMs before quoting.

---

## Core Vision

### Problem Statement

Electronic designers using KiCad must manually search distributor websites (DigiKey, LCSC, Mouser) one component at a time to find manufacturer part numbers, then copy-paste MPNs, datasheets, and specifications into schematic fields by hand. For a typical board with 50-200 components, this process is tedious, error-prone, and time-consuming. The result is often an incomplete BOM — missing MPNs, broken datasheet links, mismatched footprints, and generic values like "100nF" with no specific part assigned.

This isn't a matter of discipline — it's a workflow gap. Until KiCad 9 introduced the IPC API, no external tool could programmatically read or write component fields. The data exists in distributor databases; the fields exist in KiCad schematics. There was simply no bridge between them.

### Problem Impact

An incomplete or incorrect BOM blocks production. Missing MPNs mean the assembler cannot order parts. Wrong footprints mean boards come back with components that don't fit. Broken datasheet links mean specifications cannot be verified during review. For small businesses and hobbyists — who lack dedicated component engineering staff — these errors are discovered late, causing delays, respins, and wasted money.

Contract manufacturers receiving incomplete BOMs spend hours on cleanup before they can even quote, creating friction and delays across the supply chain.

### Why Existing Solutions Fall Short

No existing open-source tool combines component discovery and BOM verification:

- **KiCost** prices known MPNs but cannot discover new ones
- **kicad-jlcpcb-tools** places JLCPCB parts but doesn't verify or audit the BOM
- **JLCParts** offers parametric search but is web-only with no KiCad integration
- **Ki-nTree** creates library parts but doesn't audit existing designs

Engineers are left stitching together multiple tools or doing everything manually.

### Proposed Solution

KiPart Search bridges the gap between distributor databases and KiCad's component fields, keeping engineers in their design flow instead of forcing context switches to browser tabs. It provides a two-function workflow in one desktop app:

1. **Parametric discovery** — start from specs (capacitance, voltage, package) and find MPNs across free data sources (JLCPCB offline database, DigiKey API, Mouser API). No paid subscriptions required for core functionality.

2. **BOM verification** — scan a KiCad project, flag every component missing an MPN, verify existing MPNs against distributor databases, detect footprint mismatches, and guide the user through fixing each issue.

Connected to KiCad via the IPC API, the tool reads component data directly from the PCB editor, highlights components on click, and writes back verified MPNs — all without leaving the app.

### Key Differentiators

- **Two-way workflow**: discover parts you don't have AND verify parts you do — no other tool does both
- **Live KiCad integration**: reads and writes component fields via IPC API, with click-to-highlight cross-probe
- **Zero-cost baseline**: works offline with the JLCPCB database (~1M parts), no API keys needed
- **Works in 5 minutes**: zero-config with JLCPCB offline database — no API keys, no accounts, no setup
- **Safety-first write-back**: never overwrites existing fields, preview before every change
- **Made possible by KiCad 9**: the IPC API (new in KiCad 9.0) enables external tools to interact with the PCB editor programmatically for the first time

---

## Target Users

### Primary Users

**Small Business Hardware Designer (Sylvain archetype)**

- **Context:** Runs a small hardware business, designs ~2 PCBs/month with ~70 components each. Uses KiCad for schematic and PCB design. Orders components from Mouser and DigiKey, subcontracts assembly and manufacturing to CMs. Receives BOM templates from subcontractors that must be filled with correct MPNs.
- **Current workflow:** Designs circuits with generic values (100nF, 10k), then spends hours manually searching distributor websites to find and assign MPNs. Copies data by hand into KiCad fields. Fills CM-provided BOM templates manually from KiCad data.
- **Pain points:** Manual back-and-forth between KiCad and distributor websites for ~140 components/month. Risk of errors in MPNs, footprints, and datasheets that only surface when the CM flags them or boards come back wrong. BOM is critical because it goes to subcontractors — mistakes cost money and time.
- **Success looks like:** Open KiPart Search, scan the project, see what's missing, search and assign MPNs without leaving the app. Confident that every component has a verified MPN, matching footprint, and valid datasheet before sending to the CM.

**Hobbyist / Maker**

- **Context:** Designs 2-5 boards/year, typically for personal projects or small-run open-source hardware. Less experienced with component selection. Often uses JLCPCB assembly service.
- **Current workflow:** Picks components from tutorials or forum recommendations. Uses generic symbols. Struggles to find correct MPNs when it's time to order, especially matching JLCPCB's parts library.
- **Pain points:** Doesn't know where to start for MPN selection. Overwhelmed by distributor websites. Picks wrong package sizes. Wants it to "just work" with zero setup.
- **Success looks like:** Download the tool, it works immediately with the JLCPCB offline database. Double-click a component, get suggestions, assign one. Done in minutes, not hours.

### Secondary Users

**Contract Manufacturer / Assembly House**

- **Context:** Receives KiCad projects and BOMs from clients. Needs complete, correct BOMs to quote and build. Provides BOM templates to clients to fill in.
- **Current workflow:** Manually reviews client BOMs for completeness. Flags missing MPNs, wrong footprints, discontinued parts. Sends corrections back to the designer. Multiple rounds of back-and-forth.
- **Pain points:** Clients send incomplete BOMs. Time wasted on cleanup before quoting. Cannot start procurement until BOM is correct.
- **Benefit from KiPart Search:** If designers use the tool, CMs receive cleaner BOMs with fewer issues. In the future, CMs could run the verification scan themselves on received projects and export a report.

### User Journey

**Designer (Primary) Journey:**

1. **Discovery:** Finds KiPart Search via KiCad forums, Reddit, or GitHub
2. **Onboarding:** Downloads, installs, launches. Downloads JLCPCB database on first run (~5 min). No API keys needed.
3. **First use:** Opens KiCad project, clicks "Scan Project" — sees a dashboard of all components colour-coded green/amber/red. Immediately sees which components need attention.
4. **Aha moment:** Double-clicks a red component, search opens pre-filled with the component's value and package. Finds an MPN in seconds, assigns it with one click. "This is exactly what I needed."
5. **Core workflow:** Before sending BOM to CM, runs a full scan. Fixes all issues. Exports a clean, verified BOM.
6. **Long-term:** Becomes part of the standard pre-production checklist. Optionally adds DigiKey/Mouser API keys for richer data.

---

## Success Metrics

### User Success

- **BOM completion time**: Go from finished PCB layout to production-ready BOM in under 30 minutes for a 70-component board (vs ~3 hours manual)
- **BOM accuracy**: Every component has a verified MPN, correct footprint match, and valid datasheet before sending to CM
- **Zero CM bounce-backs**: No rounds of "your BOM has these issues" from the subcontractor
- **Tool becomes routine**: Used on every board before production — part of the standard pre-production checklist

### Business Objectives

This is a personal/open-source project, not a commercial product. Business objectives are:

- **Save the author's time**: Recover ~5 hours/month currently spent on manual BOM work (2 boards x ~70 components)
- **Reduce production errors**: Eliminate BOM-related respins, wrong parts, and CM back-and-forth
- **Dogfooding as validation**: If the author uses it on every board, the tool works. If not, something is wrong.

### Key Performance Indicators

| KPI | Target | How to measure |
|-----|--------|---------------|
| BOM completion time | < 30 min for 70-component board | Self-timed on real projects |
| MPN coverage after scan+assign | 100% of components have MPNs | Verification dashboard shows all green |
| CM rejection rate | 0 BOM-related issues per board | Feedback from subcontractor |
| Personal adoption | Used on every board (2/month) | If you skip it, ask why |
| Search success rate | > 90% of components found in database | Dashboard stats after scan |

---

## MVP Scope

### Core Features (Tier 1 — Already Built)

- JLCPCB offline database (~1M parts) with FTS5 search and auto-download
- PySide6 GUI: search bar with query transformation, results table with filters and detail panel
- Smart query builder (infer units from reference prefix, extract package from footprint)
- KiCad IPC API: scan project, read component fields, highlight/select on click
- Verification dashboard: green/amber/red per component, detail view
- Guided search: double-click missing MPN → pre-filled search
- Write-back: preview dialog, never overwrite non-empty, mismatch warnings (type + package)

### Next Milestone: Production-Ready BOM Export

The tool must produce a BOM that a CM (e.g. PCBWay) can use directly to source components. This requires:

1. **BOM Export** — Generate a CM-ready BOM file (Excel/CSV) matching the PCBWay template format:
   - Group components by MPN (R14,R18 → qty 2)
   - Map KiCad footprint names to standard package names (C_0805_2012Metric → 0805)
   - Include: Item #, Designator, Qty, Manufacturer, Mfg Part #, Description/Value, Package, Type (SMD/THT)
   - Flag components still missing MPNs as incomplete rows

2. **Complete MPN coverage** — Every component on the board must have a verified MPN before export. The verification dashboard already shows what's missing; BOM export should refuse or warn if coverage < 100%.

3. **Cache layer** — SQLite cache with per-source TTL to avoid redundant queries and enable faster repeat scans.

### Out of Scope for MVP

- DigiKey / Mouser API adapters (Tier 2 — not needed when JLCPCB database covers most passives and common ICs)
- CSV BOM import for standalone mode (secondary user need)
- Datasheet URL verification (HTTP HEAD check)
- Lifecycle / obsolescence check (requires API access)
- Compare mode (side-by-side part comparison)
- BOM cost estimate
- Multiple CM template formats (start with PCBWay, add others later)

### MVP Success Criteria

- Export a PCBWay-format BOM for a real 70-component board with 100% MPN coverage
- BOM accepted by CM without corrections on first submission
- Full workflow (scan → search → assign → export) completed in under 30 minutes
- Author uses it on next 2 production boards

### Future Vision

- **Tier 2**: DigiKey + Mouser API adapters, datasheet verification, lifecycle checks, CSV import, footprint-to-package matching against distributor data
- **Tier 3**: Multi-CM template support, BOM cost estimation, stock/availability checks, compare mode, verification report export
- **Long-term**: KiCad Plugin and Content Manager distribution, community-contributed CM templates, alternate part suggestions for EOL/out-of-stock components
