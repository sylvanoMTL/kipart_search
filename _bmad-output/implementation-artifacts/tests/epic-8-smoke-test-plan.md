# Epic 8 — Installer, Auto-Update & Release Pipeline: Smoke Test Plan

**Date:** 2026-03-28
**Epic:** 8 — Installer, Auto-Update & Release Pipeline (Stories 8.1–8.8)
**Tester:** Sylvain
**Current version:** 0.1.5
**Platform:** Windows 11

---

## Prerequisites

- [ ] Git repo clean (`git status` shows no uncommitted changes)
- [ ] Python venv active (`.env/Scripts/python.exe`)
- [ ] Inno Setup installed (`iscc` available on PATH or at default location)
- [ ] Nuitka installed in venv
- [ ] `gh` CLI installed and authenticated (for GitHub Releases)
- [ ] Internet connection (GitHub API access)
- [ ] Close any running instance of KiPart Search

---

## PHASE 1 — Build & Install Release A

### TEST 1.1: Version Bump to 0.2.0

**Purpose:** Verify `release.py --bump` updates all version files consistently.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | `python release.py --bump minor --skip-tests --skip-version-gate` | Build completes (7 steps). Version bumped to 0.2.0 |
| 2 | Open `pyproject.toml` | `version = "0.2.0"` |
| 3 | Open `src/kipart_search/__init__.py` | `__version__ = "0.2.0"` |
| 4 | Open `installer/kipart-search.iss` | `#define MyAppVersion "0.2.0"` |
| 5 | Check `dist/` folder | Contains: `kipart-search-0.2.0-setup.exe`, `kipart-search-0.2.0-windows.zip`, checksums file |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

### TEST 1.2: Install Release A via Inno Setup

