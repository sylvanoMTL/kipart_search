# KiCad API — Symbol Field Access (Read/Write)

*Investigation for KiPart Search — March 2026*

## Summary

**Can a plugin create or modify schematic symbol fields (e.g. MPN, Manufacturer) via the KiCad IPC API?**

**Not yet.** The IPC API (`kicad-python` / `kipy`) in KiCad 9.x is PCB-editor only. There is no schematic-side API for reading or writing symbol fields. The schematic editor API is planned for KiCad 10.x but is still in early development.

Three practical workarounds exist today, ranked by relevance to KiPart Search (a standalone PySide6 desktop tool).

---

## IPC API Status

| Feature | KiCad 9.x | KiCad 10.x (planned) |
|---|---|---|
| PCB footprint fields (read) | ✅ via `kipy` | ✅ |
| PCB footprint fields (write) | ✅ via `board.update_items()` | ✅ |
| Schematic symbol fields (read) | ❌ | Planned |
| Schematic symbol fields (write) | ❌ | Planned |
| Schematic symbol placement | ❌ | In progress (Ethan Chien) |

**Source:** KiCad dev mailing list (May 2025) — Jon Evans confirmed the schematic editor internals are still changing (sheet storage rework), so the eeschema API has not been started by the core team.

---

## Workaround 1 — Direct `.kicad_sch` Parsing (Recommended)

KiCad schematic files are plain-text S-expressions. Fields are stored as `(property ...)` entries within each `(symbol ...)` block. A standalone tool like KiPart Search can parse and rewrite these directly without KiCad running.

### File structure

```
(symbol (lib_id "Device:R") (at 123.19 57.15 0)
  (uuid 1ab71a3c-340b-469a-ada5-4f87f0b7b2fa)
  (property "Reference" "R1" (id 0) (at 125.73 55.88 0)
    (effects (font (size 1.27 1.27)) (justify left)))
  (property "Value" "1K" (id 1) (at 125.73 58.42 0)
    (effects (font (size 1.27 1.27)) (justify left)))
  (property "Footprint" "Resistor_SMD:R_0402" (id 2) (at 121.41 57.15 90)
    (effects (font (size 1.27 1.27)) hide))
  (property "Datasheet" "~" (id 3) (at 123.19 57.15 0)
    (effects (font (size 1.27 1.27)) hide))
  (property "MPN" "RC0402FR-071KL" (id 4) (at 123.19 57.15 0)
    (effects (font (size 1.27 1.27)) hide))
  (pin "1" (uuid ...))
  (pin "2" (uuid ...))
)
```

### Minimal Python parser sketch

```python
import re
from pathlib import Path

def read_symbols(sch_path: str) -> list[dict]:
    """Extract symbols and their fields from a .kicad_sch file."""
    text = Path(sch_path).read_text(encoding='utf-8')
    symbols = []

    # Match top-level (symbol ...) blocks (not lib_symbols)
    for m in re.finditer(r'\(symbol \(lib_id "([^"]+)"\)', text):
        start = m.start()
        # Find matching closing paren (simple depth counter)
        depth, pos = 0, start
        for i, c in enumerate(text[start:], start):
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    pos = i + 1
                    break
        block = text[start:pos]
        fields = {}
        for fm in re.finditer(r'\(property "([^"]+)" "([^"]*)"', block):
            fields[fm.group(1)] = fm.group(2)
        symbols.append({'lib_id': m.group(1), 'fields': fields, 'block': block})

    return symbols


def set_field(sch_path: str, reference: str, field_name: str, value: str):
    """Set or add a field on a symbol identified by reference designator."""
    text = Path(sch_path).read_text(encoding='utf-8')
    # ... locate the symbol block by Reference field, then:
    #   - if field exists: replace its value
    #   - if field missing: insert a new (property ...) line before the first (pin ...)
    Path(sch_path).write_text(text, encoding='utf-8')
```

