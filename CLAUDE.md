# KiPart Search

> Fast parametric electronic component search across multiple distributor APIs, with KiCad integration via IPC API.

## Project identity

- **Name**: KiPart Search
- **Repo**: `kipart-search`
- **License**: MIT
- **Language**: Python 3.10+
- **GUI**: PySide6 (standalone desktop app)
- **KiCad integration**: IPC API via `kicad-python` (KiCad 9.0+)
- **Author**: Sylvain Boyer (MecaFrog)

## What this tool does

Two main functions:

1. **Parametric component discovery**: start from **specs** (voltage, package, interface, capacitance…) → discover MPNs you didn't know about. This is the opposite of BOM costing tools like KiCost which start from known MPNs.

2. **BOM verification / design audit**: for an existing KiCad project, walk through every component and verify that the MPN, datasheet, symbol and footprint are correct and consistent. Flag missing fields, broken datasheet links, mismatched footprints, obsolete parts, and unresolved generic values (e.g. "100nF" with no MPN assigned).

When connected to a running KiCad instance, clicking a component in the verification table or search results highlights the corresponding footprint in the PCB editor, which KiCad then cross-probes to the schematic automatically.

## Architecture decisions

### Dual-mode: standalone + KiCad connected

The app runs as a **standalone PySide6 process**. It does NOT run inside KiCad's wxPython interpreter. When KiCad is running with IPC API enabled, the app connects via `kicad-python` to select/highlight footprints in the PCB editor. KiCad's built-in cross-probe then highlights the component in the schematic.

The IPC API in KiCad 9.0 only supports the PCB editor. Schematic editor support is expected in KiCad 10. This is fine — selecting in PCB triggers schematic highlight via KiCad's internal cross-probe.

### Project structure

```
kipart-search/
├── CLAUDE.md                # This file
├── pyproject.toml
├── README.md
├── src/
│   └── kipart_search/
│       ├── __init__.py
│       ├── __main__.py      # Entry point: python -m kipart_search
│       ├── core/            # Zero GUI dependencies
│       │   ├── models.py    # PartResult, ParametricValue, PriceBreak
│       │   ├── sources.py   # DataSource ABC + all adapters
│       │   ├── cache.py     # SQLite cache with per-source TTL
│       │   ├── search.py    # Search orchestrator (parallel queries)
│       │   ├── units.py     # Engineering value normalisation (µF↔nF↔pF)
│       │   └── verify.py    # BOM verification engine (MPN, datasheet, symbol, footprint checks)
│       ├── gui/             # PySide6 standalone app
│       │   ├── main_window.py
│       │   ├── search_bar.py
│       │   ├── results_table.py
│       │   ├── spec_panel.py
│       │   ├── settings_dialog.py
│       │   ├── verify_panel.py  # BOM verification view with per-component status
│       │   └── kicad_bridge.py  # IPC API connection to KiCad
│       └── cli/             # Optional CLI entry point
│           └── __main__.py
└── tests/
```

### Core / GUI separation

The `core/` package has **zero GUI dependencies**. It can be imported by a CLI, a future KiCad wxPython shim, or tests. All PySide6 code lives in `gui/`. All distributor API code lives in `core/sources.py`.

### Data source plugin pattern

Each distributor is a subclass of `DataSource(ABC)` with:
- `search(query, filters, limit) -> list[PartResult]`
- `get_part(mpn, manufacturer) -> PartResult`
- `is_configured() -> bool`
- `key_fields: list[str]` — required credential field names
- `needs_key: bool` — whether API key is required

Results are normalised to a common `PartResult` dataclass.

### Background search

Searches run in `QThread` workers per source, emitting results incrementally via signals. The GUI shows partial results as each source responds.

### Caching

SQLite-backed cache with per-source TTL:
- Pricing/stock: 4 hours
- Parametric data: 7–30 days
- Datasheets: indefinite

Modelled on KiCost's `QueryCache` pattern but using SQLite.

### Credentials storage

- Config file: `~/.kipart-search/config.json` (or YAML)
- API keys stored via `keyring` library for OS-native secret storage
- Environment variable overrides supported
- GUI settings dialog for entering/validating credentials

### License activation

- **Production**: One-time license key validated via LemonSqueezy API (not yet configured — no product exists yet)
- **Env var override**: `KIPART_LICENSE_KEY=anything` → activates Pro immediately, no validation
- **Dev bypass key**: Enter `dev-pro-unlock` in Preferences > License > Activate. Works only in source builds (rejected in compiled Nuitka binaries). Exercises the full GUI activation flow without a real LemonSqueezy account.
- Validated licenses are cached as HMAC-signed JWTs in keyring for offline use

### BOM verification / design audit (`core/verify.py`)

When connected to a KiCad project via the IPC API, the tool reads the board/schematic BOM and runs a series of checks on every component. The verification panel displays a table of all components with a per-field status (pass / warning / fail / missing).

**Checks performed per component:**

