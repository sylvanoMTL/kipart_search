"""KiCad schematic file (.kicad_sch) parser and field writer.

Reads and writes symbol properties in .kicad_sch S-expression files.
Uses depth-counting (not regex) for block extraction. This module has
zero GUI dependencies — stdlib only.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class SchSymbol:
    """A placed symbol instance from a .kicad_sch file."""

    lib_id: str
    reference: str
    value: str
    footprint: str
    fields: dict[str, str] = field(default_factory=dict)
    uuid: str = ""
    at_x: float = 0.0
    at_y: float = 0.0
    at_angle: float = 0.0


# ---------------------------------------------------------------------------
# Core primitive: depth-counting block finder
# ---------------------------------------------------------------------------


def _find_block(text: str, start_pos: int) -> tuple[int, int]:
    """Find the matching closing ')' for the '(' at *start_pos*.

    Uses depth counting with string-quoting awareness so that
    parentheses inside quoted strings are ignored.

    Returns ``(start_pos, end)`` where ``text[start_pos:end]`` is the
    complete block including both the opening and closing parentheses.

    Raises ``ValueError`` if *start_pos* does not point to ``(``.
    """
    if start_pos >= len(text) or text[start_pos] != "(":
        got = repr(text[start_pos]) if start_pos < len(text) else "EOF"
        raise ValueError(
            f"Expected '(' at position {start_pos}, got {got}"
        )

    depth = 0
    i = start_pos
    length = len(text)
    while i < length:
        ch = text[i]
        if ch == '"':
            # Skip quoted string — advance past closing quote
            i += 1
            while i < length:
                if text[i] == "\\" and i + 1 < length:
                    i += 2  # skip escaped char
                    continue
                if text[i] == '"':
                    break
                i += 1
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return start_pos, i + 1
        i += 1

    raise ValueError(f"Unmatched '(' at position {start_pos}")


# ---------------------------------------------------------------------------
# Read symbols
# ---------------------------------------------------------------------------

# Regex for extracting property name/value from an already-isolated block.
# Handles escaped quotes (e.g. "he said \"hello\"") via (?:[^"\\]|\\.)*.
_PROPERTY_RE = re.compile(r'\(property\s+"((?:[^"\\]|\\.)*)"\s+"((?:[^"\\]|\\.)*)"')

# Regex for extracting (at x y angle) from a symbol block.
_AT_RE = re.compile(r'\(at\s+([\d.e+-]+)\s+([\d.e+-]+)\s+([\d.e+-]+)\)')

# Regex for extracting uuid.
_UUID_RE = re.compile(r'\(uuid\s+"?([^")]+)"?\)')


def read_symbols(sch_path: Path | str) -> list[SchSymbol]:
    """Read all placed symbol instances from a .kicad_sch file.

    Skips library definitions inside ``(lib_symbols ...)``.
    """
    text = Path(sch_path).read_bytes().decode("utf-8")
    symbols: list[SchSymbol] = []

    # First, locate and skip the (lib_symbols ...) section.
    lib_sym_start = text.find("(lib_symbols")
    lib_sym_end = 0
    if lib_sym_start != -1:
        _, lib_sym_end = _find_block(text, lib_sym_start)

    # Scan for top-level (symbol (lib_id "...") ...) blocks.
    search_start = 0
    pattern = re.compile(r'\(symbol\s+\(lib_id\s+"((?:[^"\\]|\\.)*)"\)')

    while True:
        m = pattern.search(text, search_start)
        if m is None:
            break

        block_start = m.start()

        # Skip if inside lib_symbols section.
        if lib_sym_start != -1 and lib_sym_start <= block_start < lib_sym_end:
            search_start = lib_sym_end
            continue

        # Extract the full block using depth counting.
        _, block_end = _find_block(text, block_start)
        block = text[block_start:block_end]

        lib_id = m.group(1)

        # Extract all properties (unescape S-expression values).
        fields: dict[str, str] = {}
        for pm in _PROPERTY_RE.finditer(block):
            fields[_unescape_sexpr_string(pm.group(1))] = _unescape_sexpr_string(pm.group(2))

        reference = fields.get("Reference", "")
        value = fields.get("Value", "")
        footprint = fields.get("Footprint", "")

        # Extract position — first (at ...) in the block is the symbol's own
        # position, which KiCad always places before property (at ...) entries.
        at_x, at_y, at_angle = 0.0, 0.0, 0.0
        at_m = _AT_RE.search(block)
        if at_m:
            at_x = float(at_m.group(1))
            at_y = float(at_m.group(2))
            at_angle = float(at_m.group(3))

        # Extract UUID.
        uuid = ""
        uuid_m = _UUID_RE.search(block)
        if uuid_m:
            uuid = uuid_m.group(1)

        symbols.append(
            SchSymbol(
                lib_id=lib_id,
                reference=reference,
                value=value,
                footprint=footprint,
                fields=fields,
                uuid=uuid,
                at_x=at_x,
                at_y=at_y,
                at_angle=at_angle,
            )
        )

        search_start = block_end

    return symbols


# ---------------------------------------------------------------------------
# Write fields
# ---------------------------------------------------------------------------


def _unescape_sexpr_string(s: str) -> str:
    """Unescape an S-expression quoted value to a plain Python string."""
    return s.replace('\\"', '"').replace("\\\\", "\\")


def _escape_sexpr_string(s: str) -> str:
    """Escape a string for use inside an S-expression quoted value."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def set_field(
    sch_path: Path | str,
    reference: str,
    field_name: str,
    value: str,
    allow_overwrite: bool = False,
) -> bool:
    """Set or add a property field on a symbol identified by reference.

    Returns ``True`` if the file was modified, ``False`` if no change was
    made (symbol not found, or field exists and *allow_overwrite* is False).
    """
    path = Path(sch_path)
    text = path.read_bytes().decode("utf-8")

    # Locate the symbol block for the given reference.
    sym_start, sym_end = _find_symbol_block(text, reference)
    if sym_start is None:
        log.warning("Reference %r not found in %s", reference, path)
        return False

    block = text[sym_start:sym_end]

    # Check if the field already exists in this block.
    field_pattern = re.compile(
        r'\(property\s+"' + re.escape(field_name) + r'"\s+"((?:[^"\\]|\\.)*)"'
    )
    field_match = field_pattern.search(block)

    if field_match is not None:
        if not allow_overwrite:
            return False
        # Overwrite: replace the value string in-place.
        # Compute absolute positions.
        abs_val_start = sym_start + field_match.start(1)
        abs_val_end = sym_start + field_match.end(1)
        escaped = _escape_sexpr_string(value)
        text = text[:abs_val_start] + escaped + text[abs_val_end:]
    else:
        # Insert a new property before the first (pin ...) or closing ')'.
        insert_pos = _find_insertion_point(block)
        abs_insert = sym_start + insert_pos

        # Extract symbol's (at x y angle) for property positioning.
        at_m = _AT_RE.search(block)
        at_x = at_m.group(1) if at_m else "0"
        at_y = at_m.group(2) if at_m else "0"

        # Detect whether existing properties use (id N).
        uses_ids = re.search(r'\(property\s+"(?:[^"\\]|\\.)*"\s+"(?:[^"\\]|\\.)*"\s+\(id\s+\d+\)', block)

        id_part = ""
        if uses_ids:
            # Find the highest existing id and increment.
            ids = [int(x) for x in re.findall(r'\(id\s+(\d+)\)', block)]
            next_id = max(ids) + 1 if ids else 0
            id_part = f" (id {next_id})"

        # Detect indentation from surrounding properties.
        indent = _detect_indent(block)

        escaped_name = _escape_sexpr_string(field_name)
        escaped = _escape_sexpr_string(value)
        new_prop = (
            f'{indent}(property "{escaped_name}" "{escaped}"{id_part} '
            f"(at {at_x} {at_y} 0)\n"
            f"{indent}  (effects (font (size 1.27 1.27)) hide))\n"
        )

        text = text[:abs_insert] + new_prop + text[abs_insert:]

    # Atomic write: temp file + rename to prevent corruption on crash.
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.write(fd, text.encode("utf-8"))
    finally:
        os.close(fd)
    try:
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    return True


