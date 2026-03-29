"""Interactive smoke test runner for Epic 8 — Installer, Auto-Update & Release Pipeline.

Walks through each test step-by-step, collects PASS/FAIL/SKIP and notes,
then writes a timestamped results file to dist/.

Usage:
    python smoke_test_epic8.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Test definitions
# ---------------------------------------------------------------------------

TESTS: list[dict] = [
    # Phase 1 — Build & Install Release A
    {
        "id": "1.1",
        "phase": "Phase 1 — Build & Install Release A",
        "name": "Version Bump + Local Build (0.2.0)",
        "story": "8.3",
        "steps": [
            "     (--bump requires --tag, so we bump+tag+build in one command)",
            "PS> python release.py --tag --bump minor --skip-tests",
            "PS> Select-String 'version' pyproject.toml                        → expect: version = \"0.2.0\"",
            "PS> Select-String '__version__' src/kipart_search/__init__.py      → expect: \"0.2.0\"",
            "PS> Select-String 'MyAppVersion' installer/kipart-search.iss       → expect: \"0.2.0\"",
            "PS> gh run watch                                                  (wait for CI green checkmark)",
            "PS> gh release view v0.2.0                                        → shows .exe, .zip, and checksums assets",
        ],
    },
    {
        "id": "1.2",
        "phase": "Phase 1 — Build & Install Release A",
        "name": "Install Release A via Inno Setup",
        "story": "8.2",
        "steps": [
            "     (use CI-built installer from step 1.6, or local from step 1.1)",
            "PS> Start-Process dist/kipart-search-0.2.0-setup.exe              (Inno Setup wizard opens)",
            "GUI> Proceed through wizard with defaults → installs to C:\\Program Files\\KiPart Search\\",
            "GUI> Verify 'Create desktop shortcut' checkbox exists (unchecked by default)",
            "GUI> Complete installation — wizard closes without error",
            "WIN> Open Start Menu → verify 'KiPart Search' shortcut exists",
            "WIN> Settings > Apps > Installed Apps → verify 'KiPart Search' listed, version 0.2.0",
            "PS> Test-Path 'C:/Program Files/KiPart Search/kipart-search.exe'  → True",
        ],
    },
    {
        "id": "1.3",
        "phase": "Phase 1 — Build & Install Release A",
        "name": "Launch Release A — Version Verification",
        "story": "8.1, 8.2, 8.3",
        "steps": [
            "WIN> Start Menu > click 'KiPart Search'   (no console window should appear)",
            "GUI> Observe splash screen → expect 'v0.2.0' in grey text",
            "GUI> Check window title bar → expect 'KiPart Search v0.2.0'",
            "GUI> Menu: Help > About → expect dialog showing 'v0.2.0'",
            "GUI> Check status bar at bottom → expect NO 'Update available' message",
        ],
    },
    {
        "id": "1.4",
        "phase": "Phase 1 — Build & Install Release A",
        "name": "platformdirs Data Paths",
        "story": "8.1",
        "steps": [
            "PS> Test-Path \"$env:LOCALAPPDATA/KiPartSearch\"                    → True",
            "PS> Test-Path \"$env:LOCALAPPDATA/KiPartSearch/config.json\"        → True",
            "PS> Test-Path \"$env:USERPROFILE/.kipart-search\"                   → should NOT have new files (legacy path)",
        ],
    },
    {
        "id": "1.5",
        "phase": "Phase 1 — Build & Install Release A",
        "name": "Basic Functionality Sanity Check",
        "story": "all",
        "steps": [
            "GUI> Type 'capacitor 100nF' in search bar, press Enter → results appear in table",
            "GUI> Click any result row → Detail panel (right side) shows part info",
            "GUI> Check Log panel (bottom) → timestamped search messages visible",
            "GUI> Menu: Edit > Preferences → dialog opens without errors, close it",
            "GUI> Close app (X button), relaunch from Start Menu → window layout restored",
        ],
    },
    {
        "id": "1.6",
        "phase": "Phase 1 — Build & Install Release A",
        "name": "Download Release A Installer from GitHub",
        "story": "8.4",
        "steps": [
            "     (CI built the installer in step 1.1 — download it now)",
            "PS> gh release download v0.2.0 --dir dist/ --pattern '*setup.exe'",
            "PS> ls dist/kipart-search-0.2.0-setup.exe                         → file exists",
        ],
    },
    # Phase 2 — Build Release B & Update Detection
    {
        "id": "2.1",
        "phase": "Phase 2 — Build Release B & Update Detection",
        "name": "Build Release B (0.2.1)",
        "story": "8.3, 8.4",
        "steps": [
            "PS> python release.py --tag --bump patch",
            "PS> gh run watch                  (wait for CI green checkmark)",
            "PS> gh release view v0.2.1        → has kipart-search-0.2.1-setup.exe asset",
        ],
    },
    {
        "id": "2.2",
        "phase": "Phase 2 — Build Release B & Update Detection",
        "name": "Update Check on Startup",
        "story": "8.5",
        "steps": [
            "PS> python -c \"import json,pathlib,os; p=pathlib.Path(os.environ['LOCALAPPDATA'])/'KiPartSearch'/'config.json'; d=json.loads(p.read_text()); d.pop('update_check',None); p.write_text(json.dumps(d,indent=2))\"",
            "PS> & 'C:/Program Files/KiPart Search/kipart-search.exe'",
            "GUI> Wait 5-10 seconds → status bar shows 'Update available: v0.2.1'",
            "PS> Get-Content \"$env:LOCALAPPDATA/KiPartSearch/config.json\"      → update_check section present with latest_version, asset_url, check_time",
        ],
    },
    {
        "id": "2.3",
        "phase": "Phase 2 — Build Release B & Update Detection",
        "name": "Full Download & Install (Happy Path)",
        "story": "8.6, 8.7",
        "steps": [
            "GUI> Click 'Update available: v0.2.1' text in status bar → UpdateDialog opens",
            "GUI> Verify header: 'Version 0.2.1 is available (you have 0.2.0)'",
            "GUI> Verify release notes are shown in text area",
            "GUI> Verify 3 buttons: [Update Now] [Remind Me Later] [Skip This Version]",
            "GUI> Click 'Update Now' → progress bar appears, 'Downloading... X.X / Y.Y MB'",
            "GUI> Wait for download to finish → status shows path in $env:TEMP, buttons become [Install Now] [Open Folder] [Close]",
            "GUI> Click 'Install Now' → dialog: 'Windows will ask for permission...' → click OK",
            "GUI> App window closes → Windows UAC prompt appears → click Yes",
            "     (silent install runs, wait 10-30 seconds...)",
            "GUI> App relaunches automatically → splash shows 'v0.2.1'",
            "GUI> Window title: 'KiPart Search v0.2.1'",
            "GUI> Help > About: shows 'v0.2.1'",
            "WIN> Settings > Apps: 'KiPart Search' version 0.2.1",
        ],
    },
    {
        "id": "2.4",
        "phase": "Phase 2 — Build Release B & Update Detection",
        "name": "Post-Update Functionality",
        "story": "8.7",
        "steps": [
            "GUI> Search 'capacitor 100nF' → results returned normally",
            "GUI> Verify window layout is same as before update (docks, sizes)",
            "PS> Get-Content \"$env:LOCALAPPDATA/KiPartSearch/config.json\"      → file exists, not reset",
            "PS> Test-Path \"$env:LOCALAPPDATA/KiPartSearch/cache.db\"           → True (preserved)",
            "GUI> Edit > Preferences → API keys still accessible",
            "GUI> Status bar → NO 'Update available' (already on latest)",
        ],
    },
    # Phase 3 — Alternative Update Flows
    {
        "id": "3.1",
        "phase": "Phase 3 — Alternative Update Flows",
        "name": "Remind Me Later",
        "story": "8.6",
        "steps": [
            "SETUP> Reinstall Release A:",
            "PS> Start-Process dist/kipart-search-0.2.0-setup.exe",
            "SETUP> Clear update cache:",
            "PS> python -c \"import json,pathlib,os; p=pathlib.Path(os.environ['LOCALAPPDATA'])/'KiPartSearch'/'config.json'; d=json.loads(p.read_text()); d.pop('update_check',None); p.write_text(json.dumps(d,indent=2))\"",
            "PS> & 'C:/Program Files/KiPart Search/kipart-search.exe'",
            "GUI> Wait for 'Update available: v0.2.1' → click it → UpdateDialog opens",
            "GUI> Click 'Remind Me Later' → dialog closes, app continues",
            "GUI> Close app",
            "PS> python -c \"import json,pathlib,os; p=pathlib.Path(os.environ['LOCALAPPDATA'])/'KiPartSearch'/'config.json'; d=json.loads(p.read_text()); d['update_check']['check_time']=0; p.write_text(json.dumps(d,indent=2))\"",
            "PS> & 'C:/Program Files/KiPart Search/kipart-search.exe'",
            "GUI> Wait → 'Update available: v0.2.1' appears again (cache expired)",
        ],
    },
    {
        "id": "3.2",
        "phase": "Phase 3 — Alternative Update Flows",
        "name": "Skip This Version",
        "story": "8.6",
        "steps": [
            "GUI> Click 'Update available: v0.2.1' → UpdateDialog opens",
            "GUI> Click 'Skip This Version' → dialog closes",
            "PS> Get-Content \"$env:LOCALAPPDATA/KiPartSearch/config.json\"      → contains \"skipped_version\": \"0.2.1\"",
            "GUI> Close app",
            "PS> python -c \"import json,pathlib,os; p=pathlib.Path(os.environ['LOCALAPPDATA'])/'KiPartSearch'/'config.json'; d=json.loads(p.read_text()); d['update_check']['check_time']=0; p.write_text(json.dumps(d,indent=2))\"",
            "PS> & 'C:/Program Files/KiPart Search/kipart-search.exe'",
            "GUI> Wait 10s → NO 'Update available' notification (v0.2.1 is skipped)",
            "GUI> Close app",
            "PS> python -c \"import json,pathlib,os; p=pathlib.Path(os.environ['LOCALAPPDATA'])/'KiPartSearch'/'config.json'; d=json.loads(p.read_text()); d['update_check']['skipped_version']='0.2.0'; d['update_check']['check_time']=0; p.write_text(json.dumps(d,indent=2))\"",
            "PS> & 'C:/Program Files/KiPart Search/kipart-search.exe'",
            "GUI> Wait → 'Update available: v0.2.1' appears (different version than skipped)",
        ],
    },
    # Phase 4 — Failure & Resilience
    {
        "id": "4.1",
        "phase": "Phase 4 — Failure & Resilience",
        "name": "UAC Denial Recovery",
        "story": "8.8",
        "steps": [
            "SETUP> Reinstall Release A:",
            "PS> Start-Process dist/kipart-search-0.2.0-setup.exe",
            "SETUP> Clear update cache:",
            "PS> python -c \"import json,pathlib,os; p=pathlib.Path(os.environ['LOCALAPPDATA'])/'KiPartSearch'/'config.json'; d=json.loads(p.read_text()); d.pop('update_check',None); p.write_text(json.dumps(d,indent=2))\"",
            "PS> & 'C:/Program Files/KiPart Search/kipart-search.exe'",
            "GUI> Wait for 'Update available: v0.2.1' → click it",
            "GUI> Click 'Update Now' → wait for download to complete",
            "GUI> Click 'Install Now' → click OK on UAC warning dialog",
            "GUI> App closes → Windows UAC prompt appears → click 'No' (DENY)",
            "     (wait 10-30s for shim to detect failure...)",
            "GUI> App relaunches → 'Update Failed' dialog appears",
            "GUI> Verify text: 'Update could not be completed...' with 3 buttons",
            "GUI> Click 'Try Again' → UpdateDialog opens again with v0.2.1",
            "GUI> Close all dialogs → app runs normally on v0.2.0",
        ],
    },
    {
        "id": "4.2",
        "phase": "Phase 4 — Failure & Resilience",
        "name": "Download Manually Fallback",
        "story": "8.8",
        "steps": [
            "GUI> From the 'Update Failed' dialog (rerun 4.1 if needed), click 'Download Manually'",
            "WIN> Default browser opens → URL is https://github.com/sylvanoMTL/kipart-search/releases/tag/v0.2.1",
        ],
    },
    {
        "id": "4.3",
        "phase": "Phase 4 — Failure & Resilience",
        "name": "Offline Graceful Degradation",
        "story": "8.5",
        "steps": [
            "WIN> Disable Wi-Fi / unplug Ethernet (no internet)",
            "PS> python -c \"import json,pathlib,os; p=pathlib.Path(os.environ['LOCALAPPDATA'])/'KiPartSearch'/'config.json'; d=json.loads(p.read_text()); d.pop('update_check',None); p.write_text(json.dumps(d,indent=2))\"",
            "PS> & 'C:/Program Files/KiPart Search/kipart-search.exe'",
            "GUI> App starts normally — splash, main window renders",
            "GUI> Wait 10s → NO 'Update available', NO error dialog, NO error in Log panel",
            "WIN> Re-enable internet connection",
        ],
    },
    {
        "id": "4.4",
        "phase": "Phase 4 — Failure & Resilience",
        "name": "Partial Download Cleanup",
        "story": "8.8",
        "steps": [
            "PS> New-Item \"$env:TEMP/kipart-search-update-v0.0.1.partial\" -Force",
            "PS> (Get-Item \"$env:TEMP/kipart-search-update-v0.0.1.partial\").LastWriteTime = (Get-Date).AddDays(-2)",
            "PS> & 'C:/Program Files/KiPart Search/kipart-search.exe'",
            "PS> Test-Path \"$env:TEMP/kipart-search-update-v0.0.1.partial\"    → False (deleted by app)",
            "GUI> Close app",
            "PS> New-Item \"$env:TEMP/kipart-search-update-v0.0.2.partial\" -Force",
            "     (this one has current timestamp — should NOT be cleaned)",
            "PS> & 'C:/Program Files/KiPart Search/kipart-search.exe'",
            "PS> Test-Path \"$env:TEMP/kipart-search-update-v0.0.2.partial\"    → True (still exists)",
            "PS> Remove-Item \"$env:TEMP/kipart-search-update-v0.0.2.partial\"  (cleanup)",
        ],
    },
    {
        "id": "4.5",
        "phase": "Phase 4 — Failure & Resilience",
        "name": "Download Interrupted Mid-Stream",
        "story": "8.8",
        "steps": [
            "GUI> Click update notification → click 'Update Now' → download starts",
            "GUI> While progress bar is moving: disconnect internet OR close app via Task Manager",
            "PS> ls \"$env:TEMP/kipart-search-update-v0.2.1*\"                   → .partial file exists (NOT final .exe)",
            "WIN> Reconnect internet",
            "PS> & 'C:/Program Files/KiPart Search/kipart-search.exe'",
            "GUI> App starts normally, .partial remains in $env:TEMP",
            "GUI> Click update notification → 'Update Now' → download retries and completes",
        ],
    },
    # Phase 5 — Edge Cases
    {
        "id": "5.1",
        "phase": "Phase 5 — Edge Cases",
        "name": "Inno Setup Upgrade Detection",
        "story": "8.2",
        "steps": [
            "     (Release A must be installed for this test)",
            "PS> Start-Process dist/kipart-search-0.2.1-setup.exe              (or from CI download)",
            "GUI> Wizard detects existing install → upgrades in-place",
            "PS> Test-Path 'C:/Program Files/KiPart Search/kipart-search.exe'  → True",
            "WIN> Settings > Apps → single 'KiPart Search' entry, version 0.2.1",
        ],
    },
    {
        "id": "5.2",
        "phase": "Phase 5 — Edge Cases",
        "name": "Uninstall Preserves User Data",
        "story": "8.2",
        "steps": [
            "PS> ls \"$env:LOCALAPPDATA/KiPartSearch\"                           → note existing files",
            "WIN> Settings > Apps > KiPart Search > Uninstall → run uninstaller",
            "PS> Test-Path 'C:/Program Files/KiPart Search'                    → False (removed)",
            "PS> Test-Path \"$env:LOCALAPPDATA/KiPartSearch/config.json\"        → True (still exists!)",
            "WIN> Start Menu → 'KiPart Search' shortcut removed",
        ],
    },
    {
        "id": "5.3",
        "phase": "Phase 5 — Edge Cases",
        "name": "Fresh Install After Uninstall",
        "story": "8.2",
        "steps": [
            "PS> Start-Process dist/kipart-search-0.2.1-setup.exe",
            "GUI> Complete install → launch from Start Menu",
            "GUI> Splash shows 'v0.2.1'",
            "GUI> Edit > Preferences → API keys still accessible (keyring survives uninstall)",
            "GUI> Search works → cache.db still valid",
        ],
    },
    {
        "id": "5.4",
        "phase": "Phase 5 — Edge Cases",
        "name": "Dev Bypass License Activation",
        "story": "N/A",
        "steps": [
            "PS> .env/Scripts/python.exe -m kipart_search",
            "GUI> Edit > Preferences > License tab > enter 'dev-pro-unlock' > click Activate",
            "GUI> Expect: Pro activated (if license UI implemented)",
            "PS> & 'C:/Program Files/KiPart Search/kipart-search.exe'",
            "GUI> Same 'dev-pro-unlock' key → expect: REJECTED in compiled build",
        ],
    },
    {
        "id": "5.5",
        "phase": "Phase 5 — Edge Cases",
        "name": "--update-failed Flag (Manual)",
        "story": "8.8",
        "steps": [
            "PS> & 'C:/Program Files/KiPart Search/kipart-search.exe' --update-failed",
            "GUI> Main window loads → 'Update Failed' dialog appears immediately",
            "GUI> Verify 3 buttons: [Try Again] [Download Manually] [Close]",
            "GUI> Click 'Close' → dialog dismissed, app works normally",
        ],
    },
    {
        "id": "5.6",
        "phase": "Phase 5 — Edge Cases",
        "name": "24-Hour Cache TTL",
        "story": "8.5",
        "steps": [
            "PS> & 'C:/Program Files/KiPart Search/kipart-search.exe'          (fresh check happens)",
            "GUI> Wait for notification or no-notification, then close",
            "PS> & 'C:/Program Files/KiPart Search/kipart-search.exe'          (relaunch immediately)",
            "GUI> Uses cached result — no new GitHub API call (check Log panel)",
            "GUI> Close app",
            "PS> python -c \"import json,pathlib,os; p=pathlib.Path(os.environ['LOCALAPPDATA'])/'KiPartSearch'/'config.json'; d=json.loads(p.read_text()); d['update_check']['check_time']=0; p.write_text(json.dumps(d,indent=2))\"",
            "PS> & 'C:/Program Files/KiPart Search/kipart-search.exe'",
            "GUI> Fresh API call made → notification shown (if newer version exists)",
        ],
    },
    {
        "id": "5.7",
        "phase": "Phase 5 — Edge Cases",
        "name": "Open Folder Button",
        "story": "8.6",
        "steps": [
            "GUI> Start update download ('Update Now') → wait for completion",
            "GUI> Click 'Open Folder'",
            "WIN> Windows Explorer opens $env:TEMP folder with downloaded .exe file selected",
        ],
    },
    # Phase 6 — Release Script
    {
        "id": "6.1",
        "phase": "Phase 6 — Release Script Validation",
        "name": "Version Gate",
        "story": "8.3",
        "steps": [
            "PS> python release.py                             (no --bump, version matches latest GitHub release)",
            "     → expect: script exits with error about version already released",
            "PS> python release.py --skip-version-gate --skip-tests",
            "     → expect: build proceeds past version check",
        ],
    },
    {
        "id": "6.2",
        "phase": "Phase 6 — Release Script Validation",
        "name": "SHA256 Checksums",
        "story": "8.3",
        "steps": [
            "PS> ls dist/*checksums*                           → checksums file exists",
            "PS> Get-Content dist/*checksums*                  → note the SHA256 for the -setup.exe",
            "PS> certutil -hashfile dist/kipart-search-0.2.1-setup.exe SHA256",
            "     → hash matches the value in the checksums file",
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

# Step prefix legend (shown once per run)
_PREFIX_LEGEND = f"""
  {BOLD}Step prefix legend:{RESET}
    {CYAN}PS>{RESET}    = Run in VS Code PowerShell terminal
    {GREEN}GUI>{RESET}   = Action inside KiPart Search window
    {YELLOW}WIN>{RESET}   = Action in Windows (Start Menu, Settings, Explorer)
    {DIM}SETUP>{RESET} = Prerequisite — must be done before the test
