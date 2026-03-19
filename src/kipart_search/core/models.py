"""Core data models for KiPart Search."""

from __future__ import annotations

import dataclasses
import re
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


def part_result_to_dict(part: PartResult) -> dict:
    """Serialize a PartResult to a JSON-compatible dict."""
    d = dataclasses.asdict(part)
    # Enum → string for JSON serialization
    d["confidence"] = part.confidence.value
    return d


def part_result_from_dict(d: dict) -> PartResult:
    """Reconstruct a PartResult from a dict (inverse of part_result_to_dict)."""
    d = dict(d)  # shallow copy to avoid mutating caller's dict
    d["specs"] = [ParametricValue(**pv) for pv in d.get("specs", [])]
    d["price_breaks"] = [PriceBreak(**pb) for pb in d.get("price_breaks", [])]
    d["confidence"] = Confidence(d["confidence"]) if d.get("confidence") else Confidence.AMBER
    return PartResult(**d)


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


# --- Board Component & Footprint Helpers ---

# Common field names for MPN across different KiCad libraries
MPN_FIELD_NAMES = {"mpn", "manf#", "mfr part", "mfr.part", "manufacturer part number",
                   "manufacturer_part_number", "part number", "pn"}

# Common field names for Do Not Populate markers
DNP_FIELD_NAMES = {"dnp", "do_not_populate", "do not populate", "dnf", "do_not_fit"}

# Reference prefix → (component type keyword, default unit suffix)
_REF_PREFIX_MAP: dict[str, tuple[str, str]] = {
    "C": ("capacitor", "F"),
    "R": ("resistor", "Ohm"),
    "L": ("inductor", "H"),
    "D": ("diode", ""),
    "Q": ("transistor", ""),
    "U": ("IC", ""),
    "J": ("connector", ""),
    "SW": ("switch", ""),
    "F": ("fuse", ""),
    "Y": ("crystal", "Hz"),
}

# SI prefixes that appear in KiCad values without a unit suffix
_SI_PREFIXES = {"p", "n", "u", "m", "k", "M"}

# Regex: number (with optional decimal) followed by a bare SI prefix at end of string
_BARE_PREFIX_RE = re.compile(r'^(\d+\.?\d*)([pnumkM])$')

# Standard passive component sizes (imperial codes used in KiCad footprints and JLCPCB DB)
_PASSIVE_SIZES = {
    "01005", "0201", "0402", "0603", "0805", "1206", "1210",
    "1806", "1808", "1812", "1825", "2010", "2220", "2225", "2512", "2917",
}

# IC/semiconductor package prefixes to extract from footprint names
_IC_PACKAGE_RE = re.compile(
    r'(?:^|[_\-\s])'
    r'('
    r'SOT-\d+[-\d]*'
    r'|SOD-\d+\w*'
    r'|SOIC-\d+'
    r'|SOP-\d+'
    r'|SSOP-\d+'
    r'|TSSOP-\d+'
    r'|MSOP-\d+'
    r'|QFN-\d+'
    r'|QFP-\d+'
    r'|LQFP-\d+'
    r'|TQFP-\d+'
    r'|BGA-\d+'
    r'|DFN-\d+'
    r'|TO-\d+\w*'
    r')'
    r'(?=[_\-\s.]|$)',
    re.IGNORECASE,
)


def extract_ref_prefix(reference: str) -> str:
    """Extract the letter prefix from a reference designator (e.g. 'C3' → 'C', 'SW2' → 'SW')."""
    m = re.match(r'^([A-Za-z]+)', reference)
    return m.group(1).upper() if m else ""


def extract_package_from_footprint(footprint: str) -> str:
    """Extract a standardized package size or IC package name from a KiCad footprint string.

    Examples:
        'Capacitor_SMD:C_0805_2012Metric' → '0805'
        'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm' → 'SOIC-8'
        'Package_TO_SOT_SMD:SOT-23' → 'SOT-23'
        'Resistor_SMD:R_0402_1005Metric' → '0402'
    """
    # Strip library prefix
    name = footprint.split(":", 1)[-1] if ":" in footprint else footprint

    # Check for passive sizes (4-digit imperial codes)
    for size in _PASSIVE_SIZES:
        if re.search(rf'(?:^|[_\-])({re.escape(size)})(?:[_\-]|$)', name):
            return size

    # Check for IC/semiconductor packages
    m = _IC_PACKAGE_RE.search(name)
    if m:
        return m.group(1)

    return ""