### Pros and cons

- ✅ No dependency on KiCad running
- ✅ Full control, works offline and in CI/CD
- ✅ Matches KiPart Search architecture (standalone PySide6 app)
- ⚠️ Must handle S-expression nesting carefully (regex works for simple cases; a proper parser is safer for production)

---

## Workaround 2 — `kicad-skip` Library

A third-party Python library for manipulating `.kicad_sch` files with a clean object model.

```
pip install kicad-skip
```

### Usage

```python
from skip import Schematic

schem = Schematic('/path/to/my.kicad_sch')

# Read existing fields
ref = schem.symbol.U1.property.Reference.value    # "U1"
mpn = schem.symbol.U1.property.MPN.value           # "BQ25185DSGR"

# Modify a field
schem.symbol.U1.property.MPN.value = 'BQ25185DSGR'

# Save
schem.write()
```

### Pros and cons

- ✅ Clean Pythonic API, tab-completion in REPL
- ✅ Handles S-expression parsing properly
- ✅ Supports both schematic and PCB files
- ⚠️ External dependency, not maintained by KiCad team
- ⚠️ File-based — does not communicate with a running KiCad instance (no live refresh)

---

## Workaround 3 — PCB-Side Field Access via `kipy`

Footprints on the board carry schematic fields. You can read them through the IPC API, but changes do **not** propagate back to the schematic.

```python
import kipy

kicad = kipy.KiCad()
board = kicad.get_board()

for fp in board.get_footprints():
    ref = fp.reference_field.text.value
    # Custom fields are accessible but the API surface
    # for reading arbitrary fields is limited in kipy 0.6
    print(f"{ref}")
```

### Pros and cons

- ✅ Uses official IPC API
- ❌ Read-only direction (board ← schematic), no write-back
- ❌ Requires KiCad to be running with the PCB open
- ❌ Not useful for adding MPN/manufacturer fields

---

## Recommendation for KiPart Search

Given that KiPart Search is a standalone PySide6 desktop application:

1. **Primary path:** Direct `.kicad_sch` parsing (Workaround 1). Write a small S-expression parser module in `src/kipart_search/kicad_sch.py` that can read symbols + fields and write back modified fields. This keeps the tool self-contained with zero external dependency.

2. **Quick prototyping:** Use `kicad-skip` (Workaround 2) during development for fast iteration, then decide whether to keep it as a dependency or replace with a bespoke parser.

3. **Future:** When the KiCad 10 schematic API lands, add an optional IPC-based code path for live field updates while the schematic editor is open. The `kipy` API will likely expose symbol fields through a pattern similar to `board.get_footprints()` / `board.update_items()`.

---

## Standard Field Names

KiCad uses these conventional field names (the first four are mandatory, the rest are user-defined):

| ID | Name | Purpose |
|---|---|---|
| 0 | `Reference` | Designator (R1, C5, U3…) |
| 1 | `Value` | Component value (10K, 100nF…) |
| 2 | `Footprint` | Library:footprint |
| 3 | `Datasheet` | URL or `~` |
| 4+ | User fields | `MPN`, `Manufacturer`, `Supplier`, `Supplier_PN`, `LCSC`, etc. |

For KiPart Search, the most relevant fields to write are typically `MPN`, `Manufacturer`, and distributor-specific part numbers (`DigiKey_PN`, `Mouser_PN`, `LCSC`).

---

## References

- KiCad IPC API docs: https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/
- `kicad-python` (official): https://gitlab.com/kicad/code/kicad-python
- `kicad-python` PyPI: https://pypi.org/project/kicad-python/
- `kicad-python` API reference: https://docs.kicad.org/kicad-python-main/
- `kicad-skip` (third-party): https://github.com/psychogenic/kicad-skip
- KiCad eeschema API discussion: https://groups.google.com/a/kicad.org/g/devlist/c/ViU9P2nvCEA
