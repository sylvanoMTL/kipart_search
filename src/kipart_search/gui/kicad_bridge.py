"""KiCad IPC API bridge — connects to running KiCad instance.

Uses kicad-python (kipy) library for IPC API communication.
Only available when KiCad 9+ is running with IPC API enabled.
"""

from __future__ import annotations

import logging

from kipart_search.core.models import (
    BoardComponent,
    MPN_FIELD_NAMES,
    extract_ref_prefix,
)

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

    def get_project_name(self) -> str | None:
        """Return the project name, or None if not connected."""
        if self._board is None:
            return None

        # kipy/KiCad 9+: Project object via get_project()
        try:
            project = self._board.get_project()
            if hasattr(project, "name") and project.name:
                return project.name
        except Exception:
            pass

        # Fallback: board.name (filename)
        try:
            name = getattr(self._board, "name", None)
            if name:
                from pathlib import Path
                return Path(name).stem
        except Exception:
            pass

        # Legacy: get_filename()
        try:
            name = self._board.get_filename()
            if name:
                from pathlib import Path
                return Path(name).stem
        except Exception:
            pass

        return None

    def get_project_dir(self) -> Path | None:
        """Return the KiCad project directory.

        Tries multiple kipy API approaches:
        1. board.get_project().path (Project object, kipy/KiCad 9+)
        2. board.document.project.path (protobuf document)
        3. board.get_filename() parent (legacy kipy)
        """
        if self._board is None:
            return None
        from pathlib import Path

        # 1. Project object via get_project()
        try:
            project = self._board.get_project()
            if hasattr(project, "path") and project.path:
                p = Path(project.path)
                if p.is_dir():
                    return p
        except Exception:
            pass

        # 2. Document protobuf — project.path field
        try:
            doc = self._board.document
            if hasattr(doc, "project") and hasattr(doc.project, "path"):
                p = Path(doc.project.path)
                if p.is_dir():
                    return p
        except Exception:
            pass

        # 3. Legacy: get_filename() returns full .kicad_pcb path
        try:
            name = self._board.get_filename()
            if name:
                return Path(name).parent
        except Exception:
            pass

        return None

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
            # clear_selection() is not supported in KiCad 9 IPC API
            # ("no handler available for request of type ...ClearSelection").
            # Ignore the error — add_to_selection still works, it just
            # won't deselect previously selected items.
            try:
                self._board.clear_selection()
            except Exception:
                pass
            self._board.add_to_selection(fp)
            return True
        except Exception as e:
            log.warning("Failed to select %s: %s", reference, e)
            return False

    def write_field(
        self, reference: str, field_name: str, value: str,
        allow_overwrite: bool = False,
    ) -> bool:
        """Write a field value to a component (e.g. MPN, datasheet).

        KiCad 9 IPC API limitation (2026-03-20):
        -----------------------------------------
        board.update_items(fp) on a FootprintInstance **strips all custom
        fields** (MPN, Manufacturer, etc.) from the footprint definition.
        Even writing to a built-in field like Datasheet destroys any custom
        fields that were synced from the schematic via "Update PCB from
        Schematic".

        Because of this, ALL write_field calls are disabled in KiCad 9.
        The caller (main_window._on_assign_confirmed) falls back to
        local-state assignment, which updates the in-memory ComponentData
        for BOM export without touching KiCad.

        When KiCad 10 adds schematic editor IPC API support, this method
        should be revisited.  The original write logic is preserved below
        (commented out) for reference.

        See: https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/for-addon-developers/
        "In KiCad 9.0, the IPC API and the new IPC plugin system are only
        implemented in the PCB editor, due to development time constraints.
        In the future, the IPC API will be expanded to support the schematic
        editor, library editors, and other parts of KiCad."

        Test script: tests/manual_tests/test_write_field.py
        """
        # --- KiCad 9: all writes disabled to prevent field destruction ---
        log.info(
            "write_field('%s', '%s') on %s — disabled in KiCad 9. "
            "update_items() strips custom fields from footprints. "
            "Falling back to local-state assignment.",
            field_name, value, reference,
        )
        return False

        # --- KiCad 10+: re-enable the code below when schematic API is available ---
        # if not self.is_connected:
        #     return False
        #
        # fp = self._footprint_cache.get(reference)
        # if fp is None:
        #     log.warning("Component %s not found in cache", reference)
        #     return False
        #
        # try:
        #     # Check predefined fields first
        #     if field_name.lower() == "datasheet":
        #         current = fp.datasheet_field.text.value
        #         if current and current.strip() and not allow_overwrite:
        #             log.warning("Field 'datasheet' on %s is not empty, skipping", reference)
        #             return False
        #         fp.datasheet_field.text.value = value
        #         self._board.update_items(fp)
        #         return True
        #
        #     # Search custom fields
        #     for item in fp.texts_and_fields:
        #         if hasattr(item, "name") and item.name.lower() == field_name.lower():
        #             current = item.text.value if item.text else ""
        #             if current and current.strip() and not allow_overwrite:
        #                 log.warning("Field '%s' on %s is not empty, skipping", field_name, reference)
        #                 return False
        #             item.text.value = value
        #             self._board.update_items(fp)
        #             return True
        #
        #     log.info(
        #         "Field '%s' not found on %s — schematic field creation "
        #         "not supported by KiCad 9 IPC API", field_name, reference,
        #     )
        #     return False
        # except Exception as e:
        #     log.warning("Failed to write field '%s' on %s: %s", field_name, reference, e)
        #     return False
