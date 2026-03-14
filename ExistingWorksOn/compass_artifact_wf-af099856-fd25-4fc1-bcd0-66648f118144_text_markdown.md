# Open-source landscape for parametric electronic component search

**No single open-source tool does what you want to build — but nearly every piece exists in reusable form.** The ecosystem offers mature distributor API wrappers (KiCost, Ki-nTree), a proven offline parametric search architecture (JLCParts), local component database patterns (kicad-jlcpcb-tools), and rich data models (InvenTree, Part-DB) that can be composed into a PySide6 desktop tool. The critical gap: no existing project combines parametric search across multiple free distributor APIs in a desktop GUI. The Kitspace/PartInfo aggregator API — once the only free, keyless option — is effectively dead (the UK company dissolved March 2026), meaning all viable paths now require user-provided API keys.

This report catalogs every significant open-source project, API wrapper, database, and architectural pattern relevant to building a free desktop parametric component search tool. Projects are assessed for code reusability, license compatibility, and maintenance status.

---

## KiCost: the best distributor abstraction layer, but no parametric search

**KiCost** (hildogjr/KiCost, **~590 stars**, MIT, Python) is the most mature open-source multi-distributor integration codebase. Actively maintained by Salvador Tropea, with v1.1.20 released March 2025 adding Digi-Key API V4 support.

KiCost's `kicost/distributors/` directory implements a clean plugin architecture. The base class `distributor_class` in `distributor.py` defines `configure()`, `query_part_info()`, and a `QueryCache` (file-based with configurable TTL, default 7 days). Six API modules extend this base:

| Module | Auth | Status | Notes |
|--------|------|--------|-------|
| `api_nexar.py` | OAuth2 (client credentials) | ✅ Active | Primary multi-distributor source. 1,000 parts/month free |
| `api_digikey.py` | OAuth2 (authorization code) | ✅ Active | Uses external `kicost-digikey-api-v4` plugin. Browser popup for token |
| `api_mouser.py` | API key | ✅ Active | Simple key in config |
| `api_element14.py` | API key | ✅ Active | Covers Farnell, Newark, CPC across 30+ countries |
| `api_tme.py` | HMAC token + secret | ✅ Active | European distributor |
| `api_partinfo_kitspace.py` | None | ⛔ Disabled | Service dead since ~2024 |

**KiCost fundamentally only does MPN/SKU lookup, not parametric search.** The Kitspace module's GraphQL query collected `specs` data but the codebase explicitly notes "Misc data collected, currently not used inside KiCost." The Nexar API underneath *does* support parametric search via its `supSearch` endpoint with filters and aggregations, but KiCost never calls it.

The most reusable pieces are the **`QueryCache` class** (drop-in SQLite/JSON cache with TTL), the **YAML + environment variable configuration pattern** (`~/.config/kicost/config.yaml`), the **distributor name translation dicts** (normalizing "Digi-Key" vs "DigiKey" vs "digikey"), and the **OAuth2 token handling** in the Nexar and Digi-Key modules. The `DistData` model (SKU, URL, price tiers, stock, MOQ, currency) is too simple for parametric search but provides a solid pricing data structure. The `PartGroup` model is BOM-centric and not useful as-is.

**Key files to study**: `distributors/distributor.py` (base class + cache), `distributors/api_nexar.py` (OAuth2 + GraphQL), `global_vars.py` (data models), `distributors/__init__.py` (plugin registration).

---

## The KiCad ecosystem has two gems: kicad-jlcpcb-tools and KiBoM's units.py

**kicad-jlcpcb-tools** (Bouni/kicad-jlcpcb-tools, **~1,800 stars**, MIT, Python) is the most architecturally relevant project for a parametric search tool. It maintains a **local SQLite FTS5 database** of the entire JLCPCB/LCSC catalog (~1M+ parts), downloaded in chunks from GitHub Pages, with full-text search across LCSC Part #, Description, MFR Part #, Package, Library Type, Stock, and Price.

The `library.py` module handles chunked database download with progress tracking and resume capability, plus FTS5 queries like `SELECT ... FROM parts WHERE parts MATCH ?`. The `lcsc_api.py` module provides a REST client for real-time part detail enrichment via `https://cart.jlcpcb.com/shoppingCart/smtGood/getComponentDetail?componentCode={LCSC_NUMBER}`. Crucially, the project includes a **standalone mode** (`standalone_impl.py`) that decouples the UI from KiCad — directly relevant for a PySide6 standalone app. The database schema (LCSC Part, Description, MFR Part, Package, Library Type, Stock, Manufacturer, Price tiers) maps well to a parametric search use case, though it lacks deep parametric filtering (no min/max capacitance queries).

