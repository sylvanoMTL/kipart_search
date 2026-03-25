"""Interactive smoke test for write-back workflow fixes (Spec A).

Run this script in a terminal while KiPart Search is running with
KiCad 9+ connected to a test project.

Usage:
    python tests/smoke_test_writeback.py

Prerequisites:
    - KiCad 9+ running with a test project open (.kicad_pcb + .kicad_sch)
    - Close the schematic editor in KiCad before push tests
    - JLCPCB database downloaded
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

# Reuse the smoke test framework from the build smoke tests
from smoke_test_build import SmokeTestSuite, _prompt_result


def build_writeback_checklist() -> SmokeTestSuite:
    """Define smoke tests covering all 8 acceptance criteria."""
    suite = SmokeTestSuite()

    # ── AC 7: Freshness column removed ──
    suite.add(
        "no-freshness-column",
        "Scan a project. Check the verify table columns: "
        "Reference, Value, MPN, MPN Status, Footprint. "
        "There should be NO 'Freshness' column.",
        "AC 7: Freshness column removed",
    )

    # ── AC 8: No stale log messages ──
    suite.add(
        "no-stale-log",
        "After the scan completes, check the log panel. "
        "There should be NO message about 'verified before last database update' "
        "or 'stale' or 're-scan recommended'.",
        "AC 8: No stale-related log messages",
    )

    # ── AC 3: Project dir auto-detected, no picker ──
    suite.add(
        "project-dir-detected",
        "After scanning, check the log panel for a line like: "
        "'Project directory (from KiCad): C:\\...\\MyProject'. "
        "This confirms get_project_dir() works with kipy.",
        "AC 3: Project directory auto-detected from KiCad board",
    )

    # ── Assign MPNs for push test ──
    suite.add(
        "assign-mpn",
        "Double-click a component with missing MPN (e.g. C6). "
        "Search for a part, select it, click Assign. "
        "Verify the component turns GREEN in the verify table.",
        "Setup: MPN assigned locally for push test",
    )

    # ── AC 3: Push without folder picker ──
    suite.add(
        "push-no-picker",
        "Close the schematic editor in KiCad. "
        "Click 'Push to KiCad'. Confirm in the dialog. "
        "Verify NO folder picker dialog appears. "
        "Check the log for 'Project directory (cached): ...'.",
        "AC 3: No folder picker when project dir is cached",
    )

    # ── AC 5: Backup in project directory ──
    suite.add(
        "backup-project-scoped",
        "After the push, check the log for the backup path. "
        "It should be inside the KiCad project folder: "
        "{project}/.kipart-search/backups/{project-name}/{timestamp}/. "
        "NOT in %LOCALAPPDATA%\\KiPartSearch\\backups\\.",
        "AC 5: Backup stored in project directory",
    )

    # ── Re-verify after push ──
    suite.add(
        "reverify-after-push",
        "Click 'Re-verify'. Verify it reconnects to KiCad "
        "(log shows 'Re-verify' section) and rescans all components. "
        "The scan should complete with component count, not 'No components found'.",
        "Re-verify works after push (forces reconnect)",
    )

    # ── AC 1: GREEN statuses preserved on re-scan ──
    suite.add(
        "green-preserved-rescan",
        "After re-verify completes, check the previously assigned component. "
        "It should still show as Verified (GREEN), not 'Not found' (RED). "
        "The health percentage should not drop to 0%.",
        "AC 1: Verified statuses preserved across re-scans",
    )

    # ── AC 2: Changed MPN gets fresh status ──
    suite.add(
        "changed-mpn-fresh-status",
        "In KiCad schematic editor, manually change a component's MPN field "
        "to a bogus value (e.g. 'INVALID_MPN'). Save. Close schematic. "
        "Click Re-verify in KiPart Search. "
        "That component should show RED/Not found (not cached GREEN).",
        "AC 2: Changed MPN gets fresh verification, not cached",
    )

    # ── AC 4: Standalone mode folder picker ──
    suite.add(
        "standalone-folder-picker",
        "Close KiCad entirely. Restart KiPart Search. "
        "Assign an MPN to a component (if possible without scan). "
        "Click Push to KiCad. A folder picker should appear as last resort. "
        "SKIP this test if standalone push is not easily reachable.",
        "AC 4: Folder picker appears in standalone mode",
    )

    # ── AC 6: Standalone backup fallback ──
    suite.add(
        "standalone-backup-fallback",
        "If standalone push was tested above, check the backup path. "
        "It should fall back to %LOCALAPPDATA%\\KiPartSearch\\backups\\ "
        "when no project directory is available. "
        "SKIP if standalone push was not tested.",
        "AC 6: Backup falls back to user home in standalone mode",
    )

    # ── Edge case: path with spaces ──
    suite.add(
        "path-with-spaces",
        "Verify the test KiCad project path contains spaces "
        "(e.g. 'MecaFrog Rowing power meter'). "
        "If so, confirm that push and backup worked correctly "
        "with that path (no path-related errors in log).",
        "Edge case: Spaces in project path handled correctly",
    )

    return suite


def run_smoke_tests() -> None:
    """Run the interactive write-back smoke test session."""
    print("=" * 60)
    print("KiPart Search - Write-back Workflow Fixes Smoke Tests")
    print("=" * 60)
    print()
    print("Prerequisites:")
    print("  1. KiCad 9+ running with a test project open")
    print("  2. JLCPCB database downloaded in KiPart Search")
    print("  3. Close the schematic editor before push tests")
    print()
    print("Launch KiPart Search:")
    print("  .env\\Scripts\\python.exe -m kipart_search")
    print()

    input("Press Enter when ready to begin...")

    suite = build_writeback_checklist()
    total = len(suite.tests)

    for i, test in enumerate(suite.tests, 1):
        _prompt_result(i, total, test)

    suite.end_time = datetime.now()

    # Print summary
    print()
    print(suite.summary_text())

    # Save results
    output_dir = Path("_bmad-output") / "test-results"
    path = suite.save_results(output_dir)
    print(f"\nResults saved to: {path}")


if __name__ == "__main__":
    run_smoke_tests()
