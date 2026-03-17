"""Engineering value parsing and equivalent representation generation.

Parses values like '0.1 µF', '100 nF', '1 kΩ' and generates all reasonable
equivalent representations so that searches can find parts regardless of
which SI prefix the database uses.

Example:
    '0.1 µF' → ['100 nF', '0.1 µF', '100000 pF']
    '1 kΩ'   → ['1000 Ω', '1 kΩ']
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# SI prefix multipliers
# ---------------------------------------------------------------------------
_PREFIX_MULT: dict[str, float] = {
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "\u00b5": 1e-6,  # µ
    "m": 1e-3,
    "": 1,
    "k": 1e3,
    "K": 1e3,
    "M": 1e6,
    "G": 1e9,
}

# ---------------------------------------------------------------------------
# Base unit aliases → canonical form
# ---------------------------------------------------------------------------
_UNIT_CANON: dict[str, str] = {
    "F": "F",
    "H": "H",
    "\u03a9": "\u03a9",  # Ω
    "ohm": "\u03a9",
    "Ohm": "\u03a9",
    "OHM": "\u03a9",
    "V": "V",
    "A": "A",
    "W": "W",
}

# ---------------------------------------------------------------------------
# Preferred prefix tiers per unit family (small → large)
# Only includes prefixes commonly seen in component specs.
# ---------------------------------------------------------------------------
_PREFERRED_PREFIXES: dict[str, list[tuple[str, float]]] = {
    "F": [("p", 1e-12), ("n", 1e-9), ("\u00b5", 1e-6), ("m", 1e-3)],
    "H": [("p", 1e-12), ("n", 1e-9), ("\u00b5", 1e-6), ("m", 1e-3)],
    "\u03a9": [("m", 1e-3), ("", 1), ("k", 1e3), ("M", 1e6)],
    "V": [("\u00b5", 1e-6), ("m", 1e-3), ("", 1), ("k", 1e3)],
    "A": [("\u00b5", 1e-6), ("m", 1e-3), ("", 1)],
    "W": [("\u00b5", 1e-6), ("m", 1e-3), ("", 1), ("k", 1e3)],
}

# ---------------------------------------------------------------------------
# Regex: number + optional space + optional prefix + unit
# Matches after transform_query output (which inserts space and uses µ/Ω).
# Also matches raw input without space (e.g. "100nF", "1kohm").
# ---------------------------------------------------------------------------
_VALUE_RE = re.compile(
    r"(?P<number>\d+\.?\d*)"
    r"\s*"
    r"(?P<prefix>[pnu\u00b5mkKMG]?)"
    r"(?P<unit>F|H|\u03a9|[Oo][Hh][Mm]|V|A|W)"
    r"(?=\s|$)",
    re.UNICODE,
)


@dataclass
class EngineeringValue:
    """A parsed engineering value with magnitude and base unit."""

    number: float  # Numeric part as written (e.g., 0.1)
    prefix: str  # SI prefix as written (e.g., 'µ', 'k', '')
    base_unit: str  # Canonical base unit (e.g., 'F', 'Ω')
    base_value: float  # Value in base units (e.g., 0.1µF = 1e-7)
    original: str  # Original matched text


def parse_value(text: str) -> EngineeringValue | None:
    """Parse an engineering value from text.

    Examples:
        '100nF'  → EngineeringValue(100, 'n', 'F', 1e-7)
        '0.1 µF' → EngineeringValue(0.1, 'µ', 'F', 1e-7)
        '1 kΩ'   → EngineeringValue(1, 'k', 'Ω', 1000)
    """
    m = _VALUE_RE.search(text)
    if not m:
        return None

    number = float(m.group("number"))
    prefix = m.group("prefix")
    unit_raw = m.group("unit")

    base_unit = _UNIT_CANON.get(unit_raw)
    if base_unit is None:
        return None

    mult = _PREFIX_MULT.get(prefix, 1)
    base_value = number * mult

    return EngineeringValue(
        number=number,
        prefix=prefix,
        base_unit=base_unit,
        base_value=base_value,
        original=m.group(0),
    )


def _format_number(n: float) -> str | None:
    """Format a number cleanly, or None if it would look ugly.

    Keeps values between 0.1 and 99999 with at most 4 significant digits.
    """
    if n < 0.1 or n > 99_999:
        return None
    if abs(n - round(n)) < 1e-9:
        return str(int(round(n)))
    # Up to 4 significant digits
    s = f"{n:.4g}"
    # Reject scientific notation
    if "e" in s:
        return None
    return s


def equivalent_values(value: EngineeringValue) -> list[str]:
    """Generate all reasonable equivalent representations of a value.

    Each representation is formatted as "NUMBER PREFIX+UNIT" (no space),
    e.g. "100nF", "0.1µF", "1kΩ", "1000Ω".

    Returns at least the original representation.
    """
    prefixes = _PREFERRED_PREFIXES.get(value.base_unit)
    if not prefixes:
        return [value.original]

    results: list[str] = []
    for pfx, mult in prefixes:
        display_num = value.base_value / mult
        num_str = _format_number(display_num)
        if num_str is None:
            continue
        results.append(f"{num_str}{pfx}{value.base_unit}")

    return results if results else [value.original]


def generate_query_variants(query: str) -> list[str]:
    """Find the first engineering value in a query and return variant queries.

    Each variant replaces the value+unit token with an equivalent representation.
    Non-value parts of the query are preserved.

    Example:
        "0.1 µF capacitor 0805"
        → ["100nF capacitor 0805", "0.1µF capacitor 0805", "100000pF capacitor 0805"]

    Returns a single-element list with the original query if no value is found.
    """
    ev = parse_value(query)
    if ev is None:
        return [query]

    variants = equivalent_values(ev)
    if len(variants) <= 1:
        return [query]

    # Find the span of the matched token in the query
    m = _VALUE_RE.search(query)
    if m is None:
        return [query]

    before = query[: m.start()]
    after = query[m.end() :]

    return [f"{before}{v}{after}" for v in variants]
