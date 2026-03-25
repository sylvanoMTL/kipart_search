---
stepsCompleted: [1, 2, 3, 4]
inputDocuments: ['ExistingWorksOn/compass_artifact_wf-af099856-fd25-4fc1-bcd0-66648f118144_text_markdown.md']
session_topic: 'KiPart Search — free open-source parametric component discovery + BOM verification/design audit tool'
session_goals: 'Zero-cost MPN discovery across free sources, BOM verification (MPN/datasheet/symbol/footprint), non-ambiguous BOM, KiCad 9/10 plugin + standalone PySide6, reuse existing open-source via git submodules, web scraping fallback'
selected_approach: 'progressive-flow'
techniques_used: ['what-if-scenarios', 'morphological-analysis', 'six-thinking-hats', 'decision-tree-mapping', 'morphological-analysis-dist', 'role-playing-dist', 'chaos-engineering-dist']
ideas_generated: 103
context_file: 'CLAUDE.md'
session_continued: true
continuation_date: '2026-03-24'
continuation_topic: 'Windows distribution and installer strategy — Inno Setup, auto-update, multi-platform framework'
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

---

# Session Extension: Distribution & Installer Strategy (2026-03-24)

## Extension Overview

**Topic:** Distribution and installer strategy for KiPart Search Windows binary
**Goals:** Evaluate installer technologies, auto-update mechanisms, multi-platform framework, KiCad Plugin Manager integration
**Constraint:** Zero-cost distribution stack — no paid signing, no paid hosting, no paid CI
**Context:** Story 7.4 (ZIP distribution) complete, Nuitka compilation working (~115 MB, 68 files), freemium license module implemented

## Technique Selection

**Approach:** AI-Recommended Techniques
**Analysis Context:** Strategic technical decision-making with known options — needs trade-off mapping, stakeholder validation, and failure-mode discovery

**Recommended Techniques:**

- **Phase 1 — Morphological Analysis:** Map all distribution dimensions and options systematically
- **Phase 2 — Role Playing:** Stress-test from stakeholder perspectives (hobbyist, corporate EE, solo dev, returning user)
- **Phase 3 — Chaos Engineering:** Deliberately break the update flow to find failure modes before users do

---

## Phase 1: Morphological Analysis — Distribution Landscape

### Dimension Map

| Dimension | Options Explored |
|---|---|
| **Installer** | Inno Setup / NSIS / MSIX / No installer (ZIP only) |
| **Delivery channel** | GitHub Releases / Own website / KiCad PCM / winget-Chocolatey |
| **Code signing** | None / Commercial OV cert / EV cert / Azure Trusted Signing |
| **Auto-update** | None / Check GitHub + download link / Full in-app update flow |
| **Install location** | Program Files (admin) / AppData (no admin) / Portable / User chooses |
| **KiCad PCM** | Not on PCM / PCM metadata pointing external / Full PCM package / PCM launches exe |
| **First-run experience** | Just launches / Setup wizard / Guided tour / Splash |
| **Uninstaller** | None / Add/Remove Programs / Registry cleanup / Installer handles it |

### Locked Decisions

| Dimension | Decision | Rationale |
|---|---|---|
| **Installer** | Inno Setup | Free, mature, Pascal scripting, huge community |
| **Delivery** | GitHub Releases | Zero cost, zero infrastructure |
| **Code signing** | None (all platforms) | $0 budget — SmartScreen/Gatekeeper warnings acceptable, document workarounds |
| **Auto-update** | Full in-app flow (download → close → install → relaunch) | Modern UX like VS Code/Discord |
| **Install location** | Program Files default, user-selectable | Standard Windows UX |
| **KiCad PCM** | Not on PCM — standalone only | Architectural mismatch (PySide6 vs wxPython), TOS risk |
| **First-run** | Already implemented (WelcomeDialog) | DB download + API config + skip |
| **Uninstaller** | Inno Setup handles Add/Remove Programs | User data preserved separately |
| **Desktop shortcut** | Opt-in during install (default unchecked) | Respect clean desktops |
| **File associations** | None | App is workflow-driven, not file-driven |
| **Multi-platform** | Framework-ready all platforms, Windows-only actual builds for v1.0 | No Mac/Linux resources yet |

### Ideas Generated