**KiBoM** (SchrodingersGat/KiBoM, **~300 stars**, MIT, Python) contributes one critical reusable module: `units.py`, which normalizes engineering values across unit prefixes — converting between "0.1µF", "100nF", and "100000pF". This is essential for any parametric search tool comparing component values from different sources.

Other KiCad ecosystem tools have limited relevance: **KiBot** (~610 stars, AGPL) is a CI/CD automation tool with useful field name translation patterns but no search capability. **InteractiveHtmlBom** (~4,300 stars, MIT) is purely a visualization tool. **easyeda2kicad** (~900 stars, AGPL) converts LCSC/EasyEDA components to KiCad library format and documents LCSC API access patterns useful as a downstream integration (search → select → download CAD models).

---

## JLCParts is the closest existing parametric search architecture

**JLCParts** (yaqwsx/jlcparts, **741 stars**, MIT, Python + JavaScript) is the only open-source project that implements **true parametric search** for electronic components. It downloads the JLCPCB catalog XLS (~1.5M parts), processes it through Python scripts that extract and normalize parametric fields per component category, outputs per-category JSON files, and serves them through a React frontend that uses **IndexedDB for fully client-side parametric filtering and sorting**.

This architecture translates directly to a PySide6 desktop tool: replace IndexedDB with SQLite, replace React with PySide6's QTableView + QSortFilterProxyModel, and keep the Python data processing pipeline intact. The project also documents LCSC's undocumented API endpoints in an `LCSC-API.md` file — invaluable since LCSC has no official public API and rate-limits scraping to ~100 requests/minute. The initial database build takes ~3.5 days due to this rate limiting.

**Limitation**: JLCParts only covers JLCPCB/LCSC parts. The project was briefly disrupted in November 2022 when JLCPCB blocked data access, highlighting the fragility of scraping-dependent approaches.

---

## Distributor APIs: DigiKey and Nexar offer the best free parametric search

The landscape of Python-accessible distributor APIs varies dramatically in parametric search capability, free tier generosity, and authentication complexity.

**Nexar/Octopart** (GraphQL at `api.nexar.com/graphql`) provides the richest multi-distributor parametric search via its `supSearch` query, which supports filters, aggregations/facets, manufacturer filtering, and sorting across **100+ distributors**. However, the free tier is severely limited: **only 100 parts lifetime** on the Evaluation plan, and the Standard paid plan ($49/month) omits specs, lifecycle, and datasheets — making it useless for parametric search. The Pro plan ($250/month) is needed for full parametric capability. Authentication uses OAuth2 client credentials flow. No mature Python wrapper exists; direct `requests` + GraphQL is recommended over the obsolete `pyoctopart` package.

**Digi-Key API v4** (REST) offers the best balance of parametric search capability and free access. The `KeywordSearch` endpoint accepts `ParametricFilters` for category-based filtering by electrical parameters. **Free tier: 1,000 requests/day** — generous for a desktop tool. The `digikey-api` package on PyPI (peeter123/digikey-api, **~100 stars**, GPL-3.0) handles OAuth2 with auto-browser-launch and token caching, though the 3-legged OAuth flow (localhost redirect to port 8139) requires custom handling in PySide6. A Swagger-generated `digikey-apiv4` package also exists but is less user-friendly.

**Mouser** (REST, simple API key auth) is easy to integrate via `mouser` on PyPI (sparkmicro/mouser-api, **39 stars**, MIT), but **lacks parametric search entirely** — only keyword and part number search. Useful as a supplementary source for pricing/stock after finding MPNs elsewhere.

**Element14/Farnell** (REST, API key) supports some parametric search via search term prefixes (`manuPartNum:`, `any:`) and covers Farnell, Newark, and element14 stores globally. The `pyFarnell` wrapper exists but is likely unmaintained.

**TME** (REST with HMAC signature auth) provides good specs data and is well-documented at developers.tme.eu. No PyPI package exists, but official Python examples are available at tme-dev/TME-API on GitHub.

**Arrow** (REST, login + API key) offers generous rate limits (50 req/sec) but no parametric search. **LCSC** has no official API; all access requires scraping. **RS Components** has no public API. **JLCPCB** recently launched an official API at api.jlcpcb.com — worth monitoring for Python wrapper availability.

