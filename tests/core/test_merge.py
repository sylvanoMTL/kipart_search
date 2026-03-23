"""Tests for core.merge — dual-source PCB/schematic merge logic."""

from __future__ import annotations

import pytest

from kipart_search.core.kicad_sch import SchSymbol
from kipart_search.core.merge import merge_pcb_sch
from kipart_search.core.models import BoardComponent


def _make_comp(ref: str, value: str = "", mpn: str = "", footprint: str = "",
               extra_fields: dict | None = None) -> BoardComponent:
    return BoardComponent(
        reference=ref,
        value=value,
        footprint=footprint,
        mpn=mpn,
        extra_fields=extra_fields or {},
    )


def _make_sym(ref: str, value: str = "", footprint: str = "",
              lib_id: str = "Device:R", fields: dict | None = None) -> SchSymbol:
    base_fields = {"Reference": ref, "Value": value, "Footprint": footprint}
    if fields:
        base_fields.update(fields)
    return SchSymbol(
        lib_id=lib_id,
        reference=ref,
        value=value,
        footprint=footprint,
        fields=base_fields,
    )


class TestMergeComponentsInBothSources:
    """Components present in both PCB and schematic."""

    def test_both_sources_sets_source_both(self):
        pcb = [_make_comp("R1", "10k")]
        sch = [_make_sym("R1", "10k")]
        result = merge_pcb_sch(pcb, sch)
        assert result[0].source == "both"

    def test_schematic_mpn_overwrites_empty_pcb(self):
        pcb = [_make_comp("C1", "100nF", mpn="")]
        sch = [_make_sym("C1", "100nF", fields={"MPN": "GRM155R71C104KA88D"})]
        result = merge_pcb_sch(pcb, sch)
        assert result[0].mpn == "GRM155R71C104KA88D"
        assert result[0].sync_mismatches == []

    def test_schematic_mpn_overwrites_different_pcb_with_mismatch(self):
        pcb = [_make_comp("C1", "100nF", mpn="OLD_PART")]
        sch = [_make_sym("C1", "100nF", fields={"MPN": "NEW_PART"})]
        result = merge_pcb_sch(pcb, sch)
        assert result[0].mpn == "NEW_PART"
        assert len(result[0].sync_mismatches) == 1
        assert "MPN" in result[0].sync_mismatches[0]
        assert "OLD_PART" in result[0].sync_mismatches[0]
        assert "NEW_PART" in result[0].sync_mismatches[0]

    def test_pcb_mpn_preserved_when_schematic_empty(self):
        """PCB has MPN but schematic doesn't — flag mismatch but keep PCB value."""
        pcb = [_make_comp("U1", "STM32", mpn="STM32F405RGT6")]
        sch = [_make_sym("U1", "STM32")]
        result = merge_pcb_sch(pcb, sch)
        # Mismatch flagged because schematic is empty but PCB has value
        assert len(result[0].sync_mismatches) == 1
        assert "MPN" in result[0].sync_mismatches[0]

    def test_matching_values_no_mismatch(self):
        pcb = [_make_comp("R1", "10k", mpn="RC0402FR-0710KL")]
        sch = [_make_sym("R1", "10k", fields={"MPN": "RC0402FR-0710KL"})]
        result = merge_pcb_sch(pcb, sch)
        assert result[0].sync_mismatches == []
        assert result[0].source == "both"

    def test_mpn_alias_manf_hash(self):
        """MPN found via 'manf#' alias in schematic."""
        pcb = [_make_comp("C1", "100nF")]
        sch = [_make_sym("C1", "100nF", fields={"manf#": "GRM155"})]
        result = merge_pcb_sch(pcb, sch)
        assert result[0].mpn == "GRM155"


class TestSchematicOnlyComponents:
    """Components in schematic but not on PCB."""

    def test_sch_only_creates_new_component(self):
        pcb = [_make_comp("R1", "10k")]
        sch = [_make_sym("R1", "10k"), _make_sym("C5", "100nF", footprint="C_0805")]
        result = merge_pcb_sch(pcb, sch)
        assert len(result) == 2
        c5 = next(c for c in result if c.reference == "C5")
        assert c5.source == "sch_only"
        assert c5.value == "100nF"
        assert c5.footprint == "C_0805"

    def test_sch_only_with_mpn(self):
        pcb = []
        sch = [_make_sym("R1", "10k", fields={"MPN": "RC0402FR-0710KL"})]
        result = merge_pcb_sch(pcb, sch)
        assert len(result) == 1
        assert result[0].source == "sch_only"
        assert result[0].mpn == "RC0402FR-0710KL"

    def test_sch_only_extra_fields_copied(self):
        pcb = []
        sch = [_make_sym("U1", "STM32", fields={
            "MPN": "STM32F405",
            "Manufacturer": "ST",
            "Datasheet": "https://example.com/ds.pdf",
        })]
        result = merge_pcb_sch(pcb, sch)
        assert result[0].datasheet == "https://example.com/ds.pdf"
        assert result[0].mpn == "STM32F405"
        # MPN and Datasheet are stored as dedicated attributes, not duplicated in extra_fields
        assert "MPN" not in result[0].extra_fields
        assert "Datasheet" not in result[0].extra_fields
        # Manufacturer stays in extra_fields (no dedicated attribute)
        assert "Manufacturer" in result[0].extra_fields


