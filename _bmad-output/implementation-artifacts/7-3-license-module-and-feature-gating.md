# Story 7.3: License Module and Feature Gating

Status: done

## Story

As a developer,
I want a license module that validates a one-time license key and gates premium features behind class-level capability checks,
So that free and paid tiers are enforced in both development and compiled builds.

## Acceptance Criteria

1. **Given** the application starts without a license key, **When** the user launches the app, **Then** the free tier is fully functional: JLCPCB search, KiCad scan/highlight, basic verification (MPN present/missing), single-component write-back, CSV export. Pro-gated features show a disabled state with tooltip "Requires Pro license": multi-distributor search, CM BOM export templates, full verification (datasheet/footprint checks), batch write-back, Excel export.

2. **Given** the user enters a valid license key in the Preferences dialog, **When** the key is validated online via LemonSqueezy/Gumroad API, **Then** all Pro features become available immediately without restart. The license key is stored securely via `keyring`. The status bar shows "Pro" badge.

3. **Given** the app has a cached valid license but no internet connection, **When** the user launches the app offline, **Then** the offline signed-JWT fallback validates the cached key. Pro features remain available.

4. **Given** a Pro-gated feature class (e.g., `BatchWriteBack`, `CMBOMExport`), **When** instantiated without a valid Pro license, **Then** a `FeatureNotAvailable("pro")` exception is raised at `__init__` level (class-level gating, not bare conditionals).

5. **Given** the `core/license.py` module, **Then** it contains the `License` class, feature registry, and validation logic. The pricing model is one-time fee (not subscription) — no expiry check on valid keys.

## Tasks / Subtasks

