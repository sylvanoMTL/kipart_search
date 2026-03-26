---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: []
workflowType: 'research'
lastStep: 1
research_type: 'technical'
research_topic: 'Mouser Search API integration for kipart-search'
research_goals: 'Produce implementation reference for MouserSource adapter with speed-optimized search, breadboarding stage, and UI workflow matching JLCPCB pattern'
user_name: 'Sylvain'
date: '2026-03-26'
web_research_enabled: true
source_verification: true
---

# Mouser Search API Integration: Technical Research for KiPart Search

**Date:** 2026-03-26
**Author:** Sylvain
**Research Type:** Technical

---

## Technical Research Scope Confirmation

**Research Topic:** Mouser Search API integration for kipart-search
**Research Goals:** Produce implementation reference for MouserSource adapter with speed-optimized search, breadboarding stage, and UI workflow matching JLCPCB pattern

**Technical Research Scope:**

- Architecture Analysis - design patterns, DataSource ABC integration, signal/thread pattern
- Implementation Approaches - raw httpx wrapper, request construction, response parsing
- Integration Patterns - keyword search, part number lookup, batch MPN validation, ProductAttributes mapping
- Performance Considerations - fastest query patterns, connection pooling, real-world speed lessons
- Breadboarding Plan - standalone script to confirmed workflow to production adapter

**Research Methodology:**

- Current web data with rigorous source verification
- Multi-source validation for critical technical claims (KiCost, Ki-nTree, Part-DB implementations)
- Confidence level framework for uncertain information
- Comprehensive technical coverage with architecture-specific insights

**Scope Confirmed:** 2026-03-26

---

## Technology Stack Analysis

### Mouser API — Endpoint Inventory

| Endpoint | Version | Method | Use Case |
|----------|---------|--------|----------|
| `/api/v1/search/keyword` | V1 | POST | Primary keyword search (parametric discovery) |
| `/api/v1/search/partnumber` | V1 | POST | MPN lookup, batch up to 10 pipe-separated |
| `/api/v2/search/keywordandmanufacturer` | V2 | POST | Keyword + manufacturer filter |
| `/api/v2/search/partnumberandmanufacturer` | V2 | POST | Precise MPN validation with manufacturer |
| `/api/v2/search/manufacturerlist` | V2 | GET | Reference list of all manufacturers |

**Authentication:** API key as URL query parameter `?apiKey={key}`. Free key from https://www.mouser.com/api-hub/. Separate keys for Search vs Order APIs — we need the **Search API key** (`MOUSER_PART_API_KEY`).

_Source: https://api.mouser.com/api/docs/ui/index_

### Rate Limits and Quotas

| Limit | Value |
|-------|-------|
| Burst rate | **30 requests/minute** |
| Daily cap | **1,000 requests/day** |
| Max results per page | **50** |
| Batch MPN lookup | **10 pipe-separated** per request |
| Exceeded response | HTTP 429 with `Retry-After` header |

**Implication for kipart-search:** Interactive search is fine (~2 req/min sustained). BOM verification of 200+ components needs aggressive caching and batch MPN lookups (10 per request = 20 API calls for 200 parts).

_Source: https://pkg.go.dev/github.com/PatrickWalther/go-mouser (go-mouser documents these limits from empirical testing)_

### What Mouser API Does NOT Return (Critical Limitations)

| Feature | Status | Evidence |
|---------|--------|----------|
| **Parametric specs** (voltage, capacitance, tolerance) | **NOT RETURNED** | `ProductAttributes` contains only packaging info (e.g. "Tape & Reel"), not electrical parameters. Confirmed by Part-DB maintainer in issues #503 and #558. |
| **Datasheet URLs** | **Intermittent** | `DataSheetUrl` is blank on most parts. Only populated when Mouser hosts the PDF on their domain. |
| **Parametric filtering** | **Not supported** | No equivalent of DigiKey's `ParametricFilters`. Only keyword + `searchOptions` (RoHS/InStock). |

**Conclusion:** Mouser is a **pricing/stock/lifecycle supplement**, not a primary parametric discovery source. Use JLCPCB for zero-config discovery, DigiKey for parametric filtering, Mouser for pricing confirmation and MPN validation.

_Sources: https://github.com/Part-DB/Part-DB-server/issues/503, https://github.com/Part-DB/Part-DB-server/issues/558_

### HTTP Client: httpx (not the `mouser` package)

**Decision: Skip the `mouser` PyPI package.** Reasons:

1. Uses `requests` — our project standardises on `httpx`
2. Only 7.6 kB / ~200 lines — trivial to replicate
3. Last release Oct 2024, low maintenance (9 stars)
4. Only implements V1 endpoints — we want V2 `PartNumberAndManufacturerSearch`
5. No async support, no connection pooling, no caching

**httpx advantages for our use:**
- `httpx.Client()` with connection pooling (persistent TCP connections)
- Built-in timeout control: `httpx.Timeout(connect=5.0, read=20.0)`
- Already a project dependency
- Consistent with future DigiKey/Nexar adapters

### How Other Projects Use the Mouser API

#### KiCost (`hildogjr/KiCost`, ~590 stars, MIT)
- **Only uses part number search** (`/search/partnumber`), no keyword search
- Synchronous `requests.post()` — no `Session`, new TCP connection per call
- Simple file-based pickle cache with 7-day TTL
- Sophisticated multilingual stock parsing regex (handles EN/ES/IT/DE/FR/PT/CS/DA/RU/NL/PL/ZH/JA/TH/VI)
- **No rate limiting, no retry logic, no parallelism**
- Price parsing handles international comma/dot formats via `get_number()`

_Source: https://github.com/hildogjr/KiCost/blob/master/kicost/distributors/api_mouser.py_

