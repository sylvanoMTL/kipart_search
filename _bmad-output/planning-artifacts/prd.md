---
stepsCompleted: [step-01-init, step-02-discovery, step-02b-vision, step-02c-executive-summary, step-03-success, step-04-journeys, step-05-domain-skipped, step-06-innovation, step-07-project-type, step-08-scoping, step-09-functional, step-10-nonfunctional, step-11-polish]
classification:
  projectType: desktop_app
  domain: general
  complexity: low-medium
  projectContext: brownfield
inputDocuments: ['planning-artifacts/product-brief-kipart-search-2026-03-15.md', 'brainstorming/brainstorming-session-2026-03-14-1730.md', 'CLAUDE.md', 'ExistingWorksOn/compass_artifact_wf-af099856-fd25-4fc1-bcd0-66648f118144_text_markdown.md']
workflowType: 'prd'
documentCounts:
  briefs: 1
  research: 0
  brainstorming: 1
  projectDocs: 0
  projectContext: 0
---

# Product Requirements Document - KiPart Search

**Author:** Sylvain
**Date:** 2026-03-15

## Executive Summary

KiPart Search is a free, open-source PySide6 desktop application that eliminates the manual workflow gap between KiCad schematic/PCB design and production-ready BOM creation. It connects to a running KiCad 9+ instance via the IPC API to scan all board components, verify existing manufacturer part numbers against distributor databases, discover missing MPNs through parametric search, and write verified data back to component fields — all without leaving the app.

The primary user is a small-business hardware designer producing ~2 PCBs/month with ~70 components each, ordering from Mouser/DigiKey, and subcontracting assembly to CMs who require complete, accurate BOMs. Secondary users include hobbyists using JLCPCB assembly and contract manufacturers who receive BOMs from clients.

The core problem: designers manually search distributor websites one component at a time, copy-paste MPNs into KiCad fields, then fill CM-provided BOM templates by hand. For a 70-component board this takes ~3 hours and produces errors that surface late — when the CM flags issues or boards come back wrong.

### What Makes This Special

- **Two-way workflow in one tool**: no existing open-source project combines parametric component discovery with BOM verification. KiCost only prices known MPNs. kicad-jlcpcb-tools places parts but doesn't audit. JLCParts searches but has no KiCad integration.
- **Live KiCad bridge**: reads/writes component fields via IPC API, highlights footprints on click, cross-probes to schematic automatically. Made possible by KiCad 9's IPC API — the enabling technology that didn't exist before 2024.
- **Zero-config baseline**: works offline with a ~1M-part JLCPCB database. No API keys, no accounts, no setup. Download and search in 5 minutes.
- **Safety-first write-back**: never overwrites non-empty fields, preview dialog before every change, type and package mismatch warnings.
- **End goal is a CM-ready BOM**: the tool's output is a production BOM (PCBWay format) that the manufacturer can use directly to source and build.

## Project Classification

- **Type**: Desktop application (PySide6, standalone process)
- **Domain**: Electronic design automation tooling
- **Complexity**: Low-medium (well-understood patterns, no regulatory requirements)
- **Context**: Brownfield — Tier 1 MVP is built and functional (search, scan, verify, assign). Next milestone is production-ready BOM export.

## Success Criteria

### User Success

- **BOM completion time**: Finished PCB layout → production-ready BOM in < 30 minutes for a 70-component board (vs ~3 hours manual)
- **100% MPN coverage**: Every component has a verified manufacturer part number before BOM export
- **Zero CM bounce-backs**: BOM accepted by subcontractor on first submission — no "fix these 7 issues" emails
- **Correct-by-construction**: Footprint matches package, MPN matches component type, datasheet URL is valid
- **Aha moment**: Double-click a missing-MPN component → search pre-fills with value + package → find and assign MPN in seconds

### Business Success

- **Personal adoption**: Author uses KiPart Search on every board (2/month) as part of standard pre-production workflow
- **Time recovered**: ~5 hours/month saved on manual BOM work
- **Error elimination**: Zero BOM-related production issues (wrong parts, missing MPNs, footprint mismatches)
- **Dogfooding as validation**: If the author stops using it, something is fundamentally wrong — investigate and fix

### Measurable Outcomes

| Outcome | Target | Measurement |
|---------|--------|-------------|
| BOM time | < 30 min / 70-component board | Self-timed on real projects |
| MPN coverage | 100% after workflow | Dashboard shows all green |
| CM rejections | 0 per board | CM feedback |
| Search hit rate | > 90% of components found | Dashboard stats |
| Personal adoption | 100% of boards | Used on every project |

