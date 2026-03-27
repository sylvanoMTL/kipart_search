---
stepsCompleted: [1, 2, 3, 4]
inputDocuments: []
session_topic: 'Multi-API search UX architecture — how to handle fundamentally different source capabilities in a coherent search interface'
session_goals: 'Process tree of component search, evaluate unified vs tabbed, cross-source visualisation, clear UX pattern recommendation'
selected_approach: 'ai-recommended'
techniques_used: ['Decision Tree Mapping', 'Morphological Analysis', 'Role Playing']
ideas_generated: ['Process Tree #1-11', 'Morpho #1-10']
context_file: '_bmad-output/planning-artifacts/brainstorm-context-search-rethink.md'
session_active: false
workflow_completed: true
---

# Brainstorming Session Results

**Facilitator:** Sylvain
**Date:** 2026-03-25

## Session Overview

**Topic:** Multi-API search UX architecture — how to handle fundamentally different source capabilities (offline FTS5, parametric filters, keyword-only, GraphQL aggregation) in a coherent search interface
**Goals:**
1. Map the process tree of how a user actually searches for a component
2. Evaluate unified search vs tabbed per-source search with clear tradeoffs
3. Determine how to visualise and compare results across sources
4. Arrive at a clear UX pattern recommendation

### Context Guidance

_Context loaded from brainstorm-context-search-rethink.md: Current design uses source selector dropdown + shared search box with two modes. Proposed direction is tabbed per-source with query translation. Six data sources with fundamentally different capabilities. Key open questions around result visibility, cross-source comparison, single-source UX, and filter handling._

### Session Setup

_Session configured for strategic UX architecture brainstorming. Technical, decision-oriented tone. Three-phase approach: Decision Tree Mapping → Morphological Analysis → Role Playing._

## Technique Selection

**Approach:** AI-Recommended Techniques
**Analysis Context:** Multi-API search UX with focus on process tree, unified vs tabbed evaluation, and clear recommendation

**Recommended Techniques:**

- **Decision Tree Mapping:** Map the real user search workflows to reveal where source differences actually matter
- **Morphological Analysis:** Systematically explore all combinations of source type × query intent × display mode × user profile
- **Role Playing:** Walk top patterns through different user personas (hobbyist, engineer, CM buyer) to stress-test

**AI Rationale:** This sequence moves from understanding (how do users actually search?) to systematic exploration (what are ALL the options?) to validation (does the winner work for everyone?). This prevents premature commitment to tabbed-vs-unified before understanding the problem space.

## Technique Execution Results

### Phase 1: Decision Tree Mapping

**Interactive Focus:** Mapping the real search workflows from the user's perspective, identifying where source differences matter

**Process Tree #1 — MPN-Known Path (Source-Agnostic)**
User types MPN → unified search across all sources → results show availability/stock as informational columns. The user doesn't care where the data came from — they care about: does this part exist? Is it obsolete? Can I still get it? Source is a result attribute, not a search dimension. This path argues against tabbed UI.

**Process Tree #2 — Spec-Known Parametric Discovery (Two-Stage Funnel)**
Primary query is built from known specs (extracted from schematic on double-click or typed manually). All sources are queried in parallel. Results populate dynamic filters for narrowing down. The user doesn't choose a source first — they define what they need, and the system finds it everywhere. This reverses the tabbed model's assumption: "define specs, get results, then filter" instead of "pick a source, then search."

**Process Tree #3 — Toggle Mode (Unified vs. Per-Source)**
A preference toggle (or slider in the UI) lets users switch between "Combined" view (all sources merged, Source as a column) and "Per-Source" view (tabbed, each with its own translated query and filters). Both modes share the same primary search box.

**Process Tree #4 — Query Translation Visibility Problem**
The primary search box accepts natural/fuzzy input. A translation engine decomposes it into structured queries per source (JLCPCB→FTS5, DigiKey→category+filters, Mouser→keyword). The core question: can this translation be reliable enough to be invisible, or does the user need to see/edit each source's interpreted query? If translation is reliable, unified works. If it needs correction, per-source views become necessary.