**Purpose:** Verify installer works correctly (Story 8.2).

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Double-click `dist/kipart-search-0.2.0-setup.exe` | Inno Setup wizard opens |
| 2 | Proceed through wizard with defaults | Installs to `C:\Program Files\KiPart Search\` |
| 3 | Verify "Create desktop shortcut" checkbox exists | Checkbox present (unchecked by default) |
| 4 | Complete installation | Installer finishes without errors |
| 5 | Open Start Menu | "KiPart Search" shortcut present under its own group |
| 6 | Open Settings > Apps > Installed Apps | "KiPart Search" listed with version 0.2.0 |
| 7 | Check `C:\Program Files\KiPart Search\` | `kipart-search.exe` exists |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

### TEST 1.3: Launch Release A — Version Verification

**Purpose:** Verify version is displayed correctly everywhere (Stories 8.1, 8.2, 8.3).

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Launch from Start Menu shortcut | App starts without console window |
| 2 | Observe splash screen | Shows "KiPart Search" and **"v0.2.0"** in grey text |
| 3 | Check window title bar | Reads "KiPart Search v0.2.0" |
| 4 | Help > About | Dialog shows "KiPart Search v0.2.0" |
| 5 | Check status bar (bottom) | No "Update available" message (this IS the latest) |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

### TEST 1.4: platformdirs Data Paths (Story 8.1)

**Purpose:** Verify user data is stored in the correct platform location.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Navigate to `%LOCALAPPDATA%\KiPartSearch\` | Folder exists |
| 2 | Check for `config.json` | File present (created on first launch) |
| 3 | Check that `~/.kipart-search/` is NOT used for new data | No new files written to legacy path (unless migration happened) |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

### TEST 1.5: Basic Functionality Sanity Check

**Purpose:** Confirm core features still work in the compiled Release A build.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Search for "capacitor 100nF" | Results returned in search table |
| 2 | Click a result row | Detail panel shows part info |
| 3 | Check Log panel | Shows timestamped search messages |
| 4 | Open Preferences dialog | Opens without errors |
| 5 | Close and reopen the app | Window layout restored from previous session |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

### TEST 1.6: Tag & Push Release A to GitHub

**Purpose:** Create the GitHub Release so Release A has something to compare against later.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Commit version bump: `git add -A && git commit -m "Bump to 0.2.0"` | Commit created |
| 2 | `python release.py --tag` | Tag `v0.2.0` created and pushed |
| 3 | Wait for GitHub Actions to complete (watch with `gh run watch`) | CI builds successfully |
| 4 | Visit GitHub Releases page | Release `v0.2.0` exists with `.exe`, `.zip`, and checksums |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

## PHASE 2 — Build Release B & Test Update Detection

### TEST 2.1: Build Release B (version 0.2.1)

**Purpose:** Create a newer release for the update flow to detect.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | `python release.py --tag --bump patch` | Version bumped to 0.2.1, tagged `v0.2.1`, pushed |
| 2 | Wait for CI to complete | Release `v0.2.1` created on GitHub with assets |
| 3 | Verify GitHub Release `v0.2.1` has a `kipart-search-0.2.1-setup.exe` asset | Asset present and downloadable |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

### TEST 2.2: Update Check on Startup (Story 8.5)

**Purpose:** Verify Release A detects Release B on GitHub.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Delete `update_check` section from `%LOCALAPPDATA%\KiPartSearch\config.json` (force re-check) | Section removed |
| 2 | Launch Release A from `C:\Program Files\KiPart Search\kipart-search.exe` | App launches normally |
| 3 | Wait 5–10 seconds (background check) | Status bar shows: **"Update available: v0.2.1"** |
| 4 | Check `%LOCALAPPDATA%\KiPartSearch\config.json` | `update_check` section populated with `latest_version: "0.2.1"`, valid `asset_url`, `check_time` |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

### TEST 2.3: Update Dialog — Full Download & Install (Stories 8.6, 8.7)

**Purpose:** Test the complete happy-path update flow from Release A to Release B.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click on "Update available: v0.2.1" in the status bar | UpdateDialog opens |
| 2 | Verify dialog contents | Header: "Version 0.2.1 is available (you have 0.2.0)". Release notes shown. Three buttons: [Update Now], [Remind Me Later], [Skip This Version] |
| 3 | Click **"Update Now"** | Progress bar appears. Status shows "Downloading... X.X / Y.Y MB" |
| 4 | Wait for download to complete | Status shows downloaded path: `%TEMP%\kipart-search-update-v0.2.1.exe`. Buttons change to [Install Now], [Open Folder], [Close] |
| 5 | Click **"Install Now"** | UAC confirmation dialog: "Windows will ask for permission to install. Click Yes to continue." |
| 6 | Click **OK** on UAC confirmation | App closes. Windows UAC prompt appears |
| 7 | Accept UAC prompt (click Yes) | Silent installation runs (no wizard visible) |
| 8 | Wait 10–30 seconds | KiPart Search relaunches automatically |
| 9 | Observe splash screen of relaunched app | Shows **"v0.2.1"** |
| 10 | Check window title | "KiPart Search v0.2.1" |
| 11 | Help > About | Shows "KiPart Search v0.2.1" |
| 12 | Settings > Apps > Installed Apps | Version shows 0.2.1 |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

### TEST 2.4: Post-Update Functionality Check

**Purpose:** Verify Release B works correctly after in-place upgrade.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Search for "capacitor 100nF" | Results returned normally |
| 2 | Check that window layout was preserved from Release A | Layout matches previous session |
| 3 | Check `%LOCALAPPDATA%\KiPartSearch\config.json` | File preserved, not reset |
| 4 | Check `%LOCALAPPDATA%\KiPartSearch\cache.db` | Database preserved from Release A |
| 5 | Open Preferences, verify API keys are still stored | Keys still accessible via keyring |
| 6 | Verify no "Update available" in status bar | Status bar clean (already on latest) |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

## PHASE 3 — Update Dialog Alternative Flows

### TEST 3.1: "Remind Me Later" Flow (Story 8.6)

**Purpose:** Verify dismiss-and-re-prompt behaviour.

**Setup:** Reinstall Release A (0.2.0) — run `kipart-search-0.2.0-setup.exe` again. Clear `update_check` from config.json.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Launch Release A | Status bar shows "Update available: v0.2.1" after a few seconds |
| 2 | Click the update notification | UpdateDialog opens |
| 3 | Click **"Remind Me Later"** | Dialog closes. App continues normally |
| 4 | Close the app | App exits cleanly |
| 5 | Delete `update_check.check_time` from config.json (simulate 24h expiry) or set it to a time >24h ago | Cache expired |
| 6 | Relaunch Release A | Status bar shows "Update available: v0.2.1" again |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

### TEST 3.2: "Skip This Version" Flow (Story 8.6)

**Purpose:** Verify skip persistence — should not prompt for the same version again.

**Setup:** Ensure Release A (0.2.0) is installed and has detected v0.2.1.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click update notification in status bar | UpdateDialog opens |
| 2 | Click **"Skip This Version"** | Dialog closes |
| 3 | Check `%LOCALAPPDATA%\KiPartSearch\config.json` | Contains `"skipped_version": "0.2.1"` under `update_check` |
| 4 | Close and delete `check_time` from config.json (force re-check) | Cache invalidated |
| 5 | Relaunch Release A | No "Update available" notification appears (v0.2.1 is skipped) |
| 6 | To verify skip is version-specific: manually edit config.json, change `skipped_version` to `"0.2.0"` | Skipped version no longer matches latest |
| 7 | Delete `check_time`, relaunch | "Update available: v0.2.1" appears again (different version than skipped) |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

## PHASE 4 — Failure & Resilience Paths (Story 8.8)

### TEST 4.1: UAC Denial Recovery

**Purpose:** Verify app recovers gracefully when user cancels Windows UAC.

**Setup:** Ensure Release A (0.2.0) is installed. Clear `skipped_version` and `check_time` from config.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Launch Release A, wait for update notification | "Update available: v0.2.1" appears |
| 2 | Click notification, then click "Update Now" | Download starts and completes |
| 3 | Click "Install Now", confirm the UAC warning dialog | App closes, UAC prompt appears |
| 4 | **Click "No" on the Windows UAC prompt** | Installation fails (exit code != 0) |
| 5 | Wait for shim to detect failure | KiPart Search relaunches with `--update-failed` flag |
| 6 | Observe the "Update Failed" dialog | Shows: "Update could not be completed. This usually means the installer was blocked by Windows permissions or antivirus software." Three buttons: [Try Again], [Download Manually], [Close] |
| 7 | Click **"Try Again"** | UpdateDialog opens again with v0.2.1 info |
| 8 | Close all dialogs | App continues running normally on v0.2.0 |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

### TEST 4.2: "Download Manually" Fallback

**Purpose:** Verify the manual download fallback opens the correct GitHub page.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | From the "Update Failed" dialog (see TEST 4.1), click **"Download Manually"** | Default browser opens to the GitHub Release page for v0.2.1 |
| 2 | Verify the URL | Points to `https://github.com/sylvanoMTL/kipart-search/releases/tag/v0.2.1` |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