## Product Scope & Phased Development

### MVP Strategy

**MVP Approach:** Problem-solving MVP — ship the smallest addition that makes the existing tool production-complete.
**Resource Requirements:** Solo developer (author), Python/PySide6 expertise.

The tool already works for search → scan → assign. The gap is the last mile: turning verified component data into a file the CM can use directly.

### Phase 1: MVP (Tier 1 + BOM Export)

**Already built (Tier 1):**
- JLCPCB offline database with FTS5 search and auto-download
- PySide6 GUI: search bar, query transformation, results table with filters and detail panel
- Smart query builder (reference prefix → unit inference, footprint → package extraction)
- KiCad IPC API: scan project, read fields, highlight/select, write-back
- Verification dashboard: green/amber/red, detail view, guided search
- Assign dialog: preview, never-overwrite, type + package mismatch warnings

**To build (next milestone):**
1. BOM export in PCBWay Excel/CSV format (Item #, Designator, Qty, Manufacturer, Mfg Part #, Description, Package, Type)
2. Component grouping by MPN (R14,R18 → qty 2)
3. KiCad footprint → standard package name mapping (C_0805_2012Metric → 0805)
4. SMD/THT type detection from footprint
5. Incomplete BOM warning (refuse or warn if MPN coverage < 100%)
6. SQLite cache with per-source TTL

**Core User Journeys Supported:**
- Journey 1 (Happy Path): Full scan → search → assign → export workflow
- Journey 2 (Edge Case): Manual MPN entry → export with manually-entered parts included
- Journey 4 (CM): Receives correctly formatted BOM file

### Phase 2: Growth (API Enrichment)

- DigiKey API v4 adapter (parametric search, 1000 req/day free)
- Mouser API adapter (keyword search, pricing/stock)
- Datasheet URL verification (HTTP HEAD, PDF detection)
- Lifecycle / obsolescence check
- CSV BOM import for standalone mode (no KiCad required)
- Footprint-to-package validation against distributor data
- Multiple CM template formats

### Phase 3: Expansion (Multi-CM & Community)

- Multi-CM template library (PCBWay, JLCPCB, custom)
- BOM cost estimation across distributors
- Stock/availability alerts
- Alternate part suggestions for EOL/out-of-stock
- Compare mode (side-by-side part comparison)
- Verification report export (CSV, PDF)
- KiCad Plugin and Content Manager distribution
- Community-contributed CM templates

### Risk Mitigation

**Technical Risks:** KiCad IPC API may change between versions — all IPC calls isolated in `kicad_bridge.py`. JLCPCB database format may change — vendored download logic, not a submodule dependency.
**Market Risks:** Minimal — author is the primary user and validator. If it works for real production boards, it works. Open-source community feedback will surface edge cases.
**Resource Risks:** Solo developer — keep scope tight. Phase 1 is intentionally small (one export format, one database). If time is constrained, cache layer can be deferred to Phase 2 without blocking BOM export.

## User Journeys

### Journey 1: Sylvain — Pre-Production BOM Workflow (Happy Path)

**Opening Scene:** It's Thursday evening. Sylvain has just finished routing a 68-component motor controller board in KiCad. The schematic is clean, DRC passes, but the BOM is a mess — most components have generic values like "100nF" and "10k" with no MPNs. The board needs to ship to the CM by Monday.

**Rising Action:** He launches KiPart Search and clicks "Scan Project." Within seconds, the verification dashboard lights up: 23 components green (already have MPNs from his library), 6 amber (MPN assigned but couldn't be verified in JLCPCB database), 39 red (no MPN at all). The health bar reads "Ready: 34%."

He starts with the reds. Double-clicks C12 (100nF 0805) — the search panel opens pre-filled with "100nF 0805 capacitor." 47 results appear instantly. He picks a Murata GRM21BR71C104KA01L, clicks Assign. The preview dialog shows "Will write: MPN, Manufacturer, Description" — he confirms. C12 turns green.

He works through the components methodically. For passives (resistors, caps, inductors), the smart query builder nails it every time — value + package + type. For ICs, he types the part number he already knows and verifies it exists. For connectors, he searches by description.

**Climax:** 45 minutes in, the dashboard shows 100% green. He clicks "Export BOM" — the tool generates a PCBWay-format Excel file with components grouped by MPN, standard package names, quantities, and SMD/THT types. He opens it, scans the rows — everything looks right. He attaches it to the email to his CM.

**Resolution:** Monday morning, the CM confirms: "BOM received, no issues, starting procurement." No back-and-forth. No corrections. Sylvain saved ~2 hours of manual work and eliminated the usual round of "R47 has no MPN" emails.

### Journey 2: Sylvain — Component Not Found (Edge Case)

**Opening Scene:** During the same workflow, Sylvain double-clicks U3 — a TPS54302 buck converter from Texas Instruments. The search returns 0 results. The JLCPCB database doesn't carry TI's automotive-grade regulators.

**Rising Action:** He knows the MPN — he selected it during schematic design from TI's website. He types "TPS54302" in the search box. Still 0 results. The log shows "Found 0 result(s)." The JLCPCB database simply doesn't have this part.

**Climax:** He manually types the MPN into the assign dialog: MPN = "TPS54302DDCR", Manufacturer = "Texas Instruments". The preview shows these will be written to U3's fields. He confirms. U3 turns green — the MPN is assigned even though it wasn't found in the database.

**Resolution:** The BOM exports with U3 included. The CM will source it from DigiKey or Mouser. In the future, when DigiKey/Mouser API adapters are added, this search would have found it automatically. For now, manual entry is the fallback — and it works.

### Journey 3: Marc — Hobbyist First Experience

**Opening Scene:** Marc is a hobbyist who just designed his first custom keyboard PCB in KiCad — 42 components. He found KiPart Search on Reddit. He's never manually assigned MPNs before; his previous boards used JLCPCB's parts library directly.

**Rising Action:** He downloads and launches the app. A dialog prompts: "JLCPCB database not found. Download now? (~500 MB)" He clicks yes, watches the progress bar for 3 minutes. Done.

He connects to KiCad, clicks "Scan Project." The dashboard is a sea of red — only 3 components have MPNs (the ones he copied from a tutorial). 39 are missing.

**Climax:** He double-clicks the first red component — D1, a WS2812B LED. The search pre-fills with "LED" from the footprint. He types "WS2812B" — 2 results appear. He picks one, assigns it. Green. He gets faster — the resistors and capacitors are all 0805, the search builder handles them perfectly. After 20 minutes, he's at 90% green. The remaining 4 are custom connectors he enters manually.

**Resolution:** He exports the BOM and uploads it to JLCPCB's assembly service. Every LCSC part number matches. The order goes through first try. Marc thinks: "I should have had this tool 3 boards ago."

### Journey 4: CM Receiving the BOM (Secondary)

**Opening Scene:** Thierry at the assembly house opens his email Monday morning. Another KiCad project from Sylvain — motor controller board, 68 components.

**Rising Action:** He opens the attached BOM Excel file. Standard PCBWay format. He scans the columns: Item #, Designator, Qty, Manufacturer, Mfg Part #, Description, Package, Type. All populated. No empty MPN cells. No "TBD" entries.

**Climax:** He imports the BOM into his procurement system. All parts resolve. He generates a quote in 15 minutes instead of the usual hour of back-and-forth.

**Resolution:** He sends the quote to Sylvain. No "please fix these issues" email. The project moves to procurement immediately. Thierry notices: "Sylvain's BOMs have gotten much better lately."

### Journey Requirements Summary

| Journey | Key Capabilities Revealed |
|---------|--------------------------|
| **1. Happy Path** | Scan project, verification dashboard, guided search, smart query builder, assign with preview, BOM export (PCBWay format) |
| **2. Edge Case** | Manual MPN entry when database doesn't have the part, graceful handling of 0 results, fallback assign workflow |
| **3. Hobbyist** | Zero-config onboarding, database download with progress, immediate search after install, LCSC part number matching |
| **4. CM** | BOM export quality: correct grouping, standard package names, complete fields, no empty rows |

## Innovation & Novel Patterns

### Detected Innovation Areas

1. **Two-way workflow integration**: No open-source tool combines parametric component discovery with BOM verification in a single application. Existing tools do one or the other — KiPart Search does both, connected to the design tool live.

2. **KiCad IPC API as enabler**: KiCad 9 (2024) introduced the IPC API for the first time, enabling external tools to programmatically read/write component fields on the PCB editor. KiPart Search is among the first tools to exploit this capability for BOM workflows. This is a platform shift — not just an incremental improvement.

3. **Offline-first with progressive enrichment**: The zero-config JLCPCB database provides immediate value. API adapters (DigiKey, Mouser) add richness over time. Cached results grow the local knowledge base. The tool gets better with use without requiring upfront configuration.

### Market Context & Competitive Landscape

The literature review confirmed: "The missing piece is purely integration — every significant technical challenge has been solved in at least one MIT-licensed Python project." KiCost, kicad-jlcpcb-tools, JLCParts, and Ki-nTree each solve one piece. Nobody has assembled them into a unified scan → search → assign → export workflow.

### Validation Approach

- **Dogfooding**: Author uses tool on real production boards (2/month). If it works for real projects, the integration works.
- **CM acceptance**: BOM accepted by subcontractor without corrections = end-to-end validation.
- **Community feedback**: Open-source release on GitHub; KiCad forum and Reddit posts will surface edge cases.

## Desktop Application Requirements

### Project-Type Overview

KiPart Search is a standalone PySide6 desktop application that runs as an independent process alongside KiCad. It does NOT run inside KiCad's wxPython interpreter. It communicates with KiCad via the IPC API when available, but all core functionality (search, database, BOM export) works fully standalone.

### Platform Support

- **Primary**: Windows 10/11 (author's daily driver)
- **Secondary**: Linux (Ubuntu/Fedora — KiCad power users), macOS (growing KiCad community)
- **GUI framework**: PySide6 (Qt6) — cross-platform, native look-and-feel, no Electron overhead
- **Python**: 3.10+ (matches KiCad 9's bundled Python)
- **Packaging**: PyPI (`pip install kipart-search`), with future goal of KiCad Plugin and Content Manager distribution

### System Integration

- **KiCad IPC API** (KiCad 9.0+): Reads board data (footprints, fields, values), writes back MPNs and metadata, selects/highlights footprints for cross-probe. Connection auto-detected via `KICAD_API_SOCKET` environment variable or default socket path.
- **Graceful degradation**: If KiCad is not running or IPC API is unavailable, the app works fully standalone — search, database browsing, and BOM export from cached/imported data all function without KiCad.
- **File system**: SQLite databases stored in user-local directory (`~/.kipart-search/`). No admin privileges required.

### Update Strategy

- **Database updates**: JLCPCB database auto-download with progress bar on first run. Manual refresh button for subsequent updates. Database hosted as chunked files on GitHub Pages (from kicad-jlcpcb-tools).
- **Application updates**: Standard PyPI update (`pip install --upgrade kipart-search`). No auto-update mechanism in MVP — keep it simple.
- **Future**: KiCad Content Manager distribution would handle updates automatically.

### Offline Capabilities

- **Core search**: Fully offline after initial JLCPCB database download (~500 MB, ~1M parts). FTS5 full-text search with no network dependency.
- **Board scan & verification**: Works offline against local database. Components not found in local DB are flagged but don't block the workflow.
- **BOM export**: Fully offline — generates Excel/CSV from local data.
- **Online-enhanced features** (optional): DigiKey/Mouser API adapters for richer data, datasheet URL verification, pricing/stock checks. These degrade gracefully when offline.

### Background Threading

- **Search workers**: Run in `QThread` to avoid blocking the GUI. Emit results incrementally via Qt signals as each source responds.
- **Scan workers**: Board scan runs in background thread. Progress reported via signals.

### Data Storage & Caching

- **JLCPCB database**: Pre-built SQLite with FTS5 index, stored locally.
- **Cache layer**: SQLite cache with per-source TTL (pricing: 4 hours, parametric: 7–30 days, datasheets: indefinite).
- **Configuration**: `~/.kipart-search/config.json` for settings. API keys stored via `keyring` for OS-native secret storage.
- **No cloud dependency**: All data stored locally. No accounts, no telemetry, no phone-home.

## Functional Requirements

### Component Search & Discovery

- **FR1:** Designer can search for electronic components by keyword, value, package, or parametric specs across the local JLCPCB database
- **FR2:** Designer can view search results in a filterable table showing MPN, manufacturer, package, description, stock, and pricing
- **FR3:** Designer can filter search results by manufacturer and package type
- **FR4:** Designer can view detailed part information (specs, datasheet link, price breaks, stock) for any search result
- **FR5:** Designer can have search queries automatically transformed from KiCad conventions to effective search terms (e.g., R_0805 → "0805 resistor", 100n → 100nF)
- **FR6:** Designer can edit the transformed query before executing the search

### JLCPCB Offline Database

- **FR7:** Designer can download the JLCPCB parts database (~1M parts) on first run with progress indication
- **FR8:** Designer can refresh the local database to get updated part data
- **FR9:** System can perform full-text search on the local database in under 2 seconds

### KiCad Integration

- **FR10:** Designer can connect to a running KiCad 9+ instance via IPC API
- **FR11:** Designer can scan all components from the active KiCad PCB project
- **FR12:** Designer can click a component in the app to highlight/select it in KiCad's PCB editor (triggering schematic cross-probe)
- **FR13:** Designer can write back MPN, manufacturer, and description fields to a KiCad component
- **FR14:** System prevents overwriting non-empty component fields without explicit confirmation
- **FR15:** System warns when assigned part has type or package mismatch with the target component

### BOM Verification & Dashboard

- **FR16:** Designer can view a verification dashboard showing all board components colour-coded by status (green/amber/red)
- **FR17:** Designer can see per-component verification status: MPN present, MPN verified in database, footprint match
- **FR18:** Designer can view a health bar showing overall BOM readiness percentage
- **FR19:** Designer can double-click a missing-MPN component to open search pre-filled with that component's value and package
- **FR20:** Designer can re-run verification after making changes

### MPN Assignment

- **FR21:** Designer can assign an MPN from search results to a KiCad component via a preview dialog
- **FR22:** Designer can manually enter an MPN, manufacturer, and description for components not found in the database
- **FR23:** Designer can preview all field changes before confirming a write-back to KiCad

### BOM Export

- **FR24:** Designer can export a production-ready BOM in PCBWay Excel/CSV format
- **FR25:** System groups components by MPN with combined designators and correct quantities (e.g., R14,R18 → qty 2)
- **FR26:** System maps KiCad footprint names to standard package names (e.g., C_0805_2012Metric → 0805)
- **FR27:** System detects and labels components as SMD or THT based on footprint
- **FR28:** System warns or refuses BOM export when MPN coverage is below 100%
- **FR29:** BOM export includes all required PCBWay columns: Item #, Designator, Qty, Manufacturer, Mfg Part #, Description/Value, Package, Type

### Caching

- **FR30:** System caches search results and part data locally with configurable expiration per source
- **FR31:** System serves cached results for repeat queries without network access

### Application Configuration & Status

- **FR32:** Designer can store and manage API keys for distributor adapters (DigiKey, Mouser) via OS-native secret storage (enables Phase 2 multi-source search)
- **FR33:** Designer can use the application fully offline after initial database download
- **FR34:** Designer can access a Help/About dialog with app name, version, author, and license information
- **FR35:** Designer can see a clear status indicator showing current data mode (e.g., "Local DB" vs "Online — 3 sources active")

## Non-Functional Requirements

### Performance

- **NFR1:** Full-text search queries return results in < 2 seconds on a ~1M part database, as measured by end-to-end timing from query submission to results displayed
- **NFR2:** Full board scan (70 components) completes in < 10 seconds, as measured by scan start to dashboard populated
- **NFR3:** GUI remains responsive (no freezes) during all search, scan, and export operations, as verified by UI interaction during background tasks
- **NFR4:** BOM export for a 70-component board completes in < 5 seconds, as measured by export button click to file written
- **NFR5:** Application cold start to usable state in < 3 seconds (excluding database download), as measured by launch to main window interactive

### Security

- **NFR6:** API keys (DigiKey, Mouser) stored via OS-native secret storage, never in plaintext config files
- **NFR7:** No telemetry, no analytics, no data sent to external servers beyond explicit API calls initiated by the user

### Integration

- **NFR8:** KiCad IPC API connection auto-detected; no manual socket configuration required for standard installs
- **NFR9:** Application functions fully without KiCad running — all features except highlight/select and write-back work standalone
- **NFR10:** IPC API calls isolated behind a single abstraction layer to accommodate KiCad API changes across versions

### Reliability

- **NFR11:** No crashes or data loss during the scan → search → assign → export workflow
- **NFR12:** Database corruption recovery: if the JLCPCB parts database is corrupted, the user can re-download it without losing configuration or cached data
- **NFR13:** Write-back operations are atomic per component — a failed write to one component does not affect others

### Portability

- **NFR14:** Application runs on Windows 10/11, Linux (Ubuntu 22.04+, Fedora 38+), and macOS 12+ without platform-specific code paths in core logic
- **NFR15:** All file paths use platform-agnostic handling (no hardcoded separators or OS-specific paths)
