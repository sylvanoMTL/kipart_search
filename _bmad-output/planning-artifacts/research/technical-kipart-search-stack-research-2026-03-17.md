---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments:
  - ExistingWorksOn/compass_artifact_wf-af099856-fd25-4fc1-bcd0-66648f118144_text_markdown.md
workflowType: 'research'
lastStep: 2
research_type: 'technical'
research_topic: 'KiPart Search Technology Stack - PySide6, KiCad IPC API, Distributor APIs (Nexar/Octopart, Mouser, DigiKey)'
research_goals: 'Broad sweep of core technologies to inform architecture decisions: PySide6 desktop patterns, KiCad IPC API capabilities, and distributor API integration (Octopart/Nexar, Mouser, DigiKey)'
user_name: 'Sylvain'
date: '2026-03-17'
web_research_enabled: true
source_verification: true
---

# Research Report: Technical

**Date:** 2026-03-17
**Author:** Sylvain
**Research Type:** Technical

---

## Research Overview

This technical research report investigates the four technology pillars for the KiPart Search desktop application: PySide6 GUI framework, KiCad IPC API integration, distributor API ecosystem (DigiKey, Mouser, Nexar/Octopart), and local data storage with SQLite FTS5. Research combines an existing open-source landscape analysis with live web verification of current API states, library versions, and pricing tiers as of March 2026.

**Input documents:** Open-source landscape report (compass artifact), CLAUDE.md project specification.

---

## Technical Research Scope Confirmation

**Research Topic:** KiPart Search Technology Stack - PySide6, KiCad IPC API, Distributor APIs (Nexar/Octopart, Mouser, DigiKey)
**Research Goals:** Broad sweep of core technologies to inform architecture decisions

**Technical Research Scope:**

- Architecture Analysis - design patterns, frameworks, system architecture
- Implementation Approaches - development methodologies, coding patterns
- Technology Stack - languages, frameworks, tools, platforms
- Integration Patterns - APIs, protocols, interoperability
- Performance Considerations - scalability, optimization, patterns

**Research Methodology:**

- Current web data with rigorous source verification
- Multi-source validation for critical technical claims
- Confidence level framework for uncertain information
- Comprehensive technical coverage with architecture-specific insights

**Scope Confirmed:** 2026-03-17

---

## Technology Stack Analysis

### 1. PySide6 — Desktop GUI Framework

#### Core Framework

PySide6 (Qt for Python 6) is the official Python binding for Qt 6, maintained by The Qt Company. It provides a complete desktop application framework with widgets, threading, networking, and model/view architecture. For KiPart Search, PySide6 is the sole GUI dependency — the `core/` package remains GUI-free.

**Confidence: HIGH** — PySide6 is mature, actively maintained, and the Qt Company's official Python offering.

#### Threading Model for Background API Calls

PySide6 offers three threading approaches, each suited to different patterns in KiPart Search:

| Approach | Use Case in KiPart Search | Mechanism |
|----------|--------------------------|-----------|
| **QThread** | Long-lived worker threads (e.g., per-source search workers) | Subclass or `moveToThread()` pattern. Emits signals for incremental results. |
| **QThreadPool + QRunnable** | Short tasks, pooled execution (e.g., datasheet URL validation, HTTP HEAD checks) | `QThreadPool.globalInstance().start(runnable)`. Since PySide6 6.2.0, `start()` accepts plain Python functions. |
| **asyncio integration** | Async HTTP calls via `httpx` | Libraries like `qasync` or `AsyncioPySide6` bridge asyncio's event loop with Qt's. `@asyncSlot()` decorator allows async signal handlers. |

**Recommended pattern for KiPart Search:** Use `QThread` workers per data source, emitting `resultsReady(list[PartResult])` signals. The GUI connects these signals to slots that append rows to the results model. This gives incremental display as each source responds — the user sees JLCPCB results instantly while DigiKey OAuth completes.

_Source: [PythonGUIs — Multithreading with QThreadPool](https://www.pythonguis.com/tutorials/multithreading-pyside6-applications-qthreadpool/), [Qt Official QThread docs](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThread.html), [qasync GitHub](https://github.com/CabbageDevelopment/qasync), [AsyncioPySide6 GitHub](https://github.com/nguyenvuduc/AsyncioPySide6)_

#### Model/View Architecture for Results

PySide6's `QTableView` + `QAbstractTableModel` + `QSortFilterProxyModel` is the standard pattern for tabular data with filtering and sorting:

- **QAbstractTableModel subclass**: Holds the merged `list[PartResult]` from all sources. Workers append via signals; the model emits `rowsInserted` for live table updates.
- **QSortFilterProxyModel**: Provides client-side parametric filtering (e.g., filter by capacitance range, package type) without additional API calls. Subclass `filterAcceptsRow()` for multi-column filtering with unit-aware comparisons.
- **Column sorting**: Built-in via proxy model's `sort()`. Custom sort roles handle engineering values (e.g., "100nF" sorts correctly against "0.1µF").

**Confidence: HIGH** — This is the canonical Qt pattern for tabular data.

#### Credential Management

The `keyring` library provides OS-native credential storage:
- **Windows**: Windows Credential Manager
- **macOS**: Keychain
- **Linux**: Secret Service (GNOME Keyring / KDE Wallet)

Pattern: `keyring.set_password("kipart-search", "digikey_client_id", value)` / `keyring.get_password(...)`. Environment variable overrides (`KIPART_DIGIKEY_CLIENT_ID`) supported as fallback. A GUI settings dialog validates credentials by making a test API call.

**Confidence: HIGH** — `keyring` is the standard Python approach for desktop credential storage.

---

### 2. KiCad IPC API — kicad-python Library

#### Current State (March 2026)

**kicad-python v0.6.0** (released March 15, 2026) is the official Python binding for KiCad's IPC API. Unlike the older SWIG-based `pcbnew` bindings (which run inside KiCad's process), kicad-python communicates with a running KiCad instance via a socket (using `pynng` + `protobuf`).

| Property | Value |
|----------|-------|
| **Latest version** | 0.6.0 (2026-03-15) |
| **Python requirement** | ≥3.9 |
| **Dependencies** | `protobuf`, `pynng 0.9.0` |
| **KiCad requirement** | 9.0+ with API server enabled |
| **Communication** | IPC socket (auto-discovered or via `KICAD_API_SOCKET` env var) |