"""


def _input(prompt: str) -> str:
    """Read input, handle Ctrl+C / Ctrl+D gracefully."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("\n\nSmoke test aborted by user.")
        sys.exit(1)


def run_tests() -> list[dict]:
    """Walk through each test interactively, return results."""
    results: list[dict] = []
    current_phase = ""

    total = len(TESTS)
    for i, test in enumerate(TESTS, 1):
        # Phase header
        if test["phase"] != current_phase:
            current_phase = test["phase"]
            print(f"\n{'=' * 70}")
            print(f"{BOLD}{BLUE}  {current_phase}{RESET}")
            print(f"{'=' * 70}")

        print(f"\n{BOLD}[{i}/{total}] TEST {test['id']}: {test['name']}{RESET}")
        print(f"{DIM}Stories: {test['story']}{RESET}")
        print()

        for j, step in enumerate(test["steps"], 1):
            # Colorize known prefixes for readability
            colored = step
            if step.startswith("PS>"):
                colored = f"{CYAN}PS>{RESET}{step[3:]}"
            elif step.startswith("GUI>"):
                colored = f"{GREEN}GUI>{RESET}{step[4:]}"
            elif step.startswith("WIN>"):
                colored = f"{YELLOW}WIN>{RESET}{step[4:]}"
            elif step.startswith("SETUP>"):
                colored = f"{DIM}SETUP>{step[6:]}{RESET}"
            print(f"  {j:2d}. {colored}")
        print()

        # Collect result
        while True:
            verdict = _input(
                f"  Result — {GREEN}[P]ass{RESET} / {RED}[F]ail{RESET} / "
                f"{YELLOW}[S]kip{RESET} / {DIM}[Q]uit{RESET}: "
            ).upper()
            if verdict in ("P", "PASS"):
                verdict = "PASS"
                break
            elif verdict in ("F", "FAIL"):
                verdict = "FAIL"
                break
            elif verdict in ("S", "SKIP"):
                verdict = "SKIP"
                break
            elif verdict in ("Q", "QUIT"):
                print("\nSmoke test ended early by user.")
                return results
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
        print(f"  → {tag} {test['id']} {test['name']}")

    return results


