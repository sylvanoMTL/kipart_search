---
title: 'Replace Re-verify with Refresh BOM and Guard Scan Against No Sources'
slug: 'refresh-bom-guard-scan'
created: '2026-03-25'
status: 'implementation-complete'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python 3.10+', 'PySide6']
files_to_modify: ['src/kipart_search/gui/main_window.py', 'src/kipart_search/gui/verify_panel.py']
code_patterns: ['QThread worker pattern with Signal-based results', 'QMessageBox guard pattern for missing preconditions', 'Cached MPN status preservation in _on_scan_complete']
test_patterns: ['Manual testing — no automated tests for GUI']
---

# Tech-Spec: Replace Re-verify with Refresh BOM and Guard Scan Against No Sources

**Created:** 2026-03-25

## Overview

### Problem Statement

When no data sources are active (JLCPCB database not downloaded, API keys not configured), clicking Scan Project runs a pointless full scan that produces "0 verified, 47 missing/not found" and may crash silently. Additionally, Re-verify is redundant with Scan Project — it performs the same full BOM read + MPN verification with no incremental logic. Users need a lightweight way to re-read the KiCad BOM after pushing changes (F8) without re-verifying all MPNs against distributor databases.

### Solution

1. **Replace Re-verify with Refresh BOM** — a lightweight operation that reconnects to KiCad, re-reads the BOM (PCB + schematic merge), and preserves all cached MPN verification statuses. No source queries, no verification. Fast and works offline.

2. **Add source-availability guard to Scan Project** — when no data sources are active, show a helpful dialog (matching the existing search guard pattern) instead of running a meaningless scan.

### Scope

