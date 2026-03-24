"""BOM export engine — transforms component data into CM-ready files."""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from kipart_search.core.models import (
    BoardComponent,
    detect_mount_type,
    extract_package_from_footprint,
)

log = logging.getLogger(__name__)


@dataclass
class BOMColumn:
    """A single column in a BOM template."""
    header: str
    field: str
    transform: str | None = None


@dataclass
class BOMTemplate:
    """Declarative BOM template — ADR-02 compliant."""
    name: str
    columns: list[BOMColumn]
    group_by: str = "mpn"
    dnp_handling: str = "include_marked"
    file_format: str = "xlsx"


PCBWAY_TEMPLATE = BOMTemplate(
    name="PCBWay",
    columns=[
        BOMColumn(header="Item #", field="item_number"),
        BOMColumn(header="Designator", field="designator"),
        BOMColumn(header="Qty", field="quantity"),
        BOMColumn(header="Manufacturer", field="manufacturer"),
        BOMColumn(header="Mfg Part #", field="mpn"),
        BOMColumn(header="Description / Value", field="value"),
        BOMColumn(header="Package/Footprint", field="package", transform="package_extract"),
        BOMColumn(header="Type", field="mount_type", transform="smd_tht_detect"),
        BOMColumn(header="Your Instructions / Notes", field="notes"),
    ],
    file_format="xlsx",
)

JLCPCB_TEMPLATE = BOMTemplate(
    name="JLCPCB",
    columns=[
        BOMColumn(header="Comment", field="value"),
        BOMColumn(header="Designator", field="designator"),
        BOMColumn(header="Footprint", field="package", transform="package_extract"),
        BOMColumn(header="JLCPCB Part #", field="lcsc_part"),
    ],
    file_format="csv",
)

NEWBURY_TEMPLATE = BOMTemplate(
    name="Newbury Electronics",
    columns=[
        BOMColumn(header="Item#", field="item_number"),
        BOMColumn(header="Description", field="description"),
        BOMColumn(header="Quantity", field="quantity"),
        BOMColumn(header="Manufacturer Name", field="manufacturer"),
        BOMColumn(header="Manufacturer Part Number", field="mpn"),
        BOMColumn(header="Supplier Name", field="supplier_name"),
        BOMColumn(header="Supplier Part Number", field="supplier_pn"),
        BOMColumn(header="Designator", field="designator"),
        BOMColumn(header="Notes", field="notes"),
    ],
    file_format="xlsx",
)

PRESET_TEMPLATES: list[BOMTemplate] = [PCBWAY_TEMPLATE, JLCPCB_TEMPLATE, NEWBURY_TEMPLATE]


def _natural_sort_key(ref: str) -> tuple:
    """Sort key that handles mixed alpha-numeric designators naturally."""
    parts = re.split(r'(\d+)', ref)
    return tuple(int(p) if p.isdigit() else p for p in parts)


def group_components(
    components: list[BoardComponent],
) -> list[dict[str, str | int]]:
    """Group components by (MPN, manufacturer) and build row dicts."""
    groups: dict[tuple[str, str], list[BoardComponent]] = {}

    for comp in components:
        if not comp.reference:
            log.warning("Skipping component with empty reference")
            continue
        key = (comp.mpn.upper(), comp.extra_fields.get("manufacturer", "").upper())
        groups.setdefault(key, []).append(comp)

    rows: list[dict[str, str | int]] = []
    item = 1

    for (_mpn_key, _mfr_key), group in groups.items():
        first = group[0]
        refs = sorted((c.reference for c in group), key=_natural_sort_key)

        rows.append({
            "item_number": item,
            "designator": ",".join(refs),
            "quantity": len(group),
            "manufacturer": first.extra_fields.get("manufacturer", ""),
            "mpn": first.mpn,
            "value": first.value,
            "package": extract_package_from_footprint(first.footprint),
            "mount_type": detect_mount_type(first.footprint),
            "notes": "",
            "lcsc_part": first.extra_fields.get("LCSC Part", "") or first.extra_fields.get("lcsc", ""),
            "description": first.extra_fields.get("description", "") or first.value,
            "supplier_name": first.extra_fields.get("supplier_name", "") or first.extra_fields.get("Supplier", ""),
            "supplier_pn": first.extra_fields.get("supplier_pn", "") or first.extra_fields.get("Supplier Part", ""),
        })
        item += 1

    return rows


def _write_xlsx(
    rows: list[dict[str, str | int]], template: BOMTemplate, output_path: Path,
) -> Path:
    """Write BOM rows to an Excel file."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "BOM"

    headers = [col.header for col in template.columns]
    ws.append(headers)

    for row_data in rows:
        ws.append([row_data.get(col.field, "") for col in template.columns])

    wb.save(output_path)
    return output_path


def _write_csv(
    rows: list[dict[str, str | int]], template: BOMTemplate, output_path: Path,
) -> Path:
    """Write BOM rows to a CSV file."""
    headers = [col.header for col in template.columns]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row_data in rows:
            writer.writerow([row_data.get(col.field, "") for col in template.columns])

    return output_path


def export_bom(
    components: list[BoardComponent],
    template: BOMTemplate,
    output_path: Path,
) -> Path:
    """Export a BOM from component data using the given template.

    Groups components by (MPN, manufacturer), applies column transforms,
    and writes to xlsx or csv based on template.file_format.

    License gates:
    - CSV export is always free
    - Excel export requires Pro ("excel_export")
    - CM templates (PCBWay, Newbury Electronics) require Pro ("cm_export")

    Returns the output path.
    """
    from kipart_search.core.license import License
    lic = License.instance()

    # Gate Excel format (Pro only)
    if template.file_format != "csv":
        lic.require("excel_export")

    # Gate CM-specific templates (Pro only); JLCPCB CSV is free
    _CM_TEMPLATES = {"PCBWay", "Newbury Electronics"}
    if template.name in _CM_TEMPLATES:
        lic.require("cm_export")

    rows = group_components(components)

    if template.file_format == "csv":
        return _write_csv(rows, template, output_path)
    return _write_xlsx(rows, template, output_path)