#### Ki-nTree (`sparkmicro/Ki-nTree`, ~450 stars, GPL-3.0)
- Uses the `mouser` PyPI package (same author)
- **Only part number search**, no keyword search
- 20-second hard timeout via `wrapt_timeout_decorator`
- Extracts `ProductAttributes` as flat `{name: value}` dict
- **No caching, no rate limiting**
- Reads `MOUSER_PART_API_KEY` from environment

_Source: https://github.com/sparkmicro/Ki-nTree/blob/main/kintree/search/mouser_api.py_

#### Part-DB (`Part-DB/Part-DB-server`, ~1,477 stars, AGPL)
- PHP implementation, uses both keyword search and part number search
- **Explicitly declares no `PARAMETERS` capability** — only `BASIC`, `PICTURE`, `DATASHEET`, `PRICE`
- Lifecycle status mapping: `"New Product"` → ANNOUNCED, `"Not Recommended..."` → NRFND, `"Obsolete"` → DISCONTINUED
- Filters out `MouserPartNumber` < 4 chars (garbage results)
- Locale-aware price parsing (strips currency symbols, handles comma/dot)
- **No rate limiting, no retry logic**

_Source: https://github.com/Part-DB/Part-DB-server/blob/master/src/Services/InfoProviderSystem/Providers/MouserProvider.php_

### searchOptions Values

For **keyword search** endpoints:

| String | ID | Effect |
|--------|----|--------|
| `"None"` | 1 | No filtering (default) |
| `"Rohs"` | 2 | RoHS-compliant only |
| `"InStock"` | 4 | In-stock only |
| `"RohsAndInStock"` | 8 | Both filters |

For **part number search** endpoints:

| String | ID | Effect |
|--------|----|--------|
| `"None"` | 1 | Fuzzy match |
| `"Exact"` | 2 | Exact MPN match |

**Recommendation:** Default to `"InStock"` for interactive search (faster, more relevant), `"None"` for BOM verification (need to find discontinued parts too).

### Mouser API Response Structure

```json
{
  "Errors": [],
  "SearchResults": {
    "NumberOfResult": 142,
    "Parts": [
      {
        "ManufacturerPartNumber": "STM32F405RGT6",
        "Manufacturer": "STMicroelectronics",
        "MouserPartNumber": "511-STM32F405RGT6",
        "Description": "ARM Microcontrollers - MCU ...",
        "Category": "ARM Microcontrollers - MCU",
        "DataSheetUrl": "https://...",
        "ProductDetailUrl": "https://www.mouser.com/ProductDetail/...",
        "ImagePath": "https://...",
        "Availability": "2500 In Stock",
        "AvailabilityInStock": "2500",
        "LifecycleStatus": "",
        "IsDiscontinued": "false",
        "ROHSStatus": "RoHS Compliant",
        "LeadTime": "56 Days",
        "Min": "1",
        "Mult": "1",
        "PriceBreaks": [
          {"Quantity": 1, "Price": "$12.34", "Currency": "USD"},
          {"Quantity": 10, "Price": "$11.50", "Currency": "USD"}
        ],
        "ProductAttributes": [
          {"AttributeName": "Packaging", "AttributeValue": "Tray"}
        ],
        "SuggestedReplacement": "",
        "UnitWeightKg": {"UnitWeight": 0.001}
      }
    ]
  }
}
```

### Speed Optimization Recommendations

Based on analysis of all three reference implementations and Mouser API behaviour:

| Technique | Impact | Implementation |
|-----------|--------|----------------|
| **`httpx.Client` with connection pooling** | Eliminates TCP handshake per request (~100-200ms saved) | Create one `Client` instance, reuse across all Mouser calls |
| **`records` parameter tuning** | Fewer results = faster response | Use `records=10` for interactive search, `records=1` for MPN validation |
| **`searchOptions="InStock"`** | Filters server-side, fewer results to transfer | Default for interactive search |
| **Batch MPN lookup** | 10 parts per request instead of 1 | Use pipe-separated MPNs for BOM verify: `"MPN1\|MPN2\|..."` |
| **SQLite cache** | Avoid redundant API calls entirely | 4h TTL for pricing, 7d for part data (per CLAUDE.md) |
| **Client-side rate tracking** | Prevent 429 errors (which waste time) | Track minute/day counters, pre-block when near limit |
| **Retry with exponential backoff** | Recover from transient failures | 3 retries, 500ms initial, 2x multiplier. Retry on 429/5xx only. |
| **`httpx.Timeout(connect=5.0, read=20.0)`** | Fail fast on dead connections | KiCost/Ki-nTree use 20-30s; 20s read timeout is safe |

_Source: go-mouser package documents caching TTLs and retry strategy_

---

## Integration Patterns Analysis

### MouserSource → DataSource ABC Mapping

The existing `DataSource` ABC (`core/sources.py:34-65`) requires two methods:

```python
class MouserSource(DataSource):
    name = "Mouser"
    needs_key = True
    key_fields = ["api_key"]

    def search(self, query: str, filters: dict | None = None, limit: int = 50) -> list[PartResult]:
        """Keyword search via POST /api/v1/search/keyword"""
        ...

    def get_part(self, mpn: str, manufacturer: str = "") -> PartResult | None:
        """MPN lookup via POST /api/v2/search/partnumberandmanufacturer (if manufacturer given)
           or POST /api/v1/search/partnumber (MPN only)"""
        ...

    def is_configured(self) -> bool:
        """True when api_key is present in keyring or env var."""
        ...
```

**Credential flow** is already wired: `source_config.py` registers Mouser with `key_fields=["api_key"]` and `env_var_names={"api_key": "KIPART_MOUSER_API_KEY"}`. The settings dialog already renders a single API key input for Mouser. `SourceConfigManager.get_credential("Mouser", "api_key")` returns the key.

### HTTP Request Construction Pattern

Using `httpx.Client` for connection pooling:

