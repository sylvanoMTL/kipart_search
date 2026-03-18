"""KiCad IPC API bridge — connects to running KiCad instance.

Uses kicad-python (kipy) library for IPC API communication.
Only available when KiCad 9+ is running with IPC API enabled.
"""

from __future__ import annotations

import logging

from kipart_search.core.models import (
    BoardComponent,
    MPN_FIELD_NAMES,
    extract_package_from_footprint,
    extract_ref_prefix,
)

# Backward-compatible alias for callers using the private name
_extract_package_from_footprint = extract_package_from_footprint

log = logging.getLogger(__name__)


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