### TEST 4.3: Offline / Firewall Graceful Degradation (Story 8.5)

**Purpose:** Verify app launches without errors when GitHub is unreachable.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Disconnect from the internet (disable Wi-Fi / unplug Ethernet) | No network connection |
| 2 | Delete `update_check` section from config.json | Force fresh check |
| 3 | Launch Release A (or B) | App launches normally, splash screen, main window |
| 4 | Wait 10 seconds | **No** "Update available" notification. No error dialog. No console errors |
| 5 | Check Log panel | No update-related error messages visible to user |
| 6 | Reconnect to internet | Connection restored |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

### TEST 4.4: Partial Download Cleanup (Story 8.8)

**Purpose:** Verify stale `.partial` files are cleaned up on startup.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Create a fake stale partial file: create `%TEMP%\kipart-search-update-v0.0.1.partial` (empty file) | File exists in temp |
| 2 | Set the file's modification time to >24 hours ago (PowerShell: `(Get-Item $env:TEMP\kipart-search-update-v0.0.1.partial).LastWriteTime = (Get-Date).AddDays(-2)`) | File is 2 days old |
| 3 | Launch the app | App starts normally |
| 4 | Check `%TEMP%\` | The `.partial` file has been deleted |
| 5 | Create another fake partial with **current** timestamp | File exists, is fresh |
| 6 | Close and relaunch the app | File is NOT deleted (only >24h old files are cleaned) |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

### TEST 4.5: Download Interrupted Mid-Stream

**Purpose:** Verify partial download leaves `.partial` file, doesn't corrupt anything.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Start update download (click "Update Now") | Progress bar shows downloading |
| 2 | While downloading, **disconnect internet** (or kill the app via Task Manager) | Download interrupted |
| 3 | Check `%TEMP%\` | `kipart-search-update-v0.2.1.exe.partial` exists (not the final `.exe`) |
| 4 | Relaunch app, reconnect internet | App launches normally. Partial file remains (cleanup only after 24h) |
| 5 | Click update notification again, click "Update Now" | Download starts fresh and completes successfully |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

## PHASE 5 — Edge Cases & Miscellaneous

### TEST 5.1: Upgrade Detection (Inno Setup)

**Purpose:** Verify Inno Setup detects existing installation and upgrades in-place.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | With Release A installed, manually double-click `kipart-search-0.2.1-setup.exe` | Inno Setup wizard shows "KiPart Search is already installed" (or proceeds to upgrade) |
| 2 | Complete the wizard | Installs over Release A without errors |
| 3 | Check `C:\Program Files\KiPart Search\` | Only one installation, version is 0.2.1 |
| 4 | Settings > Apps | Shows single entry, version 0.2.1 |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

### TEST 5.2: Uninstall Preserves User Data (Story 8.2)

**Purpose:** Verify user data survives uninstall.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Note contents of `%LOCALAPPDATA%\KiPartSearch\` (config.json, cache.db) | Baseline recorded |
| 2 | Uninstall via Settings > Apps > KiPart Search > Uninstall | Uninstaller runs |
| 3 | `C:\Program Files\KiPart Search\` | Folder removed (or empty) |
| 4 | `%LOCALAPPDATA%\KiPartSearch\` | **Still exists** with config.json, cache.db intact |
| 5 | Start Menu | "KiPart Search" shortcut removed |
| 6 | Settings > Apps | "KiPart Search" no longer listed |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

### TEST 5.3: Fresh Install After Uninstall

**Purpose:** Verify clean reinstall picks up preserved user data.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Install Release B (0.2.1) from scratch | Installation completes |
| 2 | Launch the app | Splash shows "v0.2.1" |
| 3 | Check Preferences | Previously stored API keys still accessible (keyring) |
| 4 | Search for a part | Cache.db speeds up queries (if cached data still valid) |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

### TEST 5.4: Dev Bypass License Activation

**Purpose:** Verify dev bypass works in source builds but NOT in compiled builds.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Run from source: `python -m kipart_search` | App launches |
| 2 | Open Preferences > License > Activate | Enter `dev-pro-unlock` |
| 3 | Confirm activation | Pro features unlocked (if license UI is implemented) |
| 4 | Launch compiled binary (`C:\Program Files\KiPart Search\kipart-search.exe`) | App launches |
| 5 | Try same `dev-pro-unlock` key in compiled build | **Rejected** — dev bypass disabled in Nuitka builds |

**Result:** [ ] PASS / [ ] FAIL / [ ] N/A (license UI not yet implemented)
**Notes:** ___

---

### TEST 5.5: `--update-failed` Flag from Command Line

**Purpose:** Verify the flag can be triggered manually for testing.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Open terminal, run: `"C:\Program Files\KiPart Search\kipart-search.exe" --update-failed` | App launches |
| 2 | Observe | "Update Failed" dialog appears immediately after main window loads |
| 3 | Click "Close" | Dialog dismisses, app works normally |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

### TEST 5.6: 24-Hour Cache TTL (Story 8.5)

**Purpose:** Verify the update check respects the 24-hour cache.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Launch the app (fresh check happens) | Update notification appears (if newer version exists) |
| 2 | Close and immediately relaunch | App uses cached result — no new GitHub API call (check Log panel for absence of HTTP request) |
| 3 | Edit config.json: set `check_time` to 25 hours ago | Cache expired |
| 4 | Relaunch | Fresh GitHub API call made, update notification shown |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

### TEST 5.7: "Open Folder" Button After Download

**Purpose:** Verify the "Open Folder" button works.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Start and complete the update download | Download finishes |
| 2 | Click **"Open Folder"** | Windows Explorer opens `%TEMP%\` with the downloaded `.exe` selected |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

## PHASE 6 — Release Script Validation (Story 8.3)

### TEST 6.1: Version Gate

**Purpose:** Verify release.py refuses to build if version hasn't changed.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Run `python release.py` (without `--bump`, same version as latest GitHub release) | Script exits with error: version already released |
| 2 | Run `python release.py --skip-version-gate` | Build proceeds despite same version |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

### TEST 6.2: SHA256 Checksums

**Purpose:** Verify checksums are generated and correct.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | After a successful build, check `dist/` for checksums file | File exists (e.g., `kipart-search-0.2.1-checksums.txt` or similar) |
| 2 | Manually verify one checksum: `certutil -hashfile dist\kipart-search-0.2.1-setup.exe SHA256` | Matches the value in the checksums file |

**Result:** [ ] PASS / [ ] FAIL
**Notes:** ___

---

## Results Summary

| Phase | Test | Status |
|-------|------|--------|
| 1 | 1.1 Version Bump | |
| 1 | 1.2 Install via Inno Setup | |
| 1 | 1.3 Version Display | |
| 1 | 1.4 platformdirs Paths | |
| 1 | 1.5 Basic Functionality | |
| 1 | 1.6 Tag & Push Release A | |
| 2 | 2.1 Build Release B | |
| 2 | 2.2 Update Check on Startup | |
| 2 | 2.3 Full Download & Install | |
| 2 | 2.4 Post-Update Functionality | |
| 3 | 3.1 Remind Me Later | |
| 3 | 3.2 Skip This Version | |
| 4 | 4.1 UAC Denial Recovery | |
| 4 | 4.2 Download Manually Fallback | |
| 4 | 4.3 Offline Graceful Degradation | |
| 4 | 4.4 Partial Download Cleanup | |
| 4 | 4.5 Download Interrupted | |
| 5 | 5.1 Upgrade Detection | |
| 5 | 5.2 Uninstall Preserves Data | |
| 5 | 5.3 Fresh Install After Uninstall | |
| 5 | 5.4 Dev Bypass License | |
| 5 | 5.5 --update-failed Flag | |
| 5 | 5.6 24-Hour Cache TTL | |
| 5 | 5.7 Open Folder Button | |
| 6 | 6.1 Version Gate | |
| 6 | 6.2 SHA256 Checksums | |

**Total tests: 26**

---

## Test Execution Notes

### Important Sequencing

The tests in **Phase 1 and 2 must be executed in order** — each depends on the previous. Phases 3–6 can be executed in any order, but each test within Phase 4 (failure paths) requires reinstalling Release A first.

### Quick Reset Procedure

To reset between tests that require Release A:
1. Run `kipart-search-0.2.0-setup.exe` (reinstalls over current version)
2. Delete `update_check` section from `%LOCALAPPDATA%\KiPartSearch\config.json`
3. Delete any `kipart-search-update-*.exe` files from `%TEMP%\`

### Config File Location

All config edits reference:
```
%LOCALAPPDATA%\KiPartSearch\config.json
```
Typically: `C:\Users\sylvain\AppData\Local\KiPartSearch\config.json`

### Version Cleanup After Testing

After testing is complete, decide whether to keep v0.2.0/v0.2.1 releases on GitHub or delete them:
- `gh release delete v0.2.0 --yes`
- `gh release delete v0.2.1 --yes`
- `git tag -d v0.2.0 v0.2.1 && git push origin :refs/tags/v0.2.0 :refs/tags/v0.2.1`
- Revert version back if needed: edit pyproject.toml, __init__.py, .iss back to 0.1.5