| Field | Check | Status |
|-------|-------|--------|
| **MPN** (manf#) | Field exists and is not empty. MPN is found in at least one distributor API. Part is not obsolete/EOL. | ✅ / ⚠️ / ❌ |
| **Datasheet** | URL field exists and is not empty. URL is reachable (HTTP HEAD check, cached). Points to a PDF, not a dead link or generic page. | ✅ / ⚠️ / ❌ |
| **Symbol** | Symbol library reference is valid (library exists, symbol name resolves). Pin count matches footprint pad count where applicable. | ✅ / ⚠️ / ❌ |
| **Footprint** | Footprint library reference is valid. Footprint name is consistent with the component's package spec from the distributor (e.g. MPN says QFN-24, footprint is QFN-24). | ✅ / ⚠️ / ❌ |

**Additional BOM-level checks:**
- Components with generic values (e.g. "100nF") but no MPN assigned
- Duplicate MPNs with different values or footprints (possible copy-paste errors)
- Components excluded from BOM but still placed on board
- Missing fields that are expected by the project (configurable required-fields list)

**GUI behaviour:**
- Verification results displayed in a table: Reference | Value | MPN | Datasheet | Symbol | Footprint — each cell colour-coded (green/amber/red)
- Clicking any row highlights the component in KiCad (PCB select → schematic cross-probe)
- Double-clicking a failing MPN cell opens the parametric search pre-filled with the component's value/footprint, to help find a valid MPN
- Double-clicking a datasheet cell opens the URL in the browser
- "Re-check" button to re-run verification after fixes
- Export verification report as CSV or markdown

**Verification runs in background threads** to avoid blocking the GUI. Distributor API calls (MPN validation, obsolescence check) respect rate limits and use the cache layer.

## Data sources — implementation priority

### 1. JLCPCB/LCSC offline database (no API key needed)

**This is the zero-config baseline.** Download a pre-built SQLite FTS5 database of ~1M+ JLCPCB parts (from kicad-jlcpcb-tools' GitHub Pages hosting). Provides basic search with no API keys.

Reference code:
- `kicad-jlcpcb-tools/library.py` — chunked download + SQLite FTS5 search
- `kicad-jlcpcb-tools/lcsc_api.py` — LCSC REST client for part detail enrichment
- `yaqwsx/jlcparts` — parametric field extraction and normalisation pipeline
- LCSC unofficial endpoint: `https://cart.jlcpcb.com/shoppingCart/smtGood/getComponentDetail?componentCode={LCSC_NUMBER}`
- LCSC rate-limits scraping to ~100 req/min

The database is hosted as chunked files at `bouni.github.io/kicad-jlcpcb-tools/`.

### 2. Digi-Key API v4 (best free parametric search)

**1,000 requests/day free.** Supports `ParametricFilters` for category-based electrical parameter filtering. Best balance of parametric capability and free access.

- Auth: OAuth2 (2-legged client credentials for basic search, 3-legged with localhost:8139 callback for full access)
- Python package: `digikey-api` (peeter123/digikey-api, GPL-3.0) or official `digikey-apiv4` on PyPI
- The `hurricaneJoef` fork has v4 support: `pip install git+https://github.com/hurricaneJoef/digikey-api.git`
- Registration: https://developer.digikey.com
- Locale: site=UK, currency=GBP

### 3. Mouser (simple but keyword-only)

**Free API key, no parametric search** — keyword and MPN lookup only. Supplement with pricing/stock after finding MPNs via DigiKey or LCSC.

- Auth: API key in query parameter
- Python package: `mouser` on PyPI (sparkmicro/mouser-api, MIT)
- Registration: https://www.mouser.com/api-hub/
- Endpoint: `https://api.mouser.com/api/v2/search/keyword`

### 4. Nexar/Octopart (richest data, but expensive)

**Only worthwhile with Pro-tier keys** ($250/month). Free tier is 100 parts lifetime — useless for parametric search. The `supSearch` query supports filters, aggregations, manufacturer filtering across 100+ distributors.

- Auth: OAuth2 client credentials
- API: GraphQL at `https://api.nexar.com/graphql`
- Token URL: `https://identity.nexar.com/connect/token`
- Registration: https://portal.nexar.com
- No mature Python wrapper; use `httpx` + direct GraphQL

### 5. Element14/Farnell (European coverage)

- Auth: API key
- Some parametric search via search term prefixes
- Covers Farnell, Newark, CPC across 30+ countries

### 6. TME (European distributor)

- Auth: HMAC token + secret
- Good specs data
- Official Python examples: `tme-dev/TME-API` on GitHub
- Registration: https://developers.tme.eu

### 7. TrustedParts.com (free aggregator)

- Completely free API, sponsored by ECIA
- 25M+ part numbers from authorised distributors
- Simple REST, no Python wrapper yet

## Key open-source references

### Code to reuse or study

| Project | What to extract | License |
|---------|----------------|---------|
| **KiCost** `distributors/distributor.py` | `QueryCache` class, base distributor pattern | MIT |
| **KiCost** `distributors/api_nexar.py` | OAuth2 client credentials, GraphQL queries | MIT |
| **kicad-jlcpcb-tools** `library.py` | SQLite FTS5 database download + search | MIT |
| **kicad-jlcpcb-tools** `lcsc_api.py` | LCSC REST API client | MIT |
| **JLCParts** (`yaqwsx/jlcparts`) | Parametric field extraction pipeline | MIT |
| **KiBoM** `units.py` | Engineering value normalisation (µF↔nF↔pF) | MIT |
| **Ki-nTree** `kintree/search/` | Multi-supplier API patterns | GPL-3.0 |
| **sparkmicro/mouser-api** | Clean Mouser wrapper | MIT |
| **kicad-python** (PyPI) | IPC API bindings for KiCad 9+ | MIT |

### Key GitHub repos

- `hildogjr/KiCost` — ~590 stars, MIT, mature multi-distributor integration
- `Bouni/kicad-jlcpcb-tools` — ~1,800 stars, MIT, local JLCPCB/LCSC database
- `yaqwsx/jlcparts` — ~741 stars, MIT, only existing parametric search for JLCPCB
- `sparkmicro/Ki-nTree` — ~450 stars, GPL-3.0, part creation for KiCad+InvenTree
- `jvanderberg/kicad_jlcimport` — plugin+standalone+CLI+TUI architecture reference
- `Part-DB/Part-DB-server` — ~1,477 stars, AGPL, best parametric data model reference
- `inventree/InvenTree` — ~6,200 stars, MIT, SupplierMixin plugin architecture
- `replaysMike/Binner` — ~800 stars, GPL, C#, multi-distributor integration reference

### Dead/obsolete — avoid

- **Kitspace/PartInfo API** — company dissolved March 2026, endpoint dead
- **Octopart REST API v3/v4** — deprecated, replaced by Nexar GraphQL
- **PartKeepr** — archived July 2025
- **PartsBox** — proprietary, not open-source

## KiCad IPC API integration

### How it works

The PySide6 app connects to a running KiCad 9+ instance via the `kicad-python` library:

```python
from kipy import KiCad

kicad = KiCad()  # auto-detects socket via env vars or default path
board = kicad.get_board()
footprints = board.get_footprints()

# Select a footprint by reference → PCB highlights → schematic cross-probes
board.select(footprint)
```

Environment variables set by KiCad when launching API plugins:
- `KICAD_API_SOCKET` — socket path
- `KICAD_API_TOKEN` — instance token

For standalone launch (not from KiCad), the app auto-discovers the default socket at `/tmp/kicad/api.sock` (Linux/macOS) or the Windows equivalent.

### KiCad bridge module (`gui/kicad_bridge.py`)

Responsibilities:
- Detect if KiCad is running and IPC API is available
- Read board data: footprint references, values, existing MPN fields
- Select/highlight footprints when user clicks a search result
- Write back assigned MPNs to footprint fields
- Graceful degradation: if KiCad is not running, all features work except highlight/assign

### Cross-probe chain

`KiPart Search selects footprint in PCB` → `KiCad PCB editor highlights it` → `KiCad internal cross-probe highlights in schematic`

No schematic API needed. The PCB → schematic link is handled by KiCad internally.

## Coding style preferences

- **Minimalistic code** — simple examples that can be enhanced progressively
- **No unused metadata** — don't add fields, imports, or config that aren't used yet
- **Clean separation** — core logic has zero GUI dependencies
- **Type hints** — use them but don't over-annotate
- **Direct communication** — technically precise variable/function names
- **Languages**: Python primary, with experience in MATLAB, C/C++, Arduino
- **Preferred HTTP client**: `httpx` (already used in prototype)
- **Testing**: start with manual testing, add pytest later

## Dependencies

### Core (no GUI)
```
httpx          # HTTP client for API calls
keyring        # OS-native credential storage
```

### GUI
```
PySide6        # Qt6 bindings
```

### KiCad integration (optional)
```
kicad-python   # IPC API bindings (requires KiCad 9.0+)
```

## Current status

- Literature review complete
- Architecture decisions finalised
- Prototype `sources.py` and `main.py` exist (from earlier in conversation) — to be restructured into the `src/` layout above
- No repo created yet

## Next steps

1. Create repo with `src/kipart_search/` structure
2. Port prototype `sources.py` → `core/sources.py` with the DataSource ABC
3. Implement JLCPCB/LCSC offline database (zero-config baseline)
4. Build PySide6 GUI shell with search bar, results table, spec panel
5. Add DigiKey adapter with OAuth2
6. Add Mouser adapter
7. Implement `kicad_bridge.py` for IPC API highlight/select
8. Add SQLite cache layer
9. Implement `core/verify.py` — BOM verification engine (MPN, datasheet, symbol, footprint checks)
10. Build `gui/verify_panel.py` — verification table with colour-coded status, click-to-highlight
11. Package for PyPI and KiCad Plugin and Content Manager