def write_report(results: list[dict]) -> Path:
    """Write results to a timestamped file in dist/."""
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d-%H%M")

    passed = sum(1 for r in results if r["verdict"] == "PASS")
    failed = sum(1 for r in results if r["verdict"] == "FAIL")
    skipped = sum(1 for r in results if r["verdict"] == "SKIP")
    total = len(results)

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("EPIC 8 SMOKE TEST RESULTS")
    lines.append("Installer, Auto-Update & Release Pipeline")
    lines.append("=" * 60)
    lines.append(f"Start: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append(f"Total:   {total}")
    lines.append(f"Passed:  {passed}")
    lines.append(f"Failed:  {failed}")
    lines.append(f"Skipped: {skipped}")
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


def main():
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  KiPart Search — Epic 8 Smoke Test{RESET}")
    print(f"{BOLD}  26 tests across 6 phases{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")
    print()
    print("For each test: follow the steps, then enter the result.")
    print("P = Pass, F = Fail, S = Skip, Q = Quit early")
    print(f"Full test plan: {DIM}_bmad-output/implementation-artifacts/tests/epic-8-smoke-test-plan.md{RESET}")
    print(_PREFIX_LEGEND)

    results = run_tests()

    if not results:
        print("\nNo results recorded.")
        return

    out = write_report(results)

    passed = sum(1 for r in results if r["verdict"] == "PASS")
    failed = sum(1 for r in results if r["verdict"] == "FAIL")
    skipped = sum(1 for r in results if r["verdict"] == "SKIP")

    print(f"\n{'=' * 60}")
    print(f"  {BOLD}SUMMARY{RESET}")
    print(f"  {GREEN}Passed: {passed}{RESET}  "
          f"{RED}Failed: {failed}{RESET}  "
          f"{YELLOW}Skipped: {skipped}{RESET}  "
          f"Total: {len(results)}")
    print(f"\n  Results saved to: {out}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
