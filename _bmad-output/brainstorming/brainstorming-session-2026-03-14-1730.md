---
stepsCompleted: [1, 2, 3, 4]
inputDocuments: ['ExistingWorksOn/compass_artifact_wf-af099856-fd25-4fc1-bcd0-66648f118144_text_markdown.md']
session_topic: 'KiPart Search — free open-source parametric component discovery + BOM verification/design audit tool'
session_goals: 'Zero-cost MPN discovery across free sources, BOM verification (MPN/datasheet/symbol/footprint), non-ambiguous BOM, KiCad 9/10 plugin + standalone PySide6, reuse existing open-source via git submodules, web scraping fallback'
selected_approach: 'progressive-flow'
techniques_used: ['what-if-scenarios', 'morphological-analysis', 'six-thinking-hats', 'decision-tree-mapping']
ideas_generated: 50
context_file: 'CLAUDE.md'
---

# Brainstorming Session Results

**Facilitator:** Sylvain
**Date:** 2026-03-14

## Session Overview

**Topic:** KiPart Search — free, open-source parametric component discovery and BOM verification/design audit tool
**Goals:**
- Zero-cost baseline (no paid API keys for core functionality)
- MPN discovery across multiple free data sources (JLCPCB/LCSC offline DB, DigiKey, Mouser, TrustedParts)
- BOM verification: validate MPN, datasheet URL, symbol, footprint for every component
- Non-ambiguous bill of materials as the end goal
- Dual-mode: KiCad plugin (9/10 via IPC API) + standalone PySide6 app
- Reuse existing open-source work via git submodules (proper attribution)
- Web scraping fallback when APIs are unavailable
- KiCad 9 + 10 compatibility (IPC API, PCB editor only — schematic via cross-probe)

### Context Guidance

Literature review loaded from ExistingWorksOn/. Key finding: "The missing piece is purely integration — every significant technical challenge has been solved in at least one MIT-licensed Python project."

### Session Setup

Progressive Technique Flow selected with 4 phases: What If Scenarios → Morphological Analysis → Six Thinking Hats → Decision Tree Mapping.

## Technique Selection

**Approach:** Progressive Technique Flow
**Journey Design:** Systematic development from exploration to action

**Progressive Techniques:**

- **Phase 1 - Exploration:** What If Scenarios for maximum idea generation
- **Phase 2 - Pattern Recognition:** Morphological Analysis for mapping parameter combinations
- **Phase 3 - Development:** Six Thinking Hats for multi-perspective stress-testing
- **Phase 4 - Action Planning:** Decision Tree Mapping for implementation sequencing

---

## Phase 1: Expansive Exploration — What If Scenarios (50 Ideas)

### Data Access & Architecture

