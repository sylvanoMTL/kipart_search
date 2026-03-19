---
title: 'Fix dock panels not stretching to fill window width'
type: 'bugfix'
created: '2026-03-19'
status: 'done'
baseline_commit: 'e68ad6e'
context: []
---

# Fix dock panels not stretching to fill window width

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** When the main window is stretched horizontally, the docked panels (Verify left, Search right) do not grow to fill the available space, leaving visible empty background between or beside them.

**Approach:** Ensure the central widget placeholder truly collapses to zero and that dock container widgets have `Expanding` size policy so Qt's internal splitters distribute all available space to the docks. Clear stale saved layout state that may preserve undersized dock sizes from previous sessions.

## Boundaries & Constraints

**Always:** Preserve existing dock arrangement (Verify left, Search right, Log bottom, Detail hidden). Keep the `_apply_default_dock_sizes` 50/50 and 80/20 ratios. Ensure Log panel does not grow disproportionately.

**Ask First:** Any change to how `saveState`/`restoreState` works beyond clearing stale state.

**Never:** Remove the central widget entirely (QMainWindow requires one). Add a `resizeEvent` override that continuously forces dock sizes (defeats user-dragged resizing).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Fresh launch, no saved state | First run, window at default size | Verify and Search fill full width side by side, no gap | N/A |
| Horizontal stretch | User drags window wider | Both dock panels grow proportionally, no empty background | N/A |
| Restored saved state | Existing QSettings from previous session | Docks fill available width at restored proportions | If restore fails, fall back to defaults |
| Reset Layout | User clicks View > Reset Layout | Docks reposition and fill width correctly | N/A |

</frozen-after-approval>

## Code Map

- `src/kipart_search/gui/main_window.py` -- Central widget setup (L144-149), dock creation (L188-200), default sizing (L350-365), reset layout (L367-383)

## Tasks & Acceptance

**Execution:**
- [ ] `src/kipart_search/gui/main_window.py` -- Replace `setSizePolicy(Ignored, Ignored)` on central widget placeholder with `setMaximumSize(0, 0)` to force it to truly zero size, preventing it from claiming space between left/right dock areas
- [ ] `src/kipart_search/gui/main_window.py` -- Set `setSizePolicy(Expanding, Expanding)` on `verify_container` and `search_container` so Qt distributes stretch to these widgets within their docks
- [ ] `src/kipart_search/gui/main_window.py` -- Verify `_apply_default_dock_sizes` still produces correct proportions with the zero-size central widget (Log panel should not grow disproportionately)

**Acceptance Criteria:**
- Given the app launches fresh (no saved state), when the window appears, then Verify and Search panels fill the full width with no visible background gap
- Given the app is running, when the user stretches the window horizontally, then both panels grow to fill the new width with no empty space
- Given the app is running, when the user clicks View > Reset Layout, then panels reposition and fill the full width
- Given the app is running, when the Log panel is visible, then it remains at ~20% height and does not grow disproportionately

## Verification

**Manual checks:**
- Launch app with no saved state (delete QSettings or use Reset Layout first)
- Stretch window horizontally — confirm no empty background between/beside panels
- Stretch window vertically — confirm Log panel stays proportional
- Close and reopen — confirm restored layout also fills width
