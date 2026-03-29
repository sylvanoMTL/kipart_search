"""Interactive smoke test runner for Epic 8 — Installer, Auto-Update & Release Pipeline.

Displays clear step-by-step instructions.  You execute each step manually
(commands, GUI actions, Windows checks).  After each test, record the result
as Pass / Fail / Skip with optional notes.  A timestamped report is saved
to dist/ on exit — even on Ctrl+C or early quit.

Usage:
    .env\\Scripts\\python.exe smoke_test_epic8.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration — adjust these before running
# ---------------------------------------------------------------------------

# Release A: built by step 1.1 (--bump minor from current version)
# Release B: built by step 2.1 (--bump patch from Release A)
# Example: if current version is 0.2.0, Release A = 0.3.0, Release B = 0.3.1
VER_A = "0.3.0"
VER_B = "0.3.1"
REPO = "sylvanoMTL/kipart_search"


# ---------------------------------------------------------------------------
# Test definitions
# ---------------------------------------------------------------------------

def _build_tests() -> list[dict]:
    A = VER_A
    B = VER_B
    R = REPO

    return [
        # ── Phase 1 — Build & Install Release A ──
        {
            "id": "1.1",
            "phase": f"Phase 1 — Build & Install Release A (v{A})",
            "name": "Tag & Push to Trigger CI Build",
            "story": "8.3, 8.4",
            "steps": [
                "Run in PowerShell:",
                "  PS> .env\\Scripts\\python.exe release.py --tag --bump minor --skip-tests",
                f"       → version bumps to {A}, tags v{A}, and pushes to GitHub",
                "",
                "Wait for CI build to complete:",
                f"  PS> gh run watch --repo {R}",
                "       → wait for green checkmark",
                "",
                "Verify release assets on GitHub:",
                f"  PS> gh release view v{A} --repo {R}",
                "       → shows .exe, .zip, and checksums assets",
            ],
        },
        {
            "id": "1.2",
            "phase": f"Phase 1 — Build & Install Release A (v{A})",
            "name": "Download & Install Release A",
            "story": "8.2, 8.4",
            "steps": [
                "Download the installer:",
                f"  PS> gh release download v{A} --repo {R} --dir dist/ --pattern '*setup.exe' --clobber",
                f"  PS> ls dist\\*{A}*setup.exe",
                "       → file exists",
                "",
                "Run the installer:",
                f"  PS> Start-Process dist\\kipart-search-{A}-setup.exe",
                "",
                "In the Inno Setup wizard:",
                "  GUI> Proceed with defaults → installs to C:\\Program Files\\KiPart Search\\",
                "  GUI> Verify 'Create desktop shortcut' checkbox exists",
                "  GUI> Complete installation — wizard closes without error",
                "",
                "Verify installation:",
                "  WIN> Start Menu → 'KiPart Search' shortcut exists",
                f"  WIN> Settings > Apps > Installed Apps → 'KiPart Search' listed, version {A}",
                "  PS> Test-Path 'C:\\Program Files\\KiPart Search\\kipart-search.exe'",
                "       → True",
            ],
        },
        {
            "id": "1.3",
            "phase": f"Phase 1 — Build & Install Release A (v{A})",
            "name": "Launch Release A — Version & Update Dialog",
            "story": "8.1, 8.2, 8.5",
            "steps": [
                "Launch from Start Menu or:",
                "  PS> & 'C:\\Program Files\\KiPart Search\\kipart-search.exe'",
                "",
                "Check version display:",
                f"  GUI> Splash screen → expect 'v{A}' in grey text",
                f"  GUI> Startup popup dialog → 'You are running the latest version (v{A})'",
                f"  GUI> Window title → 'KiPart Search v{A}'",
                f"  GUI> Help > About → dialog showing 'v{A}'",
                f"  GUI> Status bar (bottom-right) → 'v{A}' displayed permanently",
            ],
        },
        {
            "id": "1.4",
            "phase": f"Phase 1 — Build & Install Release A (v{A})",
            "name": "platformdirs Data Paths",
            "story": "8.1",
            "steps": [
                "  PS> Test-Path \"$env:LOCALAPPDATA\\KiPartSearch\"",
                "       → True",
                "  PS> Test-Path \"$env:LOCALAPPDATA\\KiPartSearch\\config.json\"",
                "       → True",
                "  PS> Test-Path \"$env:USERPROFILE\\.kipart-search\\config.json\"",
                "       → should NOT exist (legacy path not used)",
            ],
        },
        {
            "id": "1.5",
            "phase": f"Phase 1 — Build & Install Release A (v{A})",
            "name": "Basic Functionality",
            "story": "all",
            "steps": [
                "If 'No datasource available' → click 'Download Database' first (fresh install).",
                "  GUI> Type 'capacitor 100nF' in search bar, press Enter → results appear",
                "  GUI> Click any result row → Detail panel shows part info",
                "  GUI> Check Log panel (bottom) → timestamped messages",
                "  GUI> Help > Check for Updates... → info dialog appears",
                "  GUI> Close app (X button), relaunch → window layout restored",
            ],
        },

        # ── Phase 2 — Build Release B & Update Detection ──
        {
            "id": "2.1",
            "phase": "Phase 2 — Build Release B & Update Detection",
            "name": f"Build Release B (v{B})",
            "story": "8.3, 8.4",
            "steps": [
                "Close KiPart Search if running.",
                "",
                "  PS> .env\\Scripts\\python.exe release.py --tag --bump patch --skip-tests",
                "",
                "Wait for CI:",
                f"  PS> gh run watch --repo {R}",
                "",
                "Verify:",
                f"  PS> gh release view v{B} --repo {R}",
                f"       → has kipart-search-{B}-setup.exe asset",
            ],
        },
        {
            "id": "2.2",
            "phase": "Phase 2 — Build Release B & Update Detection",
            "name": "Update Check Detects Release B on Startup",
            "story": "8.5, 8.6",
            "steps": [
                "Clear the update cache so the app does a fresh GitHub check:",
                "  PS> $p = \"$env:LOCALAPPDATA\\KiPartSearch\\config.json\"",
                "  PS> $d = Get-Content $p | ConvertFrom-Json",
                "  PS> $d.PSObject.Properties.Remove('update_check')",
                "  PS> $d | ConvertTo-Json -Depth 10 | Set-Content $p",
                "",
                f"Launch Release A (v{A} is still installed):",
                "  PS> & 'C:\\Program Files\\KiPart Search\\kipart-search.exe'",
                "",
                "Expected on startup:",
                f"  GUI> UpdateDialog popup appears: 'Version {B} is available (you have {A})'",
                "  GUI> 3 buttons visible: [Update Now] [Remind Me Later] [Skip This Version]",
                "  GUI> Release notes shown in text area",
                f"  GUI> Status bar shows 'Update available: v{B}' in amber",
                "",
                "DO NOT click any button yet — proceed to test 2.3.",
            ],
        },
        {
            "id": "2.3",
            "phase": "Phase 2 — Build Release B & Update Detection",
            "name": "Full Download & Install (Happy Path)",
            "story": "8.6, 8.7",
            "steps": [
                "(Continuing from test 2.2 — UpdateDialog is open)",
                "",
                "  GUI> Click 'Update Now'",
                "  GUI> Progress bar appears: 'Downloading... X.X / Y.Y MB'",
                "  GUI> Wait for download to complete",
                "  GUI> Buttons change to: [Install Now] [Open Folder] [Close]",
                "  GUI> Click 'Install Now'",
                "  GUI> Warning dialog: 'Windows will ask for permission...' → click OK",
                "  GUI> App window closes",
                "  WIN> UAC prompt appears → click Yes",
                "       (silent install runs ~10-30 seconds...)",
                "",
                "After auto-relaunch, verify:",
                f"  GUI> Splash screen shows 'v{B}'",
                f"  GUI> Startup popup: 'You are running the latest version (v{B})'",
                f"  GUI> Window title: 'KiPart Search v{B}'",
                f"  GUI> Help > About → 'v{B}'",
                f"  GUI> Status bar → 'v{B}'",
                f"  WIN> Settings > Apps → 'KiPart Search' version {B}",
            ],
        },
        {
            "id": "2.4",
            "phase": "Phase 2 — Build Release B & Update Detection",
            "name": "Post-Update Functionality",
            "story": "8.7",
            "steps": [
                "  GUI> Search 'capacitor 100nF' → results returned normally",
                "  GUI> Window layout preserved (docks, sizes same as before)",
                "  PS> Test-Path \"$env:LOCALAPPDATA\\KiPartSearch\\config.json\"   → True",
                f"  GUI> Status bar → 'v{B}' (no update notification)",
                "  GUI> Close app",
            ],
        },

        # ── Phase 3 — Alternative Update Flows ──
        {
            "id": "3.1",
            "phase": "Phase 3 — Alternative Update Flows",
            "name": "Remind Me Later",
            "story": "8.6",
            "steps": [
                f"Reinstall Release A (v{A}):",
                f"  PS> Start-Process dist\\kipart-search-{A}-setup.exe",
                "  (complete wizard)",
                "",
                "Clear update cache:",
                "  PS> $p = \"$env:LOCALAPPDATA\\KiPartSearch\\config.json\"",
                "  PS> $d = Get-Content $p | ConvertFrom-Json",
                "  PS> $d.PSObject.Properties.Remove('update_check')",
                "  PS> $d | ConvertTo-Json -Depth 10 | Set-Content $p",
                "",
                "  PS> & 'C:\\Program Files\\KiPart Search\\kipart-search.exe'",
                f"  GUI> UpdateDialog appears with v{B}",
                "  GUI> Click 'Remind Me Later' → dialog closes, app continues",
                "  GUI> Close app",
                "",
                "Expire cache and relaunch:",
                "  PS> $d = Get-Content $p | ConvertFrom-Json",
                "  PS> $d.update_check.check_time = 0",
                "  PS> $d | ConvertTo-Json -Depth 10 | Set-Content $p",
                "  PS> & 'C:\\Program Files\\KiPart Search\\kipart-search.exe'",
                "  GUI> UpdateDialog appears again (cache expired → fresh check)",
                "  GUI> Close app",
            ],
        },
        {
            "id": "3.2",
            "phase": "Phase 3 — Alternative Update Flows",
            "name": "Skip This Version",
            "story": "8.6",
            "steps": [
                "Clear update cache (same as 3.1 setup).",
                "",
                "  PS> & 'C:\\Program Files\\KiPart Search\\kipart-search.exe'",
                "  GUI> UpdateDialog appears → click 'Skip This Version'",
                "  GUI> Dialog closes",
                "  GUI> Close app",
                "",
                "Verify skip was saved:",
                "  PS> Get-Content \"$env:LOCALAPPDATA\\KiPartSearch\\config.json\"",
                f"       → contains \"skipped_version\": \"{B}\"",
                "",
                "Expire cache and relaunch:",
                "  PS> $p = \"$env:LOCALAPPDATA\\KiPartSearch\\config.json\"",
                "  PS> $d = Get-Content $p | ConvertFrom-Json",
                "  PS> $d.update_check.check_time = 0",
                "  PS> $d | ConvertTo-Json -Depth 10 | Set-Content $p",
                "  PS> & 'C:\\Program Files\\KiPart Search\\kipart-search.exe'",
                f"  GUI> Startup popup: 'latest version' (v{B} is skipped)",
                "  GUI> NO UpdateDialog appears",
                "  GUI> Close app",
            ],
        },

        # ── Phase 4 — Failure & Resilience ──
        {
            "id": "4.1",
            "phase": "Phase 4 — Failure & Resilience",
            "name": "UAC Denial Recovery",
            "story": "8.8",
            "steps": [
                f"Reinstall Release A (if not already on v{A}).",
                "Clear update cache (same as before).",
                "",
                "  PS> & 'C:\\Program Files\\KiPart Search\\kipart-search.exe'",
                "  GUI> UpdateDialog appears → click 'Update Now'",
                "  GUI> Wait for download to complete",
                "  GUI> Click 'Install Now' → click OK on warning",
                "  GUI> App closes → UAC prompt appears",
                "  WIN> Click 'No' (DENY the UAC prompt)",
                "       (wait 10-30s for shim to detect failure...)",
                "  GUI> App relaunches → 'Update Failed' dialog appears",
                "  GUI> Verify: 3 buttons [Try Again] [Download Manually] [Close]",
                f"  GUI> Click 'Close' → app runs normally on v{A}",
            ],
        },
        {
            "id": "4.2",
            "phase": "Phase 4 — Failure & Resilience",
            "name": "Download Manually Fallback",
            "story": "8.8",
            "steps": [
                "Launch with --update-failed flag:",
                "  PS> & 'C:\\Program Files\\KiPart Search\\kipart-search.exe' --update-failed",
                "",
                "  GUI> 'Update Failed' dialog appears",
                "  GUI> Click 'Download Manually'",
                f"  WIN> Browser opens → https://github.com/{R}/releases",
            ],
        },
        {
            "id": "4.3",
            "phase": "Phase 4 — Failure & Resilience",
            "name": "Offline Graceful Degradation",
            "story": "8.5",
            "steps": [
                "  WIN> Disable Wi-Fi / unplug Ethernet",
                "",
                "Clear update cache, then launch:",
                "  PS> & 'C:\\Program Files\\KiPart Search\\kipart-search.exe'",
                "",
                "  GUI> App starts normally — no crash, no error dialog",
                "  GUI> Startup popup → graceful message (no error)",
                "  GUI> Log panel → no scary error messages",
                "",
                "  WIN> Re-enable internet",
                "  GUI> Close app",
            ],
        },
        {
            "id": "4.4",
            "phase": "Phase 4 — Failure & Resilience",
            "name": "Partial Download Cleanup",
            "story": "8.8",
            "steps": [
                "Create a fake old .partial file:",
                "  PS> New-Item \"$env:TEMP\\kipart-search-update-v0.0.1.partial\" -Force",
                "  PS> (Get-Item \"$env:TEMP\\kipart-search-update-v0.0.1.partial\").LastWriteTime = (Get-Date).AddDays(-2)",
                "",
                "  PS> & 'C:\\Program Files\\KiPart Search\\kipart-search.exe'",
                "  (wait for app to load, then close)",
                "",
                "  PS> Test-Path \"$env:TEMP\\kipart-search-update-v0.0.1.partial\"",
                "       → False (deleted by app)",
            ],
        },
        {
            "id": "4.5",
            "phase": "Phase 4 — Failure & Resilience",
            "name": "--update-failed Flag",
            "story": "8.8",
            "steps": [
                "  PS> & 'C:\\Program Files\\KiPart Search\\kipart-search.exe' --update-failed",
                "",
                "  GUI> Main window loads → 'Update Failed' dialog appears immediately",
                "  GUI> Verify 3 buttons: [Try Again] [Download Manually] [Close]",
                "  GUI> Click 'Close' → dialog dismissed, app works normally",
            ],
        },

        # ── Phase 5 — Edge Cases ──
        {
            "id": "5.1",
            "phase": "Phase 5 — Edge Cases",
            "name": "Inno Setup Upgrade Detection",
            "story": "8.2",
            "steps": [
                "Download Release B installer:",
                f"  PS> gh release download v{B} --repo {R} --dir dist/ --pattern '*setup.exe' --clobber",
                "",
                "Run it over the existing install:",
                f"  PS> Start-Process dist\\kipart-search-{B}-setup.exe",
                "",
                "  GUI> Wizard detects existing install → upgrades in-place",
                "  PS> Test-Path 'C:\\Program Files\\KiPart Search\\kipart-search.exe'  → True",
                f"  WIN> Settings > Apps → single 'KiPart Search' entry, version {B}",
            ],
        },
        {
            "id": "5.2",
            "phase": "Phase 5 — Edge Cases",
            "name": "Uninstall Preserves User Data",
            "story": "8.2",
            "steps": [
                "  WIN> Settings > Apps > KiPart Search > Uninstall",
                "",
                "  PS> Test-Path 'C:\\Program Files\\KiPart Search'",
                "       → False (removed)",
                "  PS> Test-Path \"$env:LOCALAPPDATA\\KiPartSearch\\config.json\"",
                "       → True (user data preserved!)",
                "  WIN> Start Menu → 'KiPart Search' shortcut removed",
            ],
        },
        {
            "id": "5.3",
            "phase": "Phase 5 — Edge Cases",
            "name": "Fresh Install After Uninstall",
            "story": "8.2",
            "steps": [
                f"  PS> Start-Process dist\\kipart-search-{B}-setup.exe",
                "  GUI> Complete install → launch from Start Menu",
                f"  GUI> Splash shows 'v{B}'",
                "  GUI> Search works, previous settings preserved",
            ],
        },
        {
            "id": "5.4",
            "phase": "Phase 5 — Edge Cases",
            "name": "24-Hour Cache TTL",
            "story": "8.5",
            "steps": [
                "  PS> & 'C:\\Program Files\\KiPart Search\\kipart-search.exe'",
                "  GUI> Startup dialog appears (fresh check), then close app",
                "",
                "Relaunch immediately:",
                "  PS> & 'C:\\Program Files\\KiPart Search\\kipart-search.exe'",
                "  GUI> Uses cached result — no new GitHub API call (verify in Log panel)",
                "  GUI> Close app",
                "",
                "Expire cache and relaunch:",
                "  PS> $p = \"$env:LOCALAPPDATA\\KiPartSearch\\config.json\"",
                "  PS> $d = Get-Content $p | ConvertFrom-Json",
                "  PS> $d.update_check.check_time = 0",
                "  PS> $d | ConvertTo-Json -Depth 10 | Set-Content $p",
                "  PS> & 'C:\\Program Files\\KiPart Search\\kipart-search.exe'",
                "  GUI> Fresh API call → startup dialog reflects current state",
            ],
        },
        {
            "id": "5.5",
            "phase": "Phase 5 — Edge Cases",
            "name": "Help > Check for Updates (Manual Trigger)",
            "story": "8.5, 8.6",
            "steps": [
                "  GUI> With app running: Help > Check for Updates...",
                "  GUI> Dialog appears (either 'up to date' or UpdateDialog)",
                "  GUI> Close dialog, app continues normally",
            ],
        },

        # ── Phase 6 — Release Script Validation ──
        {
            "id": "6.1",
            "phase": "Phase 6 — Release Script Validation",
            "name": "Version Gate",
            "story": "8.3",
            "steps": [
                "Run without --bump (version matches latest release):",
                "  PS> .env\\Scripts\\python.exe release.py --skip-tests",
                "       → expect: exits with error about version already released",
                "",
                "Run with --skip-version-gate:",
                "  PS> .env\\Scripts\\python.exe release.py --skip-version-gate --skip-tests",
                "       → expect: build proceeds past version check",
            ],
        },
        {
            "id": "6.2",
            "phase": "Phase 6 — Release Script Validation",
            "name": "SHA256 Checksums",
            "story": "8.3",
            "steps": [
                "  PS> ls dist\\*checksums*",
                "       → checksums file exists",
                "  PS> Get-Content dist\\*checksums*",
                "       → note the SHA256 for the setup.exe",
                f"  PS> certutil -hashfile dist\\kipart-search-{B}-setup.exe SHA256",
                "       → hash matches the value in the checksums file",
            ],
        },
    ]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"
DIM = "\033[2m"


class _Abort(Exception):
    pass


def _input(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        raise _Abort


def _print_progress(results: list[dict], total: int) -> None:
    passed = sum(1 for r in results if r["verdict"] == "PASS")
    failed = sum(1 for r in results if r["verdict"] == "FAIL")
    skipped = sum(1 for r in results if r["verdict"] == "SKIP")
    print(
        f"\n  {DIM}Progress: "
        f"{GREEN}{passed} passed{RESET}{DIM}, "
        f"{RED}{failed} failed{RESET}{DIM}, "
        f"{YELLOW}{skipped} skipped{RESET}{DIM} "
        f"/ {total} total{RESET}"
    )


def run_tests(results: list[dict]) -> None:
    tests = _build_tests()
    current_phase = ""
    total = len(tests)

    for i, test in enumerate(tests, 1):
        if test["phase"] != current_phase:
            current_phase = test["phase"]
            print(f"\n{'=' * 70}")
            print(f"{BOLD}{BLUE}  {current_phase}{RESET}")
            print(f"{'=' * 70}")

        print(f"\n{BOLD}[{i}/{total}] TEST {test['id']}: {test['name']}{RESET}")
        print(f"{DIM}Stories: {test['story']}{RESET}")
        print()

        for step in test["steps"]:
            # Colorize known prefixes
            colored = step
            if step.strip().startswith("PS>"):
                colored = step.replace("PS>", f"{CYAN}PS>{RESET}", 1)
            elif step.strip().startswith("GUI>"):
                colored = step.replace("GUI>", f"{GREEN}GUI>{RESET}", 1)
            elif step.strip().startswith("WIN>"):
                colored = step.replace("WIN>", f"{YELLOW}WIN>{RESET}", 1)
            elif step.strip().startswith("→"):
                colored = f"{DIM}{step}{RESET}"
            print(f"  {colored}")
        print()

        # Collect result
        while True:
            verdict = _input(
                f"  Result — {GREEN}[P]ass{RESET} / {RED}[F]ail{RESET} / "
                f"{YELLOW}[S]kip{RESET} / {DIM}[Q]uit{RESET}: "
            ).upper()
            if verdict in ("P", "PASS"):
                verdict = "PASS"; break
            elif verdict in ("F", "FAIL"):
                verdict = "FAIL"; break
            elif verdict in ("S", "SKIP"):
                verdict = "SKIP"; break
            elif verdict in ("Q", "QUIT"):
                print("\nSmoke test ended early by user.")
                return
            else:
                print("  Enter P, F, S, or Q.")

        notes = _input("  Notes (Enter to skip): ")

        results.append({
            "id": test["id"],
            "phase": test["phase"],
            "name": test["name"],
            "story": test["story"],
            "verdict": verdict,
            "notes": notes,
        })

        tag = {
            "PASS": f"{GREEN}[PASS]{RESET}",
            "FAIL": f"{RED}[FAIL]{RESET}",
            "SKIP": f"{YELLOW}[SKIP]{RESET}",
        }[verdict]
        print(f"  {BOLD}→ {tag} {test['id']} {test['name']}{RESET}")

        if verdict == "FAIL":
            _print_progress(results, total)
            while True:
                choice = _input(
                    f"\n  {RED}Test failed.{RESET} "
                    f"[{GREEN}C{RESET}]ontinue / [{RED}Q{RESET}]uit and save report? "
                ).upper()
                if choice in ("C", "CONTINUE"):
                    break
                elif choice in ("Q", "QUIT"):
                    print("\n  Stopping after failure. Report will be saved.")
                    return
                else:
                    print("  Enter C or Q.")


def write_report(results: list[dict]) -> Path:
    tests = _build_tests()
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d-%H%M")

    passed = sum(1 for r in results if r["verdict"] == "PASS")
    failed = sum(1 for r in results if r["verdict"] == "FAIL")
    skipped = sum(1 for r in results if r["verdict"] == "SKIP")
    remaining = len(tests) - len(results)

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("EPIC 8 SMOKE TEST RESULTS")
    lines.append("Installer, Auto-Update & Release Pipeline")
    lines.append("=" * 60)
    lines.append(f"Date: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Release A: v{VER_A}  |  Release B: v{VER_B}")
    lines.append("")
    lines.append(f"Total:   {len(results)}")
    lines.append(f"Passed:  {passed}")
    lines.append(f"Failed:  {failed}")
    lines.append(f"Skipped: {skipped}")
    if remaining > 0:
        lines.append(f"Not run: {remaining}")
    lines.append("")
    lines.append("DETAILED RESULTS:")

    current_phase = ""
    for r in results:
        if r["phase"] != current_phase:
            current_phase = r["phase"]
            lines.append(f"\n  --- {current_phase} ---")
        tag = f"[{r['verdict']}]"
        lines.append(f"  {tag:6s} {r['id']}. {r['name']}")
        lines.append(f"         Stories: {r['story']}")
        if r["notes"]:
            lines.append(f"         Notes: {r['notes']}")

    lines.append("")
    lines.append("=" * 60)
    if failed > 0:
        lines.append(f"VERDICT: {failed} FAILURE(S) — SEE NOTES ABOVE")
    else:
        lines.append("VERDICT: ALL PASSED")
    lines.append("=" * 60)

    dist = Path(__file__).parent / "dist"
    dist.mkdir(exist_ok=True)
    out = dist / f"smoke-test-epic8-{timestamp}.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _finish(results: list[dict], aborted: bool = False) -> None:
    if not results:
        print("\nNo results recorded.")
        return

    out = write_report(results)
    tests = _build_tests()

    passed = sum(1 for r in results if r["verdict"] == "PASS")
    failed = sum(1 for r in results if r["verdict"] == "FAIL")
    skipped = sum(1 for r in results if r["verdict"] == "SKIP")
    remaining = len(tests) - len(results)

    print(f"\n{'=' * 60}")
    if aborted:
        print(f"  {BOLD}{YELLOW}ABORTED{RESET} (Ctrl+C)")
    print(f"  {BOLD}SUMMARY{RESET}")
    print(f"  {GREEN}Passed: {passed}{RESET}  "
          f"{RED}Failed: {failed}{RESET}  "
          f"{YELLOW}Skipped: {skipped}{RESET}  "
          f"Total: {len(results)}")
    if remaining > 0:
        print(f"  {DIM}Not run: {remaining}{RESET}")
    print(f"\n  Results saved to: {out}")
    print(f"{'=' * 60}\n")


def main():
    tests = _build_tests()
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  KiPart Search — Epic 8 Smoke Test{RESET}")
    print(f"{BOLD}  {len(tests)} tests across 6 phases{RESET}")
    print(f"{BOLD}  Release A: v{VER_A}  |  Release B: v{VER_B}{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")
    print()
    print(f"  {CYAN}PS>{RESET}   = Run in VS Code PowerShell terminal")
    print(f"  {GREEN}GUI>{RESET}  = Action inside KiPart Search window")
    print(f"  {YELLOW}WIN>{RESET}  = Action in Windows (Start Menu, Settings, Explorer)")
    print()
    print("For each test: follow the steps, then enter the result.")
    print("P = Pass, F = Fail, S = Skip, Q = Quit early")
    print("On failure: choose to Continue or Quit (report saved either way)")
    print()

    results: list[dict] = []
    try:
        run_tests(results)
        _finish(results)
    except _Abort:
        print("\n\n  Smoke test interrupted by user.")
        _finish(results, aborted=True)


if __name__ == "__main__":
    main()