**Process Tree #5 — Progressive Disclosure (Translator-First with Manual Override)**
Default UX is unified — single search box, automatic translation per source, merged results. When the translator fails or results look wrong, the user can "expand" to see the per-source translated queries and correct them. Not a full tabbed mode — a debug/refinement panel normally hidden. The 80% case stays clean, the 20% case gets a lightweight correction UI.

**Process Tree #6 — Accordion Source Queries (Unified with Per-Source Refinement)**
One fuzzy search box drives everything. Below it, a collapsible accordion shows each source's interpreted query — JLCPCB keeps its refinement search box, DigiKey shows structured category+filters, Mouser shows its keyword string. Each is editable. Filters and results table are unified below.

**Process Tree #7 — MPN-Grouped Expandable Results (Uniform Columns)**
Results table groups by MPN. Same columns throughout — collapsed parent row shows merged Sources column (comma-separated), expanded child rows repeat the same columns but each tagged to a single source. Clicking any row (parent or child) loads that source's full detail in the detail panel below. No inline price/stock in the tree — detail panel does the heavy lifting.

**Process Tree #8 — Two Fundamentally Different Modes**

| Aspect | Unified Mode | Per-API Mode |
|--------|-------------|--------------|
| Search | Fuzzy box → accordion per-source queries | Tab per source, each with source-native search |
| Filters | Unified dynamic filters from merged results | Per-source filters matching that API's capabilities |
| Results | Single table, MPN-grouped, expandable by source | One table per tab, source-specific columns |
| Detail panel | Shared | Same |
| Use case | "Find me this part anywhere" | "I'm designing for JLCPCB, show me JLCPCB-specific filters" |

These are genuinely different workflows. Unified mode is for discovery and comparison. Per-API mode is for deep exploration of one vendor's catalog with that vendor's native capabilities exposed.

**Process Tree #9 — Complete Search Workflow (Mode-Aware)**
```
User action (double-click verify panel OR manual type)
         │
         ▼
┌─────────────────────────┐
│  Main Fuzzy Search Box  │  ← always present, shared across both modes
└─────────┬───────────────┘
          │
    [Slide Toggle: Unified / Per-API]
          │
    ┌─────┴──────┐
    ▼            ▼
 UNIFIED      PER-API
    │            │
    ▼            ▼
 Collapsible    Tabs
 accordion:     ┌──────┬────────┬────────┐
 ├ JLCPCB      │JLCPCB│ DigiKey│ Mouser │
 ├ DigiKey      └──┬───┴────────┴────────┘
 └ Mouser          │
    │              ▼
    │           Per-tab search box (translated)
    │           Per-tab dynamic filters
    │              │
    ▼              ▼
 Unified        Per-tab
 dynamic        results
 filters        table
    │              │
    ▼              ▼
 MPN-grouped    Source-specific
 results table  results table
    │              │
    └──────┬───────┘
           ▼
     Detail Panel (cleared on toggle)
```

**Process Tree #10 — Toggle State Preservation Rules**
The fuzzy search box is the single source of truth. Per-source translated queries are derived from it. When toggling modes, only the layout changes — the fuzzy query stays, translated queries regenerate, but results and filters reset because the display model is different. Detail panel clears.

**Process Tree #11 — Mode Toggle with Dirty State Warning**
Each per-source search box tracks whether it's been manually edited (dirty flag). On toggle, if any source query has been manually modified, show a confirmation dialog: "You have manual edits in [DigiKey, Mouser]. Switching modes will reset these. Continue?" Prevents silent data loss.

### Phase 2: Morphological Analysis

**Interactive Focus:** Systematically crossing dimensions (query intent × source capability × display mode × user profile) to find gaps and edge cases

