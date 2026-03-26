# Sprint Change Proposal: Data Storage Model Tidying

**Date:** 2026-03-25
**Triggered by:** Documentation drift and need to formalize two-location data model
**Scope:** Minor — documentation updates + one docstring fix, no behavioral code changes

## Section 1: Issue Summary

Over 9 epics of development, the data storage model evolved organically:
- Story 8.1 migrated from `~/.kipart-search/` to `platformdirs`, but 20+ documentation references still used the old path
- Story 9.1 (in review) correctly stores verification state in the project folder, but its epic spec described the old `{data_dir}/projects/{hash}` approach
- The boundary between "per-user data" (AppData) and "per-project data" (KiCad project folder) was never formally documented
- Multiple designers working on the same KiCad project need project-level data (verification state, backups) shareable via the project folder

## Section 2: Impact Analysis

### Epic Impact
No epics affected. All code is already correct — the implementation puts:
- User data in platformdirs (`core/paths.py`)
- Project data in `{project_dir}/.kipart-search/` (`project_state.py`, `main_window.py` backup manager)

### Artifact Updates Applied

| Artifact | Changes |
|----------|---------|
| **architecture.md** | Replaced "User Data Files" section with comprehensive "Data Storage Model" (user data + project data + multi-user principle). Fixed 3 `~/.kipart-search/` refs in ADRs. |
| **prd.md** | Updated 2 refs: File system section now describes two-location model; config path uses platformdirs. |
| **epics.md** | Fixed 7 `~/.kipart-search/` refs to use `{data_dir}/` or `{project_dir}/.kipart-search/` as appropriate. Fixed Story 9.1 implementation details to match actual code (project-dir storage, no hash). Left Story 8.1 legacy refs intact (they correctly describe the migration source). |
| **ux-design-specification.md** | Fixed backup path to `{project_dir}/.kipart-search/backups/`. |
| **CLAUDE.md** | Added "Data storage — two-location model" section. Updated config path to platformdirs. |
| **core/paths.py** | Clarified `backups_dir()` docstring as standalone-mode fallback only. |

### Technical Impact
None — no behavioral code changes. The code was already correct.

## Section 3: Recommended Approach

**Direct Adjustment** — all changes applied in this proposal. No rollback, no MVP scope change.

- **Effort:** Low (documentation only)
- **Risk:** Low (no code behavior changes)
- **Timeline impact:** None

## Section 4: Data Storage Model (Canonical Reference)

### User Data (per machine/user) — platformdirs

Location: `platformdirs.user_data_dir("KiPartSearch")` — resolved via `core/paths.py`

| File | Purpose |
|------|---------|
| `config.json` | Source enable/disable, welcome version |
| `cache.db` | SQLite query cache (per-source TTL) |
| `jlcpcb/parts-fts5.db` | JLCPCB offline database (~1M parts) |
| `jlcpcb/db_meta.json` | Database download metadata |
| `templates/*.json` | Custom BOM export templates |
| OS Keyring | API keys (DigiKey, Mouser, Nexar) + license key/JWT |
| QSettings | Window geometry, dock state |

### Project Data (per KiCad project) — shareable

Location: `{kicad_project_dir}/.kipart-search/`

| File | Purpose |
|------|---------|
| `verification-state.json` | User review decisions (Verified/Attention/Rejected) |
| `backups/{timestamp}/components.json` | Component state snapshot before write-back |
| `backups/{timestamp}/undo_log.csv` | Per-field change audit trail |
| `backups/{timestamp}/*.kicad_sch` | Schematic file copies |

### Standalone Fallback

When no KiCad project is connected, backups go to `{data_dir}/backups/`.

### Multi-User Principle

Multiple designers can work on the same KiCad project. Each has their own user data (API keys, cache, database). Project data lives in the KiCad project folder and is visible to all team members. The `.kipart-search/` folder can be committed to version control (`verification-state.json` is shareable; `backups/` can be gitignored).

## Section 5: Implementation Handoff

**Scope:** Minor — all changes already applied in this session.
**Handoff:** Development team — changes are documentation + docstring only.
**Success criteria:** No remaining `~/.kipart-search/` references in active planning artifacts (except Story 8.1 migration description).