| Distributor | Parametric Search | Free Tier | Auth | Best Python Package |
|---|---|---|---|---|
| **Nexar/Octopart** | ✅ Excellent (Pro plan only) | 100 parts lifetime | OAuth2 | Direct GraphQL |
| **Digi-Key** | ✅ Good | 1,000 req/day | OAuth2 (3-legged) | `digikey-api` (GPL-3.0) |
| **Mouser** | ❌ Keyword only | Free (limits undocumented) | API key | `mouser` (MIT) |
| **Element14/Farnell** | ⚠️ Limited | Free | API key | `pyFarnell` |
| **TME** | ✅ Specs available | Free | HMAC | Manual (official examples) |
| **Arrow** | ❌ No | Free, 50 req/sec | API key | None |
| **LCSC/JLCPCB** | ❌ No API | N/A (scraping) | None | None |

Two aggregator options deserve mention: **TrustedParts.com API** (free, sponsored by ECIA, 25M+ part numbers from authorized distributors) and **OEMSecrets API** (140+ distributors, access by request). Neither has a Python wrapper but both are simple REST endpoints.

---

## Inventory tools offer mature data models but not search

**InvenTree** (inventree/InvenTree, **~6,200 stars**, MIT, Python/Django) is the largest and most active project in this space. Its `SupplierMixin` plugin architecture defines a clean interface (`get_search_results()`, `get_import_data()`, pricing/parameters extraction) for modular distributor integrations. Community plugins exist for Mouser and DigiKey. The `inventree-python` client library provides programmatic access to parts, categories, parameters, suppliers, and BOMs — directly usable from a PySide6 app. InvenTree's Django ORM models for `Part`, `PartCategory`, `PartParameter`, `SupplierPart` are the best reference for designing a component data schema. **However**, InvenTree is an inventory management system, not a parametric search tool — its parametric filtering by custom parameters is basic.

**Part-DB** (Part-DB/Part-DB-server, **~1,477 stars**, AGPL-3.0, PHP/Symfony) has the most sophisticated parametric search of any inventory tool, with JSON-column-based parameter storage supporting min/typ/max values with units and automatic scaling. Its "information provider" architecture integrates Octopart, DigiKey, Farnell, Mouser, LCSC, and TME for auto-populating part data. Part-DB also serves as a KiCad HTTP Library source. The AGPL license limits direct code reuse, but the architectural patterns and data model are excellent references.