_Source: [kicad-python on PyPI](https://pypi.org/project/kicad-python/), [kicad-python docs](https://docs.kicad.org/kicad-python-main/)_

#### API Capabilities Relevant to KiPart Search

**Board & Footprint Access:**

```python
from kipy import KiCad

kicad = KiCad()  # auto-discovers socket
board = kicad.get_board()
footprints = board.get_footprints()  # -> Sequence[FootprintInstance]

for fp in footprints:
    ref = fp.reference_field    # e.g., "C1", "U3"
    val = fp.value_field        # e.g., "100nF", "STM32F407"
    pos = fp.position           # Vector2
    layer = fp.layer            # F.Cu or B.Cu
    sheet = fp.sheet_path       # schematic sheet location
    fields = fp.texts_and_fields  # all fields including custom ones (manf#, etc.)
    attrs = fp.attributes       # DNP, BOM exclusion flags
```

**Selection Management (triggers cross-probe):**

```python
board.clear_selection()
board.add_to_selection(footprint)  # -> highlights in PCB editor
# KiCad's internal cross-probe then highlights in schematic automatically
board.get_selection()              # -> currently selected items
board.remove_from_selection(item)
```

**Cross-Probe Chain:** `kicad-python selects footprint in PCB` → `KiCad PCB editor highlights` → `KiCad internal cross-probe highlights in schematic`. No schematic API needed — the PCB → schematic link is handled by KiCad internally.

**Confidence: HIGH** — Verified against official docs and PyPI. The API is in "public beta" but the core board/footprint/selection methods are stable.

#### Limitations

- **PCB editor only**: KiCad 9's IPC API only exposes the PCB editor. Schematic API is expected in KiCad 10.
- **Requires running KiCad**: Unlike SWIG bindings, cannot read `.kicad_pcb` files offline. KiPart Search must gracefully degrade when KiCad is not running.
- **No field write-back yet**: Reading fields (reference, value, custom) is supported. Writing fields back (e.g., assigning an MPN) may require direct file manipulation or waiting for API expansion.
- **Documentation sparse**: The API is documented but minimal — reading source code is often necessary.

_Source: [KiCad Forum — IPC API discussion](https://forum.kicad.info/t/kicad-9-0-python-api-ipc-api/57236), [kicad-python Board docs](https://docs.kicad.org/kicad-python-main/board.html)_

---

### 3. Distributor APIs — DigiKey, Mouser, Nexar/Octopart

#### 3a. DigiKey API v4

**The best free parametric search API for a desktop tool.**

| Property | Value |
|----------|-------|
| **API version** | v4 (REST) |
| **Rate limit** | 120 requests/minute, 1,000 requests/day |
| **Auth** | OAuth2 — both 2-legged (client credentials) and 3-legged (authorization code) |
| **Token lifetime** | 10 min (2-legged), 30 min (3-legged) |
| **Parametric search** | ✅ `ParametricFilters` on `KeywordSearch` endpoint |
| **Free tier** | Yes — 1,000 req/day with no subscription |
| **Python package** | `digikey-api` on PyPI (peeter123/digikey-api, GPL-3.0) |

**Key capability:** The `KeywordSearch` endpoint accepts `ParametricFilters` that narrow results by category-specific electrical parameters (e.g., capacitance range, voltage rating, package). You first do a broad keyword search, get available parametric filter options from the response, then refine with specific filter values. This two-step pattern is the core of parametric search.

**OAuth2 considerations for PySide6:**
- **2-legged flow** (client credentials): Simpler — just client_id + client_secret → token. No user interaction. Suitable for basic search.
- **3-legged flow** (authorization code): Requires browser popup + localhost callback on port 8139. The `digikey-api` package handles this automatically, but PySide6 may need a custom `QWebEngineView` or system browser launch + local HTTP server to capture the callback.
- **Token refresh**: 10-min lifetime means tokens must be refreshed frequently. Cache tokens and refresh proactively.

**License concern:** The `digikey-api` package is GPL-3.0. For an MIT-licensed project, either: (a) use it as an external dependency (acceptable under GPL linking rules for Python), (b) use the Swagger-generated `digikey-apiv4` package (check its license), or (c) implement a thin wrapper using `httpx` directly against the REST endpoints.

_Source: [DigiKey Developer Portal](https://developer.digikey.com/documentation), [DigiKey OAuth docs](https://developer.digikey.com/faq/oauth-authentication-and-authorization), [digikey-api on PyPI](https://pypi.org/project/digikey-api/)_

#### 3b. Mouser API v2

**Simple integration, but keyword-only — no parametric search.**

| Property | Value |
|----------|-------|
| **API version** | v2 (REST) |
| **Auth** | API key (in query parameter or header) |
| **Parametric search** | ❌ Keyword and MPN lookup only |
| **Free tier** | Yes — free API key, limits undocumented but generous |
| **Python package** | `mouser` on PyPI (sparkmicro/mouser-api, MIT) |

**Role in KiPart Search:** Supplementary source for pricing, stock, and MPN validation after finding parts via DigiKey parametric search or JLCPCB local database. The simple API key auth makes it the easiest distributor to integrate.

**Available operations:**
- `SearchByKeyword` — text search across Mouser catalog
- `SearchByPartNumber` — exact or partial MPN lookup
- Returns: MPN, manufacturer, description, pricing tiers, stock, datasheet URL, package

**Python libraries:**
- `mouser` (sparkmicro, MIT) — clean, maintained wrapper with YAML config for API keys
- `pymouser` (AlexSartori) — alternative with similar functionality

_Source: [sparkmicro/mouser-api GitHub](https://github.com/sparkmicro/mouser-api), [mouser on PyPI](https://pypi.org/project/mouser/), [pymouser on PyPI](https://pypi.org/project/pymouser/)_

#### 3c. Nexar/Octopart GraphQL API

**Richest data but confusing tier structure — free tier is limited but includes specs.**

| Property | Value |
|----------|-------|
| **API** | GraphQL at `api.nexar.com/graphql` |
| **Auth** | OAuth2 client credentials |
| **Token URL** | `identity.nexar.com/connect/token` |
| **Parametric search** | ✅ `supSearch` query with filters, aggregations, manufacturer filtering |

**Plan comparison (verified March 2026):**

| Feature | Evaluation (Free) | Standard (Paid) | Pro (Paid) | Enterprise |
|---------|-------------------|-----------------|------------|------------|
| **Matched parts** | 100 | 2,000 | 15,000 | Custom |
| **Advanced Search** | ✅ | ✅ | ✅ | ✅ |
| **Pricing & Availability** | ✅ | ✅ | ✅ | ✅ |
| **Tech Specs** | ✅ | ❌ | ✅ (add-on) | ✅ |
| **Lifecycle Status** | ✅ | ❌ | ✅ (add-on) | ✅ |
| **Datasheets** | ✅ | ❌ | ✅ (add-on) | ✅ |
| **ECAD Modules** | ✅ | ❌ | ❌ | ✅ |

**Critical insight:** The Evaluation (Free) tier paradoxically includes specs, lifecycle, and datasheets — features that the *paid* Standard plan excludes! However, 100 matched parts is a lifetime limit, making it useful only for light MPN validation, not parametric discovery.

**Role in KiPart Search:** Optional premium source. Only worthwhile for users with Pro/Enterprise keys. The `supSearch` query provides the richest multi-distributor aggregated data (100+ distributors), parametric filtering, and lifecycle/obsolescence data. For users without Nexar keys, DigiKey + JLCPCB local DB covers the core use case.

**No mature Python wrapper** — use `httpx` + direct GraphQL queries. The obsolete `pyoctopart` package targets the deprecated REST API v3/v4.

_Source: [Nexar API](https://nexar.com/api), [Nexar Compare Plans](https://nexar.com/compare-plans), [Octopart FAQ](https://octopart.com/faq/for-api-users), [Nexar GraphQL examples](https://support.nexar.com/support/solutions/articles/101000494582-nexar-playground-graphql-query-examples)_

---

### 4. Local Data Storage — SQLite FTS5

#### Full-Text Search Engine

SQLite FTS5 (Full-Text Search 5) is a virtual table module that provides fast text search via an inverted index. It ships with Python's standard library — no additional installation required.

**Performance characteristics:**
- Inverted index maps tokens to rows, dramatically faster than `LIKE '%term%'` scans
- BM25 ranking built-in for relevance scoring
- Supports prefix queries, phrase queries, proximity queries, and boolean operators
- Column weighting allows prioritizing MPN matches over description matches

**For KiPart Search:**
- The JLCPCB/LCSC local database (~1M+ parts) uses FTS5 for keyword search across LCSC Part #, Description, MFR Part #, Package
- Cached API results can be stored in a separate SQLite table, building a growing local parametric database over time
- FTS5 handles the "zero-config baseline" — search works without any API keys

_Source: [SQLite FTS5 Extension](https://www.sqlite.org/fts5.html), [FTS5 in Practice](https://thelinuxcode.com/sqlite-full-text-search-fts5-in-practice-fast-search-ranking-and-real-world-patterns/), [Python SQLite JSON1 + FTS5](https://charlesleifer.com/blog/using-the-sqlite-json1-and-fts5-extensions-with-python/)_

#### Cache Architecture

| Data Type | TTL | Storage |
|-----------|-----|---------|
| Pricing & stock | 4 hours | SQLite table, keyed by `{source}:{mpn}` |
| Parametric data | 7–30 days | SQLite table with JSON columns for specs |
| Datasheets | Indefinite | SQLite table with URL + HTTP status |
| Search results | 24 hours | SQLite FTS5 table for re-querying cached results |

Cache keys: `{source}:{query_type}:{normalized_query}` with SHA-256 hash.

---

### 5. Development Tools and Platform

| Tool | Choice | Rationale |
|------|--------|-----------|
| **Language** | Python 3.10+ | Required by PySide6, kicad-python, and all distributor API packages |
| **HTTP client** | `httpx` | Async-capable, used in prototype, cleaner API than `requests` |
| **Package manager** | `pip` + `pyproject.toml` | Standard Python packaging |
| **Testing** | Manual initially, `pytest` later | Per project coding style preferences |
| **Credential storage** | `keyring` | OS-native secret storage |
| **Config** | JSON (`~/.kipart-search/config.json`) | Simple, no YAML dependency for config |
| **Platform** | Windows primary, cross-platform via PySide6/Qt | Qt handles platform abstractions |

---

### 6. Technology Adoption Trends

#### What's Changing (2025–2026)

- **KiCad IPC API maturation**: v0.6.0 released March 2026. Schematic API expected in KiCad 10. The ecosystem is rapidly growing — plugins are transitioning from SWIG to IPC API.
- **Nexar plan restructuring**: The free tier now includes specs/lifecycle (100 parts lifetime). Previous reports indicated these were Pro-only. This changes the value proposition for light usage.
- **DigiKey v4 stability**: The v3→v4 migration is complete. The `digikey-api` package now has v4 support via community forks.
- **JLCPCB official API**: JLCPCB recently launched an official API at `api.jlcpcb.com` — worth monitoring for replacing the unofficial scraping-based approaches.
- **PySide6 asyncio bridges**: `qasync` and `AsyncioPySide6` are gaining adoption, making it easier to use `httpx` async directly with Qt's event loop instead of manual `QThread` management.

#### Dead Ends to Avoid

- **Kitspace/PartInfo API** — company dissolved March 2026, endpoint dead
- **Octopart REST API v3/v4** — deprecated, replaced by Nexar GraphQL
- **PartKeepr** — archived July 2025
- **`pyoctopart`** — targets deprecated Octopart REST API

**Confidence: HIGH** for PySide6, DigiKey, Mouser, SQLite FTS5.
**Confidence: MEDIUM** for Nexar pricing (plan details may change), kicad-python field write-back capabilities.

---

## Integration Patterns Analysis

### API Authentication Patterns

KiPart Search integrates three distinct authentication mechanisms. Each requires different handling in a desktop application context.

#### DigiKey — OAuth2 2-Legged (Client Credentials)

The simplest OAuth2 flow for a desktop app. No user browser interaction needed for basic search.

**Token endpoint (production):** `https://api.digikey.com/v1/oauth2/token`
**Token endpoint (sandbox):** `https://sandbox-api.digikey.com/v1/oauth2/token`

```
POST /v1/oauth2/token
Content-Type: application/x-www-form-urlencoded

client_id={client_id}&client_secret={client_secret}&grant_type=client_credentials
```

**Response:** `{ "access_token": "...", "expires_in": 600, "token_type": "Bearer" }`

**Critical details:**
- Token lifetime: **10 minutes (600 seconds)**
- **No refresh token** in 2-legged flow — must request a new token every 10 minutes
- Every API request requires: `Authorization: Bearer {token}` + `X-DIGIKEY-Client-Id: {client_id}`
- Rate limits: 120 requests/minute, 1,000/day

**Integration pattern for KiPart Search:**
- Cache token with expiry timestamp
- Check expiry before each request; proactively refresh when < 60 seconds remaining
- Implement a `DigiKeyAuth` class that manages token lifecycle transparently

_Source: [DigiKey 2-Legged OAuth](https://developer.digikey.com/tutorials-and-resources/oauth-20-2-legged-flow), [DigiKey OAuth FAQ](https://developer.digikey.com/faq/oauth-authentication-and-authorization)_

#### DigiKey — OAuth2 3-Legged (Authorization Code)

Required for full access (user-specific features). More complex due to browser interaction.

**Flow:**
1. Open browser to DigiKey authorization URL with `client_id`, `redirect_uri`, `response_type=code`
2. User logs into their DigiKey account and grants consent
3. DigiKey redirects to `localhost:8139` with authorization code
4. App exchanges code for access token (30-min lifetime) + refresh token

**PySide6 integration options:**
- **Option A:** Launch system browser + run a local `http.server` on port 8139 to capture the callback. This is what the `digikey-api` package does.
- **Option B:** Use `QWebEngineView` embedded browser. More seamless UX but adds a heavy dependency (QtWebEngine).
- **Recommended:** Option A — simpler, fewer dependencies, proven pattern.

_Source: [DigiKey 3-Legged OAuth](https://developer.digikey.com/tutorials-and-resources/oauth-20-3-legged-flow)_

#### Mouser — API Key

Simplest possible auth. API key passed as query parameter or header.

```
GET https://api.mouser.com/api/v2/search/keyword?apiKey={api_key}
```

**Integration pattern:** Store key in `keyring`, inject into request headers. No token lifecycle management needed.

_Source: [sparkmicro/mouser-api](https://github.com/sparkmicro/mouser-api), [mouser on PyPI](https://pypi.org/project/mouser/)_

#### Nexar — OAuth2 Client Credentials

Similar to DigiKey 2-legged but with a different token endpoint.

**Token endpoint:** `https://identity.nexar.com/connect/token`

```
POST /connect/token
Content-Type: application/x-www-form-urlencoded

client_id={client_id}&client_secret={client_secret}&grant_type=client_credentials
```

**Integration pattern:** Same token caching approach as DigiKey. Token lifetime varies — cache based on `expires_in` from response.

_Source: [Nexar API](https://nexar.com/api), [Nexar Getting Started](https://support.nexar.com/support/solutions/articles/101000440020-make-your-first-octopart-supply-data-query)_

---

### API Communication Protocols

#### REST (DigiKey, Mouser) — JSON over HTTPS

Both DigiKey v4 and Mouser v2 use standard REST:
- Request: JSON body with search parameters
- Response: JSON with part results, pricing, parametric data
- HTTP client: `httpx` (sync for QThread workers, or async with `qasync`)

**DigiKey Parametric Search flow:**
1. `POST /products/v4/search/keyword` with broad keyword → returns results + available `ParametricFilters`
2. User selects filter values from the response's filter options
3. `POST /products/v4/search/keyword` with keyword + `ParametricFilters` → narrowed results

This two-step "search then refine" pattern is fundamental to the KiPart Search UX.

_Source: [DigiKey Developer Portal](https://developer.digikey.com/documentation)_

#### GraphQL (Nexar/Octopart) — Single endpoint

Nexar uses GraphQL at `https://api.nexar.com/graphql`. All queries go to one endpoint with the query in the POST body.

**supSearch query with parametric filtering:**

```graphql
query {
  supSearch(
    q: "capacitor"
    filters: {
      manufacturer_id: ["Murata"]
      capacitance: ["(1.5E-12__1.6E-12)"]
      numberofpins: ["2"]
    }
    sort: "capacitance"
    sortDir: Asc
    limit: 20
  ) {
    hits
    results {
      part { mpn manufacturer { name } shortDescription }
      descriptions { text }
    }
  }
}
```

**Filter syntax (verified):**
- Range: `"(min__max)"` using double underscores — e.g., `capacitance: ["(1E-6__10E-6)"]` for 1µF–10µF
- Open range: `"(__max)"` or `"(min__)"` — e.g., `numberofpins: ["(__8)"]` for ≤8 pins
- OR logic: `["value1", "value2"]` — e.g., `numberofpins: ["8", "16"]`
- SI units: Values in base SI — capacitance in Farads, resistance in Ohms

**Aggregations (facets):** `specAggs(size: 10, attributeNames: ["lifecyclestatus"])` returns bucket counts per attribute value — useful for building filter UI dynamically.

_Source: [Nexar Filter Guide](https://support.nexar.com/support/solutions/articles/101000452264-supply-sorting-and-filtering-your-queries), [Nexar GraphQL Examples](https://support.nexar.com/support/solutions/articles/101000494582-nexar-playground-graphql-query-examples)_

#### IPC Socket (KiCad) — Protobuf over nng

kicad-python communicates via `pynng` (nanomsg next generation) sockets with protobuf-encoded messages. The socket path is either:
- Set by KiCad via `KICAD_API_SOCKET` environment variable (when launched as plugin)
- Auto-discovered at the default path (standalone launch)

**Connection pattern for KiPart Search:**
```python
from kipy import KiCad

try:
    kicad = KiCad()  # auto-discovers socket
    board = kicad.get_board()
    connected = True
except Exception:
    connected = False  # KiCad not running — degrade gracefully
```

_Source: [kicad-python on PyPI](https://pypi.org/project/kicad-python/), [kicad-python docs](https://docs.kicad.org/kicad-python-main/)_

---

### Data Format Normalization

A critical integration challenge: each API returns different field names, units, and structures for the same data.

#### Part Result Normalization

| Field | DigiKey v4 | Mouser v2 | Nexar GraphQL | JLCPCB Local DB |
|-------|-----------|-----------|---------------|-----------------|
| MPN | `ManufacturerPartNumber` | `ManufacturerPartNumber` | `part.mpn` | `MFR Part #` |
| Manufacturer | `Manufacturer.Name` | `Manufacturer` | `part.manufacturer.name` | `Manufacturer` |
| Description | `ProductDescription` | `Description` | `part.shortDescription` | `Description` |
| Datasheet | `DatasheetUrl` | `DataSheetUrl` | `part.bestDatasheet.url` | N/A (via LCSC API) |
| Stock | `QuantityAvailable` | `Availability` | `seller.offers[].inventoryLevel` | `Stock` |
| Price | `UnitPrice` in `PriceBreaks[]` | `PriceBreaks[]` | `seller.offers[].prices[]` | `Price` (string) |
| Package | In `Parameters[]` | `Package` | In `part.specs[]` | `Package` |

**Normalization strategy:** Each `DataSource` adapter maps its raw response to a common `PartResult` dataclass. The adapter handles all field name translation, unit conversion, and missing field handling internally.

#### Engineering Value Normalization

Component values come in inconsistent formats: "0.1µF", "100nF", "100000pF", "0.1uF". The `units.py` module (inspired by KiBoM) normalizes these to a canonical form with a numeric value in base SI units for comparison and filtering.

---

### Multi-Source Search Orchestration

#### Parallel Worker Pattern

```
User types query
    │
    ▼
SearchOrchestrator.search(query, filters)
    │
    ├──► QThread Worker: JLCPCB (local SQLite) ──► Signal: results_ready(source, [PartResult])
    ├──► QThread Worker: DigiKey (REST API)     ──► Signal: results_ready(source, [PartResult])
    ├──► QThread Worker: Mouser (REST API)      ──► Signal: results_ready(source, [PartResult])
    └──► QThread Worker: Nexar (GraphQL API)    ──► Signal: results_ready(source, [PartResult])
    │
    ▼
ResultsModel receives signals on GUI thread
    │
    ├──► beginInsertRows() / endInsertRows()
    ├──► QSortFilterProxyModel applies active filters
    └──► QTableView updates incrementally
```

**Thread safety rule:** `QAbstractTableModel` is NOT thread-safe. Workers must emit signals with result data; the model's slot (running on GUI thread) calls `beginInsertRows()` / `endInsertRows()` to append rows safely.

**Incremental display:** JLCPCB local DB responds in milliseconds. DigiKey/Mouser respond in 1–3 seconds. Nexar may take longer. The user sees local results instantly while API results stream in.

_Source: [Qt QAbstractItemModel docs](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QAbstractItemModel.html), [Qt Thread Signals Example](https://doc.qt.io/qtforpython-6/examples/example_widgets_thread_signals.html)_

---

### Rate Limiting Strategy

| Source | Rate Limit | Strategy |
|--------|-----------|----------|
| **JLCPCB Local** | None (local DB) | No limiting needed |
| **DigiKey** | 120/min, 1,000/day | Token bucket: 2 req/sec burst, daily counter with warning at 80% |
| **Mouser** | Undocumented (generous) | Conservative: 1 req/sec |
| **Nexar** | Per-plan part limits | Count matched parts, warn when approaching plan limit |
| **LCSC enrichment** | ~100 req/min (unofficial) | Strict: 1 req/sec with backoff |

**Implementation:** Per-source rate limiter using a simple token bucket. Each `DataSource` adapter checks the limiter before making a request. On HTTP 429, exponential backoff with jitter (2s, 4s, 8s, max 30s).

---

### Integration Security Patterns

#### Credential Storage

| Credential | Storage | Fallback |
|------------|---------|----------|
| DigiKey client_id + client_secret | `keyring` (OS native) | `KIPART_DIGIKEY_CLIENT_ID` env var |
| Mouser API key | `keyring` | `KIPART_MOUSER_API_KEY` env var |
| Nexar client_id + client_secret | `keyring` | `KIPART_NEXAR_CLIENT_ID` env var |

**Security rules:**
- Never log or display credentials in UI
- Never store in plain-text config files
- Validate credentials on entry (test API call)
- `keyring` uses Windows Credential Manager / macOS Keychain / Linux Secret Service

#### Transport Security

- All API calls over HTTPS (TLS 1.2+ required by DigiKey)
- KiCad IPC API uses local socket — no network exposure
- OAuth2 tokens cached in memory only, not persisted to disk

**Confidence: HIGH** — All patterns verified against current API documentation and official examples.

---

## Architectural Patterns and Design

### System Architecture: Layered Desktop Application

KiPart Search follows a **layered architecture** with strict dependency direction — upper layers depend on lower layers, never the reverse. This is the canonical pattern for desktop applications with external data sources.

```
┌─────────────────────────────────────────────────┐
│                 GUI Layer (PySide6)              │
│  main_window, search_bar, results_table,        │
│  spec_panel, settings_dialog, verify_panel,     │
│  kicad_bridge                                   │
├─────────────────────────────────────────────────┤
│              Core Layer (zero GUI deps)          │
│  search orchestrator, verify engine,             │
│  models (PartResult, ParametricValue)           │
├─────────────────────────────────────────────────┤
│             Data Source Layer (adapters)         │
│  DataSource ABC → JLCPCB, DigiKey, Mouser,     │
│  Nexar adapters                                 │
├─────────────────────────────────────────────────┤
│             Infrastructure Layer                 │
│  SQLite cache, keyring credentials, units.py,   │
│  rate limiters, HTTP client (httpx)             │
└─────────────────────────────────────────────────┘
```

**Key constraint:** The `core/` package has zero GUI dependencies. It can be imported by the CLI, tests, or a future KiCad wxPython shim. All PySide6 code lives in `gui/`. All distributor API code lives in `core/sources.py`.

_Source: Pattern verified across [KiCost distributor architecture](https://github.com/hildogjr/KiCost), [InvenTree SupplierMixin](https://github.com/inventree/InvenTree), [kicad-jlcpcb-tools standalone_impl.py](https://github.com/Bouni/kicad-jlcpcb-tools)_

---

### Design Pattern: Adapter / Strategy (DataSource ABC)

The core architectural pattern is the **Adapter pattern** implemented via Python's `ABC` (Abstract Base Class). Each distributor is a pluggable adapter that normalizes its API's idiosyncrasies behind a common interface.

```python
class DataSource(ABC):
    """Abstract base for all component data sources."""

    @abstractmethod
    def search(self, query: str, filters: dict, limit: int) -> list[PartResult]: ...

    @abstractmethod
    def get_part(self, mpn: str, manufacturer: str) -> PartResult: ...

    @abstractmethod
    def is_configured(self) -> bool: ...

    key_fields: list[str]   # required credential field names
    needs_key: bool          # whether API key is required
```

**Why ABC over Protocol:** For KiPart Search, `ABC` is preferred over `typing.Protocol` because:
- Adapters are explicitly registered, not duck-typed
- `ABC` enforces implementation at class definition time (fails fast)
- The `is_configured()` check pattern requires concrete interface definition
- KiCost and InvenTree both use this approach — proven in the domain

**Adapter registration:** Adapters are instantiated at startup based on configuration. Only adapters with `is_configured() == True` participate in searches. This allows graceful degradation — if no API keys are configured, only the JLCPCB local database is active.

_Source: [Python ABC docs](https://docs.python.org/3/library/abc.html), [Adapter Pattern in Python](https://codesignal.com/learn/courses/structural-patterns-in-python/lessons/introduction-to-the-adapter-pattern-in-python), [KiCost distributor_class](https://github.com/hildogjr/KiCost)_

---

### Design Pattern: Qt ModelView for Results

Qt's **ModelView** pattern (Qt's variant of MVC where View and Controller are merged) is the backbone of the results display.

```
┌──────────────┐    ┌─────────────────────┐    ┌─────────────┐
│  Data Source  │───►│ QAbstractTableModel │───►│ QSortFilter  │───► QTableView
│  Workers      │    │ (ResultsModel)      │    │ ProxyModel   │
│  (QThreads)   │    │                     │    │ (filtering)  │
└──────────────┘    └─────────────────────┘    └─────────────┘
     signals              data store              client-side
                                                  filtering
```

**Three components:**

1. **ResultsModel** (`QAbstractTableModel` subclass): Holds `list[PartResult]`. Workers emit signals → model's slot calls `beginInsertRows()`/`endInsertRows()`. Provides `data()`, `rowCount()`, `columnCount()`, `headerData()` for the view.

2. **FilterProxyModel** (`QSortFilterProxyModel` subclass): Overrides `filterAcceptsRow()` for multi-column parametric filtering (capacitance range, voltage range, package match). Overrides `lessThan()` for unit-aware sorting (so "100nF" sorts correctly against "0.1µF"). Filtering is instant — no API calls needed.

3. **QTableView**: Displays the proxy model. Column resizing, sorting by header click, selection triggers KiCad cross-probe.

**Incremental population:** The model uses `canFetchMore()` / `fetchMore()` for lazy loading if result sets are very large, plus `beginInsertRows()`/`endInsertRows()` for streaming results from background workers.

_Source: [PythonGUIs ModelView Tutorial](https://www.pythonguis.com/tutorials/pyside6-modelview-architecture/), [Qt QAbstractTableModel docs](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QAbstractTableModel.html)_

---

### Design Pattern: Graceful Degradation

KiPart Search has multiple optional dependencies that may or may not be available at runtime. The architecture must degrade gracefully at every level.

| Dependency | When Available | When Unavailable | Degraded Behavior |
|------------|---------------|-----------------|-------------------|
| **KiCad** | Running with IPC API enabled | Not running or API disabled | All search works. Click-to-highlight and BOM verification disabled. Status bar shows "KiCad: disconnected" |
| **DigiKey keys** | User configured client_id + secret | No credentials | DigiKey adapter excluded from search. Other sources still active |
| **Mouser key** | User configured API key | No credentials | Mouser adapter excluded. Other sources still active |
| **Nexar keys** | User configured client_id + secret | No credentials | Nexar adapter excluded. Other sources still active |
| **Internet** | Network available | Offline | Only JLCPCB local DB active. Cached results from previous API calls served with staleness indicator |
| **JLCPCB DB** | Downloaded | Not yet downloaded | Prompt user to download. Other API sources still work if configured |

**Implementation pattern:**
- Each adapter's `is_configured()` gates its participation
- KiCad bridge uses try/except on connection with periodic reconnect attempts
- Cache serves stale data with visual indicator when source is unreachable
- Status bar shows per-source connection state (green/amber/red icons)

_Source: [Graceful Degradation patterns](https://dev.to/lovestaco/graceful-degradation-keeping-your-app-functional-when-things-go-south-jgj), [kicad-jlcpcb-tools standalone_impl.py](https://github.com/Bouni/kicad-jlcpcb-tools)_

---

### Design Pattern: Cache-Aside with Per-Source TTL

The caching layer sits between adapters and the network, using the **cache-aside** pattern: check cache first, on miss → call API → store result.

```python
def search(self, query, filters, limit):
    cache_key = self._make_key(query, filters)
    cached = self.cache.get(cache_key)
    if cached and not cached.is_expired:
        return cached.data

    results = self._api_call(query, filters, limit)
    self.cache.put(cache_key, results, ttl=self.ttl)
    return results
```

**SQLite-backed, not in-memory:** Unlike `functools.lru_cache` or `cachetools`, the cache persists across app restarts. This is critical for a desktop app — the user shouldn't re-fetch the same DigiKey results every time they relaunch.

**Per-source TTL:** Different data types have different freshness requirements. Pricing changes hourly; parametric specs change rarely. The cache respects this.

**Offline mode:** When an API is unreachable, serve stale cached results with a visual "stale data" indicator rather than showing nothing.

_Source: [LiteCache — SQLite-backed cache](https://github.com/colingrady/LiteCache), [cachew — SQLite cache with decorators](https://github.com/karlicoss/cachew), [cachetools docs](https://cachetools.readthedocs.io/)_

---

### Design Pattern: Search Orchestrator (Mediator)

The `SearchOrchestrator` acts as a **Mediator** between the GUI and multiple data source adapters. It:

1. Receives a search request from the GUI
2. Fans out to all configured adapters in parallel (one QThread per adapter)
3. Collects incremental results via signals
4. Deduplicates results by MPN + manufacturer
5. Merges pricing from multiple sources for the same part
6. Forwards merged results to the ResultsModel

**Deduplication strategy:** When the same MPN appears from multiple sources, merge into a single `PartResult` with offers from all sources. Priority for parametric data: Nexar > DigiKey > Mouser > JLCPCB (based on data richness).

---

### Scalability and Maintainability Considerations

#### Adding New Data Sources

The adapter pattern makes adding a new distributor straightforward:
1. Create a new class inheriting from `DataSource`
2. Implement `search()`, `get_part()`, `is_configured()`
3. Define `key_fields` for credential management
4. Register the adapter in the configuration

No changes to the orchestrator, GUI, or cache layer are needed.

#### Performance Patterns

| Concern | Pattern | Implementation |
|---------|---------|----------------|
| **Slow API responses** | Background QThread workers | Users see partial results immediately |
| **Large local DB** | SQLite FTS5 with indexed columns | Sub-100ms search on 1M+ parts |
| **Frequent token refresh** | Proactive token caching | Refresh DigiKey token when < 60s remaining |
| **Result set rendering** | Virtual scrolling via QTableView | Only visible rows are rendered |
| **Repeated searches** | Cache-aside with SQLite persistence | Instant results for cached queries |

---

### Data Architecture: PartResult Model

The central data model that all adapters normalize to:

```python
@dataclass
class PartResult:
    mpn: str
    manufacturer: str
    description: str
    datasheet_url: str | None
    category: str | None
    specs: dict[str, ParametricValue]  # normalized parametric data
    offers: list[Offer]                # per-distributor pricing/stock
    lifecycle: str | None              # Active, NRND, EOL, Obsolete
    source: str                        # which adapter provided this

@dataclass
class ParametricValue:
    name: str           # canonical name (e.g., "Capacitance")
    value: float        # numeric value in base SI units
    unit: str           # SI unit (e.g., "F", "Ω", "V")
    display: str        # human-readable (e.g., "100nF")

@dataclass
class Offer:
    source: str         # "digikey", "mouser", "nexar", "jlcpcb"
    sku: str
    stock: int
    moq: int
    price_breaks: list[PriceBreak]
    currency: str
    url: str

@dataclass
class PriceBreak:
    quantity: int
    unit_price: float
```

This model is inspired by KiCost's `DistData` (for pricing) and Part-DB's parameter model (for min/typ/max specs with units). It's richer than either alone.

_Source: Data model patterns from [KiCost global_vars.py](https://github.com/hildogjr/KiCost), [Part-DB parameter model](https://github.com/Part-DB/Part-DB-server), [InvenTree SupplierPart model](https://github.com/inventree/InvenTree)_

**Confidence: HIGH** — All patterns derived from proven open-source implementations in the same domain, verified against current documentation.

---

## Implementation Approaches and Technology Adoption

### Project Setup and Structure

**Recommended structure (src layout with pyproject.toml):**

```
kipart-search/
├── pyproject.toml          # Package metadata, dependencies, entry points
├── README.md
├── CLAUDE.md
├── src/
│   └── kipart_search/
│       ├── __init__.py
│       ├── __main__.py     # Entry point: python -m kipart_search
│       ├── core/           # Zero GUI dependencies
│       │   ├── models.py   # PartResult, ParametricValue, PriceBreak, Offer
│       │   ├── sources.py  # DataSource ABC + all adapters
│       │   ├── cache.py    # SQLite cache with per-source TTL
│       │   ├── search.py   # Search orchestrator (parallel queries)
│       │   ├── units.py    # Engineering value normalisation
│       │   └── verify.py   # BOM verification engine
│       ├── gui/            # PySide6 standalone app
│       │   ├── main_window.py
│       │   ├── search_bar.py
│       │   ├── results_table.py
│       │   ├── spec_panel.py
│       │   ├── settings_dialog.py
│       │   ├── verify_panel.py
│       │   └── kicad_bridge.py
│       └── cli/            # Optional CLI entry point
│           └── __main__.py
└── tests/
```

**Why src layout:** The `src/` layout is the current Python best practice (2025+). It prevents accidental imports of the uninstalled package during development, ensures tests run against the installed version, and is the default for modern tools like Poetry and Flit.

_Source: [Python Packaging — src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/), [Real Python — project layout](https://realpython.com/ref/best-practices/project-layout/)_

---

### Dependency Management and Licensing

**Core dependencies (MIT-compatible):**

| Package | Purpose | License | Required |
|---------|---------|---------|----------|
| `httpx` | HTTP client for API calls | BSD-3 | Yes |
| `keyring` | OS-native credential storage | MIT | Yes |
| `PySide6-Essentials` | Qt6 GUI (lighter than full PySide6) | LGPL-3.0 | Yes (GUI) |
| `kicad-python` | KiCad IPC API bindings | MIT | Optional |

**License-sensitive dependencies:**

| Package | Purpose | License | Risk | Mitigation |
|---------|---------|---------|------|------------|
| `digikey-api` | DigiKey v4 wrapper | **GPL-3.0** | Copyleft — if bundled with PyInstaller, the entire app may need GPL licensing | **Option A:** Use as pip dependency only (user installs separately). **Option B:** Write a thin `httpx`-based DigiKey adapter directly against the REST API (no GPL dependency). **Recommended: Option B** |
| `mouser` | Mouser API wrapper | MIT | None | Safe to use directly |

**Critical licensing decision:** The `digikey-api` package is GPL-3.0. For an MIT-licensed project:
- Using it as a Python `pip install` dependency is legally debatable — the FSF considers dynamic linking to create a derivative work under GPL
- **Safest approach:** Write a thin DigiKey adapter using `httpx` directly against DigiKey's REST API. The OAuth2 flow and search endpoints are well-documented. This avoids the GPL question entirely.
- The existing landscape report and DigiKey API docs provide enough detail to implement this without the GPL wrapper.

_Source: [GPL/LGPL compliance with PyInstaller](https://velovix.github.io/post/lgpl-gpl-license-compliance-with-pyinstaller/), [Python packaging licensing guide](https://packaging.python.org/en/latest/guides/licensing-examples-and-user-scenarios/)_

---

### JLCPCB Local Database — Implementation Options

Two options for the zero-config offline database:

**Option A: kicad-jlcpcb-tools database (chunked download)**
- Pre-built SQLite FTS5 database hosted at `bouni.github.io/kicad-jlcpcb-tools/`
- ~11 chunks, ~76MB each (~840MB total compressed)
- Maintained by the kicad-jlcpcb-tools GitHub workflow
- Pros: Proven, widely used, includes stock/pricing
- Cons: Large download, chunks can 404 if hosting changes

**Option B: CDFER/jlcpcb-parts-database (curated, smaller)**
- Automatically updated SQLite database filtered to in-stock parts only
- Sources data from yaqwsx/jlcparts, processes with FTS index
- Removes low-stock components (<5 units)
- Includes CSV of basic/preferred parts
- Pros: Smaller, curated, actively maintained
- Cons: Less complete (filters out low-stock items)

**Recommended: Option A as primary, Option B as alternative.** Option A provides the most complete dataset. The chunked download pattern with progress tracking and resume capability is already proven in kicad-jlcpcb-tools.

_Source: [kicad-jlcpcb-tools library.py](https://github.com/Bouni/kicad-jlcpcb-tools/blob/main/library.py), [CDFER/jlcpcb-parts-database](https://github.com/CDFER/jlcpcb-parts-database)_

---

### DigiKey API — Developer Registration and Testing

**Registration process (verified):**
1. Register at https://developer.digikey.com/
2. Create an organization and add members
3. Create a Sandbox application — receives client_id + client_secret
4. Set OAuth callback to `https://localhost:8139/digikey_callback`
5. Test against Sandbox environment (valid response structure, not production data)
6. When ready, create a Production application

**Sandbox vs Production:**
- Sandbox: `https://sandbox-api.digikey.com/` — returns valid structure with test data
- Production: `https://api.digikey.com/` — real data, real rate limits

**Development workflow:** Build and test against Sandbox first (no rate limit concerns), then switch to Production by changing the base URL and using production credentials.

_Source: [DigiKey Developer Portal](https://developer.digikey.com/), [DigiKey Sandbox Guide](https://developer.digikey.com/tutorials-and-resources/developer-and-sandbox)_

---

### Packaging and Distribution

**Phase 1: pip install (PyPI)**
```bash
pip install kipart-search
python -m kipart_search  # or `kipart-search` CLI entry point
```

This is the primary distribution method. Users install via pip, which handles all dependencies. `pyproject.toml` defines entry points for both GUI and CLI.

**Phase 2: Standalone executable (optional, later)**

| Tool | Pros | Cons |
|------|------|------|
| **pyside6-deploy** | Official Qt tool, optimized for PySide6 | Less mature than alternatives |
| **PyInstaller** | Largest ecosystem, easiest to start | Slower startup (~50s reported), large bundle |
| **cx_Freeze** | Faster startup (~8s reported) | Recent PySide6 compatibility issues |
| **Nuitka** | Best performance (compiles to C) | Longer build times, more complex setup |

**Recommendation:** Start with pip/PyPI only. Add PyInstaller or Nuitka packaging later if users request standalone executables. The `PySide6-Essentials` package (instead of full `PySide6`) reduces bundle size by excluding QtWebEngine, Qt3D, and other heavy modules.

_Source: [PythonGUIs Packaging Guide](https://www.pythonguis.com/tutorials/packaging-pyside6-applications-windows-pyinstaller-installforge/), [Qt Deployment docs](https://doc.qt.io/qtforpython-6/deployment/index.html), [2026 PyInstaller vs cx_Freeze vs Nuitka](https://ahmedsyntax.com/2026-comparison-pyinstaller-vs-cx-freeze-vs-nui/)_

---

### Testing Strategy

**Phase 1 (current): Manual testing**
- Per project coding style preferences, start with manual testing
- Use DigiKey Sandbox for API integration testing without consuming rate limits
- Test KiCad bridge against a running KiCad instance with a test project

**Phase 2 (later): pytest**
- Unit tests for `core/` (models, units, cache, search orchestrator)
- Mock API responses for adapter tests (avoid hitting real APIs in CI)
- Integration tests for SQLite FTS5 queries against a small test database
- No GUI tests initially — test core logic only

---

### Risk Assessment and Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **DigiKey OAuth complexity** | Medium | High (blocks primary parametric search) | Start with 2-legged flow (simpler). Test against Sandbox first. Fall back to keyword search if OAuth fails. |
| **JLCPCB database hosting changes** | Low | Medium (breaks zero-config baseline) | Cache downloaded DB locally. Support alternative DB sources (CDFER). Monitor for 404s. |
| **kicad-python API breaking changes** | Medium | Low (only affects KiCad integration) | Pin kicad-python version. KiCad bridge is isolated — changes don't affect search. |
| **Nexar plan tier changes** | Medium | Low (optional source) | Nexar is always optional. Document plan requirements clearly. |
| **GPL licensing contamination** | High | High (forces project license change) | Avoid `digikey-api` GPL package. Write thin `httpx` adapter instead. |
| **Rate limit exhaustion** | Medium | Medium (degraded search) | Daily counter with warnings. Cache aggressively. Educate users about limits in settings. |
| **PySide6 version compatibility** | Low | Medium | Use `PySide6-Essentials` for lighter footprint. Pin major version in pyproject.toml. |

---

## Technical Research Recommendations

### Implementation Roadmap

1. **Foundation**: Project structure, `pyproject.toml`, `core/models.py`, `core/units.py`
2. **Local search**: JLCPCB SQLite FTS5 database download + search (`core/sources.py` JLCPCB adapter)
3. **GUI shell**: PySide6 main window, search bar, results table with ModelView pattern
4. **DigiKey adapter**: OAuth2 2-legged flow with `httpx` (no GPL dependency), parametric search
5. **Mouser adapter**: Simple API key auth, keyword search supplement
6. **Cache layer**: SQLite-backed cache with per-source TTL
7. **KiCad bridge**: IPC API connection, footprint selection, cross-probe
8. **BOM verification**: `core/verify.py` + `gui/verify_panel.py`
9. **Nexar adapter**: Optional, for users with Pro keys
10. **Packaging**: PyPI distribution, then standalone executable if requested

### Technology Stack Recommendations (Confirmed)

| Layer | Technology | Confidence |
|-------|-----------|------------|
| **Language** | Python 3.10+ | HIGH |
| **GUI** | PySide6-Essentials | HIGH |
| **HTTP client** | httpx | HIGH |
| **Local DB** | SQLite FTS5 (stdlib) | HIGH |
| **Credentials** | keyring | HIGH |
| **KiCad integration** | kicad-python (optional) | HIGH |
| **DigiKey** | Custom httpx adapter (avoid GPL) | HIGH |
| **Mouser** | `mouser` PyPI package (MIT) | HIGH |
| **Nexar** | Custom httpx + GraphQL (optional) | MEDIUM |
| **Packaging** | pip/PyPI primary, PyInstaller later | HIGH |

### Key Decision: Avoid GPL Dependencies

The single most important implementation decision is to **not use the `digikey-api` GPL-3.0 package**. Instead, write a thin DigiKey adapter using `httpx` directly against DigiKey's REST API. The OAuth2 2-legged flow is straightforward, and the parametric search endpoints are well-documented. This keeps the project MIT-licensed without legal ambiguity.

---

## Research Synthesis

### Executive Summary

**KiPart Search fills a clear gap in the open-source electronics tooling ecosystem.** No existing tool combines parametric component search across multiple free distributor APIs in a desktop GUI with KiCad integration. Every significant technical piece exists in reusable form — but nobody has assembled them. This research confirms the technology stack is mature, the APIs are accessible, and the architectural patterns are proven.

**The four technology pillars are solid:**

1. **PySide6** provides a complete desktop framework with QThread workers for parallel API calls, ModelView architecture for incremental result display, and QSortFilterProxyModel for instant client-side parametric filtering. The technology is mature, well-documented, and actively maintained by The Qt Company.

2. **kicad-python v0.6.0** (released March 2026) exposes board/footprint access and selection management via the KiCad 9+ IPC API. Selecting a footprint programmatically triggers KiCad's internal cross-probe to the schematic — no schematic API needed. The library is official, maintained by the KiCad team, and stable for the read/select operations KiPart Search requires.

3. **Distributor APIs** offer viable free tiers: DigiKey v4 provides 1,000 requests/day with true parametric search via `ParametricFilters`. Mouser offers simple keyword search with a free API key. Nexar/Octopart provides the richest multi-distributor data but requires paid Pro keys for practical use. The JLCPCB/LCSC offline database (~1M+ parts) gives a zero-config baseline requiring no API keys at all.

4. **SQLite FTS5** ships with Python's standard library, provides sub-100ms full-text search with BM25 ranking on million-row databases, and serves as both the local search engine and the persistent cache layer.

**Key Technical Findings:**

- **GPL licensing trap**: The `digikey-api` Python package is GPL-3.0. Using it in an MIT-licensed project creates legal ambiguity. Write a thin `httpx`-based adapter instead — the DigiKey REST API is well-documented enough.
- **Nexar pricing inversion**: The free Evaluation tier (100 parts lifetime) paradoxically includes specs, lifecycle, and datasheets — features the paid Standard plan excludes. Only the Pro tier restores them.
- **DigiKey parametric search is a two-step flow**: Broad keyword search returns available filter options; user refines with specific parametric values. This shapes the entire search UX.
- **Thread safety is critical**: `QAbstractTableModel` must only be modified on the GUI thread. Background workers emit signals; the model's slot appends rows safely.
- **Graceful degradation is architectural**: Every external dependency (KiCad, API keys, internet, local DB) can be absent — the app continues working with whatever is available.

**Strategic Technical Recommendations:**

1. **Avoid GPL**: Write custom DigiKey and Nexar adapters using `httpx` directly
2. **Start local**: JLCPCB offline database first — delivers value with zero API keys
3. **Incremental display**: QThread per source with signal-based result streaming
4. **Cache everything**: SQLite-backed cache persists across app restarts, serves stale data offline
5. **Isolate KiCad**: Bridge module gracefully degrades when KiCad is not running

---

### Table of Contents

1. [Research Overview](#research-overview)
2. [Technical Research Scope Confirmation](#technical-research-scope-confirmation)
3. [Technology Stack Analysis](#technology-stack-analysis)
   - 3.1 PySide6 — Desktop GUI Framework
   - 3.2 KiCad IPC API — kicad-python Library
   - 3.3 Distributor APIs — DigiKey, Mouser, Nexar/Octopart
   - 3.4 Local Data Storage — SQLite FTS5
   - 3.5 Development Tools and Platform
   - 3.6 Technology Adoption Trends
4. [Integration Patterns Analysis](#integration-patterns-analysis)
   - 4.1 API Authentication Patterns
   - 4.2 API Communication Protocols
   - 4.3 Data Format Normalization
   - 4.4 Multi-Source Search Orchestration
   - 4.5 Rate Limiting Strategy
   - 4.6 Integration Security Patterns
5. [Architectural Patterns and Design](#architectural-patterns-and-design)
   - 5.1 Layered Desktop Application Architecture
   - 5.2 Adapter / Strategy (DataSource ABC)
   - 5.3 Qt ModelView for Results
   - 5.4 Graceful Degradation
   - 5.5 Cache-Aside with Per-Source TTL
   - 5.6 Search Orchestrator (Mediator)
   - 5.7 PartResult Data Model
6. [Implementation Approaches and Technology Adoption](#implementation-approaches-and-technology-adoption)
   - 6.1 Project Setup and Structure
   - 6.2 Dependency Management and Licensing
   - 6.3 JLCPCB Local Database Options
   - 6.4 DigiKey Developer Registration
   - 6.5 Packaging and Distribution
   - 6.6 Testing Strategy
   - 6.7 Risk Assessment and Mitigation
7. [Technical Research Recommendations](#technical-research-recommendations)
8. [Research Synthesis](#research-synthesis) (this section)
9. [Source Documentation](#source-documentation)

---

### Technical Research Methodology

**Research approach:**
- Combined existing open-source landscape analysis (compass artifact) with live web verification
- All API endpoints, pricing tiers, and library versions verified against current official sources (March 2026)
- Multiple sources consulted for contested claims (e.g., Nexar plan features verified against nexar.com/compare-plans)
- Confidence levels assigned: HIGH (verified against official docs), MEDIUM (single source or rapidly changing), LOW (unverified)

**Original research goals:** Broad sweep of core technologies to inform architecture decisions — PySide6 desktop patterns, KiCad IPC API capabilities, and distributor API integration.

**Achieved objectives:**
- Complete technology stack evaluation with version-specific details
- Integration patterns documented with code examples and verified API syntax
- Architectural patterns mapped to proven open-source implementations
- Implementation roadmap with risk assessment and licensing analysis
- Critical discovery: GPL licensing trap identified and mitigated before implementation

---

### Future Technical Outlook

**Near-term (2026):**
- KiCad 10 expected to add schematic API to IPC API — will enable direct schematic field editing
- JLCPCB official API (`api.jlcpcb.com`) may replace scraping-based approaches
- PySide6 asyncio bridges (`qasync`, `AsyncioPySide6`) gaining adoption — may simplify threading model

**Medium-term (2027–2028):**
- Distributor APIs likely to consolidate around OAuth2 + REST/GraphQL
- kicad-python will mature — field write-back (MPN assignment) likely to be supported
- Potential for a common open-source component data model standard

---

## Source Documentation

### Primary Sources (Official Documentation)

| Source | URL | Accessed |
|--------|-----|----------|
| kicad-python PyPI | https://pypi.org/project/kicad-python/ | 2026-03-17 |
| kicad-python Board docs | https://docs.kicad.org/kicad-python-main/board.html | 2026-03-17 |
| DigiKey Developer Portal | https://developer.digikey.com/documentation | 2026-03-17 |
| DigiKey OAuth 2-Legged | https://developer.digikey.com/tutorials-and-resources/oauth-20-2-legged-flow | 2026-03-17 |
| DigiKey Sandbox Guide | https://developer.digikey.com/tutorials-and-resources/developer-and-sandbox | 2026-03-17 |
| Nexar API Plans | https://nexar.com/compare-plans | 2026-03-17 |
| Nexar Filter Guide | https://support.nexar.com/support/solutions/articles/101000452264 | 2026-03-17 |
| Nexar GraphQL Examples | https://support.nexar.com/support/solutions/articles/101000494582 | 2026-03-17 |
| Qt QAbstractItemModel | https://doc.qt.io/qtforpython-6/PySide6/QtCore/QAbstractItemModel.html | 2026-03-17 |
| Qt QThread docs | https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThread.html | 2026-03-17 |
| SQLite FTS5 Extension | https://www.sqlite.org/fts5.html | 2026-03-17 |
| Python Packaging src layout | https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/ | 2026-03-17 |

### Open-Source Project References

| Project | Stars | License | Relevance |
|---------|-------|---------|-----------|
| kicad-jlcpcb-tools | ~1,800 | MIT | Local JLCPCB/LCSC database pattern |
| KiCost | ~590 | MIT | Distributor API abstraction, cache pattern |
| JLCParts | ~741 | MIT | Parametric field extraction pipeline |
| InvenTree | ~6,200 | MIT | SupplierMixin, data model reference |
| Part-DB | ~1,477 | AGPL | Parametric data model reference |
| sparkmicro/mouser-api | ~39 | MIT | Mouser API wrapper |
| CDFER/jlcpcb-parts-database | — | — | Alternative curated JLCPCB database |
| qasync | — | BSD | PySide6 asyncio bridge |

### Secondary Sources

| Source | URL |
|--------|-----|
| PythonGUIs Multithreading Tutorial | https://www.pythonguis.com/tutorials/multithreading-pyside6-applications-qthreadpool/ |
| PythonGUIs ModelView Tutorial | https://www.pythonguis.com/tutorials/pyside6-modelview-architecture/ |
| PythonGUIs Packaging Guide | https://www.pythonguis.com/tutorials/packaging-pyside6-applications-windows-pyinstaller-installforge/ |
| KiCad Forum IPC API Discussion | https://forum.kicad.info/t/kicad-9-0-python-api-ipc-api/57236 |
| FTS5 in Practice | https://thelinuxcode.com/sqlite-full-text-search-fts5-in-practice-fast-search-ranking-and-real-world-patterns/ |
| Python SQLite JSON1 + FTS5 | https://charlesleifer.com/blog/using-the-sqlite-json1-and-fts5-extensions-with-python/ |
| GPL/LGPL PyInstaller Compliance | https://velovix.github.io/post/lgpl-gpl-license-compliance-with-pyinstaller/ |
| 2026 PyInstaller vs cx_Freeze vs Nuitka | https://ahmedsyntax.com/2026-comparison-pyinstaller-vs-cx-freeze-vs-nui/ |

---

**Technical Research Completion Date:** 2026-03-17
**Research Period:** Comprehensive technical analysis based on current web data
**Source Verification:** All critical technical facts verified against official documentation
**Technical Confidence Level:** HIGH — based on multiple authoritative sources with live verification

_This technical research document serves as the authoritative reference for KiPart Search architecture decisions and provides the foundation for the solution design phase._