**In Scope:**
- Rename Re-verify button → Refresh BOM (label, tooltip, log messages)
- Refresh BOM logic: reconnect, re-read components, merge schematic, skip MPN verification, preserve all cached MPN statuses
- Add no-source guard to Scan Project with dialog pointing to JLCPCB download / Preferences
- Refresh BOM needs NO source guard (doesn't use sources)

**Out of Scope:**
- Smart incremental re-verify (future brainstorm)
- API source adapters (DigiKey, Mouser, etc.)
- Changes to the existing search guard
- Any new UI panels or widgets

## Context for Development

### Codebase Patterns

- **Guard pattern**: `_on_search()` at main_window.py:732 checks `self._orchestrator.active_sources` and shows a `QMessageBox.information` dialog if empty. Scan Project should replicate this.
- **Worker pattern**: `ScanWorker(QThread)` at main_window.py:83 does BOM read + MPN verification in `run()`. Refresh BOM needs a lighter worker (or a flag on ScanWorker) that skips the verification loop (lines 108-133).
- **Status preservation**: `_on_scan_complete()` at main_window.py:849 already restores local assignments (`_local_assignments`) and cached GREEN statuses (`_cached_mpn_statuses`/`_cached_mpn_values`). Refresh BOM reuses this handler but passes cached statuses through instead of fresh verification results.
- **Signal naming**: `reverify_requested` signal on VerifyPanel (verify_panel.py:91) — rename to `refresh_requested`.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `src/kipart_search/gui/main_window.py` | `_on_reverify()` (line 821), `_on_scan()` (line 792), `_on_scan_complete()` (line 849), `ScanWorker` (line 83) |
| `src/kipart_search/gui/verify_panel.py` | `reverify_button` (line 107), `reverify_requested` signal (line 91), `set_results()` (line 172) |
| `src/kipart_search/core/search.py` | `SearchOrchestrator.active_sources` property (line 32), `verify_mpn()` (line 137) |

### Technical Decisions

- **Refresh BOM deliberately skips MPN verification** to stay fast and source-independent
- **Scan Project remains the "heavy" full audit** operation requiring active sources
- **Add `skip_verify` flag to ScanWorker** rather than creating a separate worker class — keeps the BOM-reading and schematic-merge logic in one place, avoids duplication
- **Refresh BOM passes cached `_cached_mpn_statuses` as `mpn_statuses`** — `_on_scan_complete` then applies its existing local-assignment and cache-restoration logic on top
- **`has_sources` for Refresh BOM**: use `self._last_has_sources` (cached from previous scan) so the verify panel doesn't incorrectly downgrade statuses to AMBER "Unverified"
- Typical workflow: Scan Project → assign MPNs → push + F8 → Refresh BOM → (optional) Scan Project again for full re-verification

## Implementation Plan

### Tasks

- [x] Task 1: Add `skip_verify` flag to `ScanWorker`
  - File: `src/kipart_search/gui/main_window.py`
  - Action: Add `skip_verify: bool = False` parameter to `ScanWorker.__init__()`. In `run()`, when `skip_verify` is True: skip the MPN verification loop (lines 108-133), emit `scan_complete` with an **empty** `mpn_statuses` dict and `db_mtime=None`. Keep the BOM read + schematic merge logic unchanged.
  - Notes: Empty `mpn_statuses` signals to `_on_scan_complete` that no fresh verification was done — the handler will fill in from cache.

- [x] Task 2: Add source-availability guard to `_on_scan()`
  - File: `src/kipart_search/gui/main_window.py`
  - Action: At the top of `_on_scan()` (before the KiCad connection attempt at line 794), add a guard matching the search pattern:
    ```python
    if not self._orchestrator.active_sources:
        QMessageBox.information(
            self,
            "No Data Source",
            "No data source available.\n\n"
            "Download the JLCPCB database (File > Download Database) "
            "or configure API keys in Tools > Preferences.",
        )
        return
    ```
  - Notes: Guard goes before the KiCad connect — no point connecting if we can't verify anything.

- [x] Task 3: Rename Re-verify → Refresh BOM in `VerifyPanel`
  - File: `src/kipart_search/gui/verify_panel.py`
  - Action:
    - Rename signal `reverify_requested` → `refresh_requested` (line 91)
    - Rename button `reverify_button` → `refresh_button` (line 107)
    - Change button text from `"Re-verify"` to `"Refresh BOM"` (line 107)
    - Update accessible name to `"Refresh BOM"` (line 108)
    - Update tooltip to `"Re-read components from KiCad (preserves verification status)"` (line 109)
  - Notes: All references to `reverify_button` and `reverify_requested` in other files must be updated in Task 4.

- [x] Task 4: Update all `reverify` references in `MainWindow`
  - File: `src/kipart_search/gui/main_window.py`
  - Action: Replace all occurrences:
    - `reverify_requested` → `refresh_requested` (line 248)
    - `reverify_button` → `refresh_button` (lines 836, 905, 937)
    - `_on_reverify` → `_on_refresh_bom` (lines 248, 821)
  - Notes: Use find-and-replace across the file.

- [x] Task 5: Rewrite `_on_refresh_bom()` (formerly `_on_reverify`)
  - File: `src/kipart_search/gui/main_window.py`
  - Action: Replace the body of the method (lines 821-847) with:
    ```python
    def _on_refresh_bom(self):
        """Re-read BOM from KiCad without re-verifying MPNs.

        Reconnects to KiCad to pick up board changes after push + F8.
        Preserves all cached MPN verification statuses.
        """
        self.log_panel.section("Refresh BOM")
        ok, error_msg = self._bridge.connect()
        if not ok:
            QMessageBox.warning(
                self, "Not Connected",
                f"Cannot reconnect to KiCad: {error_msg}\n\n"
                "Make sure KiCad is running.",
            )
            return

        self.verify_panel.refresh_button.setEnabled(False)
        self._act_scan.setEnabled(False)
        self._set_action_status("Refreshing BOM...")
        self.log_panel.log(
            f"Refreshing {len(self.verify_panel.get_components())} components..."
        )

        self._scan_worker = ScanWorker(
            self._bridge, self._orchestrator, skip_verify=True
        )
        self._scan_worker.log.connect(self.log_panel.log)
        self._scan_worker.scan_complete.connect(self._on_scan_complete)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.start()
    ```
  - Notes: The key difference is `skip_verify=True`. No source guard needed.

- [x] Task 6: Update `_on_scan_complete()` to handle Refresh BOM (empty statuses)
  - File: `src/kipart_search/gui/main_window.py`
  - Action: After the local-assignments restoration block (line 877), add logic to fill empty `mpn_statuses` from cache:
    ```python
    # If no fresh verification was done (Refresh BOM), carry forward cached statuses
    if not mpn_statuses:
        for comp in components:
            ref = comp.reference
            cached = self._cached_mpn_statuses.get(ref)
            if cached is not None:
                mpn_statuses[ref] = cached
            elif not comp.has_mpn:
                mpn_statuses[ref] = Confidence.RED
    ```
    This block should go **before** the `has_sources` computation (line 878). Also cache `has_sources` so Refresh BOM can reuse it: add `self._last_has_sources` attribute, set it after computing `has_sources`, and use it as fallback when `mpn_statuses` was empty:
    ```python
    has_sources = bool(self._orchestrator.active_sources) or (
        not mpn_statuses_was_empty and False  # only for scan
    )
    ```
    Simpler approach: just use `self._last_has_sources` when the incoming `mpn_statuses` was empty.
  - Notes: Initialize `self._last_has_sources = True` alongside `self._cached_mpn_statuses` in `__init__`.

- [x] Task 7: Update `_on_scan_error()` to use renamed button
  - File: `src/kipart_search/gui/main_window.py`
  - Action: Change `self.verify_panel.reverify_button` → `self.verify_panel.refresh_button` at line 937.

- [x] Task 8: Update log messages
  - File: `src/kipart_search/gui/main_window.py`
  - Action: In `_on_scan_complete()`, update the status bar message to differentiate: if Refresh BOM (statuses were carried from cache), use `"Refresh complete: {n} components"` instead of `"Scan complete: {n} components"`. Add a `self._is_refresh` flag set in `_on_refresh_bom` / `_on_scan` to distinguish.
  - Notes: Alternatively, check whether `mpn_statuses` was empty on entry.

### Acceptance Criteria

- [x] AC 1: Given no active data sources (JLCPCB DB not downloaded, no API keys), when the user clicks Scan Project, then a dialog appears saying "No Data Source" with guidance to download JLCPCB database or configure API keys. The scan does NOT run.

- [x] AC 2: Given active data sources, when the user clicks Scan Project, then the scan runs normally with full MPN verification (no behavioral change).

- [x] AC 3: Given a completed scan with verified components, when the user clicks Refresh BOM, then the app reconnects to KiCad, re-reads all components, and displays them with their **previously cached MPN statuses preserved** (GREEN stays GREEN, AMBER stays AMBER).

- [x] AC 4: Given a completed scan, when the user pushes MPNs to KiCad, presses F8, then clicks Refresh BOM, then the updated MPN fields from KiCad are visible in the table, and previously verified statuses are preserved.

- [x] AC 5: Given no prior scan has been done (fresh app launch), when the user clicks Refresh BOM, then the app reads the BOM from KiCad and shows all components with no MPN verification statuses (RED for missing MPN, no status for others).

- [x] AC 6: Given no KiCad connection, when the user clicks Refresh BOM, then a "Not Connected" warning dialog appears (existing behavior preserved).

- [x] AC 7: Given the verify panel is visible, then the button reads "Refresh BOM" (not "Re-verify"), with tooltip "Re-read components from KiCad (preserves verification status)".

## Additional Context

### Dependencies

None — this is a pure GUI/orchestration change. No new packages or external services.

### Testing Strategy

Manual testing:
1. Launch app with no JLCPCB database → click Scan Project → verify "No Data Source" dialog appears
2. Download JLCPCB database → click Scan Project → verify full scan with MPN verification runs
3. After scan, click Refresh BOM → verify BOM re-reads, statuses preserved
4. Assign MPN, push to KiCad, F8, click Refresh BOM → verify updated fields shown, GREEN status preserved
5. Disconnect KiCad → click Refresh BOM → verify "Not Connected" dialog
6. Verify button text, tooltip, and accessible name are correct

### Notes

- Future brainstorm: smart incremental re-verify that only checks changed MPNs against sources
- The `skip_verify` flag on ScanWorker is designed to be extensible — a future "smart re-verify" could use a different flag value or additional parameters
- `_last_has_sources` prevents Refresh BOM from incorrectly showing all MPNs as "Unverified" when sources happen to be unavailable at refresh time but were available during the original scan