**[Data Access #1]**: Tiered Data Source Hierarchy
_Concept_: Three-tier fallback chain: (1) Free offline/online databases (no keys) → (2) Free-registration API keys → (3) Web scraping as last resort
_Novelty_: Graceful degradation — tool always works, varying richness

**[Data Access #2]**: Database-First, API-Second Philosophy
_Concept_: Primary value from browsing databases (local SQLite, online). APIs are structured access to online databases. Without APIs, data still exists on websites.
_Novelty_: Reframes APIs as convenience, not necessity

### Trust & Data Provenance

**[Trust #3]**: Authoritative Sources Only
_Concept_: Every data point traces back to a distributor or manufacturer. No community-contributed parametric data. The tool is an aggregator, not a database.
_Novelty_: Opposite of community wiki approach — prevents data drift

**[Trust #4]**: User-Selectable Source Configuration
_Concept_: Checkboxes — user chooses which sources to trust. Results show provenance per data point.
_Novelty_: Like choosing package repositories in Linux

**[Ecosystem #5]**: The PLM Fragmentation Problem
_Concept_: Many PLMs exist (InvenTree, Part-DB, Binner) but none integrated into KiCad workflow. KiPart Search is the search/verification layer in front of PLMs, not a competing PLM.
_Novelty_: Focused scope — complementing, not competing

**[Trust #6]**: Confidence Scoring via Cross-Reference
_Concept_: Query multiple sources for same MPN. Agreement = high confidence. Disagreement (different footprint, wrong category) = warning. A resistor query returning a capacitor = red flag.
_Novelty_: Active inconsistency detection across sources

**[Trust #7]**: Data Provenance Tags on Every Field
_Concept_: Each field shows source: "MPN: DigiKey API", "Package: LCSC database". User always knows where data came from.
_Novelty_: Transparent data lineage

**[Feedback #8]**: Error Reporting Back to Source
_Concept_: When verification detects issues (dead datasheet, footprint mismatch), mechanism to flag it. Even if just a local log initially.
_Novelty_: Every user becomes a data quality sensor

### Privacy & Data Flow

**[Privacy #9]**: Pull-Only Architecture
_Concept_: Tool only pulls data from internet or local databases. No telemetry, no shared cache, no peer-to-peer. Local cache for user only.
_Novelty_: Strong privacy — tool is a client, never a server

**[Privacy #10]**: Optional Cache File Exchange via GitHub
_Concept_: Export/import local cache as a file. Share on GitHub if desired. No service, no account, no sync — just a file.
_Novelty_: Community sharing without community infrastructure

### UX & Workflow

**[Workflow #11]**: MPN-First Triage on Plugin Launch
_Concept_: Click plugin → auto-scan → separate "has MPN" (verify) vs "no MPN" (discover). No user action needed for triage.
_Novelty_: Tool decides workflow based on project state

**[Workflow #12]**: Guided Parametric Resolution for Generic Components
_Concept_: For "100nF" with no MPN, tool detects capacitor, prompts for voltage/tolerance/package. Works with partial info — shows broader results when specs are incomplete.
_Novelty_: Progressive refinement, not "fill all fields or nothing"

**[Workflow #13]**: Footprint as a Hard Filter
_Concept_: If footprint assigned (e.g. 0805), every MPN suggestion must match. No footprint = warning. Footprint mismatch = red flag.
_Novelty_: Footprint gates the search — not optional metadata

**[UX #14]**: Plugin is On-Demand, Not Always-On
_Concept_: Nothing shows when KiCad opens. User clicks plugin when ready. Clean separation — no background processes.
_Novelty_: Respects engineer's workflow

**[UX #15]**: Explicit "Scan Project" Button, No Auto-Run
_Concept_: Plugin opens with clean interface + "Scan Project" button. User controls when scanning happens.
_Novelty_: User controls bandwidth and timing

**[UX #16]**: Footprint as Optional Filter with Bypass
_Concept_: Footprint filters search by default. Checkbox "Ignore footprint filter" for custom footprints or early-stage design.
_Novelty_: Simple toggle handles custom footprint problem

**[Verify #17]**: Custom Footprint Warning, Not Error
_Concept_: Unrecognised footprint = amber warning "Custom footprint — cannot verify package match." Not red error.
_Novelty_: Avoids false negatives that train users to ignore warnings

**[Verify #18]**: Three-Level Severity System
_Concept_: Red (confident something is wrong), Amber (can't fully verify), Green (verified across sources).
_Novelty_: Clear "broken" vs "uncertain" distinction — prevents alert fatigue

### Standalone Mode

**[Standalone #19]**: CSV BOM Import
_Concept_: Standalone accepts CSV BOM from any EDA tool. Same verification dashboard. Works for Altium, Eagle, hand-made spreadsheets.
_Novelty_: Massively wider audience beyond KiCad

**[Standalone #20]**: Same Workflow, Different Input Source
_Concept_: Three input modes (KiCad IPC / CSV / Manual), same core engine. Architecture separates input from verification+search.
_Novelty_: GUI and engine stay the same regardless of source

**[Standalone #21]**: Smart CSV Column Mapping
_Concept_: Auto-detect common column names ("Part Number" vs "MPN" vs "Manf#"). Manual mapping for unrecognised columns. Save mapping per format.
_Novelty_: User teaches tool once per format

### Safety & Write-Back

**[Safety #22]**: Never Overwrite Library-Defined Fields
_Concept_: Fields inherited from curated libraries (e.g. VRTH) are read-only. Only write to instance-level empty fields.
_Novelty_: Respects library author's work

**[Safety #23]**: Conservative Approach — Never Overwrite Non-Empty Fields by Default
_Concept_: Before writing, check if field has value. If yes → show to user, require explicit "overwrite" confirmation. Simpler than detecting library origin, equally safe.
_Novelty_: Achieves safety without needing KiCad library metadata

**[Workflow #24]**: Write-Back with Explicit User Confirmation
_Concept_: Preview dialog: "I will add: MPN = X, Voltage = 50V, Datasheet = URL. Confirm?" Per-component or batch.
_Novelty_: No silent writes

**[Standalone #25]**: Standalone Edits CSV, Not KiCad Files
_Concept_: Standalone: enrich and re-export CSV. KiCad modification only via IPC API with live connection. Never directly modify .kicad_sch files.
_Novelty_: Avoids dangerous direct file modification

### Parameter Templates

**[Params #26]**: Built-in Templates per Component Category
_Concept_: Each category has Required / Important / Optional parameters. Progressive disclosure, not a wall of 50 fields.
_Novelty_: Tool guides user through what matters, in priority order

**[Params #27]**: Technology/Family as Key Filter
_Concept_: Before parametric values, determine technology: MLCC vs Electrolytic vs Tantalum (caps), thick vs thin film (resistors). Changes everything downstream.
_Novelty_: Technology is upstream of all parameters

**[Params #28]**: Not All Fields Mandatory — Smart Defaults with Warnings
_Concept_: Missing dielectric? Search works but warns: "Dielectric not specified — results include X5R, X7R, C0G." Works with partial info, educates about risks.
_Novelty_: Doesn't block user, doesn't hide risk

### Lifecycle & Availability

**[Verify #29]**: Lifecycle Status Check
_Concept_: Query MPN lifecycle: Active → NRND → EOL → Obsolete. First-class verification check, same level as MPN/datasheet/footprint.
_Novelty_: Catch obsolescence at design time, not ordering time

**[Verify #30]**: Drop-in Replacement Suggestion
_Concept_: NRND/EOL/Obsolete → auto-search alternatives with matching specs and package, status = Active. "3 active replacements found."
_Novelty_: Beyond flagging — offers solutions

### Pricing & Stock

**[Pricing #31]**: Stock & Price as On-Demand Detail
_Concept_: Main table stays clean. Click/expand row reveals pricing and stock across sources.
_Novelty_: Respects primary mission (verification), data one click away

**[Pricing #32]**: BOM Total Rough Cost Estimate
_Concept_: Summary line: "Estimated BOM cost: ~€12.50 (47 components, qty 1)". Order of magnitude, not precise costing.
_Novelty_: One number sanity check, not competing with KiCost

**[Availability #33]**: Stock Shortage Detection
_Concept_: Very low or zero stock across all sources = amber/red flag during verification. Availability is a design-time constraint.
_Novelty_: Treats availability as BOM problem, not purchasing surprise

**[Availability #34]**: Shortage Triggers Replacement Suggestion
_Concept_: Same replacement engine as lifecycle — if no stock, offer compatible alternatives with stock. Unified "find replacement" regardless of trigger.
_Novelty_: One replacement workflow for multiple triggers

### Export & Reporting

**[Export #35]**: Machine-Readable Verification Report
_Concept_: Output as CSV or JSON: Reference, Value, MPN, Status, Lifecycle, Stock, Unit Price, Warnings. Parseable, diffable, importable.
_Novelty_: Machines first, humans second

**[Export #36]**: Verification History as Timestamped Files
_Concept_: Each scan saves bom-report-YYYY-MM-DD.csv. No database — filesystem is the history. Works with git.
_Novelty_: Simple files, no state management

**[Export #37]**: BOM Cost Tracking Over Time
_Concept_: Each report includes total estimated cost + availability summary. Track trends across development.
_Novelty_: Cost tracking as byproduct of verification

**[Integration #38]**: Export Compatible with Downstream Tools
_Concept_: Enriched BOM export follows conventions KiCost, InvenTree, JLCPCB assembly expect. No format conversion.
_Novelty_: Explicitly designed as the verification step between design and costing/ordering

### Search UX

**[Search #39]**: Hybrid Search — Keywords First, Then Parametric Filters
_Concept_: Text box → results → filter panel (voltage, package, tolerance). Like e-commerce: broad search, then refine.
_Novelty_: No intimidating form upfront

**[Search #40]**: Compare Mode — Side by Side
_Concept_: Select 2-3 parts, click "Compare". Side-by-side parameters, differences highlighted.
_Novelty_: Built-in comparison replaces manual spreadsheet work

**[Search #41]**: Search Results Show Source Icons
_Concept_: Small icons per result showing which sources returned it. Visual provenance at a glance.
_Novelty_: Visual confidence without text clutter

### Offline Behaviour

**[Offline #42]**: Offline-First with JLCPCB Database
_Concept_: No internet → tool works with local DB. Search + basic MPN lookup functional. Online checks skipped with clear indication.
_Novelty_: Always useful — plane, firewall, air-gapped

**[Offline #43]**: Cache Enables Progressive Offline Capability
_Concept_: Every API result cached. More usage = richer local data. Cache entries show age.
_Novelty_: Tool improves with use

**[Offline #44]**: Clear Online/Offline Status Indicator
_Concept_: Status bar: "Online — 3 sources active" or "Offline — local database only."
_Novelty_: Transparency about data scope

### Database Management

**[Database #45]**: User-Controlled Download and Update
_Concept_: First launch prompts download. Subsequent launches check version, offer update if newer available. No automatic downloads.
_Novelty_: User controls bandwidth and timing

### Write-Back Safety (Phase 3 Deep Dive)

**[Safety #46]**: Preview-Before-Write Dialog
_Concept_: Diff-style preview showing Current vs New Value per field. Confirm / Skip / Edit before writing.
_Novelty_: User sees exactly what will change

**[Safety #47]**: Write-Back Undo Log
_Concept_: Every write logged: timestamp, reference, field, old value, new value. CSV file survives beyond KiCad's undo.
_Novelty_: Safety net that outlives the session

**[Safety #48]**: Batch Confirm with Individual Override
_Concept_: Batch preview for identical components (R1-R4). User can uncheck individuals. Default all checked.
_Novelty_: Efficient batch workflow with per-component control

**[Safety #49]**: Dry Run Mode
_Concept_: Settings toggle: show what would change but don't write. For testing, demos, learning.
_Novelty_: Risk-free exploration of write-back workflow

**[Safety #50]**: Never Write to Non-Empty Fields by Default
_Concept_: Only write to empty fields. Existing values shown as "(no change)". User must explicitly tick "overwrite" per field.
_Novelty_: Conservative default protects existing data

---

## Phase 2: Pattern Recognition — Morphological Analysis

### Dimension Map

| Dimension | Options |
|-----------|---------|
| **Input Mode** | KiCad IPC API / CSV import / Manual search |
| **Data Source** | Local DB (JLCPCB) / Free API (DigiKey, Mouser) / Web scraping / Cache |
| **Core Function** | Parametric search / BOM verification / MPN discovery / Replacement finder |
| **Verification Check** | MPN exists / Datasheet valid / Footprint matches / Symbol valid / Lifecycle active / Stock available |
| **Output** | Dashboard view / Enriched CSV export / Verification report / Write-back to KiCad |
| **Trust Layer** | Confidence score / Source provenance / Cross-reference / Severity levels (red/amber/green) |
| **User Control** | Source selection / Footprint filter toggle / Scan on demand / Write confirmation / Parameter templates |

### Priority Tiers (Revised)

**Tier 1 — Core MVP:**
- Manual search mode
- JLCPCB/LCSC local database (user-controlled download/update)
- Basic MPN lookup and parametric search
- Results table with source provenance
- Parameter templates for passives (R, C, L)
- Scan Project button (KiCad IPC API)
- Write-back to KiCad (safety: never overwrite non-empty fields, explicit confirmation)
- Confidence scoring (red/amber/green)

**Tier 2 — BOM Verification:**
- CSV import for standalone mode
- Full verification dashboard (MPN, datasheet, footprint, symbol checks)
- Lifecycle check + replacement suggestion
- Footprint filter with bypass toggle
- Custom footprint warning

**Tier 3 — Polish:**
- DigiKey/Mouser API adapters
- Web scraping fallback
- Stock/pricing on-demand detail
- Rough BOM cost estimate
- Compare mode
- Verification history / export reports
- Cache management
- Smart CSV column mapping

---

## Phase 3: Idea Development — Six Thinking Hats

### White Hat (Facts)
- JLCPCB database: ~1M+ parts, SQLite FTS5, proven pattern from kicad-jlcpcb-tools (MIT)
- KiCad IPC API: PCB editor only, KiCad 9 + 10. Schematic API not available yet.
- kicad-python library on PyPI for IPC API access
- PySide6 runs as separate process — no wxPython conflict
- **Fact gap resolved**: IPC API does not clearly expose library vs instance field distinction. Conservative approach adopted: never overwrite non-empty fields without explicit confirmation.

### Red Hat (Emotions)
- **Frustration risks**: 500MB database download on first launch, silent project modification, result overload
- **Delight opportunities**: First "Scan Project" moment showing BOM health, guided MPN resolution, one-click problem fixing
- **Critical UX moment**: Database download must be rock solid — progress bar, resume, clear errors

### Yellow Hat (Benefits)
- No existing tool does scan + verify + search in one workflow — genuinely new
- Zero cost with JLCPCB database
- Git submodules = faster development + proper attribution
- Parameter templates guide users instead of blank search
- Confidence scoring builds trust from day one
- **Killer feature**: Scan Project showing "your BOM has these 7 problems, here's how to fix each one"

### Black Hat (Risks)
1. JLCPCB database format could change (submodule dependency)
2. KiCad IPC API breaking changes between 9.x and 10.x
3. Write-back bugs could corrupt projects — **highest risk, addressed with 5 safety measures**
4. Parameter templates are hand-crafted — wrong fields = poor results
5. Tier 1 scope is still large
6. PySide6 + KiCad IPC on Windows packaging challenges

### Green Hat (Creative Solutions — Write-Back Safety)
- Preview-before-write dialog (Safety #46)
- Write-back undo log as CSV (Safety #47)
- Batch confirm with individual override (Safety #48)
- Dry run mode toggle (Safety #49)
- Never write non-empty fields by default (Safety #50)

### Blue Hat (Process)
- Write-back workflow: Scan → Dashboard → Click problem → Search → Select MPN → Preview (safety gate) → Confirm → Write (logged) → Dashboard refresh
- Two safety layers: preview gate (prevent mistakes) + undo log (recover from mistakes)

---

## Phase 4: Action Planning — Decision Tree Mapping

### Build Sequence

| Step | What | Build or Reuse | Depends on |
|------|------|:-:|---|
| 0 | Project setup + vendored code with attribution | Build | — |
| 1 | Core models + parameter templates | Build | — |
| 2 | JLCPCB database source adapter | Vendor + Build | 1 |
| 3 | Units normalisation | Vendor (KiBoM units.py) | — |
| 4 | Search orchestrator + confidence scoring | Build | 1, 2, 3 |
| 5 | Cache layer (SQLite + TTL) | Build | 1 |
| 6 | Basic GUI shell (search bar + results) | Build | 4 |
| **M1** | **Standalone search works** | | |
| 7 | KiCad bridge (kicad-python IPC API) | Build | 1 |
| 8 | Scan Project + verification dashboard | Build | 4, 6, 7 |
| **M2** | **Scan + verify works** | | |
| 9 | Write-back with safety (preview + never-overwrite) | Build | 7, 8 |
| 10 | Guided search from dashboard | Build | 4, 6, 8 |
| **M3** | **Full Tier 1 MVP** | | |

### Critical Path

Steps 0 → 1 → 2 → 4 → 6 is the critical path to Milestone 1.
Steps 3 and 5 are independent, can be built anytime before needed.

### Code Reuse Strategy: Vendor with Attribution (not git submodules)

Adversarial review found that git submodules are impractical for these cases:
- kicad-jlcpcb-tools `library.py` imports wxPython — can't be used directly from PySide6
- KiBoM `units.py` — pulling an entire repo as submodule for one file is overkill

**Revised approach**: Vendor (copy) the relevant code with clear MIT attribution headers. Write our own downloader with PySide6/Qt signals. Extract the SQLite FTS5 search logic.

| Source Repo | What to vendor | License |
|------|--------------|---------|
| kicad-jlcpcb-tools | SQLite FTS5 search logic, database URL/chunking scheme | MIT |
| KiBoM | units.py — engineering value normalisation | MIT |

Git submodules remain an option for future larger, self-contained library integrations.

---

## Adversarial Review Resolutions

### Finding #4: Confidence scoring with single source (RESOLVED)

In Tier 1 (JLCPCB only), confidence is based on **match quality**, not cross-referencing:

| Confidence | Meaning (single source) |
|:---:|---|
| **Green** | MPN found, category matches, footprint matches |
| **Amber** | MPN found but uncertain — category mismatch, custom footprint, approximate value |
| **Red** | MPN not found, or clear mismatch (resistor query → capacitor result) |

Evolves to cross-referencing when Tier 3 adds DigiKey/Mouser.

### Finding #3: kicad-jlcpcb-tools as submodule (RESOLVED)

library.py imports wxPython for progress events. Cannot be used as submodule directly.
**Decision**: Vendor the SQLite FTS5 search logic with attribution. Write our own downloader.

### Finding #6: Scan Project scope in Tier 1 vs Tier 2 (RESOLVED)

| Check | Tier 1 | Tier 2 |
|-------|:---:|:---:|
| MPN field exists and not empty | Yes | Yes |
| MPN found in JLCPCB database | Yes | Yes |
| Category match (resistor → resistor) | Yes | Yes |
| Footprint assigned (not empty) | Yes | Yes |
| Confidence score (match quality) | Yes | Yes |
| Datasheet URL reachable (HTTP HEAD) | No | Yes |
| Datasheet points to PDF | No | Yes |
| Symbol library reference valid | No | Yes |
| Footprint matches MPN package spec | No | Yes |
| Lifecycle status (API query) | No | Yes |

### Finding #8: Milestone acceptance criteria (RESOLVED)

**Milestone 1 — Standalone search works:**
- PySide6 window launches without errors on Windows
- User can download JLCPCB database via GUI with progress bar
- Keyword search returns results from local database
- Results table shows: MPN, manufacturer, description, package, source provenance
- Parameter template for capacitors filters by capacitance/voltage/package
- Search returns results in under 2 seconds for 1M+ part database
- Works fully offline after database download

**Milestone 2 — Scan + verify works:**
- Plugin connects to running KiCad 9 via IPC API
- "Scan Project" reads all components from PCB
- Dashboard shows: has MPN / missing MPN / MPN issues with counts
- Confidence scoring: green/amber/red per component
- Clicking a row highlights component in KiCad PCB editor
- Works on a real KiCad project with 20+ components

**Milestone 3 — Full Tier 1 MVP:**
- Click missing MPN row → search pre-filled with value + footprint
- Select MPN → preview dialog shows what will change
- Write-back: confirmed fields written via IPC API
- Only empty fields written by default
- Full workflow tested: scan → search → assign → rescan shows green

### Trimmed / Deferred Ideas

**Dropped entirely:**
- #10 Cache file exchange via GitHub — niche, adds complexity, low value
- #8 Error reporting back to source — no mechanism to report upstream
- Git submodules approach — overkill, replaced by vendor-with-attribution

**Deferred from Tier 1 to Tier 2:**
- #47 Write-back undo log (CSV) — useful but not needed for basic preview + never-overwrite safety
- #48 Batch confirm with individual override — add when dashboard is fuller

**Deferred from Tier 1 to Tier 3:**
- #49 Dry run mode — polish feature, not essential

---

## Creative Facilitation Narrative

This session progressed from broad exploration (data architecture, trust, privacy) through structured analysis (morphological mapping, priority tiers) to concrete planning (build sequence with milestones). Key breakthrough moments: the confidence scoring concept, the "never overwrite non-empty fields" safety principle, and the realisation that the Scan Project dashboard is the killer feature. The progressive flow naturally converged from 50 ideas to a focused 10-step build plan with 3 clear milestones. Adversarial review identified 12 issues; the 4 most critical were resolved: confidence scoring algorithm defined for single-source MVP, git submodules replaced with vendor-with-attribution, Scan Project scope clarified per tier, and acceptance criteria added to all milestones.