**PartKeepr** was archived on GitHub in July 2025. **PartsBox** is proprietary (not open-source). **Binner** (~800 stars, GPL, C#/.NET) is cross-platform and integrates DigiKey, Mouser, Octopart, Arrow, TME, and AliExpress, with notable barcode-parsing for 20+ manufacturer label formats — useful as an architecture reference but not Python-reusable.

---

## No comprehensive open parametric database exists

**There is no freely downloadable, comprehensive parametric component database** comparable to SiliconExpert or Octopart's commercial offerings. Authoritative parametric data is controlled by distributors and aggregators. JEDEC standards are free to download but are specification documents (PDFs), not databases. IPC standards require paid membership.

The closest options for offline data are:

- **JLCPCB/LCSC catalog** (~1.5M parts): Downloadable as XLS, processable via JLCParts' Python pipeline into structured JSON with parametric fields. Currently the **best freely available offline parametric dataset**.
- **kicad-jlcpcb-tools database**: Pre-built SQLite FTS5 database of JLCPCB parts, hosted as chunked files at `bouni.github.io/kicad-jlcpcb-tools/`.
- **Kitspace electro-grammar** (279 stars, MIT, JavaScript): ANTLR4-based parser that extracts parametric data from component description strings — useful for normalizing unstructured descriptions into structured specs.
- **JITX Open Components Database**: Component models in Stanza language with parametric data for real manufacturers. Niche.
- **Kaggle datasets**: Only image-classification datasets, not parametric data.

Community projects that aggregate/scrape component data include **LCSC-Dumper** (full LCSC catalog scraper, 3.5+ days to run) and **reinderien/digikey** (DigiKey scraper with category caching).

---

## Architectural blueprint for a PySide6 parametric search tool

Analyzing the patterns across all projects reveals a consistent, proven architecture. Here is a synthesized blueprint combining the best approaches.

**Adapter layer**: Use an ABC-based `DistributorAdapter` interface (inspired by KiCost's `distributor_class` and InvenTree's `SupplierMixin`). Each distributor implements `search(query, filters, limit)`, `get_part(mpn, manufacturer)`, `configure(config)`, and `validate_credentials()`. Return a unified `ComponentResult` dataclass with MPN, manufacturer, description, specs (as normalized `ParametricValue` objects with parsed numeric values and SI units), offers (per-distributor: SKU, stock, MOQ, price breaks, currency, URL), lifecycle status, datasheet URL, and category.

**Caching**: SQLite-backed cache with per-source TTL (pricing: 4 hours, parametric data: 7-30 days, datasheets: indefinite) — modeled on KiCost's `QueryCache` but using SQLite instead of JSON files. Cache keys hashed as `{source}:{query_type}:{normalized_query}`. Add an in-memory LRU layer for hot session data. Enable offline mode that serves stale cache with visual staleness indicators.

**Local database**: Adopt kicad-jlcpcb-tools' pattern of a pre-built SQLite FTS5 database for the JLCPCB/LCSC catalog as a "basic search works without API keys" baseline. The ~1M+ parts with descriptions, packages, stock, and pricing provide useful results for many common components. Augment with cached results from API queries over time, building a growing local parametric database.

**Parametric filtering**: Use `QSortFilterProxyModel` subclass for client-side filtering over merged results — instant response without additional API calls when refining parameters. Normalize specs using a parameter alias dictionary (mapping "Capacitance" / "Cap" / "Nominal Capacitance" to a canonical name) and a unit-aware parser (port KiBoM's `units.py` or use the `pint` library) for SI unit conversion.

**GUI structure**: `QMainWindow` with search bar + category selector, a parametric filter panel (`QTreeView` or custom filter widgets), a results table (`QTableView` + `QSortFilterProxyModel`), and a detail panel showing specs, offers, datasheet, image, and lifecycle. Background API queries via `QThread` workers emitting results incrementally per adapter, so users see partial results immediately.

**Authentication**: Store API keys using the `keyring` library for OS-native secret storage. Support YAML config + environment variable overrides (KiCost's pattern). For Digi-Key's OAuth2, implement a local HTTP server callback handler within the PySide6 app. For Nexar, use client credentials flow (simpler). Display credential validation status per adapter in a settings panel.

**Rate limiting**: Token-bucket rate limiter per API with configurable limits. Exponential backoff with jitter on 429/503 errors (use the `tenacity` library). Queue API calls in background thread.

---

## Recommended implementation priority and key reusable code

For fastest time-to-value, build in this order:

1. **JLCPCB/LCSC offline database** (week 1): Port kicad-jlcpcb-tools' `library.py` chunked download + SQLite FTS5 pattern. This gives basic search with zero API keys. Augment with JLCParts' parametric data processing for richer filtering.

2. **DigiKey adapter** (week 2): Use `digikey-api` package (or the Swagger-generated `digikey-apiv4`). DigiKey offers the best free parametric search at 1,000 requests/day. Implement the OAuth2 callback server.

3. **Mouser adapter** (week 2): Use `mouser` PyPI package (MIT license). Simple API key auth. Keyword search only — supplement DigiKey's parametric filtering with Mouser's pricing/stock data.

4. **Nexar adapter** (week 3): Direct GraphQL with `requests`. Only worthwhile if users have Pro-tier keys. Provides the richest multi-distributor aggregated data.

5. **Element14 + TME adapters** (week 3-4): Fill out European distributor coverage.

Key files to extract or study from existing projects:

- **KiCost** `distributors/distributor.py`: `QueryCache` class, `distributor_class` base pattern
- **KiCost** `distributors/api_nexar.py`: OAuth2 client credentials flow, GraphQL query construction
- **kicad-jlcpcb-tools** `library.py`: SQLite FTS5 database download and search
- **kicad-jlcpcb-tools** `lcsc_api.py`: JLCPCB/LCSC REST API client
- **JLCParts** data processing scripts: Parametric field extraction and normalization pipeline
- **JLCParts** `LCSC-API.md`: Undocumented LCSC endpoint documentation
- **KiBoM** `units.py`: Engineering value normalization (µF↔nF↔pF)
- **Ki-nTree** `kintree/search/`: Multi-supplier API integration patterns and field normalization
- **sparkmicro/mouser-api**: Clean MIT-licensed Mouser wrapper

---

## Conclusion

The open-source electronics tooling ecosystem is rich in components but lacks an integrated solution. **KiCost provides the best distributor API abstraction layer** (MIT, Python, 6 active API modules), **kicad-jlcpcb-tools provides the best local search database pattern** (MIT, Python, SQLite FTS5 with 1M+ JLCPCB parts), and **JLCParts provides the only working parametric search architecture** (MIT, Python data pipeline). The **DigiKey API v4 offers the most generous free parametric search** at 1,000 requests/day — making it the best primary API for a tool that works without paid subscriptions. Nexar/Octopart's crippled free tier (100 parts lifetime) makes it viable only as a premium option with user-provided Pro keys.

The missing piece is purely integration: a PySide6 shell that composes these existing modules into a unified search experience. Every significant technical challenge — OAuth2 handling, GraphQL query construction, FTS5 search, unit normalization, price break parsing, multi-source deduplication — has been solved in at least one MIT-licensed Python project. The engineering task is assembly, not invention.