_THT_LIBS = {"Package_DIP", "Connector_PinHeader", "Connector_PinSocket"}
_SMD_LIBS = {"Package_SO", "Package_QFP", "Package_DFN_QFN", "Package_BGA",
             "Package_CSP", "LED_SMD"}


def detect_mount_type(footprint: str) -> str:
    """Detect mount type (SMD or THT) from a KiCad footprint string.

    Checks the library prefix (before ':') for _SMD or _THT suffixes,
    then falls back to specific library name matching.
    Default: 'SMD' (conservative — most modern designs are SMD-dominant).
    """
    lib_prefix = footprint.split(":", 1)[0] if ":" in footprint else footprint

    # Check for explicit SMD/THT in library prefix
    if "_THT" in lib_prefix:
        return "THT"
    if "_SMD" in lib_prefix:
        return "SMD"

    # Check specific library names
    for lib in _THT_LIBS:
        if lib_prefix.startswith(lib):
            return "THT"
    for lib in _SMD_LIBS:
        if lib_prefix.startswith(lib):
            return "SMD"

    return "SMD"


def _infer_value_with_unit(value: str, ref_prefix: str) -> str:
    """Add unit suffix to a bare SI-prefixed value based on component type.

    Examples:
        ('10u', 'C') → '10uF'
        ('10k', 'R') → '10kohm'
        ('4.7p', 'C') → '4.7pF'
        ('100n', 'L') → '100nH'
        ('STM32F405', 'U') → 'STM32F405'  (no change — not a bare prefix)
    """
    info = _REF_PREFIX_MAP.get(ref_prefix)
    if not info or not info[1]:
        return value

    _, unit_suffix = info

    # Already has a recognized unit? Return as-is.
    if re.search(r'[FHV]\b', value) or re.search(r'[Oo]hm\b', value):
        return value

    m = _BARE_PREFIX_RE.match(value.strip())
    if m:
        number, prefix = m.groups()
        if prefix in ("k", "M") and unit_suffix == "Ohm":
            return f"{number}{prefix}ohm"
        return f"{number}{prefix}{unit_suffix}"

    return value


@dataclass
class BoardComponent:
    """A component read from the KiCad board."""
    reference: str        # e.g. "C3", "R1", "U2"
    value: str            # e.g. "100nF", "10k", "STM32F405RG"
    footprint: str        # e.g. "Capacitor_SMD:C_0805_2012Metric"
    mpn: str = ""         # Manufacturer Part Number (may be empty)
    datasheet: str = ""   # Datasheet URL (may be empty)
    extra_fields: dict[str, str] = field(default_factory=dict)
    verified_at: float | None = None    # time.time() when MPN verification completed
    verified_source: str | None = None  # source name used for verification (e.g. "JLCPCB")

    @property
    def has_mpn(self) -> bool:
        return bool(self.mpn.strip())

    @property
    def is_dnp(self) -> bool:
        """Check if this component is marked as Do Not Populate."""
        for key, val in self.extra_fields.items():
            if key.lower() in DNP_FIELD_NAMES:
                return val.strip().lower() not in ("", "0", "false", "no")
        return False

    @property
    def footprint_short(self) -> str:
        """Return just the footprint name without library prefix."""
        if ":" in self.footprint:
            return self.footprint.split(":", 1)[1]
        return self.footprint

    def build_search_query(self) -> str:
        """Build a smart search query from component metadata.

        Infers unit suffix from the reference prefix (C→F, R→Ohm, L→H),
        extracts package size from the footprint, and adds component type keyword.
        """
        ref_prefix = extract_ref_prefix(self.reference)
        info = _REF_PREFIX_MAP.get(ref_prefix)

        parts: list[str] = []

        # Value with inferred unit
        value = _infer_value_with_unit(self.value, ref_prefix)
        if value:
            parts.append(value)

        # Package from footprint
        package = extract_package_from_footprint(self.footprint)
        if package:
            parts.append(package)

        # Component type keyword (only for passives/common types, not for ICs with specific MPNs)
        if info and ref_prefix in ("C", "R", "L", "D"):
            parts.append(info[0])

        return " ".join(parts)


def is_stale(component: BoardComponent, db_mtime: float | None) -> bool:
    """Check if a component's verification is stale (verified before last DB update).

    Only checks the temporal relationship between verified_at and db_mtime.
    Callers should filter out components that already need action (e.g. RED
    confidence) before treating the result as a stale indicator.

    Rules:
    - Never-verified (verified_at is None) → NOT stale
    - No database (db_mtime is None) → NOT stale
    - verified_at < db_mtime → STALE
    """
    if component.verified_at is None:
        return False
    if db_mtime is None:
        return False
    return component.verified_at < db_mtime