**Morpho #1 — Translation Confidence as Table Watermark**
When a source has partial/failed translation, show a watermark-style overlay at the bottom-right corner of the results table (OrcaSlicer pattern): "⚠️ DigiKey: partial match — expand source queries to refine". Subtle, non-blocking, visible. Multiple warnings stack. Clicking the watermark expands the accordion to that source's query box.

**Morpho #2 — Single-Source Auto-Simplification**
When only one source is configured, the toggle switch hides, accordion/tabs disappear entirely. UI becomes: fuzzy search box → filters → results → detail. No unnecessary chrome. Simplest UX for the most common beginner case.

**Morpho #3 — BOM Double-Click Search Propagation**
Default: double-click from verify panel triggers search on all tabs/sources in background, user stays on current tab. Optional preference: "Only search active source on BOM double-click" — for users working within one vendor's catalog or conserving API quota.

**Morpho #4 — API Rate Budget Awareness**
Track API call count per source per day. Show subtle counter near source name: "DigiKey (847/1000)". When approaching the limit, warn before executing. Prevents burning through DigiKey quota on exploratory searches.

**Morpho #5 — Source Pause/Resume in Unified Mode**
Each source in the accordion or tab bar has a small toggle — enabled/disabled. In unified mode, a disabled source is skipped during search but stays visible (greyed out). Serves double duty: rate limit conservation AND "I don't care about Mouser right now" workflow simplification. Disabled state persists within session, not across restarts.

**Morpho #6 — Filter Strategy: Always Client-Side**
When the user applies a dynamic filter in unified mode, all sources filter client-side from existing results. Never re-query on filter change. If the user wants source-native parametric precision, they toggle to Per-API mode. Keeps unified mode fast and predictable.

**Morpho #7 — Clear Separation of Concerns**
Unified mode = cast a wide net, browse, compare, filter what came back. Per-API mode = deep dive with native power, re-query with structured filters, precise exploration. Client-side filtering in unified mode reinforces this separation.

**Morpho #8 — Per-API Tab Search: Explicit Per Tab**
In Per-API mode, the fuzzy search populates all tabs' search boxes (translated), but only the active tab auto-executes the search. Other tabs show the translated query with a watermark: "Press Search to query DigiKey". User clicks Search when navigating to that tab. Optional preference: "Auto-search all tabs".

**Morpho #9 — Watermark Pending-Search State**
Three distinct states per tab: not searched (watermark message) → searching (spinner) → results (table). Avoids confusion between "no results found" and "not searched yet".

**Morpho #10 — Batch Verification as Separate Module**
Batch BOM verification is a distinct feature (separate menu/module), not part of the search UX. The search panel stays focused on interactive single-component exploration. Batch mode is a future module for bulk MPN checks with rate-managed API calls.

### Phase 3: Role Playing

**Interactive Focus:** Walking the designed UX through three user personas to stress-test

**Persona 1: Marie (Hobbyist, JLCPCB only)**
- Single source → auto-simplification: no toggle, no accordion, no tabs
- Double-clicks component in verify panel → fuzzy search → JLCPCB results → filters (Basic/Extended) → pick part
- Result: passes cleanly. Simplest possible UX for the most common beginner case.
- No re-onboarding needed when adding a second source — UI changes are self-evident, welcome dialog on first launch covers onboarding.

**Persona 2: Raj (Engineer, JLCPCB + DigiKey)**
- Parametric discovery: "rail-to-rail op-amp low offset"
- Unified mode: JLCPCB returns fuzzy matches, DigiKey returns poor results
- Watermark appears: "⚠️ DigiKey: partial match"
- Clicks watermark → accordion expands → manually sets DigiKey parametric fields → precise results appear
- Can also toggle to Per-API mode for full DigiKey-native filter experience
- Result: both modes have clear distinct value. Unified + accordion fixes the query. Per-API gives DigiKey-native filters (Vos, GBW, slew rate) that unified can't offer.

