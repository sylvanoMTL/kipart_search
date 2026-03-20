"""Manual test: KiCad 9 IPC API write_field behaviour.

Findings (2026-03-20):
======================
KiCad 9 IPC API limitation — board.update_items(fp) on a FootprintInstance
STRIPS ALL CUSTOM FIELDS (MPN, Manufacturer, etc.) from the footprint
definition.  This is destructive:

1. Custom fields (MPN, Manufacturer) are properties of schematic symbols,
   not PCB footprints.  They appear on footprints only after
   "Update PCB from Schematic" (F8).

2. Calling update_items(fp) sends the entire footprint proto back to KiCad.
   KiCad accepts the update but drops custom fields from the definition
   items list on the round-trip.

3. Even writing to a BUILT-IN field (like Datasheet) via update_items()
   destroys any custom fields that were synced from the schematic.

4. The IPC API cannot create new symbol fields — it only exposes the
   PCB editor.  Schematic editor API is expected in KiCad 10.

Reference:
  https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/for-addon-developers/
  "In KiCad 9.0, the IPC API and the new IPC plugin system are only
  implemented in the PCB editor, due to development time constraints."

Consequence:
  write_field() is disabled in KiCad 9.  All MPN assignments use
  local-state storage (in-memory ComponentData) for BOM export.
  When KiCad 10 adds schematic API, re-enable write_field() and
  re-run this test to verify.

Prerequisites:
  - KiCad 9+ running with IPC API enabled
  - A board with component C6 that has MPN and Manufacturer fields
    manually added to its schematic symbol
  - "Update PCB from Schematic" (F8) run after adding fields
  - PCB saved after update

Usage:
  python tests/manual_tests/test_write_field.py

WARNING: This test calls update_items() which DESTROYS custom fields
on the footprint.  You will need to re-run "Update PCB from Schematic"
after running this test to restore them.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add src to path so we can import the project
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


def main():
    # Import here so missing kipy doesn't crash at module level
    from kipart_search.gui.kicad_bridge import KiCadBridge

    bridge = KiCadBridge()

    # Step 1: Connect
    print("Connecting to KiCad...")
    ok = bridge.connect()
    if not ok:
        print("FAIL: Could not connect to KiCad IPC API")
        return 1
    print(f"OK: Connected (is_connected={bridge.is_connected})")

    # Step 2: Read components
    print("\nReading components...")
    components = bridge.get_components()
    print(f"OK: Read {len(components)} components")

    # Step 3: Find C6 and show its current fields
    c6 = None
    for comp in components:
        if comp.reference == "C6":
            c6 = comp
            break
    if c6 is None:
        print("FAIL: C6 not found on board")
        return 1

    print(f"\nC6 current state:")
    print(f"  value     = {c6.value!r}")
    print(f"  footprint = {c6.footprint!r}")
    print(f"  mpn       = {c6.mpn!r}")
    print(f"  extra     = {c6.extra_fields}")

    # Step 4: List all fields visible on the footprint
    fp = bridge._footprint_cache.get("C6")
    if fp is None:
        print("FAIL: C6 not in footprint cache")
        return 1

    print(f"\nC6 footprint fields (texts_and_fields):")
    has_mpn_field = False
    has_mfr_field = False
    for item in fp.texts_and_fields:
        name = getattr(item, "name", None)
        text_val = item.text.value if hasattr(item, "text") and item.text else "N/A"
        print(f"  name={name!r:25s}  value={text_val!r}")
        if name == "MPN":
            has_mpn_field = True
        if name == "Manufacturer":
            has_mfr_field = True

    if not has_mpn_field or not has_mfr_field:
        print("\nFAIL: MPN and/or Manufacturer fields not found on C6.")
        print("  Did you add them in the schematic and run 'Update PCB from Schematic' (F8)?")
        return 1

    # Step 5: Test writing via update_items (demonstrates the bug)
    print("\n" + "=" * 60)
    print("WARNING: The following update_items() call will DESTROY")
    print("custom fields on C6.  Re-run F8 after this test.")
    print("=" * 60)

    test_mpn = "TEST_MPN_12345"
    test_mfr = "TEST_MANUFACTURER"

    # Write MPN directly (bypassing the disabled write_field)
    print(f"\nWriting MPN='{test_mpn}' directly via update_items...")
    for item in fp.texts_and_fields:
        if getattr(item, "name", None) == "MPN":
            item.text.value = test_mpn
            break
    for item in fp.texts_and_fields:
        if getattr(item, "name", None) == "Manufacturer":
            item.text.value = test_mfr
            break

    # Check cached object has the values
    print("\nCached footprint fields after local modification:")
    for item in fp.texts_and_fields:
        name = getattr(item, "name", None)
        if name in ("MPN", "Manufacturer"):
            text_val = item.text.value if item.text else "N/A"
            print(f"  name={name!r:25s}  value={text_val!r}")

    # Send to KiCad via update_items
    print("\nCalling board.update_items(fp)...")
    bridge._board.update_items(fp)
    print("OK: update_items returned")

    # Re-read from KiCad
    print("\nRe-reading components from KiCad (fresh footprint objects)...")
    components2 = bridge.get_components()
    c6_after = None
    for comp in components2:
        if comp.reference == "C6":
            c6_after = comp
            break

    if c6_after is None:
        print("FAIL: C6 not found after re-read")
        return 1

    print(f"\nC6 after update_items (fresh read from KiCad):")
    print(f"  mpn       = {c6_after.mpn!r}")
    print(f"  extra     = {c6_after.extra_fields}")

    # Check if custom fields survived
    fp_after = bridge._footprint_cache.get("C6")
    fields_after = {}
    if fp_after:
        for item in fp_after.texts_and_fields:
            name = getattr(item, "name", None)
            if name in ("MPN", "Manufacturer"):
                fields_after[name] = item.text.value if item.text else ""

    print(f"\nCustom fields on footprint after round-trip:")
    if not fields_after:
        print("  NONE — custom fields were DESTROYED by update_items()")
        print("\n*** CONFIRMED: update_items() strips custom fields in KiCad 9 ***")
        print("*** write_field() must remain disabled until KiCad 10 ***")
    else:
        for name, val in fields_after.items():
            print(f"  {name} = {val!r}")
        if fields_after.get("MPN") == test_mpn:
            print("\n*** PASS: MPN survived update_items — KiCad may have fixed the bug ***")
            print("*** Consider re-enabling write_field() ***")
        else:
            print(f"\n*** FAIL: MPN expected {test_mpn!r}, got {fields_after.get('MPN')!r} ***")

    print("\nReminder: run 'Update PCB from Schematic' (F8) to restore custom fields.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