def _find_symbol_block(
    text: str, reference: str
) -> tuple[int | None, int | None]:
    """Find the (symbol ...) block containing the given reference designator."""
    pattern = re.compile(r'\(symbol\s+\(lib_id\s+"(?:[^"\\]|\\.)*"\)')

    # Skip lib_symbols section.
    lib_sym_start = text.find("(lib_symbols")
    lib_sym_end = 0
    if lib_sym_start != -1:
        _, lib_sym_end = _find_block(text, lib_sym_start)

    search_start = 0
    while True:
        m = pattern.search(text, search_start)
        if m is None:
            return None, None

        block_start = m.start()

        if lib_sym_start != -1 and lib_sym_start <= block_start < lib_sym_end:
            search_start = lib_sym_end
            continue

        _, block_end = _find_block(text, block_start)
        block = text[block_start:block_end]

        # Check if this block's Reference matches.
        ref_m = re.search(r'\(property\s+"Reference"\s+"((?:[^"\\]|\\.)*)"', block)
        if ref_m and ref_m.group(1) == reference:
            return block_start, block_end

        search_start = block_end


def _find_insertion_point(block: str) -> int:
    """Find where to insert a new property in a symbol block.

    Insert before the first ``(pin ...)`` line, or before the closing
    ``)``, whichever comes first.
    """
    # Try multiline first: (pin on its own line.
    pin_match = re.search(r'\n(\s*)\(pin\s', block)
    if pin_match:
        return pin_match.start() + 1  # after the newline

    # Try inline (pin — no preceding newline (single-line or compact format).
    pin_inline = re.search(r'\(pin\s', block)
    if pin_inline:
        return pin_inline.start()

    # No pin lines — insert before the closing ')'.
    # Find the last ')' and go back to the start of that line.
    last_close = block.rfind(")")
    line_start = block.rfind("\n", 0, last_close)
    if line_start == -1:
        return last_close
    return line_start + 1


