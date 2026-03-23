"""Merge schematic and PCB component data for dual-source scan."""

from __future__ import annotations

import logging

from kipart_search.core.kicad_sch import SchSymbol
from kipart_search.core.models import BoardComponent, MPN_FIELD_NAMES

log = logging.getLogger(__name__)

# Field names recognised as Manufacturer across KiCad naming conventions
_MANUFACTURER_FIELD_NAMES = {
    "manufacturer", "mfr", "mfg", "manf", "vendor",
}

# Fields where schematic is source of truth (copied over PCB values)
_SCH_PRIORITY_FIELDS = MPN_FIELD_NAMES | _MANUFACTURER_FIELD_NAMES | {
    "description", "supplier", "supplier part number",
}


def _find_field(fields: dict[str, str], aliases: set[str]) -> tuple[str, str]:
    """Find the first matching field name from aliases. Returns (key, value)."""
    for key, val in fields.items():
        if key.lower().strip() in aliases:
            return key, val
    return "", ""


def merge_pcb_sch(
    pcb_components: list[BoardComponent],
    sch_symbols: list[SchSymbol],
) -> list[BoardComponent]:
    """Merge PCB and schematic component data.

    Match by reference designator (exact match — KiCad enforces consistent casing).
    Schematic fields take priority for MPN, Manufacturer, and custom properties.
    PCB-only components are unchanged. Schematic-only symbols become new BoardComponents.
    """
    # Build lookup: reference → SchSymbol (skip power/flag symbols)
    sch_by_ref: dict[str, SchSymbol] = {}
    for sym in sch_symbols:
        ref = sym.reference
        if not ref or ref.startswith("#"):
            continue
        # Skip power symbols by lib_id
        if sym.lib_id.startswith("power:"):
            continue
        sch_by_ref[ref] = sym

    # Track which schematic symbols get matched
    matched_sch_refs: set[str] = set()

    # Merge into PCB components
    for comp in pcb_components:
        sym = sch_by_ref.get(comp.reference)
        if sym is None:
            # PCB-only — leave source as default "pcb_only"
            continue

        matched_sch_refs.add(comp.reference)
        comp.source = "both"

        # Compare and merge fields — schematic is source of truth
        mismatches: list[str] = []

        # MPN
        sch_mpn_key, sch_mpn = _find_field(sym.fields, MPN_FIELD_NAMES)
        if sch_mpn:
            if comp.mpn and comp.mpn != sch_mpn:
                mismatches.append(
                    f"MPN: schematic='{sch_mpn}', PCB='{comp.mpn}'"
                )
            comp.mpn = sch_mpn
        elif comp.mpn and not sch_mpn:
            # PCB has MPN but schematic doesn't — flag as mismatch
            mismatches.append(
                f"MPN: schematic='', PCB='{comp.mpn}'"
            )

        # Manufacturer
        sch_mfr_key, sch_mfr = _find_field(sym.fields, _MANUFACTURER_FIELD_NAMES)
        pcb_mfr_key, pcb_mfr = _find_field(comp.extra_fields, _MANUFACTURER_FIELD_NAMES)
        if sch_mfr:
            if pcb_mfr and pcb_mfr != sch_mfr:
                mismatches.append(
                    f"Manufacturer: schematic='{sch_mfr}', PCB='{pcb_mfr}'"
                )
            # Write schematic value into extra_fields
            target_key = pcb_mfr_key if pcb_mfr_key else (sch_mfr_key if sch_mfr_key else "Manufacturer")
            comp.extra_fields[target_key] = sch_mfr

        # Copy other schematic-priority fields not already handled
        for field_name, field_value in sym.fields.items():
            fl = field_name.lower().strip()
            # Skip standard KiCad properties (Reference, Value, Footprint)
            if fl in ("reference", "value", "footprint"):
                continue
            # Skip already-handled MPN and Manufacturer fields
            if fl in MPN_FIELD_NAMES or fl in _MANUFACTURER_FIELD_NAMES:
                continue
            if fl in _SCH_PRIORITY_FIELDS and field_value:
                existing = comp.extra_fields.get(field_name, "")
                if existing and existing != field_value:
                    mismatches.append(
                        f"{field_name}: schematic='{field_value}', PCB='{existing}'"
                    )
                comp.extra_fields[field_name] = field_value

        # Datasheet from schematic (case-insensitive lookup)
        sch_ds = ""
        for _fk, _fv in sym.fields.items():
            if _fk.lower().strip() == "datasheet":
                sch_ds = _fv
                break
        if sch_ds and sch_ds != comp.datasheet:
            if comp.datasheet and comp.datasheet != sch_ds:
                mismatches.append(
                    f"Datasheet: schematic='{sch_ds}', PCB='{comp.datasheet}'"
                )
            comp.datasheet = sch_ds

        comp.sync_mismatches = mismatches

    # Create BoardComponent entries for schematic-only symbols
    for ref, sym in sch_by_ref.items():
        if ref in matched_sch_refs:
            continue

        # Extract MPN from schematic fields
        _, mpn = _find_field(sym.fields, MPN_FIELD_NAMES)

        # Collect extra fields (exclude standard KiCad properties and fields
        # already stored as dedicated BoardComponent attributes)
        _skip = {"reference", "value", "footprint", "datasheet"}
        extra: dict[str, str] = {}
        for fname, fval in sym.fields.items():
            fl = fname.lower().strip()
            if fl in _skip:
                continue
            if fl in MPN_FIELD_NAMES:
                continue
            extra[fname] = fval

        # Case-insensitive datasheet lookup
        ds = ""
        for _fk, _fv in sym.fields.items():
            if _fk.lower().strip() == "datasheet":
                ds = _fv
                break

        pcb_components.append(BoardComponent(
            reference=ref,
            value=sym.value,
            footprint=sym.footprint,
            mpn=mpn,
            datasheet=ds,
            extra_fields=extra,
            source="sch_only",
        ))

    return pcb_components
