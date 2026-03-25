"""Interactive smoke test checklist for compiled KiPart Search binary.

Run this script in a terminal while the compiled binary is running.
It walks through each feature, prompts pass/fail/skip, and saves results.

Usage:
    python tests/smoke_test_build.py
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class SmokeTest:
    """A single manual verification check."""

    name: str
    description: str
    acceptance_criteria: str
    result: str = "pending"  # pass, fail, skip
    notes: str = ""


@dataclass
class SmokeTestSuite:
    """Collection of smoke tests with reporting."""

    tests: list[SmokeTest] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None

    def add(self, name: str, description: str, acceptance_criteria: str) -> None:
        self.tests.append(SmokeTest(name, description, acceptance_criteria))

    @property
    def pass_count(self) -> int:
        return sum(1 for t in self.tests if t.result == "pass")

    @property
    def fail_count(self) -> int:
        return sum(1 for t in self.tests if t.result == "fail")

    @property
    def skip_count(self) -> int:
        return sum(1 for t in self.tests if t.result == "skip")

    @property
    def pending_count(self) -> int:
        return sum(1 for t in self.tests if t.result == "pending")

    def summary_text(self) -> str:
        total = len(self.tests)
        lines = [
            "=" * 60,
            "SMOKE TEST RESULTS",
            "=" * 60,
            f"Start: {self.start_time:%Y-%m-%d %H:%M:%S}",
        ]
        if self.end_time:
            lines.append(f"End:   {self.end_time:%Y-%m-%d %H:%M:%S}")
        lines += [
            "",
            f"Total:   {total}",
            f"Passed:  {self.pass_count}",
            f"Failed:  {self.fail_count}",
            f"Skipped: {self.skip_count}",
        ]
        if self.pending_count > 0:
            lines.append(f"Pending: {self.pending_count}")
        lines.append("")
        if self.fail_count > 0:
            lines.append("FAILURES:")
            for t in self.tests:
                if t.result == "fail":
                    lines.append(f"  - {t.name}: {t.description}")
                    if t.notes:
                        lines.append(f"    Notes: {t.notes}")
            lines.append("")

        lines.append("DETAILED RESULTS:")
        for i, t in enumerate(self.tests, 1):
            icon = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}.get(
                t.result, "????"
            )
            lines.append(f"  [{icon}] {i}. {t.name}")
            lines.append(f"         {t.description}")
            lines.append(f"         AC: {t.acceptance_criteria}")
            if t.notes:
                lines.append(f"         Notes: {t.notes}")

        lines.append("")
        lines.append("=" * 60)
        verdict = "ALL PASSED" if self.fail_count == 0 else "HAS FAILURES"
        lines.append(f"VERDICT: {verdict}")
        lines.append("=" * 60)
        return "\n".join(lines)

    def save_results(self, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        date_str = self.start_time.strftime("%Y-%m-%d-%H%M")
        path = output_dir / f"smoke-test-results-{date_str}.txt"
        path.write_text(self.summary_text(), encoding="utf-8")
        return path


def _prompt_result(test_num: int, total: int, test: SmokeTest) -> None:
    """Prompt user for pass/fail/skip on a single test."""
    print(f"\n--- Test {test_num}/{total}: {test.name} ---")
    print(f"  Description: {test.description}")
    print(f"  AC: {test.acceptance_criteria}")
    print()

    while True:
        result = input("  Result [p]ass / [f]ail / [s]kip: ").strip().lower()
        if result in ("p", "pass"):
            test.result = "pass"
            break
        if result in ("f", "fail"):
            test.result = "fail"
            test.notes = input("  Failure notes: ").strip()
            break
        if result in ("s", "skip"):
            test.result = "skip"
            reason = input("  Skip reason (optional): ").strip()
            if reason:
                test.notes = reason
            break
        print("  Invalid input. Enter p, f, or s.")


def build_checklist() -> SmokeTestSuite:
    """Define the full smoke test checklist covering AC #1-#8."""
    suite = SmokeTestSuite()

    # --- App Launch ---
    suite.add(
        "launch",
        "App launches without errors — no console window, main window visible",
        "AC #1, #8: Binary launches, GUI renders",
    )
    suite.add(
        "welcome-dialog",
        "Welcome dialog appears on first run (delete ~/.kipart-search/config.json first)",
        "AC #1: First-run experience works",
    )

    # --- JLCPCB Database ---
    suite.add(
        "jlcpcb-download",
        "JLCPCB database download completes with progress bar indication",
        "AC #1: Database download with progress indication",
    )

    # --- Search ---
    suite.add(
        "fts-search",
        "Full-text search returns results (type 'capacitor 100nF', verify results)",
        "AC #2: Search results return in under 5 seconds",
    )
    suite.add(
        "query-transform",
        "Search query transformation works (type 'R_0805', verify transform to '0805 resistor')",
        "AC #2: Query transformation pipeline functional",
    )
    suite.add(
        "dynamic-filters",
        "Dynamic filters appear after search (Manufacturer, Package dropdowns)",
        "AC #2: Filter UI renders and filters results",
    )

    # --- Detail Panel ---
    suite.add(
        "detail-panel",
        "Detail panel shows part info when a search result is selected",
        "AC #7: UI panels render correctly",
    )

    # --- KiCad Connection ---
    suite.add(
        "kicad-connection",
        "KiCad IPC connection works — status bar shows 'Connected' (requires KiCad 9+ running)",
        "AC #3: kicad-python optional import resolved, connection established",
    )
    suite.add(
        "board-scan",
        "Board scan populates verify panel with component list (requires KiCad connected)",
        "AC #4: Scan functions correctly",
    )
    suite.add(
        "click-to-highlight",
        "Click-to-highlight selects footprint in KiCad PCB editor",
        "AC #4: Highlight functions correctly",
    )
    suite.add(
        "assign-dialog",
        "Assign dialog opens from context menu or detail panel",
        "AC #4: Single-component write-back UI works",
    )
    suite.add(
        "push-to-kicad",
        "Push to KiCad writes fields to .kicad_sch file (requires KiCad connected)",
        "AC #4: Write-back functions correctly",
    )
    suite.add(
        "backup-created",
        "Backup created in ~/.kipart-search/backups/ after write session",
        "AC #4: Write-back safety intact",
    )

    # --- BOM Export ---
    suite.add(
        "bom-export-xlsx",
        "BOM export produces valid .xlsx file (select PCBWay template, export)",
        "AC #5: openpyxl working in compiled binary",
    )
    suite.add(
        "bom-export-csv",
        "BOM export produces valid .csv file",
        "AC #5: CSV export works",
    )

    # --- Keyring ---
    suite.add(
        "keyring-store",
        "Keyring stores and retrieves a test API key via Preferences dialog",
        "AC #6: OS-native Windows Vault backend works",
    )

    # --- QDockWidget Panels ---
    suite.add(
        "dock-panels",
        "QDockWidget panels can be floated, docked, tabbed, and hidden",
        "AC #8: All panel operations work",
    )
    suite.add(
        "layout-persist",
        "Layout persists after close and reopen",
        "AC #8: QSettings layout persistence works",
    )
    suite.add(
        "reset-layout",
        "View > Reset Layout restores default arrangement",
        "AC #8: Reset restores defaults",
    )

    # --- Verify Panel ---
    suite.add(
        "verify-colours",
        "Verify panel colour coding renders correctly (green/amber/red backgrounds)",
        "AC #7: Colour-coded status indicators render",
    )

    # --- Log Panel ---
    suite.add(
        "log-panel",
        "Log panel shows timestamped messages",
        "AC #7: Log panel functional",
    )

    # --- Performance ---
    suite.add(
        "cold-start-time",
        "Cold start time under 5 seconds (close app, relaunch, time it)",
        "AC #2: NFR19 startup performance",
    )

    return suite


def run_smoke_tests() -> None:
    """Run the interactive smoke test session."""
    print("=" * 60)
    print("KiPart Search — Compiled Binary Smoke Tests")
    print("=" * 60)
    print()
    print("Prerequisites:")
    print("  1. Build the binary: python build_nuitka.py")
    print("  2. Launch the compiled binary from dist/ folder")
    print("  3. Optionally have KiCad 9+ running with a project open")
    print()
    print("For each test, perform the described action in the running")
    print("binary and record pass/fail/skip.")
    print()

    input("Press Enter when ready to begin...")

    suite = build_checklist()
    total = len(suite.tests)

    for i, test in enumerate(suite.tests, 1):
        _prompt_result(i, total, test)

    suite.end_time = datetime.now()

    # Print summary
    print()
    print(suite.summary_text())

    # Save results
    dist_dir = Path(__file__).resolve().parent.parent / "dist"
    path = suite.save_results(dist_dir)
    print(f"\nResults saved to: {path}")

    if suite.fail_count > 0:
        print(
            f"\n{suite.fail_count} test(s) FAILED. "
            "Fix issues in build_nuitka.py, rebuild, and re-test."
        )


if __name__ == "__main__":
    run_smoke_tests()