- [x] Task 1: Create `core/license.py` — License class and feature registry (AC: #4, #5)
  - [x] 1.1 Define `FeatureNotAvailable` exception class
  - [x] 1.2 Define feature registry mapping feature names to tiers (`FREE_FEATURES`, `PRO_FEATURES` sets)
  - [x] 1.3 Implement `License` class as singleton with `has(feature) -> bool`, `tier -> str`, `activate(key) -> bool`
  - [x] 1.4 Implement online validation via LemonSqueezy/Gumroad REST API using `httpx`
  - [x] 1.5 Implement offline signed-JWT fallback: cache validated license as JWT in keyring, verify signature locally
  - [x] 1.6 Implement `require(feature)` method that raises `FeatureNotAvailable` if feature not available
  - [x] 1.7 Store/retrieve license key via `keyring` (service: "kipart-search", username: "license-key")
  - [x] 1.8 Signal mechanism: `license_changed` callback list so GUI can react to activation without restart

- [x] Task 2: Add feature gates to existing code (AC: #1, #4)
  - [x] 2.1 Gate multi-distributor search: in `SearchOrchestrator.search()`, filter to JLCPCB-only when free tier
  - [x] 2.2 Gate CM BOM export templates: in `BOMExporter` — CSV always allowed, Excel + CM templates require Pro
  - [x] 2.3 Gate full verification: `update_license_state()` hook added to verify panel; current verify panel only does basic MPN checks (free tier) — full checks (datasheet URL, footprint consistency) not yet implemented
  - [x] 2.4 Gate batch write-back: single-component assign dialog is free; batch "Push all to KiCad" requires Pro
  - [x] 2.5 Use class-level `__init__` gating pattern — call `License.instance().require("feature_name")` in `__init__`

- [x] Task 3: Add license UI to Preferences dialog (AC: #2)
  - [x] 3.1 Add "License" tab/section to `source_preferences_dialog.py` with key input field and "Activate" button
  - [x] 3.2 Show validation status: green checkmark (valid), red X (invalid), spinner during validation
  - [x] 3.3 On successful activation, emit signal to update all gated UI elements immediately
  - [x] 3.4 Show current tier in dialog: "Free" or "Pro (licensed)"

- [x] Task 4: Update status bar and toolbar for tier visibility (AC: #2)
  - [x] 4.1 Add "Pro" badge to status bar right zone when licensed (green pill, same style as connection badge)
  - [x] 4.2 Disable Pro-gated toolbar actions with tooltip "Requires Pro license" when free tier
  - [x] 4.3 Subscribe to `license_changed` to update badges/tooltips dynamically

- [x] Task 5: Disable Pro features in GUI with visual indicators (AC: #1)
  - [x] 5.1 In export dialog: disable Excel/CM template options, show "Pro" label
  - [x] 5.2 In verify panel: `update_license_state()` placeholder ready; no Pro-only columns exist yet (full verification checks are future work)
  - [x] 5.3 In search bar source selector: disable non-JLCPCB sources with "Pro" tooltip
  - [x] 5.4 Batch write-back gated in `_on_push_to_kicad()` (main_window.py); assign dialog has no batch mode — it is always single-component

- [x] Task 6: Tests (AC: all)
  - [x] 6.1 Test `License` class: default free tier, feature registry, `has()` and `require()` methods
  - [x] 6.2 Test `FeatureNotAvailable` raised correctly for Pro features when unlicensed
  - [x] 6.3 Test feature gates don't block free-tier operations
  - [x] 6.4 Test activation flow with mocked API response
  - [x] 6.5 Test offline JWT fallback validates cached key

## Dev Notes

### Feature Tier Split (War Room Consensus)

**Free tier** (genuinely useful — must never feel crippled):
- JLCPCB search (local FTS5 database)
- KiCad scan + click-to-highlight
- Basic verification (MPN present/missing only)
- Single-component write-back (assign dialog)
- CSV BOM export

**Pro tier** (productivity-at-scale — upgrade trigger is 70+ component boards):
- Multi-distributor search (DigiKey, Mouser, Octopart)
- CM BOM export templates (JLCPCB, PCBWay, Newbury Electronics) + Excel export
- Full verification (datasheet URL check, footprint consistency, symbol validation)
- Batch write-back ("Push all to KiCad")

### Pricing Model

One-time license fee ($30-50 range), NOT subscription. KiCad community strongly resists SaaS/subscription tooling. No expiry checks on valid keys.

### Architecture Pattern: Class-Level Gating

Use `raise FeatureNotAvailable("pro")` in `__init__` of gated classes. This is harder to patch in compiled binary than bare `if not license.has()` conditionals scattered through the code.

```python
# In core/license.py
class FeatureNotAvailable(Exception):
    def __init__(self, tier: str):
        super().__init__(f"Feature requires {tier} license")
        self.tier = tier

class License:
    _instance = None

    @classmethod
    def instance(cls) -> "License":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def has(self, feature: str) -> bool:
        """Check if current tier includes feature."""
        ...

    def require(self, feature: str) -> None:
        """Raise FeatureNotAvailable if feature not available."""
        if not self.has(feature):
            raise FeatureNotAvailable("pro")
```

```python
# In gated class __init__
class CMBOMExport:
    def __init__(self, ...):
        License.instance().require("cm_export")
        # ... rest of init
```

### Online Validation (LemonSqueezy/Gumroad)

Use `httpx` (already a project dependency) for API calls. Both platforms provide simple REST endpoints for license key validation:

- **LemonSqueezy**: `POST https://api.lemonsqueezy.com/v1/licenses/validate` with `license_key` and `instance_name`
- **Gumroad**: `POST https://api.gumroad.com/v2/licenses/verify` with `product_id` and `license_key`

Pick ONE platform (recommend LemonSqueezy — better developer experience, one-time fee support). The validation endpoint returns JSON with license status. On success, generate a signed JWT cached in keyring for offline fallback.

### Offline JWT Fallback

When online validation succeeds:
1. Create a JWT payload: `{"tier": "pro", "validated_at": timestamp, "machine_id": hash}`
2. Sign with an embedded secret (sufficient for compiled binary — not attempting DRM, just honest gating)
3. Store in keyring as "kipart-search" / "license-jwt"

On offline startup:
1. Load JWT from keyring
2. Verify signature
3. If valid → Pro tier enabled (no expiry check)

### Credential Storage Pattern

Follow existing `source_config.py` pattern for keyring usage:
- Service name: `"kipart-search"`
- License key username: `"license-key"`
- License JWT username: `"license-jwt"`
- Environment variable override: `KIPART_LICENSE_KEY`

### Dev Bypass Key

For testing Pro features without a real LemonSqueezy account:
- **Key**: `dev-pro-unlock`
- **Where**: Preferences > License section > enter key > click Activate
- **Guard**: Only works when `"__compiled__" not in globals()` — rejected in Nuitka binaries
- **Effect**: Skips online validation, activates Pro tier, caches JWT in keyring
- Persists across restarts; use the Deactivate button to revert to free tier
- The env var `KIPART_LICENSE_KEY=anything` also works but bypasses the GUI flow entirely

### GUI Integration Points

**Files to modify:**

| File | Change |
|------|--------|
| `core/license.py` | **NEW** — License class, feature registry, validation, JWT |
| `core/source_config.py` | ~~Add `get_license_key()` / `set_license_key()`~~ — NOT MODIFIED: License class handles its own keyring storage directly via `_keyring_get`/`_keyring_set` helpers |
| `gui/source_preferences_dialog.py` | Add License tab with key input + Activate button |
| `gui/main_window.py` | Initialize License on startup, subscribe to tier changes, update status bar |
| `gui/export_dialog.py` | Disable Excel/CM options when free tier |
| `gui/verify_panel.py` | Disable datasheet/footprint check columns when free tier |
| `gui/search_bar.py` | Disable non-JLCPCB sources when free tier |
| `gui/assign_dialog.py` | Disable batch mode when free tier |
| `build_nuitka.py` | Ensure `core/license.py` included (should be automatic via `--include-package=kipart_search`) |

**Status bar "Pro" badge** — same pill widget pattern as the existing connection mode badge in `main_window.py` (left zone has green "Connected to KiCad" pill / gray "Standalone" pill). Add "Pro" green pill to right zone.

### Existing Patterns to Follow

- **Keyring access**: See `source_config.py` lines 87-251 — `SourceConfigManager` class, `keyring.get_password()` / `keyring.set_password()` with try/except for backend failures
- **Config persistence**: `~/.kipart-search/config.json` via `SourceConfigManager._load_config()` / `_save_config()`
- **Status bar updates**: `main_window.py` — `_update_status_bar()` method updates left/center/right zones
- **Dialog pattern**: See `source_preferences_dialog.py` for modal dialog with validation feedback
- **Nuitka keyring fix**: `__main__.py` `_init_keyring_compiled()` forces Windows backend when `"__compiled__" in globals()` — license keyring calls will work in compiled binary
- **Background threading**: Feature gates must be thread-safe since `SearchWorker` and `ScanWorker` run in QThreads

### Project Structure Notes

- `core/license.py` is a new file in `core/` — zero GUI dependencies, consistent with core/GUI separation
- License validation uses `httpx` (already a dependency) — no new deps needed
- JWT handling: use `hmac` + `json` + `base64` from stdlib (no PyJWT dependency needed for simple HMAC-signed tokens)
- The singleton pattern for `License` class is appropriate here — license state is global app state

### What NOT to Do

- Do NOT add PyJWT dependency — use stdlib `hmac`/`hashlib` for simple signed tokens
- Do NOT add expiry checks — one-time license, no subscription
- Do NOT add hardware fingerprinting or activation limits — keep it honest, not DRM
- Do NOT modify `pyproject.toml` license field yet — that happens at distribution time
- Do NOT add telemetry or phone-home beyond explicit license validation
- Do NOT scatter `if license.has()` checks everywhere — use class-level `__init__` gating
- Do NOT block app startup on license validation — validate async, default to free tier

### Previous Story Intelligence (Story 7.2)

**Key learnings from Story 7.2:**
- Nuitka binary at `dist/__main__.dist/__main__.exe` (47 MB exe, 116 MB total with deps)
- After Story 7.1 code review, `--output-filename=kipart-search` flag added (rebuild produces `kipart-search.exe`)
- All existing `--include-*` flags sufficient — no additional flags needed for current features
- `"__compiled__" in globals()` correctly detects Nuitka runtime
- `_init_keyring_compiled()` in `__main__.py` already working — license keyring calls will work
- Windows Defender may flag Nuitka binaries (known issue #2685, needs code signing later)
- SSL certs bundled via certifi; `truststore` package available if needed
- 215 tests passing; some pre-existing Qt segfaults in MainWindow-instantiating GUI tests (unrelated)

**Files created/modified in Story 7.2:**
- `tests/smoke_test_build.py` — Interactive smoke test checklist (22 tests)
- `tests/test_smoke_test_build.py` — Pytest tests for smoke test framework
- `build_nuitka.py` — Fixed dist path comment

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 7, Story 7.3]
- [Source: _bmad-output/planning-artifacts/epics.md — Additional Requirements: License gating architecture]
- [Source: _bmad-output/planning-artifacts/epics.md — FR38, FR39, NFR16, NFR17]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-03: Credential Storage]
- [Source: src/kipart_search/core/source_config.py — keyring pattern, lines 87-251]
- [Source: src/kipart_search/gui/main_window.py — status bar, lines 189-350]
- [Source: src/kipart_search/__main__.py — Nuitka keyring init, lines 6-26]
- [Source: _bmad-output/implementation-artifacts/7-2-compiled-binary-full-functionality-verification.md — Dev notes]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

### Completion Notes List

- Task 1: Created `core/license.py` with `License` singleton, `FeatureNotAvailable` exception, feature registry (`FREE_FEATURES`, `PRO_FEATURES`), `has()`/`require()` methods, LemonSqueezy online validation via httpx, offline HMAC-signed JWT fallback using stdlib only (no PyJWT), keyring storage, env var override (`KIPART_LICENSE_KEY`), and `on_change()` callback mechanism.
- Task 2: Added feature gates — `SearchOrchestrator.search()` filters to local-only sources when free tier; `SearchOrchestrator.search_source()` raises `FeatureNotAvailable` for non-local sources; `export_bom()` gates Excel format (`excel_export`) and CM templates (`cm_export`); `_on_push_to_kicad()` gates batch write-back. Updated existing tests to use `pro_license` fixture.
- Task 3: Added License section to `SourcePreferencesDialog` with key input, Activate/Deactivate buttons, validation status indicators (green check/red X), background `LicenseValidationWorker` thread, tier display pill, and `license_changed` signal.
- Task 4: Added "Pro" green pill badge to status bar right zone (visible when licensed), connected `license_changed` callback to update badge and toolbar tooltips dynamically.
- Task 5: Export dialog disables Excel format and CM templates (PCBWay, Newbury) with "[Pro]" suffix when free tier, defaults to JLCPCB CSV. Search bar source selector disables non-JLCPCB sources with "Requires Pro license" tooltip. Batch Push to KiCad shows informational dialog when free tier.
- Task 6: 32 tests covering feature registry (disjoint sets, known features), exception class, singleton pattern, default free tier, `has()`/`require()`, callbacks, activation/deactivation flow, JWT sign/verify roundtrip, tampered token detection, offline JWT restoration, env var override, wrong-machine JWT rejection, search orchestrator gating (free filters to local, pro includes all), BOM export gating (CSV free, Excel blocked, CM blocked).

### Change Log

- 2026-03-23: Story 7.3 implementation complete — license module, feature gating, GUI integration, 32 tests
- 2026-03-24: Code review #1 fixes — JWT secret XOR-obfuscated, thread-safe callbacks, verify panel `update_license_state()` hook, search bar refresh on license change, FakeSource decoupled from license in cache tests, story tasks clarified. Fixed QThread cross-thread parenting: LicenseValidationWorker now only validates online, activation runs on main thread via `activate(_skip_validation=True)`. Added `dev-pro-unlock` dev bypass key (source builds only). Hardened conftest to block keyring reads during singleton reset.

### File List

**New files:**
- src/kipart_search/core/license.py
- tests/test_license.py

**Modified files:**
- src/kipart_search/core/search.py (license gate in search/search_source)
- src/kipart_search/core/bom_export.py (license gate in export_bom)
- src/kipart_search/gui/main_window.py (license init, Pro badge, license_changed callback, batch push gate)
- src/kipart_search/gui/source_preferences_dialog.py (License section, LicenseValidationWorker)
- src/kipart_search/gui/export_dialog.py (Pro gates on templates/formats)
- src/kipart_search/gui/search_bar.py (Pro gates on non-local sources)
- src/kipart_search/gui/verify_panel.py (update_license_state() hook for future Pro checks)
- tests/conftest.py (_reset_license_singleton, pro_license fixtures)
- tests/core/test_bom_export.py (pro_license fixture for Excel/CM tests)
- tests/core/test_offline_operation.py (pro_license for cached API source test)
- tests/core/test_sqlite_query_cache.py (pro_license for orchestrator cache tests)
- _bmad-output/implementation-artifacts/sprint-status.yaml (status update)