**Persona 3: Wei (Power User, all sources configured)**
- Multi-MPN workflow: find primary MPN in unified → toggle to Per-API for deep parametric discovery of alternatives → toggle back to unified for cross-source comparison
- Natural flow between modes validates the toggle design
- Batch BOM verification correctly scoped as separate future module
- Result: toggle serves different phases of the same task.

## Idea Organization and Prioritization

### Theme 1: Search Architecture — Two-Mode Design

The core UX pattern: unified mode with collapsible accordion for per-source query visibility, and per-API tabbed mode with source-native filters. Slide toggle switches between them. Fuzzy search box is the shared source of truth across both modes.

### Theme 2: Query Translation Engine

Automatic decomposition of fuzzy input into structured queries per source. Confidence scoring (full / partial / keyword fallback). OrcaSlicer-style watermark overlay for partial matches. Progressive disclosure — accordion collapsed by default, expanded when translator fails.

### Theme 3: Results Display — MPN-Grouped Expandable

Uniform columns throughout. Collapsed parent row shows comma-separated Sources. Expanded child rows each tagged to one source. Click loads source-specific detail panel. Clean, no inline price/stock clutter.

### Theme 4: Mode Toggle Behaviour

Intent (fuzzy query) persists, presentation resets. Dirty state warning before discarding manual edits. Detail panel clears. Layout changes (tabs appear/disappear).

### Theme 5: Per-API Tab Behaviour

Only active tab auto-executes. Other tabs show watermark "Press Search to query [source]". Three states: not searched → searching → results. Preference for auto-search all tabs.

### Theme 6: API Budget & Rate Management

Per-source daily counter. Source pause/resume toggle. BOM double-click defaults to all sources (preference for active-only). Batch verification as separate future module.

### Cross-Cutting Decisions

| Decision | Resolution |
|----------|-----------|
| Filters re-query or client-side? | Always client-side. Per-API mode for deep parametric. |
| Single source UX? | Auto-simplify, hide all multi-source chrome |
| MPN lookup — source matters? | No, unified is clearly better |
| Batch BOM check? | Separate module, out of scope for search UX |
| Price comparison? | Falls out naturally from MPN-grouped results, no special UI |
| Onboarding for new sources? | Not needed, first-launch welcome dialog covers it |

### Prioritization Results

**Build order:**

1. **High Impact, Build First**: Unified mode with accordion + MPN-grouped results — the default experience for all users
2. **High Impact, Build Second**: Per-API tabbed mode with source-native filters — the power-user deep dive
3. **Medium Impact**: Query translation engine with confidence scoring — can start simple (keyword passthrough) and improve over time
4. **Medium Impact**: Slide toggle between modes with dirty state warning
5. **Lower Priority**: Rate budget indicator, source pause/resume, batch verification module

### Quick Wins

- Single-source auto-simplification (hide chrome when only 1 source configured)
- Watermark for pending-search state in tabs (simple UI state management)
- Client-side filtering decision (simplifies implementation — no re-query logic needed in unified mode)

### Breakthrough Concepts

- **OrcaSlicer-style watermark for translation confidence** — non-blocking, clickable, actionable
- **Accordion as progressive disclosure** — translator-first with manual override, not a full tabbed fallback
- **Fuzzy box as single source of truth** — clean mental model for mode toggling

## Session Summary and Insights

**Key Achievements:**

- Mapped complete process tree (11 nodes) covering all search entry points and workflows
- Resolved the tabbed-vs-unified debate with a two-mode toggle design, each serving genuinely different workflows
- Identified API rate budget as a previously unconsidered concern
- Validated design across 3 user personas with no blocking issues
- Established clear build order from unified (default) to per-API (power user)

**Session Reflections:**

The initial question ("should each source get its own tab?") turned out to be a false binary. The answer is both — but as two fundamentally different modes serving different workflows, not as a compromise. Unified mode is for discovery and comparison. Per-API mode is for deep vendor-specific exploration. The slide toggle makes the choice explicit and reversible. The key architectural insight is that the fuzzy search box is the single source of truth — everything below it is presentation of that intent.
