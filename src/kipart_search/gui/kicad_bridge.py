"""KiCad IPC API bridge — connects to running KiCad instance.

Uses kicad-python (kipy) library for IPC API communication.
Only available when KiCad 9+ is running with IPC API enabled.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BoardComponent:
    """A component read from the KiCad board."""
    reference: str        # e.g. "C3", "R1", "U2"
    value: str            # e.g. "100nF", "10k", "STM32F405RG"
    footprint: str        # e.g. "Capacitor_SMD:C_0805_2012Metric"
    mpn: str = ""         # Manufacturer Part Number (may be empty)
    datasheet: str = ""   # Datasheet URL (may be empty)


class KiCadBridge:
    """Interface to a running KiCad instance via IPC API.

    Graceful degradation: if KiCad is not running, all methods
    return empty results or False. No exceptions.
    """

    def __init__(self):
        self._kicad = None
        self._board = None

    def connect(self) -> bool:
        """Attempt to connect to KiCad IPC API.

        Returns True if connection successful, False otherwise.
        """
        try:
            from kipy import KiCad
            self._kicad = KiCad()
            self._board = self._kicad.get_board()
            return True
        except Exception:
            self._kicad = None
            self._board = None
            return False

    @property
    def is_connected(self) -> bool:
        return self._board is not None

    def get_components(self) -> list[BoardComponent]:
        """Read all components from the board."""
        if not self.is_connected:
            return []

        # TODO: Iterate footprints, extract reference, value, footprint,
        # MPN field, datasheet field → list of BoardComponent
        return []

    def select_component(self, reference: str) -> bool:
        """Select/highlight a component in KiCad by reference.

        KiCad's internal cross-probe will highlight it in the schematic.
        """
        if not self.is_connected:
            return False

        # TODO: Find footprint by reference, call board.select()
        return False

    def write_field(self, reference: str, field_name: str, value: str) -> bool:
        """Write a field value to a component (e.g. MPN, datasheet).

        Safety: caller must check that the field is empty before calling.
        """
        if not self.is_connected:
            return False

        # TODO: Find footprint, set field value via IPC API
        return False
