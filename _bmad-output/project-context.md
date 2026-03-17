---
project_name: 'kipart-search'
user_name: 'Sylvain'
date: '2026-03-17'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'code_quality', 'workflow_rules', 'critical_rules']
status: 'complete'
rule_count: 42
optimized_for_llm: true
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

- **Python 3.10+** — type hints with `X | Y` union syntax, `from __future__ import annotations` in every file
- **PySide6** (Qt6) — GUI framework, standalone process (NOT inside KiCad's wxPython)
- **httpx** — HTTP client for API calls
- **keyring** — OS-native secret storage for API keys
- **kicad-python** (kipy) — optional, KiCad 9+ IPC API bindings
- **SQLite3** (stdlib) — FTS5 database for JLCPCB parts + QueryCache
- **hatchling** — build system (pyproject.toml)
- **pytest** — test framework (dev dependency)

## Critical Implementation Rules

### Python-Specific Rules

- Every file starts with `from __future__ import annotations` for deferred type evaluation
- Use `X | Y` union syntax (not `Optional[X]` or `Union[X, Y]`)
- Dataclasses for all data models (`@dataclass`), not TypedDict or Pydantic
- `Enum` for constrained value sets (e.g., `Confidence.GREEN/AMBER/RED`)
- `logging.getLogger(__name__)` at module level — never `print()` for diagnostics
- `Path` from `pathlib` for all file paths — never string concatenation
- Imports: stdlib → third-party → project, separated by blank lines
- Lazy imports in `__main__.py` (import inside function) to speed up CLI startup

### PySide6 & Architecture Rules

- **STRICT core/GUI separation**: `core/` has ZERO GUI imports — no PySide6, no Qt. It can be used by CLI, tests, or future KiCad wxPython shim.
- All GUI code lives in `gui/`. All distributor/database code lives in `core/sources.py`.
- Background work uses `QThread` subclasses with `Signal` for results — never block the main thread.
- Worker pattern: subclass QThread, define Signals (results_ready, error, log), override `run()`.
- Signals emit plain Python types (list, str, dict) — never Qt objects across threads.
- KiCad IPC API calls isolated in `gui/kicad_bridge.py` — no other module imports kipy directly.
- Graceful degradation: if kicad-python is not installed or KiCad is not running, all features except highlight/select and write-back work normally.
- Widget hierarchy: QMainWindow → QSplitter → panels. No deeply nested custom layouts.
- Colour constants for confidence: GREEN=#C8FFC8, AMBER=#FFEBB4, RED=#FFC8C8 (defined in verify_panel.py).

### Testing Rules

- pytest is the test framework — no unittest classes
- No tests exist yet — start with manual testing, add pytest later
- Test files go in `tests/` mirroring the `src/kipart_search/` structure
- Core modules can be tested without any GUI or Qt dependency
- GUI testing requires QApplication — use `pytest-qt` if/when GUI tests are added
- Mock the KiCad IPC API in tests — do not require a running KiCad instance
- JLCPCB database tests should use a small fixture DB, not the full 500MB download

### Code Quality & Style Rules

- File naming: snake_case for all Python files (e.g., `main_window.py`, `query_transform.py`)
- Class naming: PascalCase (e.g., `SearchOrchestrator`, `JLCPCBSource`, `PartResult`)
- Constants: UPPER_SNAKE_CASE at module level (e.g., `JLCPCB_COLUMNS`, `MPN_FIELD_NAMES`)
- Private/internal: leading underscore prefix (e.g., `_REF_PREFIX_MAP`, `_QUERY_FIXUPS`)
- Docstrings: triple-quote on first line of module/class/method. Brief — one-liner preferred. Only add where logic isn't self-evident.
- No type-annotation overkill — use hints but don't over-annotate obvious types
- Vendored code lives in `vendored/` with MIT attribution headers in the file (e.g., `vendored/units.py` from KiBoM)
- Package layout: `src/kipart_search/` — hatchling builds from `src/`
- Entry point: `python -m kipart_search` → `__main__.py` → `gui.main_window.run_app()`

### Development Workflow Rules

- Single developer (author) — no branch naming or PR conventions yet
- No CI/CD pipeline — manual testing workflow
- Config stored at `~/.kipart-search/config.json` — never store API keys in plaintext there; use keyring
- JLCPCB database stored at `~/.kipart-search/parts-fts5.db` — downloaded as chunked zip files from GitHub Pages
- No auto-update mechanism — standard `pip install --upgrade kipart-search`
- Cross-platform: develop on Windows (primary), test on Linux/macOS (secondary). Use `Path` everywhere.
- Git: MIT license, main branch, no submodules — vendored code instead

### Critical Don't-Miss Rules

- **NEVER** import PySide6/Qt in `core/` modules — this breaks the core/GUI separation contract
- **NEVER** overwrite non-empty KiCad component fields without explicit user confirmation (safety-first write-back)
- **NEVER** directly modify .kicad_sch or .kicad_pcb files — always use IPC API via kicad_bridge.py
- JLCPCB database uses ASCII for cap/inductor units (uF, nF, uH) but Unicode Ω for resistors (10kΩ) — `query_transform` and `sources.py` handle this mismatch with fixup tables. Do not "fix" the inconsistency.
- MPN field has 8+ aliases in KiCad libraries: "mpn", "manf#", "mfr part", "mfr.part", "manufacturer part number", etc. Always search all aliases via `MPN_FIELD_NAMES` set in kicad_bridge.py.
- KiCad footprint names like `C_0805_2012Metric` need package extraction (→ "0805") — done by `_extract_package_from_footprint()` in kicad_bridge.py, which handles passive sizes, IC packages (QFN, SOIC, SOT), and connector pin counts.
- The `DataSource` ABC (`core/sources.py`) is the plugin pattern — new distributors subclass it with `search()`, `get_part()`, `is_configured()`. Never bypass this abstraction.
- Query transformation is a 3-stage pipeline: (1) footprint prefix rules → (2) EE unit rules → (3) SI prefix normalization. Order matters — do not reorder stages.
- `generate_query_variants()` in `core/units.py` produces all equivalent SI representations (e.g., 0.1µF → [100nF, 0.1µF, 100000pF]). Search uses ALL variants for database matching.
- Download dialog uses chunked zip reassembly — the JLCPCB DB is split into numbered chunks. The chunk count comes from a remote text file. Do not assume a fixed chunk count.

---

## Usage Guidelines

**For AI Agents:**

- Read this file before implementing any code
- Follow ALL rules exactly as documented
- When in doubt, prefer the more restrictive option
- The core/GUI separation is the most critical architectural constraint

**For Humans:**

- Keep this file lean and focused on agent needs
- Update when technology stack or patterns change
- Remove rules that become obvious over time

Last Updated: 2026-03-17
