"""Core data models for KiPart Search."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Confidence(Enum):
    """Verification confidence level."""
    GREEN = "green"    # Verified, consistent
    AMBER = "amber"    # Uncertain, can't fully verify
    RED = "red"        # Failed, clear mismatch or not found


@dataclass
class PriceBreak:
    """A single price break from a distributor."""
    quantity: int
    unit_price: float
    currency: str = "EUR"


@dataclass
class ParametricValue:
    """A single parametric spec with normalised value and unit."""
    name: str            # e.g. "Capacitance", "Voltage Rating"
    raw_value: str       # e.g. "100nF", "50V"
    numeric_value: float | None = None  # e.g. 1e-7
    unit: str | None = None             # e.g. "F", "V"

    def __str__(self) -> str:
        return self.raw_value


@dataclass
class PartResult:
    """A component search result from any data source."""
    mpn: str                          # Manufacturer Part Number
    manufacturer: str = ""
    description: str = ""
    package: str = ""                 # e.g. "0805", "QFN-24"
    category: str = ""               # e.g. "Capacitors", "Resistors"
    datasheet_url: str = ""
    lifecycle: str = ""               # "Active", "NRND", "EOL", "Obsolete"
    source: str = ""                  # Which data source returned this
    source_part_id: str = ""          # Source-specific ID (e.g. LCSC part number)
    source_url: str = ""              # Link to part on source website

    specs: list[ParametricValue] = field(default_factory=list)
    price_breaks: list[PriceBreak] = field(default_factory=list)
    stock: int | None = None

    confidence: Confidence = Confidence.AMBER

    def get_spec(self, name: str) -> ParametricValue | None:
        """Get a spec by name (case-insensitive)."""
        name_lower = name.lower()
        for spec in self.specs:
            if spec.name.lower() == name_lower:
                return spec
        return None


# --- Parameter Templates ---
# Define which parameters matter per component category.
# Priority: required > important > optional

@dataclass
class ParamField:
    """A parameter field definition for a component category template."""
    name: str
    priority: str  # "required", "important", "optional"
    description: str = ""


PARAM_TEMPLATES: dict[str, list[ParamField]] = {
    "capacitor": [
        ParamField("capacitance", "required", "Capacitance value"),
        ParamField("voltage", "important", "Voltage rating"),
        ParamField("dielectric", "important", "Dielectric type (MLCC: X5R, X7R, C0G, NP0...)"),
        ParamField("tolerance", "important", "Tolerance (e.g. 10%, 5%, 1%)"),
        ParamField("package", "important", "Package/footprint (e.g. 0805, 0402)"),
        ParamField("technology", "important", "Technology (MLCC, Electrolytic, Tantalum, Film)"),
        ParamField("temperature_range", "optional", "Operating temperature range"),
        ParamField("manufacturer", "optional", "Preferred manufacturer"),
    ],
    "resistor": [
        ParamField("resistance", "required", "Resistance value"),
        ParamField("tolerance", "important", "Tolerance (e.g. 1%, 5%)"),
        ParamField("power_rating", "important", "Power rating"),
        ParamField("package", "important", "Package/footprint (e.g. 0805, 0402)"),
        ParamField("technology", "important", "Technology (thick film, thin film, wire-wound)"),
        ParamField("tcr", "optional", "Temperature coefficient of resistance"),
        ParamField("manufacturer", "optional", "Preferred manufacturer"),
    ],
    "inductor": [
        ParamField("inductance", "required", "Inductance value"),
        ParamField("current_rating", "important", "Rated current"),
        ParamField("dcr", "important", "DC resistance"),
        ParamField("package", "important", "Package/footprint"),
        ParamField("type", "important", "Type (ferrite, air core, shielded)"),
        ParamField("srf", "optional", "Self-resonant frequency"),
        ParamField("tolerance", "optional", "Tolerance"),
        ParamField("manufacturer", "optional", "Preferred manufacturer"),
    ],
}