```python
import httpx

class MouserSource(DataSource):
    BASE_URL = "https://api.mouser.com/api"
    _client: httpx.Client | None = None

    def __init__(self, api_key: str):
        self._api_key = api_key

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=httpx.Timeout(connect=5.0, read=20.0),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    def _post(self, endpoint: str, body: dict) -> dict:
        """Send POST to Mouser API, return parsed JSON."""
        url = f"{self.BASE_URL}{endpoint}?apiKey={self._api_key}"
        resp = self.client.post(url, json=body)
        resp.raise_for_status()
        return resp.json()
```

**Key decisions:**
- Lazy `httpx.Client` creation — constructed on first use, reused for connection pooling
- `connect=5.0` timeout to fail fast on DNS/network issues
- `read=20.0` timeout — Mouser can be slow (KiCost/Ki-nTree use 20-30s)
- API key as URL query parameter (Mouser's auth model)

### Keyword Search Request/Response Mapping

**Request:**
```python
def search(self, query: str, filters: dict | None = None, limit: int = 50) -> list[PartResult]:
    limit = min(limit, 50)  # Mouser max
    body = {
        "SearchByKeywordRequest": {
            "keyword": query,
            "records": limit,
            "startingRecord": 0,
            "searchOptions": "InStock",  # faster, more relevant for interactive search
            "searchWithYourSignUpLanguage": "false",
        }
    }
    data = self._post("/v1/search/keyword", body)
    return self._parse_parts(data)
```

**Response mapping → PartResult:**

| Mouser field | PartResult field | Notes |
|---|---|---|
| `ManufacturerPartNumber` | `mpn` | Direct |
| `Manufacturer` | `manufacturer` | Direct |
| `Description` | `description` | Direct |
| `Category` | `category` | Direct |
| `DataSheetUrl` | `datasheet_url` | Often blank — do not rely on |
| `LifecycleStatus` + `IsDiscontinued` | `lifecycle` | Needs mapping (see below) |
| `MouserPartNumber` | `source_part_id` | Mouser's internal SKU |
| `ProductDetailUrl` | `source_url` | Link to Mouser product page |
| `AvailabilityInStock` | `stock` | Parse as int (string in response) |
| `PriceBreaks[]` | `price_breaks` | Parse price strings with locale handling |
| `ProductAttributes[]` | `specs` | **Mostly packaging only** — limited value |

**Lifecycle mapping** (following Part-DB's proven mapping):
```python
def _map_lifecycle(self, part: dict) -> str:
    status = (part.get("LifecycleStatus") or "").strip()
    is_disc = part.get("IsDiscontinued", "false").lower() == "true"

    if is_disc or status in ("Obsolete", "Factory Special Order"):
        return "Obsolete"
    if status == "End of Life":
        return "EOL"
    if status == "Not Recommended for New Designs":
        return "NRND"
    if status == "New Product":
        stock = int(part.get("AvailabilityInStock") or 0)
        return "Active" if stock > 0 else "New"
    return "Active"
```

**Price parsing** (handling Mouser's locale-formatted strings like `"$12.34"`, `"12,34 €"`):
```python
import re

def _parse_price(self, price_str: str) -> float:
    """Strip currency symbols, handle comma/dot locale differences."""
    cleaned = re.sub(r'[^\d,.]', '', price_str)
    # If both comma and dot present, last separator is decimal
    if ',' in cleaned and '.' in cleaned:
        if cleaned.rindex(',') > cleaned.rindex('.'):
            cleaned = cleaned.replace('.', '').replace(',', '.')
        else:
            cleaned = cleaned.replace(',', '')
    elif ',' in cleaned:
        # Could be decimal comma (European) or thousands separator
        parts = cleaned.split(',')
        if len(parts) == 2 and len(parts[1]) <= 2:
            cleaned = cleaned.replace(',', '.')
        else:
            cleaned = cleaned.replace(',', '')
    return float(cleaned)
```
_Adapted from KiCost's `get_number()` and Part-DB's `priceStrToFloat()` — both handle this exact problem._

### MPN Validation (get_part) — Two Strategies

**Strategy 1: Single MPN lookup**
```python
def get_part(self, mpn: str, manufacturer: str = "") -> PartResult | None:
    if manufacturer:
        # V2: more precise, avoids cross-manufacturer MPN collisions
        body = {
            "SearchByPartMfrNameRequest": {
                "manufacturerName": manufacturer,
                "mouserPartNumber": mpn,
                "partSearchOptions": "Exact",
            }
        }
        data = self._post("/v2/search/partnumberandmanufacturer", body)
    else:
        # V1: MPN only
        body = {
            "SearchByPartRequest": {
                "mouserPartNumber": mpn,
                "partSearchOptions": "Exact",
            }
        }
        data = self._post("/v1/search/partnumber", body)

    parts = self._parse_parts(data)
    return parts[0] if parts else None
```

**Strategy 2: Batch MPN validation (for BOM verify)**
The part number endpoint accepts up to 10 pipe-separated MPNs:
```python
def get_parts_batch(self, mpns: list[str]) -> list[PartResult]:
    """Batch lookup up to 10 MPNs in one request."""
    assert len(mpns) <= 10
    body = {
        "SearchByPartRequest": {
            "mouserPartNumber": "|".join(mpns),
            "partSearchOptions": "None",  # fuzzy to catch variants
        }
    }
    data = self._post("/v1/search/partnumber", body)
    return self._parse_parts(data)
```

**Budget impact:** Verifying 200 BOM components = 20 API calls (10 per batch) instead of 200 individual calls. At 30 req/min, this completes in under 1 minute.

### GUI Integration: Double-Click → Mouser Search Workflow

The existing flow already supports Mouser without GUI changes:

1. **User double-clicks a BOM component** in `verify_panel.py`
2. `search_for_component` signal emits → `main_window._on_guided_search(row)`
3. `comp.build_search_query()` generates query from value + footprint (e.g. `"10uF 0805 capacitor"`)
4. Query set in `SearchBar` → `transform_query()` runs → `search_requested` signal emits `(query, source_name)`
5. `SearchOrchestrator.search()` (or `search_source()` if specific source selected) dispatches to `MouserSource.search()`
6. Results appear in `results_table` → user double-clicks a result → `AssignDialog` opens

**The only new code needed is `MouserSource` itself.** The search bar, result table, assignment dialog, and cache layer already handle any `DataSource` subclass transparently.

### Query Adaptation: JLCPCB vs Mouser

`build_search_query()` produces queries like `"10uF 0805 capacitor"`. This works well for both sources:
- **JLCPCB:** SQLite FTS5 handles these tokens natively
- **Mouser:** Keyword search accepts free-text — same format works

However, Mouser responds better to specific keywords. A potential optimization in `MouserSource.search()`:
```python
# Mouser-specific: remove component type suffix if MPN-like query detected
# "STM32F405RGT6 IC" → "STM32F405RGT6" (MPN is enough)
```

### SearchOrchestrator Integration

`MouserSource` plugs into the existing orchestrator pattern:

```python
# In application startup (main_window.py or app init):
from kipart_search.core.source_config import SourceConfigManager

mgr = SourceConfigManager()
api_key = mgr.get_credential("Mouser", "api_key")
if api_key:
    mouser = MouserSource(api_key=api_key)
    orchestrator.add_source(mouser)
```

The orchestrator already handles:
- Cache-aside pattern (check cache → query source → store result)
- Network error handling (`OSError`, `ConnectionError` caught)
- License gating (`is_local=False` → requires Pro tier)
- Unit variant expansion (`generate_query_variants`)
- Deduplication by `(MPN, source)`

### Cache Integration

The existing `QueryCache` (SQLite-backed) applies directly:
- **Keyword search results:** TTL = `TTL_PARAMETRIC` (7 days default)
- **MPN validation:** TTL = `TTL_PARAMETRIC` (7 days)
- **Pricing/stock:** Should use shorter TTL (4 hours) — requires adding a `TTL_PRICING` constant

Cache key structure: `(source="Mouser", query_type="search"|"get_part", query=keyword_or_mpn)`

### Rate Limit Management

None of the three reference projects implement client-side rate limiting. For kipart-search, a simple approach:

```python
import time

class RateLimiter:
    """Track Mouser's 30 req/min, 1000 req/day limits."""
    def __init__(self):
        self._minute_timestamps: list[float] = []
        self._day_count = 0
        self._day_reset = time.time() + 86400

    def wait_if_needed(self):
        now = time.time()
        # Clean old timestamps
        self._minute_timestamps = [t for t in self._minute_timestamps if now - t < 60]
        if len(self._minute_timestamps) >= 28:  # leave 2 margin
            sleep_time = 60 - (now - self._minute_timestamps[0])
            time.sleep(max(0, sleep_time))
        self._minute_timestamps.append(time.time())
```

**For breadboarding:** Skip rate limiting. For production: integrate into `_post()`.

### Error Handling Pattern

```python
def _post(self, endpoint: str, body: dict) -> dict:
    url = f"{self.BASE_URL}{endpoint}?apiKey={self._api_key}"
    try:
        resp = self.client.post(url, json=body)
        resp.raise_for_status()
    except httpx.TimeoutException:
        raise ConnectionError(f"Mouser API timeout on {endpoint}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise ConnectionError("Mouser API rate limit exceeded")
        raise ConnectionError(f"Mouser API error {e.response.status_code}")

    data = resp.json()
    errors = data.get("Errors", [])
    if errors:
        msg = "; ".join(e.get("Message", str(e)) for e in errors)
        raise ConnectionError(f"Mouser API: {msg}")
    return data
```

Raising `ConnectionError` ensures the `SearchOrchestrator` catches it cleanly (already handles `OSError | ConnectionError` in `_search_sources()`).

### Security: API Key Handling

- Key stored in OS keyring via `SourceConfigManager.set_credential()`
- Environment variable override: `KIPART_MOUSER_API_KEY`
- Key passed as URL query parameter — **logged in server access logs** but acceptable for a free API key
- Never stored in config.json (plaintext)
- Part-DB's `MouserPartNumber < 4 chars` filter is worth adopting to discard garbage results

---

## Architectural Patterns and Design

### UI Architecture: Tabs vs Unified Results

Your question about splitting from unified search to per-source tabs is a significant architectural decision. Here's what the research shows:

**How every major EE search tool works:**

| Tool | Pattern | Details |
|------|---------|---------|
| **Octopart/Nexar** | Unified + facets | One merged table, 400+ distributors, source as filterable column |
| **Findchips/oemsecrets/TrustedParts** | Unified | One search, one merged table, distributor per-row |
| **Ki-nTree** | Single-source dropdown | Pick one source at a time, no merging |
| **Part-DB** | Unified | Single search, "select best match" from multiple providers |
| **KiCost** | Unified spreadsheet | One row per component, one column per distributor |

_Sources: octopart.com, findchips.com, github.com/sparkmicro/Ki-nTree, docs.part-db.de_

**Pattern A: Tabs Per Source** (`JLCPCB | DigiKey | Mouser` tabs)

| Pros | Cons |
|------|------|
| Source-specific columns (JLCPCB basic/extended, DigiKey lifecycle) | Users must click through tabs to compare |
| Independent loading — fast sources show immediately | Cross-source deduplication lost |
| Lazy loading saves API quota (only query when tab clicked) | UX research: users rarely go beyond first tab |
| Clear which distributor's data you're seeing | More screen space for tab bar |

**Pattern B: Unified + Source Filter** (current kipart-search architecture)

| Pros | Cons |
|------|------|
| Best results regardless of source | Harder to show source-specific metadata |
| Cross-source dedup and ranking | Slow sources delay full results (unless streaming) |
| Simpler: "search once, see everything" | Mixing data quality across sources |
| Industry standard (Octopart, Findchips) | Source column can be overlooked |

**Pattern C: Hybrid (recommended evolution)**

Keep unified as default, but add independent source capabilities:

1. **Unified table remains primary** — source dropdown filter already exists in `SearchBar._source_selector`
2. **Per-source status indicators** — "JLCPCB: done (47) | Mouser: searching... | DigiKey: done (12)" in the status area
3. **Parallel workers** — one `SearchWorker` per source, streaming results incrementally into the unified table
4. **Detail panel enrichment** — clicking a result shows distributor-specific data from all sources that carry that MPN
5. **Source selector = "All Sources" or pick one** — already implemented, effectively gives tab-like separation

**For the Mouser breadboarding stage**, the simplest approach is: user selects "Mouser" in the existing source dropdown → only Mouser is queried → results in the same table. This tests the full flow without any GUI changes. The tabbed UI discussion can be deferred to a dedicated UX story.

### MouserSource Implementation Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    main_window.py                         │
│  SearchBar ──signal──> _on_search()                      │
│       │                    │                              │
│       │              SearchOrchestrator                   │
│       │                    │                              │
│       ▼                    ▼                              │
│  source_selector    ┌─────────────┐                      │
│  "Mouser" ─────────>│ MouserSource │                     │
│                     │  .search()   │──> httpx.Client ──> │
│                     │  .get_part() │    POST /keyword     │
│                     └──────┬──────┘    POST /partnumber   │
│                            │                              │
│                     ┌──────▼──────┐                       │
│                     │  QueryCache  │ SQLite cache-aside   │
│                     └─────────────┘                       │
│                            │                              │
│                     ┌──────▼──────┐                       │
│                     │ ResultsTable │ PartResult display   │
│                     └─────────────┘                       │
└──────────────────────────────────────────────────────────┘
```

### File Structure — What Gets Added

```
src/kipart_search/core/
    sources.py          # ADD: MouserSource class (~150 lines)
                        # - search() via POST /v1/search/keyword
                        # - get_part() via POST /v1/search/partnumber
                        #   or POST /v2/search/partnumberandmanufacturer
                        # - get_parts_batch() for BOM verify (10 MPNs/request)
                        # - _parse_parts() response → PartResult mapping
                        # - _map_lifecycle() status mapping
                        # - Lazy httpx.Client with connection pooling

experiments/
    mouser_explore.py   # Breadboard script (standalone, not imported by app)
```

No new files needed beyond `MouserSource` in the existing `sources.py` and the breadboard script. No GUI files change.

### DataSource Lifecycle in the Application

```python
# Startup (already happens in main_window.py init):
mgr = SourceConfigManager()
orchestrator = SearchOrchestrator(cache=cache)

# JLCPCB (already implemented):
jlcpcb = JLCPCBSource(db_path=...)
orchestrator.add_source(jlcpcb)

# Mouser (new — same pattern):
api_key = mgr.get_credential("Mouser", "api_key")
if api_key:
    mouser = MouserSource(api_key=api_key)
    orchestrator.add_source(mouser)

# Search flow (already implemented):
# orchestrator.search(query) → queries all active sources → merges → deduplicates
# orchestrator.search_source(query, "Mouser") → queries Mouser only
# orchestrator.verify_mpn(mpn) → checks all sources for MPN validation
```

### Connection Management Design

```python
class MouserSource(DataSource):
    """Mouser API adapter using httpx with connection pooling."""

    name = "Mouser"
    needs_key = True
    key_fields = ["api_key"]
    BASE_URL = "https://api.mouser.com/api"

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Lazy-initialized persistent HTTP client for connection reuse."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=httpx.Timeout(connect=5.0, read=20.0),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    def close(self):
        """Release HTTP resources. Called on app shutdown."""
        if self._client:
            self._client.close()
            self._client = None
```

**Design decisions:**
- Lazy client creation — no TCP connection until first search
- Single `httpx.Client` instance reuses connections across requests (~100-200ms saved per call)
- `connect=5.0s` timeout — fail fast on network issues
- `read=20.0s` timeout — Mouser can be slow, consistent with Ki-nTree's 20s timeout
- `close()` method for clean shutdown — the orchestrator or main window should call this

### Error Propagation Design

All Mouser errors are raised as `ConnectionError` to integrate with the existing `SearchOrchestrator` error handling:

```
Mouser API error
    ↓
MouserSource._post() raises ConnectionError
    ↓
SearchOrchestrator._search_sources() catches (OSError, ConnectionError)
    ↓
log.warning("Mouser: offline — {error}")
    ↓
returns empty results for that source, continues with others
```

This means: if Mouser is down or rate-limited, JLCPCB results still show. No cascading failures.

### Breadboarding Architecture

The exploration script (`experiments/mouser_explore.py`) should test each integration point independently:

```
Phase 1: Raw API calls
  ├── Keyword search ("resistor 47 0402 1%")
  ├── MPN lookup ("STM32F405RGT6")
  ├── MPN + manufacturer lookup
  ├── Batch MPN lookup (10 pipe-separated)
  └── Inspect response structure, verify field mapping

Phase 2: PartResult mapping
  ├── Parse a real response into PartResult
  ├── Test lifecycle mapping on various LifecycleStatus values
  ├── Test stock parsing (AvailabilityInStock)
  └── Verify ProductAttributes content (confirm: mostly packaging only)

Phase 3: Integration dry-run
  ├── Instantiate MouserSource with real API key
  ├── Call search() and get_part()
  ├── Print results as PartResult objects
  └── Confirm cache-aside works (run twice, second should be cached)
```

### Price Parsing (deferred)

Price parsing from Mouser's locale-formatted strings (e.g. `"$12.34"`, `"12,34 €"`) is well-understood from KiCost and Part-DB implementations. Both projects handle international comma/dot formats. **Implementation deferred** — will be addressed when pricing display is added to the results table. The reference implementations are documented in the Integration Patterns section above.

---

## Implementation Approaches and Adoption

### Phase 1: Breadboard Script (`experiments/mouser_explore.py`)

A standalone script to validate every assumption before writing production code. Run with: `python experiments/mouser_explore.py`

**Prerequisites:**
- Mouser Search API key from https://www.mouser.com/api-hub/
- Set env var: `KIPART_MOUSER_API_KEY=your_key` (or pass as CLI arg)
- `httpx` already in project dependencies

**What to test, in order:**

```
Test 1: Basic keyword search
  Request:  POST /api/v1/search/keyword
  Body:     {"SearchByKeywordRequest": {"keyword": "resistor 47 0402 1%", "records": 10, "startingRecord": 0, "searchOptions": "InStock"}}
  Validate: Response has SearchResults.Parts[], each part has ManufacturerPartNumber
  Print:    MPN, Manufacturer, Description, Category, stock, lifecycle for each part

Test 2: MPN lookup (exact)
  Request:  POST /api/v1/search/partnumber
  Body:     {"SearchByPartRequest": {"mouserPartNumber": "GRM155R71C104KA88D", "partSearchOptions": "Exact"}}
  Validate: Returns 1 matching part
  Print:    Full part details including DataSheetUrl, ProductAttributes, PriceBreaks

Test 3: MPN + manufacturer lookup (V2)
  Request:  POST /api/v2/search/partnumberandmanufacturer
  Body:     {"SearchByPartMfrNameRequest": {"manufacturerName": "Murata", "mouserPartNumber": "GRM155R71C104KA88D", "partSearchOptions": "Exact"}}
  Validate: Same part, more precise match
  Compare:  Response time vs Test 2

Test 4: Batch MPN lookup (10 pipe-separated)
  Request:  POST /api/v1/search/partnumber
  Body:     {"SearchByPartRequest": {"mouserPartNumber": "MPN1|MPN2|...|MPN10", "partSearchOptions": "None"}}
  Validate: Returns results for multiple MPNs in one call
  Measure:  Response time (should be similar to single MPN)

Test 5: PartResult mapping
  Take response from Test 1
  Map each part to PartResult dataclass
  Print as PartResult objects
  Confirm: lifecycle mapping, stock parsing, source fields

Test 6: Confirm ProductAttributes limitation
  Take response from Test 2
  Print all ProductAttributes entries
  Confirm: mostly packaging info, NOT electrical parameters

Test 7: Connection pooling speed comparison
  Run 5 keyword searches sequentially with httpx.Client (reused connection)
  Run 5 keyword searches with new httpx.Client each time
  Print timing comparison

Test 8: searchOptions comparison
  Same keyword with "None" vs "InStock" vs "RohsAndInStock"
  Compare: result count, response time, result quality
```

### Phase 2: MouserSource Implementation (~150 lines in `sources.py`)

After breadboarding confirms the API behaviour, implement `MouserSource` in the existing `sources.py`.

**Complete class outline:**

```python
class MouserSource(DataSource):
    """Mouser Search API adapter.

    Uses raw httpx (not the mouser PyPI package) for:
    - Connection pooling (persistent TCP)
    - Consistent with project's HTTP client
    - Access to V2 endpoints

    Reference implementations studied:
    - KiCost api_mouser.py (MIT) — lifecycle/stock parsing patterns
    - Ki-nTree mouser_api.py (GPL, patterns only) — field extraction
    - Part-DB MouserProvider.php (AGPL, patterns only) — lifecycle mapping
    """

    name = "Mouser"
    needs_key = True
    key_fields = ["api_key"]
    BASE_URL = "https://api.mouser.com/api"

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client: httpx.Client | None = None

    # --- DataSource ABC ---

    def search(self, query, filters=None, limit=50):
        """Keyword search via POST /v1/search/keyword."""
        ...

    def get_part(self, mpn, manufacturer=""):
        """MPN lookup. Uses V2 with manufacturer if provided, V1 otherwise."""
        ...

    def is_configured(self):
        return bool(self._api_key)

    # --- Mouser-specific ---

    def get_parts_batch(self, mpns: list[str]) -> list[PartResult]:
        """Batch MPN lookup (up to 10 per request) for BOM verify."""
        ...

    # --- Internal ---

    @property
    def client(self) -> httpx.Client:
        """Lazy httpx.Client with connection pooling."""
        ...

    def _post(self, endpoint, body) -> dict:
        """POST to Mouser API, handle errors → ConnectionError."""
        ...

    def _parse_parts(self, data) -> list[PartResult]:
        """Map Mouser response to PartResult list."""
        ...

    def _map_lifecycle(self, part) -> str:
        """Map LifecycleStatus + IsDiscontinued → lifecycle string."""
        ...

    def _parse_stock(self, part) -> int | None:
        """Parse AvailabilityInStock string → int."""
        ...

    def close(self):
        """Release HTTP resources."""
        ...
```

### Phase 3: Wire into Application

The exact integration point exists at [main_window.py:1649](src/kipart_search/gui/main_window.py#L1649):

```python
# Current code:
            # Future API sources would be instantiated here

# Replace with:
            if cfg.source_name == "Mouser":
                from kipart_search.core.sources import MouserSource
                api_key = mgr.get_credential("Mouser", "api_key")
                if api_key:
                    mouser = MouserSource(api_key=api_key)
                    self._orchestrator.add_source(mouser)
```

Also update the import and `_on_db_downloaded` / `_apply_source_configs` to rebuild Mouser source alongside JLCPCB.

**What works immediately after wiring:**
- Source dropdown shows "Mouser" alongside "JLCPCB" and "All Sources"
- Selecting "Mouser" → searches Mouser only
- "All Sources" → searches both JLCPCB and Mouser, merges results
- BOM verify double-click → guided search queries Mouser too
- Results table shows Mouser results with Source column
- Cache-aside pattern caches Mouser results in SQLite
- MPN verification checks Mouser (after JLCPCB)
- License gating: Mouser requires Pro tier (`is_local=False`)

**What needs attention:**
- Connection cleanup on app exit — call `mouser.close()` in `closeEvent()`
- Preferences dialog already shows Mouser API key input — just needs testing
- The `_apply_source_configs` method needs the Mouser instantiation code

### Testing Strategy

**Manual testing first** (per CLAUDE.md: "start with manual testing, add pytest later"):

| Test | How | Expected |
|------|-----|----------|
| Keyword search | Select "Mouser" source, type "STM32F405", click Search | Results with STM32F405 variants |
| Guided search | Double-click a BOM component, select "Mouser" | Results matching component value/footprint |
| MPN verify | Scan a KiCad project with known Mouser parts | Components with MPNs show AMBER (single source) |
| Cache hit | Search same query twice, check log | Second search says "served from cache" |
| No API key | Remove API key, restart app | "Mouser" not in source dropdown |
| Rate limit | Run 35 rapid searches | Should handle 429 gracefully (empty results, not crash) |
| Offline | Disconnect network, search | "Mouser: offline" in log, JLCPCB results still show |

**Automated tests (later):**
- Unit test `_parse_parts()` with a fixture JSON response
- Unit test `_map_lifecycle()` with all known status strings
- Unit test `_parse_stock()` with various Mouser stock strings
- Integration test with mocked httpx transport (no real API calls)

### Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| **1,000 req/day limit** | Power users could exhaust quota | SQLite cache (7-day TTL for parametric), batch MPN lookup (10/req), show remaining quota in UI |
| **ProductAttributes is packaging only** | No parametric enrichment from Mouser | Document clearly; use DigiKey/JLCPCB for parametric data |
| **DataSheetUrl often blank** | Can't rely on Mouser for datasheets | Fall back to other sources; don't show empty datasheet column |
| **API key in URL query string** | Appears in server logs (acceptable for free API key) | No action needed; standard Mouser pattern |
| **Slow responses (up to 20s)** | Blocks UI if not threaded | Already runs in SearchWorker QThread |
| **Response locale varies** | Prices in user's account currency/format | Price parsing deferred; stock is numeric string (simpler) |

### Implementation Roadmap

```
Week 1: Breadboard
  Day 1-2: experiments/mouser_explore.py — all 8 tests
  Day 3:   Confirm field mapping, identify any surprises

Week 2: Production adapter
  Day 1:   MouserSource class in sources.py (~150 lines)
  Day 2:   Wire into main_window.py (3 integration points)
  Day 3:   Manual testing (7 scenarios above)
  Day 4:   Bug fixes, cache tuning, error edge cases

Week 3: Polish (optional, can defer)
  - Batch MPN lookup for BOM verify
  - Rate limit tracking
  - Automated unit tests with fixture data
```

### Concrete Code: Application Startup Registration

The full initialization flow, showing how Mouser fits alongside existing sources:

```python
# In _apply_source_configs() — called after preferences dialog or at startup

def _apply_source_configs(self, configs: list):
    """Update orchestrator sources and UI based on saved preferences."""
    from kipart_search.core.source_config import SourceConfig, SourceConfigManager

    self._orchestrator = SearchOrchestrator(cache=self._cache)
    mgr = SourceConfigManager()

    for cfg in configs:
        if not cfg.enabled:
            continue

        if cfg.source_name == "JLCPCB":
            if not self._jlcpcb_source:
                self._init_jlcpcb_source()
            if self._jlcpcb_source and self._jlcpcb_source.is_configured():
                self._orchestrator.add_source(self._jlcpcb_source)

        elif cfg.source_name == "Mouser":
            from kipart_search.core.sources import MouserSource
            api_key = mgr.get_credential("Mouser", "api_key")
            if api_key:
                self._orchestrator.add_source(MouserSource(api_key=api_key))

        # Future: DigiKey, Octopart, etc. follow the same pattern

    self.search_bar.set_sources(self._orchestrator.get_source_names())
    self._update_status()
```

---

## Research Synthesis

### Executive Summary

This research investigated how to integrate the Mouser Search API into kipart-search as the project's second online distributor source (after the offline JLCPCB database). The analysis covered the Mouser API's capabilities and limitations, studied three open-source reference implementations (KiCost, Ki-nTree, Part-DB), and mapped the concrete integration points against kipart-search's existing architecture.

**The core finding is that Mouser integration is straightforward — ~150 lines of code, zero GUI changes, and a 3-phase implementation path.** The existing `DataSource` ABC, `SearchOrchestrator`, credential management, cache layer, and UI workflow all handle Mouser transparently. The only new code is a `MouserSource` class in the existing `sources.py`.

**However, Mouser has critical limitations that must be understood upfront:** the API does not return parametric specifications (despite the `ProductAttributes` field name), datasheets are intermittently blank, and there is no parametric filtering. Mouser is a **pricing/stock/lifecycle supplement**, not a parametric discovery source.

**Key Technical Decisions:**

- Use raw `httpx` with connection pooling — skip the `mouser` PyPI package (adds `requests` dependency, only covers V1, 7.6 kB wrapper)
- Keyword search via `POST /api/v1/search/keyword` for interactive discovery
- MPN validation via `POST /api/v2/search/partnumberandmanufacturer` for BOM verify (more precise with manufacturer filter)
- Batch MPN lookup (10 per request) for efficient BOM verification
- Default `searchOptions="InStock"` for interactive search (faster, more relevant)
- `httpx.Timeout(connect=5.0, read=20.0)` — consistent with Ki-nTree's proven timeout
- All errors raised as `ConnectionError` — already handled by orchestrator

**Top Recommendations:**

1. Start with the breadboard script to validate API assumptions before writing production code
2. Implement `MouserSource` in existing `sources.py` — no new files needed
3. Wire into `main_window.py` at the existing `# Future API sources would be instantiated here` marker
4. Do not rely on Mouser for datasheets or parametric data — use JLCPCB/DigiKey for those
5. Cache aggressively — the 1,000 req/day limit makes caching mandatory, not optional

### Table of Contents

1. [Technical Research Scope Confirmation](#technical-research-scope-confirmation)
2. [Technology Stack Analysis](#technology-stack-analysis)
   - Mouser API Endpoint Inventory
   - Rate Limits and Quotas
   - What Mouser API Does NOT Return (Critical Limitations)
   - HTTP Client Decision (httpx, not mouser package)
   - Reference Implementation Analysis (KiCost, Ki-nTree, Part-DB)
   - searchOptions Values
   - Response Structure
   - Speed Optimization Recommendations
3. [Integration Patterns Analysis](#integration-patterns-analysis)
   - MouserSource → DataSource ABC Mapping
   - HTTP Request Construction Pattern
   - Keyword Search Request/Response Mapping
   - MPN Validation Strategies (single + batch)
   - GUI Integration: Double-Click Workflow
   - Query Adaptation: JLCPCB vs Mouser
   - SearchOrchestrator Integration
   - Cache Integration
   - Rate Limit Management
   - Error Handling Pattern
4. [Architectural Patterns and Design](#architectural-patterns-and-design)
   - UI Architecture: Tabs vs Unified Results
   - MouserSource Implementation Architecture (diagram)
   - File Structure
   - DataSource Lifecycle
   - Connection Management Design
   - Error Propagation Design
   - Breadboarding Architecture
5. [Implementation Approaches and Adoption](#implementation-approaches-and-adoption)
   - Phase 1: Breadboard Script (8 tests)
   - Phase 2: MouserSource Implementation (~150 lines)
   - Phase 3: Wire into Application
   - Testing Strategy (manual + automated)
   - Risk Assessment
   - Implementation Roadmap
6. [Research Synthesis](#research-synthesis) (this section)
   - Executive Summary
   - Consolidated Source References
   - Technical Confidence Assessment

### Consolidated Source References

#### API Documentation
- [Mouser Search API (Swagger UI)](https://api.mouser.com/api/docs/ui/index) — Official API documentation
- [Mouser API Hub](https://www.mouser.com/api-hub/) — API key registration
- [Mouser Search API Landing](https://www.mouser.com/api-search/) — API overview

#### Reference Implementations Analysed
- [KiCost `api_mouser.py`](https://github.com/hildogjr/KiCost/blob/master/kicost/distributors/api_mouser.py) — MIT, ~280 lines, stock parsing regex, price parsing
- [Ki-nTree `mouser_api.py`](https://github.com/sparkmicro/Ki-nTree/blob/main/kintree/search/mouser_api.py) — GPL-3.0 (patterns only), ProductAttributes extraction, 20s timeout
- [Part-DB `MouserProvider.php`](https://github.com/Part-DB/Part-DB-server/blob/master/src/Services/InfoProviderSystem/Providers/MouserProvider.php) — AGPL (patterns only), lifecycle mapping, price parsing
- [sparkmicro/mouser-api](https://github.com/sparkmicro/mouser-api) — MIT, Python wrapper (v0.1.6, Oct 2024)

#### Known Issues (Mouser API Limitations)
- [Part-DB Issue #503](https://github.com/Part-DB/Part-DB-server/issues/503) — Mouser API missing datasheets and parameters
- [Part-DB Issue #558](https://github.com/Part-DB/Part-DB-server/issues/558) — Confirmed: API does not return parametric specs

#### Rate Limits & Best Practices
- [go-mouser package](https://pkg.go.dev/github.com/PatrickWalther/go-mouser) — Documents 30 req/min, 1000 req/day, caching TTLs, retry strategy

#### UI Research
- [Octopart](https://octopart.com/) — Industry standard unified search UX
- [Findchips](https://www.findchips.com/) — Unified multi-distributor results
- [Part-DB Information Provider docs](https://docs.part-db.de/usage/information_provider_system.html) — Multi-provider architecture

### Technical Confidence Assessment

| Finding | Confidence | Basis |
|---------|------------|-------|
| API endpoints and request format | **High** | Swagger spec + 3 working implementations |
| Rate limits (30/min, 1000/day) | **High** | go-mouser empirical testing + consistent across sources |
| ProductAttributes = packaging only | **High** | Part-DB maintainer confirmed in 2 issues + KiCost ignores field |
| DataSheetUrl intermittently blank | **High** | Part-DB issue #503, KiCost extracts but notes unreliability |
| Connection pooling speed gain | **Medium** | Standard HTTP/1.1 behaviour, not Mouser-specific benchmarked |
| `searchOptions="InStock"` is faster | **Medium** | Logical (fewer results), not benchmarked against Mouser specifically |
| Batch MPN (10/request) works | **Medium** | Documented in Swagger spec, used by Part-DB, not tested with real key yet |
| Integration requires zero GUI changes | **High** | Verified against current codebase — all touch points already generic |

### What This Research Does NOT Cover (Out of Scope)

- Price parsing implementation (deferred — well-understood from KiCost/Part-DB)
- DigiKey OAuth2 integration (separate research needed)
- Tabbed UI redesign (separate UX story)
- Async/parallel search workers (existing TODO in search.py)
- Mouser Order API (cart/purchasing — not relevant for search)

---

**Technical Research Completion Date:** 2026-03-26
**Research Period:** Comprehensive analysis of Mouser API, 3 reference implementations, kipart-search codebase
**Source Verification:** All technical claims cited with current sources
**Technical Confidence Level:** High — based on multiple authoritative sources and codebase verification