**[Dist #1]**: GitHub Releases as Single Distribution Point
_Concept_: GitHub Releases hosts the installer `.exe`. Auto-update checks `api.github.com/repos/{owner}/{repo}/releases/latest` for newer `tag_name`. Zero infrastructure cost, zero maintenance.
_Novelty_: Version check is one unauthenticated GET request (60 req/hr per IP)

**[Dist #2]**: Inno Setup Per-User Install Option
_Concept_: Default install to Program Files (admin required). User can override path. Inno Setup supports both with folder selection page.
_Novelty_: Standard Windows flow — nothing surprising

**[Dist #3]**: SmartScreen Mitigation via Reputation Building
_Concept_: SmartScreen learns from download volume. Warning disappears organically. Document "More info → Run anyway" on GitHub release page. Add signing when revenue justifies it.
_Novelty_: Treats signing as a milestone, not a prerequisite

**[Dist #4]**: Inno Setup with User-Selectable Install Path
_Concept_: Default `C:\Program Files\KiPart Search\`. User can browse to change. Inno Setup auto-creates Start Menu shortcut + Add/Remove Programs entry.
_Novelty_: Standard Windows UX

**[Dist #5]**: Version Check via GitHub Releases API
_Concept_: On app launch, GET `api.github.com/repos/{owner}/{repo}/releases/latest`. Compare `tag_name` against `__version__`. If newer → show banner with download link. 5 lines of httpx code.
_Novelty_: Zero infrastructure

**[Dist #6]**: No KiCad PCM — Avoid TOS Risk
_Concept_: KiCad PCM is for plugins running inside KiCad's wxPython. Distributing a standalone PySide6 exe is an architectural mismatch. Stay off PCM entirely.
_Novelty_: Avoids "is this a plugin or an app?" identity confusion

**[Dist #7]**: Inno Setup Handles User Data Gracefully on Uninstall
_Concept_: Installer writes to Program Files. User data lives in `%LOCALAPPDATA%\KiPartSearch\`. Uninstaller removes Program Files only. Optionally prompts "Remove user data?" (default No). Reinstall/upgrade finds existing data.
_Novelty_: Clean separation means upgrades never lose settings or cached database

**[Dist #8]**: Detect Existing Installation on Upgrade
_Concept_: Inno Setup checks registry for previous install path. If found: "Upgrading from vX.X.X to vY.Y.Y". Skip folder selection (use existing path). Preserve user data.
_Novelty_: Prevents accidental duplicate installations

**[Dist #9]**: Desktop Shortcut as Opt-In During Install
_Concept_: Inno Setup "Additional Tasks" page with checkbox: "Create desktop shortcut" (default unchecked). Start Menu entry always created.
_Novelty_: Respects users who keep clean desktops

**[Dist #10]**: No File Associations
_Concept_: KiPart Search is launched, then connects to KiCad or imports a BOM. Users don't "open a file with" KiPart Search. File associations would confuse the mental model.
_Novelty_: Respects that this is a tool, not a document editor

---

## Phase 2: Role Playing — Stakeholder Perspectives

### Persona 1: KiCad Hobbyist (First-Timer)

**[Dist #11]**: SmartScreen Warning Acceptable for v1.0
_Concept_: Target audience (PCB engineers) regularly install EDA tools and niche engineering software — used to clicking through. Document steps on GitHub release page. Revisit signing when download volume or revenue justifies cost.
_Novelty_: Honest trade-off — $0 now vs $200+/yr

**[Dist #12]**: GitHub Release Page as Trust Signal
_Concept_: Users see source code, commit history, stars, open issues, author name. GitHub-hosted `.exe` from a visible author is more trustworthy than random website download. Include SHA256 checksums in release notes.
_Novelty_: GitHub's reputation does the trust-building that code signing would otherwise do

### Persona 2: Professional EE at a Company

**[Dist #13]**: Corporate Install Guidance in README
_Concept_: README section: "Installing on managed corporate machines" — SmartScreen workaround, IT whitelist suggestion, and the portable ZIP alternative (no install, no admin, no registry). The ZIP from Story 7.4 becomes the corporate/portable escape hatch.
_Novelty_: Two distribution formats serving two audiences — installer for normal users, ZIP for restricted environments

### Persona 3: Solo Dev (Release Pipeline)

**[Dist #14]**: Scripted Release Pipeline (Local, Not CI)
_Concept_: Single `release.py` that chains: version bump check → Nuitka build → ZIP package → Inno Setup compile → checksums. Not CI/CD — just a local script that prevents forgetting steps.
_Novelty_: Automation where it matters (reproducibility), manual where it's fine (upload)

**[Dist #15]**: GitHub Actions for Build (Future/Multi-Platform)
_Concept_: Push a tag → Actions runs Nuitka on platform runners → attaches artifacts to release. Future option for local builds, practically required for multi-platform.
_Novelty_: Local script designed so it can be copy-pasted into CI later

**[Dist #16]**: Automated Release Builder Script
_Concept_: One command runs: verify tests pass → GPL license check → Nuitka build → ZIP → Inno Setup → SHA256 checksums. Fails fast on any step.
_Novelty_: One command, all checks, all artifacts

**[Dist #17]**: Release Checklist Printed at End
_Concept_: After build succeeds, print human checklist: upload files, tag commit, write release notes. Script catches automatable mistakes, checklist catches human ones.
_Novelty_: Hybrid automation

**[Dist #18]**: Version Gate — Refuse to Build if Version Unchanged
_Concept_: Release script reads `pyproject.toml` version, checks latest GitHub release tag. If match → refuses to build. Prevents shipping same version number twice.
_Novelty_: Catches most common solo-dev release error before a 10-minute Nuitka build

**[Dist #19]**: Inno Setup Script as Versioned Source File
_Concept_: `installer.iss` in repo. Version injected by build script via `#define MyAppVersion "X.Y.Z"`. No manual editing per release.
_Novelty_: Version flows from pyproject.toml → build script → Inno Setup define

### Persona 4: Returning User (Update Flow)

**[Dist #20]**: Migrate User Data to %LOCALAPPDATA%
_Concept_: Change all `Path.home() / ".kipart-search"` to `%LOCALAPPDATA%\KiPartSearch\` on Windows via `platformdirs`. One-time migration: if old path exists and new is empty, move data over.
_Novelty_: Follows Windows conventions. IT admins expect app data under AppData, not hidden dotfiles.

**[Dist #21]**: LOCALAPPDATA (Not Roaming) for Large Data
_Concept_: JLCPCB database is ~500 MB. `%APPDATA%` (roaming) syncs across domain-joined machines. Use `%LOCALAPPDATA%` — machine-local, no roaming.
_Novelty_: Correct Windows semantics for large caches

**[Dist #22]**: Full In-App Update Flow (Download → Close → Install → Relaunch)
_Concept_: On startup, background check GitHub Releases API. If newer version: dialog with release notes summary + [Update Now] [Remind Me Later] [Skip This Version]. "Update Now": download installer to temp with progress bar → "Ready to install, app will close and reopen" → launch installer `/VERYSILENT` → app exits → installer overwrites Program Files → relaunches app.
_Novelty_: Zero manual steps — same UX as VS Code, Discord, Slack

**[Dist #23]**: Explicit Pre-Close Warning About UAC
_Concept_: Update dialog warns BEFORE closing: "Windows will ask for permission to install. Click Yes to continue." Sets expectations so UAC prompt has context.
_Novelty_: Sets expectations before the app disappears

**[Dist #24]**: Inno Setup Preserves User Data by Design
_Concept_: Installer only writes to Program Files. All user data in `%LOCALAPPDATA%\KiPartSearch\`. Uninstaller optionally prompts to remove user data (default: No). Upgrade = overwrite Program Files, data untouched.
_Novelty_: Clean separation already architecturally correct

**[Dist #25]**: Inno Setup Silent Mode for In-App Updates
_Concept_: Same `.exe` installer serves two purposes: (1) First install — full GUI wizard. (2) In-app update — `/VERYSILENT /SUPPRESSMSGBOXES`, no GUI. One installer, two modes.
_Novelty_: No separate update mechanism needed

**[Dist #26]**: Download to Temp, Verify Before Launching
_Concept_: Download new installer to `%TEMP%\kipart-search-update-vX.Y.Z.exe`. Verify file size matches GitHub release asset size. Optionally verify SHA256. If fail → "Download corrupted, please try again."
_Novelty_: Simple integrity check prevents corrupted updates

**[Dist #27]**: Graceful Fallback if Silent Install Fails
_Concept_: If installer fails, old version still in Program Files untouched — Inno Setup is atomic. Next launch detects same update available. "Update failed. [Try Again] [Download Manually]"
_Novelty_: Failed update never bricks the install

**[Dist #28]**: Three-Tier User Control (Update Now / Remind Later / Skip This Version)
_Concept_: "Remind Me Later" = check again next launch. "Skip This Version" persists `skipped_version` in config — only alerts for newer versions.
_Novelty_: Three-tier control: now / not now / not this version

---

## Phase 3: Chaos Engineering — Breaking the Update Flow

### Attack Surface 1: The Update Flow

**[Chaos #29]**: Antivirus Quarantines Downloaded Installer
_Concept_: Unsigned exe in `%TEMP%` is classic malware behavior. AV quarantines it. App tries to launch → file not found.
_Mitigation_: Check file exists after download. If missing → "Your antivirus may have blocked the update. Download manually from GitHub." with clickable link.

**[Chaos #30]**: App Closes, Installer Fails, Nothing Relaunches
_Concept_: App exits. Installer hits permission error. User left with nothing open.
_Mitigation_: Update shim (`.bat` watchdog script) — waits for app exit, runs installer, if failure relaunches old version with `--update-failed` flag.

**[Chaos #31]**: User Closes Progress Bar Mid-Download
_Concept_: Partial `.exe` in temp. Next launch tries to resume/launch partial file?
_Mitigation_: Download to `.partial` extension. Only rename to `.exe` after size verification. Delete `.partial` files on startup.

**[Chaos #32]**: GitHub API Rate Limit Hit
_Concept_: 60 req/hr unauthenticated. Frequent restarts could hit limit.
_Mitigation_: Cache last check with timestamp. Only check once per 24 hours. If 403 → silently skip.

**[Chaos #33]**: GitHub Down or Unreachable
_Concept_: Corporate firewall or GitHub outage. Version check times out. App startup delayed.
_Mitigation_: Background thread with 5-second timeout. App launches immediately regardless. Failure = silent skip.

### Attack Surface 2: The Shim

**[Dist #34]**: Update Shim — Watchdog `.bat` Script
_Concept_: App writes `update.bat` to `%TEMP%`: (1) Wait for kipart-search.exe to exit (max 30s), (2) Run installer `/VERYSILENT`, (3) Check exit code, (4) If failure → relaunch old exe with `--update-failed`. ~15 lines.
_Novelty_: Simple, covers the "nothing is open" gap completely

**[Chaos #35]**: Shim Itself Blocked by AV/Policy
_Concept_: Some environments block script execution from `%TEMP%`.
_Mitigation_: If shim can't spawn → "Automatic update couldn't start. Installer downloaded to [path]. Please close KiPart Search and run it manually." Copy path to clipboard.

**[Chaos #36]**: UAC Prompt Appears With No Context
_Concept_: `/VERYSILENT` suppresses Inno Setup GUI but UAC still appears. App is closed, user sees random elevation prompt.
_Mitigation_: Warn user BEFORE closing: "Windows will ask for permission. Click Yes."

**[Chaos #37]**: User Denies UAC
_Concept_: User clicks No on UAC. Installer never runs. Shim detects non-zero exit.
_Mitigation_: Shim relaunches old app with `--update-failed`. Error dialog: "Update needs administrator permission. [Try Again] [Download Manually]"

### Attack Surface 3: The Installer

**[Chaos #38]**: User Runs Installer While App is Open (Manual Download)
_Concept_: Manual download from GitHub, runs installer while app is open. Locked files.
_Mitigation_: Inno Setup `CloseApplications=yes` + `CloseApplicationsFilter=kipart-search.exe`. Detects running process, offers to close it.

**[Chaos #39]**: Multiple Versions in Different Locations
_Concept_: v0.1.0 in Program Files, v0.2.0 on Desktop. Two copies, Start Menu points to old.
_Mitigation_: Inno Setup `AppId` ensures registry tracks one installation. Shows "already installed at [path]" if different location detected.

**[Chaos #40]**: Installer Corrupted During Download
_Concept_: Network drop mid-download. Truncated exe.
_Mitigation_: In-app: file size verification (#26). Manual: SHA256 in release notes.

### Attack Surface 4: User Data

**[Chaos #41]**: Data Path Migration Fails Mid-Way
_Concept_: Migration from `~/.kipart-search/` to `%LOCALAPPDATA%` crashes after config but before 500 MB database.
_Mitigation_: Atomic per file: copy → verify → delete old. If any step fails → keep both copies, log warning. App checks both locations as fallback.

**[Chaos #42]**: SQLite Database Schema Mismatch After Update
_Concept_: New app version opens old DB. Schema incompatibility causes crash.
_Mitigation_: Schema version check on startup. Old schema → migration SQL. Newer schema (downgrade) → warning, refuse to corrupt.

---

## Multi-Platform Framework Extension

### Platform Strategy

**[Dist #43]**: Multi-Platform Compiled Binaries from Day One (Framework-Ready)
_Concept_: All code is platform-aware from day one (platformdirs, platform-specific update logic). Only Windows build pipeline is operational for v1.0. macOS/Linux build scripts exist as stubs.
_Novelty_: Zero extra effort for Windows. Zero wasted effort when Mac/Linux become possible.

**[Dist #44]**: Platform-Specific Distribution Formats

| Platform | Binary | Package | Update Mechanism |
|---|---|---|---|
| **Windows** | Nuitka standalone | Inno Setup `.exe` | In-app → shim → `/VERYSILENT` → relaunch |
| **macOS** | Nuitka `--macos-create-app-bundle` | `.dmg` disk image | In-app → replace `.app` bundle → relaunch |
| **Linux** | Nuitka standalone | AppImage (single file) | In-app → replace AppImage → relaunch |

**[Dist #45]**: `platformdirs` for All Data Paths (Prerequisite)
_Concept_: Replace all `Path.home() / ".kipart-search"` with `platformdirs.user_data_dir("KiPartSearch")`. Returns correct path on every OS. BSD license, Nuitka-safe.
_Novelty_: One line of code handles three platforms

**[Dist #46]**: macOS Considerations
_Concept_: Unsigned `.app` triggers Gatekeeper ("right-click → Open → Open"). Apple Developer cert $99/yr — refused, accept Gatekeeper friction. Universal binary (x86_64 + arm64) or two downloads. DMG via `create-dmg` or `hdiutil`.
_Novelty_: macOS most hostile for unsigned apps but $0 budget is firm

**[Dist #47]**: Linux — AppImage Wins
_Concept_: Single file, no install, runs on any distro. No root needed. No sandbox issues (unlike Flatpak/Snap which may block KiCad IPC socket). `chmod +x` and run.
_Novelty_: AppImage is the "ZIP equivalent" for Linux

**[Dist #48]**: GitHub Actions for Multi-Platform CI
_Concept_: Push tag → three parallel runners (windows-latest, macos-latest, ubuntu-latest) → Nuitka → artifacts attached to release. Free tier: 2,000 min/month. Windows active, macOS/Linux disabled until resources available.
_Novelty_: Can't manually build on three OSes — CI practically required for multi-platform

**[Dist #49]**: Platform-Specific Update Shim
_Concept_: Windows: `.bat` (launches installer). macOS: `.sh` (replaces `.app` bundle). Linux: `.sh` (replaces AppImage, `chmod +x`). macOS/Linux simpler — just file replacement, no installer.
_Novelty_: Windows is the most complex; other platforms are lighter

**[Dist #50]**: Unified Update Checker, Platform-Specific Download
_Concept_: GitHub Releases API returns multiple assets per release. App detects `sys.platform` and picks correct asset. One update dialog, three download targets.
_Novelty_: Update UI identical on all platforms — only download URL and post-action differ

**[Dist #51]**: Framework-Ready Multi-Platform, Windows-Only Builds for v1.0
_Concept_: All code platform-aware. Only Windows pipeline operational. macOS/Linux as documented stubs. Enabling later = uncommenting CI config, not rewriting code.
_Novelty_: One-line change to activate a new platform in CI

**[Dist #52]**: GitHub Actions with Platform Matrix (Windows Active, Others Disabled)
_Concept_: `.github/workflows/release.yml` defines matrix `[windows-latest, macos-latest, ubuntu-latest]`. macOS/Linux jobs commented out or gated. Enabling = uncommenting 2 lines.
_Novelty_: CI framework complete from day one

**[Dist #53]**: Zero-Cost Distribution Stack — No Exceptions
_Concept_: Entire pipeline costs $0/yr. No signing certs. GitHub Actions free tier. GitHub Releases hosting. SmartScreen/Gatekeeper warnings documented.

| Platform | Signing | UX Impact | Mitigation |
|---|---|---|---|
| Windows | None | "More info → Run anyway" | Document on release page |
| macOS | None | "right-click → Open → Open" | Document on release page |
| Linux | Not needed | No warnings | AppImage just works |

---

## Idea Organization and Prioritization

### Thematic Summary

| Theme | Ideas | Key Decisions |
|---|---|---|
| **Core Distribution Architecture** | #1-10, #13 | Inno Setup + GitHub Releases, ZIP as corporate fallback |
| **In-App Update Flow** | #22, #25, #26, #28, #32, #33, #34 | Full download→close→install→relaunch with shim |
| **Update Failure Resilience** | #29-31, #35-37, #27, #40 | Shim watchdog, AV fallback, partial download protection |
| **Installer Behavior** | #8, #19, #38, #39, #7 | Upgrade detection, AppId, CloseApplications, version inject |
| **User Data Paths** | #20, #21, #41, #42, #45 | platformdirs → LOCALAPPDATA, atomic migration |
| **Release Pipeline** | #14-18 | Automated build chain, version gate, printed checklist |
| **Trust & Signing** | #3, #11, #12, #53 | Zero-cost, reputation-based, document workarounds |
| **Multi-Platform Framework** | #43-52 | Framework-ready all platforms, Windows-only builds v1.0 |

### Breakthrough Concepts

1. **The Update Shim (#34)** — ~15 lines of `.bat` solves the scariest failure mode. Simple, elegant, complete.
2. **ZIP as Corporate Fallback (#13)** — Story 7.4's ZIP isn't obsolete, it's the restricted-environment distribution format.
3. **One Installer, Two Modes (#25)** — Same `.exe` for first install (GUI wizard) and in-app update (`/VERYSILENT`).
4. **Framework-Ready Multi-Platform (#51)** — All code platform-aware from day one, only Windows pipeline active. Activating a new platform = uncommenting CI config.

### Prioritized Action Items

**Must Have (v1.0):**
- `platformdirs` migration (prerequisite for everything)
- Inno Setup `.iss` script with upgrade detection, AppId, shortcuts
- In-app update flow (check → dialog → download → shim → install → relaunch)
- Shim watchdog with failure fallback
- Automated release build script
- Failure resilience (AV fallback, partial download, UAC warning)

**Nice to Have (v1.0):**
- SHA256 verification of downloaded installer
- Version gate in build script
- SQLite schema versioning

**Deferred (post-v1.0):**
- macOS `.dmg` packaging + build
- Linux AppImage packaging + build
- GitHub Actions CI (activate when multi-platform is real)
- Code signing (activate when revenue justifies it)

### Build Sequence

| Step | What | Scope | Depends on |
|---|---|---|---|
| **S1** | `platformdirs` for all data paths + migration from `~/.kipart-search/` | All platforms | — |
| **S2** | Inno Setup `.iss` script (install, uninstall, upgrade, shortcuts) | Windows | S1 |
| **S3** | Extend build script → full release chain (tests → build → ZIP → Inno → checksums) | Windows | S2 |
| **S4** | GitHub Actions CI (Windows active, macOS/Linux stubs) | Framework | S3 |
| **S5** | In-app version check (GitHub API, 24h cache, background thread, 5s timeout) | All platforms | — |
| **S6** | Update dialog (platform-aware download, Update Now / Remind Later / Skip) | All platforms | S5 |
| **S7** | Update shim — Windows `.bat` operational, macOS/Linux `.sh` stubs | Windows + stubs | S2, S6 |
| **S8** | Failure resilience (AV fallback, partial download, UAC warning, `--update-failed`) | Windows | S7 |

S1 and S5 are independent — can be developed in parallel.

---

## Session Summary and Insights

### Key Achievements

- **53 new ideas** generated for distribution strategy (103 total across both sessions)
- **8 locked decisions** covering every distribution dimension
- **14 failure modes** identified and mitigated via Chaos Engineering
- **Complete build sequence** with 8 steps and dependency mapping
- **Multi-platform framework** designed for future expansion at zero extra cost

### Breakthrough Moments

- Realizing the ZIP from Story 7.4 isn't obsolete — it's the corporate/restricted fallback
- The update shim concept: 15 lines of `.bat` solving the scariest UX gap
- "One installer, two modes" eliminating the need for a separate update mechanism
- Framework-ready multi-platform without any wasted effort on Windows delivery

### Creative Facilitation Narrative (Extension)

This extension session tackled a concrete engineering decision (distribution strategy) using three complementary techniques. Morphological Analysis mapped the full option space and quickly locked 8 decisions through direct user input. Role Playing surfaced the critical data path issue (`~/.kipart-search/` → `%LOCALAPPDATA%`) and the release pipeline automation need. Chaos Engineering was the most productive phase — finding 14 failure modes in the update flow, most notably the "app closed but installer failed" gap that led to the shim concept. The user's firm $0 budget constraint simplified many decisions (no signing, GitHub-only hosting, free CI tier) and the late pivot to multi-platform framework-readiness added valuable future-proofing without increasing v1.0 scope.