class TestPCBOnlyComponents:
    """Components on PCB but not in schematic."""

    def test_pcb_only_unchanged(self):
        pcb = [_make_comp("R1", "10k", mpn="SOME_MPN")]
        sch = []  # empty schematic
        result = merge_pcb_sch(pcb, sch)
        assert len(result) == 1
        assert result[0].source == "pcb_only"
        assert result[0].mpn == "SOME_MPN"
        assert result[0].sync_mismatches == []


class TestFiltering:
    """Power symbols and invalid references are filtered out."""

    def test_power_symbols_filtered_by_reference(self):
        pcb = [_make_comp("R1", "10k")]
        sch = [
            _make_sym("R1", "10k"),
            _make_sym("#PWR01", "GND", lib_id="power:GND"),
        ]
        result = merge_pcb_sch(pcb, sch)
        # Only R1 — power symbol should not appear
        assert len(result) == 1
        assert result[0].reference == "R1"

    def test_power_symbols_filtered_by_lib_id(self):
        pcb = []
        sch = [_make_sym("VCC1", "VCC", lib_id="power:VCC")]
        result = merge_pcb_sch(pcb, sch)
        assert len(result) == 0

    def test_empty_reference_filtered(self):
        pcb = [_make_comp("R1", "10k")]
        sch = [
            _make_sym("R1", "10k"),
            _make_sym("", "test"),
        ]
        result = merge_pcb_sch(pcb, sch)
        assert len(result) == 1


class TestManufacturerMerge:
    """Manufacturer field merge with mismatch detection."""

    def test_manufacturer_copied_from_schematic(self):
        pcb = [_make_comp("R1", "10k", extra_fields={})]
        sch = [_make_sym("R1", "10k", fields={"Manufacturer": "Yageo"})]
        result = merge_pcb_sch(pcb, sch)
        assert result[0].extra_fields.get("Manufacturer") == "Yageo"

    def test_manufacturer_mismatch_detected(self):
        pcb = [_make_comp("R1", "10k", extra_fields={"Manufacturer": "Samsung"})]
        sch = [_make_sym("R1", "10k", fields={"Manufacturer": "Yageo"})]
        result = merge_pcb_sch(pcb, sch)
        assert any("Manufacturer" in m for m in result[0].sync_mismatches)


class TestDatasheetMerge:
    """Datasheet field merge."""

    def test_datasheet_copied_from_schematic(self):
        pcb = [_make_comp("R1", "10k")]
        sch = [_make_sym("R1", "10k", fields={"Datasheet": "https://ds.pdf"})]
        result = merge_pcb_sch(pcb, sch)
        assert result[0].datasheet == "https://ds.pdf"

    def test_datasheet_mismatch_detected(self):
        pcb = [BoardComponent(
            reference="R1", value="10k", footprint="",
            datasheet="https://old.pdf",
        )]
        sch = [_make_sym("R1", "10k", fields={"Datasheet": "https://new.pdf"})]
        result = merge_pcb_sch(pcb, sch)
        assert result[0].datasheet == "https://new.pdf"
        assert any("Datasheet" in m for m in result[0].sync_mismatches)


class TestMultipleComponents:
    """Mixed scenarios with multiple components."""

    def test_mixed_sources(self):
        """PCB has R1 and C1; schematic has R1, C1, and U1 (not placed)."""
        pcb = [
            _make_comp("R1", "10k"),
            _make_comp("C1", "100nF"),
        ]
        sch = [
            _make_sym("R1", "10k"),
            _make_sym("C1", "100nF"),
            _make_sym("U1", "STM32"),
        ]
        result = merge_pcb_sch(pcb, sch)
        assert len(result) == 3

        by_ref = {c.reference: c for c in result}
        assert by_ref["R1"].source == "both"
        assert by_ref["C1"].source == "both"
        assert by_ref["U1"].source == "sch_only"

    def test_pcb_only_when_no_schematic_symbols(self):
        pcb = [_make_comp("R1", "10k"), _make_comp("C1", "100nF")]
        sch = []
        result = merge_pcb_sch(pcb, sch)
        assert all(c.source == "pcb_only" for c in result)