def _detect_indent(block: str) -> str:
    """Detect indentation used for (property ...) lines in a symbol block."""
    m = re.search(r'\n(\s+)\(property\s', block)
    if m:
        return m.group(1)
    return "    "


# ---------------------------------------------------------------------------
# Lock-file detection
# ---------------------------------------------------------------------------


def is_schematic_locked(sch_path: Path | str) -> bool:
    """Check if KiCad has the schematic file open.

    KiCad 9 creates a lock file ``~<filename>.lck`` in the same directory
    while the file is open in the editor.  Returns ``True`` if the lock
    file exists, meaning the schematic should NOT be written to.
    """
    sch_path = Path(sch_path)
    lock_file = sch_path.parent / f"~{sch_path.name}.lck"
    return lock_file.exists()


# ---------------------------------------------------------------------------
# Sub-sheet discovery
# ---------------------------------------------------------------------------

_SHEETFILE_RE = re.compile(r'\(property\s+"Sheetfile"\s+"((?:[^"\\]|\\.)*)"')


def find_schematic_files(project_dir: Path | str) -> list[Path]:
    """Discover the root .kicad_sch and all sub-sheets in a KiCad project.

    The root schematic has the same stem as the ``.kicad_pro`` file.
    Sub-sheets are discovered by scanning ``(sheet ...)`` blocks for
    ``(property "Sheetfile" "...")`` entries.
    """
    project_dir = Path(project_dir)

    # Find the .kicad_pro file to identify the root schematic.
    pro_files = list(project_dir.glob("*.kicad_pro"))
    if not pro_files:
        log.warning("No .kicad_pro file found in %s", project_dir)
        return []

    if len(pro_files) > 1:
        log.warning("Multiple .kicad_pro files in %s, using %s", project_dir, pro_files[0].name)

    root_name = pro_files[0].stem
    root_sch = project_dir / f"{root_name}.kicad_sch"
    if not root_sch.exists():
        log.warning("Root schematic %s not found", root_sch)
        return []

    result: list[Path] = [root_sch]
    visited: set[Path] = {root_sch.resolve()}

    # BFS through sheets.
    queue: deque[Path] = deque([root_sch])
    while queue:
        current = queue.popleft()
        text = current.read_bytes().decode("utf-8")

        # Find all (sheet ...) blocks.
        search_pos = 0
        while True:
            idx = text.find("(sheet ", search_pos)
            if idx == -1:
                break
            # Make sure this is a top-level sheet block, not inside lib_symbols.
            _, sheet_end = _find_block(text, idx)
            sheet_block = text[idx:sheet_end]

            sf_m = _SHEETFILE_RE.search(sheet_block)
            if sf_m:
                sub_path = current.parent / _unescape_sexpr_string(sf_m.group(1))
                # Guard against path traversal: sub-sheet must stay
                # inside the project directory.
                try:
                    resolved = sub_path.resolve()
                    if not resolved.is_relative_to(project_dir.resolve()):
                        log.warning(
                            "Ignoring sub-sheet outside project: %s", sub_path
                        )
                        search_pos = sheet_end
                        continue
                except (ValueError, OSError):
                    search_pos = sheet_end
                    continue
                if sub_path.exists() and resolved not in visited:
                    visited.add(sub_path.resolve())
                    result.append(sub_path)
                    queue.append(sub_path)

            search_pos = sheet_end

    return result


def find_symbol_sheet(
    project_dir: Path | str, reference: str
) -> Path | None:
    """Find which schematic sheet contains the symbol with *reference*."""
    sheets = find_schematic_files(project_dir)
    for sheet in sheets:
        symbols = read_symbols(sheet)
        for sym in symbols:
            if sym.reference == reference:
                return sheet
    return None
