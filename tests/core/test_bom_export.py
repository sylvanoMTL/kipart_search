"""Tests for the BOM export engine (Story 2.1)."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

from kipart_search.core.bom_export import (
    PCBWAY_TEMPLATE,
    BOMTemplate,
    export_bom,
    _natural_sort_key,
)
from kipart_search.core.models import (
    BoardComponent,
    detect_mount_type,
    extract_package_from_footprint,
)


# ── Fixtures ──

def _make_comp(ref: str, value: str, footprint: str, mpn: str = "",
               manufacturer: str = "") -> BoardComponent:
    extra = {}
    if manufacturer:
        extra["manufacturer"] = manufacturer
    return BoardComponent(
        reference=ref, value=value, footprint=footprint,
        mpn=mpn, extra_fields=extra,
    )


@pytest.fixture
def three_components() -> list[BoardComponent]:
    """Two resistors with same MPN + one cap."""
    return [
        _make_comp("R1", "10k", "Resistor_SMD:R_0805_2012Metric",
                    mpn="RC0805FR-0710KL", manufacturer="Yageo"),
        _make_comp("R2", "10k", "Resistor_SMD:R_0805_2012Metric",
                    mpn="RC0805FR-0710KL", manufacturer="Yageo"),
        _make_comp("C1", "100nF", "Capacitor_SMD:C_0402_1005Metric",
                    mpn="GRM155R71C104KA88D", manufacturer="Murata"),
    ]


# ── Template Tests ──

class TestPCBWayTemplate:
    def test_has_9_columns(self):
        assert len(PCBWAY_TEMPLATE.columns) == 9

    def test_column_headers(self):
        headers = [c.header for c in PCBWAY_TEMPLATE.columns]
        assert headers == [
            "Item #", "Designator", "Qty", "Manufacturer", "Mfg Part #",
            "Description / Value", "Package/Footprint", "Type",
            "Your Instructions / Notes",
        ]

    def test_file_format_xlsx(self):
        assert PCBWAY_TEMPLATE.file_format == "xlsx"

    def test_group_by_mpn(self):
        assert PCBWAY_TEMPLATE.group_by == "mpn"


# ── Grouping Tests ──

class TestGrouping:
    def test_grouping_by_mpn(self, three_components, tmp_path):
        out = tmp_path / "bom.xlsx"
        export_bom(three_components, PCBWAY_TEMPLATE, out)

        from openpyxl import load_workbook
        wb = load_workbook(out)
        ws = wb.active
        rows = list(ws.iter_rows(min_row=2, values_only=True))

        assert len(rows) == 2

        # R1+R2 grouped
        r_row = next(r for r in rows if "R1" in str(r[1]))
        assert r_row[1] == "R1,R2"
        assert r_row[2] == 2
        assert r_row[4] == "RC0805FR-0710KL"

        # C1 alone
        c_row = next(r for r in rows if "C1" in str(r[1]))
        assert c_row[1] == "C1"
        assert c_row[2] == 1


# ── Natural Sort Tests ──

class TestNaturalSort:
    def test_designator_natural_sort(self):
        refs = ["R1", "R10", "R2"]
        sorted_refs = sorted(refs, key=_natural_sort_key)
        assert sorted_refs == ["R1", "R2", "R10"]

    def test_mixed_prefixes(self):
        refs = ["C1", "C10", "C2", "R1"]
        sorted_refs = sorted(refs, key=_natural_sort_key)
        assert sorted_refs == ["C1", "C2", "C10", "R1"]


# ── Package Extraction Tests ──

class TestPackageExtraction:
    def test_0805(self):
        assert extract_package_from_footprint("Capacitor_SMD:C_0805_2012Metric") == "0805"

    def test_0402(self):
        assert extract_package_from_footprint("Resistor_SMD:R_0402_1005Metric") == "0402"

    def test_soic(self):
        assert extract_package_from_footprint("Package_SO:SOIC-8_3.9x4.9mm_P1.27mm") == "SOIC-8"

    def test_sot23(self):
        assert extract_package_from_footprint("Package_TO_SOT_SMD:SOT-23") == "SOT-23"

    def test_unknown(self):
        assert extract_package_from_footprint("Custom:MyFootprint") == ""


# ── SMD/THT Detection Tests ──

class TestMountTypeDetection:
    def test_resistor_smd(self):
        assert detect_mount_type("Resistor_SMD:R_0805_2012Metric") == "SMD"

    def test_package_dip_tht(self):
        assert detect_mount_type("Package_DIP:DIP-8_W7.62mm") == "THT"

    def test_package_so_smd(self):
        assert detect_mount_type("Package_SO:SOIC-8") == "SMD"

    def test_package_to_sot_tht(self):
        assert detect_mount_type("Package_TO_SOT_THT:TO-220-3") == "THT"

    def test_capacitor_tht(self):
        assert detect_mount_type("Capacitor_THT:C_Disc_D3.0mm_W2.0mm_P2.50mm") == "THT"

    def test_connector_pin_header_tht(self):
        assert detect_mount_type("Connector_PinHeader:PinHeader_1x04") == "THT"

    def test_default_smd(self):
        assert detect_mount_type("SomeUnknownLib:Part") == "SMD"


# ── Excel Output Tests ──

class TestExcelOutput:
    def test_excel_output(self, three_components, tmp_path):
        out = tmp_path / "bom.xlsx"
        result = export_bom(three_components, PCBWAY_TEMPLATE, out)

        assert result == out
        assert out.exists()

        from openpyxl import load_workbook
        wb = load_workbook(out)
        ws = wb.active

        # Check header row
        headers = [cell.value for cell in ws[1]]
        assert headers == [c.header for c in PCBWAY_TEMPLATE.columns]

        # Check data rows exist
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        assert len(rows) == 2

    def test_item_numbers_sequential(self, three_components, tmp_path):
        out = tmp_path / "bom.xlsx"
        export_bom(three_components, PCBWAY_TEMPLATE, out)

        from openpyxl import load_workbook
        wb = load_workbook(out)
        ws = wb.active
        rows = list(ws.iter_rows(min_row=2, values_only=True))

        item_numbers = [r[0] for r in rows]
        assert item_numbers == [1, 2]

    def test_package_column_populated(self, three_components, tmp_path):
        out = tmp_path / "bom.xlsx"
        export_bom(three_components, PCBWAY_TEMPLATE, out)

        from openpyxl import load_workbook
        wb = load_workbook(out)
        ws = wb.active
        rows = list(ws.iter_rows(min_row=2, values_only=True))

        # Package is column index 6 (0-based)
        packages = [r[6] for r in rows]
        assert "0805" in packages
        assert "0402" in packages

    def test_type_column_populated(self, three_components, tmp_path):
        out = tmp_path / "bom.xlsx"
        export_bom(three_components, PCBWAY_TEMPLATE, out)

        from openpyxl import load_workbook
        wb = load_workbook(out)
        ws = wb.active
        rows = list(ws.iter_rows(min_row=2, values_only=True))

        # Type is column index 7
        types = [r[7] for r in rows]
        assert all(t == "SMD" for t in types)


# ── CSV Output Tests ──

class TestCSVOutput:
    def test_csv_output(self, three_components, tmp_path):
        csv_template = BOMTemplate(
            name="PCBWay-CSV", columns=PCBWAY_TEMPLATE.columns,
            file_format="csv",
        )
        out = tmp_path / "bom.csv"
        result = export_bom(three_components, csv_template, out)

        assert result == out
        assert out.exists()

        with open(out, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Header + 2 data rows
        assert len(rows) == 3
        assert rows[0] == [c.header for c in PCBWAY_TEMPLATE.columns]


# ── Edge Cases ──

class TestEdgeCases:
    def test_empty_component_list(self, tmp_path):
        out = tmp_path / "empty.xlsx"
        export_bom([], PCBWAY_TEMPLATE, out)

        from openpyxl import load_workbook
        wb = load_workbook(out)
        ws = wb.active

        # Header only, no data rows
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        assert len(rows) == 0

        # Header exists
        headers = [cell.value for cell in ws[1]]
        assert len(headers) == 9

    def test_components_with_no_mpn(self, tmp_path):
        comps = [
            _make_comp("R1", "10k", "Resistor_SMD:R_0805_2012Metric", mpn=""),
            _make_comp("R2", "10k", "Resistor_SMD:R_0805_2012Metric", mpn=""),
        ]
        out = tmp_path / "no_mpn.xlsx"
        export_bom(comps, PCBWAY_TEMPLATE, out)

        from openpyxl import load_workbook
        wb = load_workbook(out)
        ws = wb.active
        rows = list(ws.iter_rows(min_row=2, values_only=True))

        # Both grouped into one row (same empty MPN)
        assert len(rows) == 1
        assert rows[0][2] == 2  # qty
        assert rows[0][4] in ("", None)  # empty MPN (openpyxl returns None for empty cells)


# ── No GUI Import Test ──

class TestNoGUIImports:
    def test_no_pyside6_in_modules(self):
        # Force fresh import check
        import importlib
        importlib.import_module("kipart_search.core.bom_export")
        pyside_modules = [k for k in sys.modules if k.startswith("PySide6")]
        # PySide6 may be loaded by other tests, so check bom_export source instead
        source_path = Path(__file__).parent.parent.parent / "src" / "kipart_search" / "core" / "bom_export.py"
        content = source_path.read_text()
        assert "PySide6" not in content
        assert "from kipart_search.gui" not in content
