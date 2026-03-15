"""KiCad IPC API bridge — connects to running KiCad instance.

Uses kicad-python (kipy) library for IPC API communication.
Only available when KiCad 9+ is running with IPC API enabled.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# Common field names for MPN across different KiCad libraries
MPN_FIELD_NAMES = {"mpn", "manf#", "mfr part", "mfr.part", "manufacturer part number",
                   "manufacturer_part_number", "part number", "pn"}

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
# Uses [-_\b] boundaries since KiCad footprints use underscores as delimiters
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


def _extract_ref_prefix(reference: str) -> str:
    """Extract the letter prefix from a reference designator (e.g. 'C3' → 'C', 'SW2' → 'SW')."""
    m = re.match(r'^([A-Za-z]+)', reference)
    return m.group(1).upper() if m else ""


def _extract_package_from_footprint(footprint: str) -> str:
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
        # Match as standalone token: _0805_, _0805-, 0805_ etc.
        if re.search(rf'(?:^|[_\-])({re.escape(size)})(?:[_\-]|$)', name):
            return size

    # Check for IC/semiconductor packages
    m = _IC_PACKAGE_RE.search(name)
    if m:
        return m.group(1)

    return ""


def _infer_value_with_unit(value: str, ref_prefix: str) -> str:
    """Add unit suffix to a bare SI-prefixed value based on component type.

    Examples:
        ('10u', 'C') → '10uF'
        ('10k', 'R') → '10kohm'   (will be transformed by query_transform later)
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

    @property
    def has_mpn(self) -> bool:
        return bool(self.mpn.strip())

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
        ref_prefix = _extract_ref_prefix(self.reference)
        info = _REF_PREFIX_MAP.get(ref_prefix)

        parts: list[str] = []

        # Value with inferred unit
        value = _infer_value_with_unit(self.value, ref_prefix)
        if value:
            parts.append(value)

        # Package from footprint
        package = _extract_package_from_footprint(self.footprint)
        if package:
            parts.append(package)

        # Component type keyword (only for passives/common types, not for ICs with specific MPNs)
        if info and ref_prefix in ("C", "R", "L", "D"):
            parts.append(info[0])

        return " ".join(parts)


