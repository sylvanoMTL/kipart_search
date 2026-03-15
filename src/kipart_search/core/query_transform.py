"""Pre-search query transformation for EE unit normalisation and footprint expansion.

Ported from PartManufacturerSearch_prototype (Sylvain Boyer / MecaFrog, MIT).
"""

import re

# ---------------------------------------------------------------------------
# Quoted-segment bypass
# ---------------------------------------------------------------------------
_QUOTE_RE = re.compile(r'"([^"]*)"')


# ---------------------------------------------------------------------------
# Footprint prefix rules  (applied first)
# ---------------------------------------------------------------------------
# R_0805 -> 0805 resistor,  C_0402 -> 0402 capacitor, etc.
# The underscore distinguishes these from LCSC C-numbers (C12345 has no underscore).
_FOOTPRINT_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\bR_(\S+)'),  r'\1 resistor'),
    (re.compile(r'\bC_(\S+)'),  r'\1 capacitor'),
    (re.compile(r'\bL_(\S+)'),  r'\1 inductor'),
    (re.compile(r'\bD_(\S+)'),  r'\1 diode'),
]


# ---------------------------------------------------------------------------
# EE unit rules  (order matters)
# ---------------------------------------------------------------------------
_UNIT_RULES: list[tuple[re.Pattern, str]] = [
    # Kilo/Mega/Milli ohm — before generic Ohm
    (re.compile(r'kohm', re.IGNORECASE), 'k\u03a9'),
    (re.compile(r'Mohm'),                'M\u03a9'),   # case-sensitive: M = Mega
    (re.compile(r'mohm'),                'm\u03a9'),   # case-sensitive: m = milli
    # Generic Ohm
    (re.compile(r'\bOhm\b', re.IGNORECASE), '\u03a9'),
    # Micro units  (u -> \u00b5)
    (re.compile(r'uF\b'),  '\u00b5F'),
    (re.compile(r'uH\b'),  '\u00b5H'),
    (re.compile(r'uA\b'),  '\u00b5A'),
    (re.compile(r'uV\b'),  '\u00b5V'),
    # Insert space between number and unit
    (re.compile(
        r'(\d)'
        r'(p[FH]|n[FH]|m[FHVA]|\u00b5[FHAV]|[kK]\u03a9|M\u03a9|m\u03a9|\u03a9)'
    ), r'\1 \2'),
]


def transform_query(raw: str) -> str:
    """Apply EE unit normalisation and footprint expansion.

    Double-quoted segments are preserved unchanged.
    """
    # 1. Extract quoted segments, replace with placeholders
    quoted: list[str] = []

    def _save(m: re.Match) -> str:
        idx = len(quoted)
        quoted.append(m.group(0))
        return f'\x00Q{idx}\x00'

    text = _QUOTE_RE.sub(_save, raw)

    # 2. Footprint prefixes
    for pat, repl in _FOOTPRINT_RULES:
        text = pat.sub(repl, text)

    # 3. Unit substitutions then spacing
    for pat, repl in _UNIT_RULES:
        text = pat.sub(repl, text)

    # 4. Restore quoted segments
    for idx, original in enumerate(quoted):
        text = text.replace(f'\x00Q{idx}\x00', original)

    return text


def strip_quotes(query: str) -> str:
    """Remove protective double quotes before sending to an API."""
    return query.replace('"', '')