class KiCadBridge:
    """Interface to a running KiCad instance via IPC API.

    Graceful degradation: if KiCad is not running, all methods
    return empty results or False. No exceptions.
    """

    def __init__(self):
        self._kicad = None
        self._board = None
        self._footprint_cache: dict[str, object] = {}  # reference → FootprintInstance

    def connect(self) -> tuple[bool, str]:
        """Attempt to connect to KiCad IPC API.

        Returns (success, diagnostic_message).
        """
        try:
            from kipy import KiCad
        except ImportError:
            msg = "kicad-python (kipy) not installed — KiCad integration disabled"
            log.info(msg)
            return False, msg

        try:
            self._kicad = KiCad()
            self._board = self._kicad.get_board()
            log.info("Connected to KiCad IPC API")
            return True, "Connected"
        except Exception as e:
            log.info("Could not connect to KiCad: %s", e)
            self._kicad = None
            self._board = None
            return False, str(e)

    def get_diagnostics(self) -> str:
        """Gather diagnostic info for debugging connection issues."""
        import os
        import platform

        lines = [
            f"Platform: {platform.system()} {platform.release()}",
            f"Python: {platform.python_version()}",
        ]

        # kipy version
        try:
            import kipy
            lines.append(f"kipy version: {getattr(kipy, '__version__', 'unknown')}")
        except ImportError:
            lines.append("kipy: NOT INSTALLED")

        # Environment variables KiCad sets for API plugins
        for var in ("KICAD_API_SOCKET", "KICAD_API_TOKEN", "KICAD_RUN_FROM_BUILD_DIR"):
            val = os.environ.get(var)
            lines.append(f"{var}: {val or '(not set)'}")

        # Check common socket paths
        if platform.system() == "Windows":
            pipe_path = r"\\.\pipe\kicad"
            lines.append(f"Windows named pipe prefix: {pipe_path}")
            # Check KICAD_API_SOCKET or default
            socket_val = os.environ.get("KICAD_API_SOCKET", "(not set)")
            lines.append(f"Expected socket: {socket_val}")
        else:
            import glob
            sock_patterns = ["/tmp/kicad/api.sock", "/tmp/kicad/*.sock"]
            found = []
            for pat in sock_patterns:
                found.extend(glob.glob(pat))
            if found:
                lines.append(f"Found sockets: {', '.join(found)}")
            else:
                lines.append("No KiCad API sockets found in /tmp/kicad/")

        # Connection state
        lines.append(f"Bridge connected: {self.is_connected}")

        return "\n".join(lines)

    @property
    def is_connected(self) -> bool:
        return self._board is not None

    def get_components(self) -> list[BoardComponent]:
        """Read all components from the board."""
        if not self.is_connected:
            return []

        components = []
        self._footprint_cache.clear()

        try:
            footprints = self._board.get_footprints()
        except Exception as e:
            log.warning("Failed to read footprints: %s", e)
            return []

        for fp in footprints:
            try:
                ref = fp.reference_field.text.value
                value = fp.value_field.text.value
                footprint_id = str(fp.definition.id) if fp.definition else ""

                # Read datasheet field
                datasheet = ""
                try:
                    datasheet = fp.datasheet_field.text.value
                except Exception:
                    pass

                # Read all custom fields, find MPN
                mpn = ""
                extra_fields = {}
                try:
                    for item in fp.texts_and_fields:
                        if hasattr(item, "name") and hasattr(item, "text"):
                            fname = item.name
                            fval = item.text.value if item.text else ""
                            extra_fields[fname] = fval
                            if fname.lower().strip() in MPN_FIELD_NAMES:
                                mpn = fval
                except Exception:
                    pass

                self._footprint_cache[ref] = fp

                components.append(BoardComponent(
                    reference=ref,
                    value=value,
                    footprint=footprint_id,
                    mpn=mpn,
                    datasheet=datasheet,
                    extra_fields=extra_fields,
                ))
            except Exception as e:
                log.warning("Failed to read footprint: %s", e)
                continue

        log.info("Read %d components from KiCad board", len(components))
        return components

    def select_component(self, reference: str) -> bool:
        """Select/highlight a component in KiCad by reference.

        KiCad's internal cross-probe will highlight it in the schematic.
        """
        if not self.is_connected:
            return False

        fp = self._footprint_cache.get(reference)
        if fp is None:
            log.warning("Component %s not found in cache", reference)
            return False

        try:
            self._board.clear_selection()
            self._board.add_to_selection(fp)
            return True
        except Exception as e:
            log.warning("Failed to select %s: %s", reference, e)
            return False

    def write_field(self, reference: str, field_name: str, value: str) -> bool:
        """Write a field value to a component (e.g. MPN, datasheet).

        Safety: caller must check that the field is empty before calling.
        This method does NOT overwrite non-empty fields.
        """
        if not self.is_connected:
            return False

        fp = self._footprint_cache.get(reference)
        if fp is None:
            log.warning("Component %s not found in cache", reference)
            return False

        try:
            # Check predefined fields first
            if field_name.lower() == "datasheet":
                current = fp.datasheet_field.text.value
                if current and current.strip():
                    log.warning("Field 'datasheet' on %s is not empty, skipping", reference)
                    return False
                fp.datasheet_field.text.value = value
                self._board.update_items(fp)
                return True

            # Search custom fields
            for item in fp.texts_and_fields:
                if hasattr(item, "name") and item.name.lower() == field_name.lower():
                    current = item.text.value if item.text else ""
                    if current and current.strip():
                        log.warning("Field '%s' on %s is not empty, skipping", field_name, reference)
                        return False
                    item.text.value = value
                    self._board.update_items(fp)
                    return True

            log.warning("Field '%s' not found on %s", field_name, reference)
            return False
        except Exception as e:
            log.warning("Failed to write field '%s' on %s: %s", field_name, reference, e)
            return False
