"""Tests for core/kicad_sch.py — KiCad schematic file parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from kipart_search.core.kicad_sch import (
    _find_block,
    find_schematic_files,
    find_symbol_sheet,
    is_schematic_locked,
    read_symbols,
    set_field,
)

# ---------------------------------------------------------------------------
# Fixtures — minimal .kicad_sch content
# ---------------------------------------------------------------------------

MINIMAL_SCH = """\
(kicad_sch (version 20231120) (generator "eeschema") (generator_version "8.0")
  (lib_symbols
    (symbol "Device:R"
      (symbol "Device:R_0_1"
        (polyline (pts (xy -1.016 -2.54) (xy -1.016 2.54)) (stroke (width 0)))
      )
    )
    (symbol "Device:C"
      (symbol "Device:C_0_1"
        (polyline (pts (xy -1.016 -0.762) (xy 1.016 -0.762)) (stroke (width 0)))
      )
    )
  )
  (symbol (lib_id "Device:R") (at 123.19 57.15 0) (unit 1)
    (uuid "aaa-bbb-111")
    (property "Reference" "R1" (at 125.73 55.88 0)
      (effects (font (size 1.27 1.27)) (justify left)))
    (property "Value" "10K" (at 125.73 58.42 0)
      (effects (font (size 1.27 1.27)) (justify left)))
    (property "Footprint" "Resistor_SMD:R_0402" (at 121.41 57.15 90)
      (effects (font (size 1.27 1.27)) hide))
    (property "Datasheet" "~" (at 123.19 57.15 0)
      (effects (font (size 1.27 1.27)) hide))
    (pin "1" (uuid "pin-1"))
    (pin "2" (uuid "pin-2"))
  )
  (symbol (lib_id "Device:C") (at 140.0 60.0 0) (unit 1)
    (uuid "ccc-ddd-222")
    (property "Reference" "C1" (at 142.0 58.0 0)
      (effects (font (size 1.27 1.27)) (justify left)))
    (property "Value" "100nF" (at 142.0 62.0 0)
      (effects (font (size 1.27 1.27)) (justify left)))
    (property "Footprint" "Capacitor_SMD:C_0805" (at 140.0 60.0 0)
      (effects (font (size 1.27 1.27)) hide))
    (property "Datasheet" "~" (at 140.0 60.0 0)
      (effects (font (size 1.27 1.27)) hide))
    (property "MPN" "GRM21BR71C104KA01L" (at 140.0 60.0 0)
      (effects (font (size 1.27 1.27)) hide))
    (pin "1" (uuid "pin-3"))
    (pin "2" (uuid "pin-4"))
  )
)
"""

SCH_WITH_SHEETS = """\
(kicad_sch (version 20231120) (generator "eeschema")
  (lib_symbols)
  (symbol (lib_id "Device:R") (at 100 100 0) (unit 1)
    (uuid "aaa")
    (property "Reference" "R1" (at 100 100 0)
      (effects (font (size 1.27 1.27))))
    (property "Value" "1K" (at 100 100 0)
      (effects (font (size 1.27 1.27))))
    (pin "1" (uuid "p1"))
  )
  (sheet (at 200 100) (size 20 15)
    (property "Sheetname" "Power" (at 200 99 0)
      (effects (font (size 1.27 1.27))))
    (property "Sheetfile" "power.kicad_sch" (at 200 115 0)
      (effects (font (size 1.27 1.27))))
  )
  (sheet (at 250 100) (size 20 15)
    (property "Sheetname" "Audio" (at 250 99 0)
      (effects (font (size 1.27 1.27))))
    (property "Sheetfile" "audio.kicad_sch" (at 250 115 0)
      (effects (font (size 1.27 1.27))))
  )
)
"""

SUBSHEET_SCH = """\
(kicad_sch (version 20231120) (generator "eeschema")
  (lib_symbols)
  (symbol (lib_id "Device:C") (at 50 50 0) (unit 1)
    (uuid "sub-aaa")
    (property "Reference" "C10" (at 50 50 0)
      (effects (font (size 1.27 1.27))))
    (property "Value" "10uF" (at 50 50 0)
      (effects (font (size 1.27 1.27))))
    (pin "1" (uuid "sp1"))
    (pin "2" (uuid "sp2"))
  )
)
"""


# ---------------------------------------------------------------------------
# Task 1: _find_block and read_symbols
# ---------------------------------------------------------------------------


class TestFindBlock:
    """Subtask 1.1: depth-counting block finder."""

    def test_simple_block(self):
        text = "(hello (world) foo)"
        start, end = _find_block(text, 0)
        assert text[start:end] == "(hello (world) foo)"

    def test_nested_block(self):
        text = "prefix (a (b (c))) suffix"
        start, end = _find_block(text, 7)
        assert text[start:end] == "(a (b (c)))"

    def test_string_with_parens(self):
        text = '(property "name(1)" "val(2)")'
        start, end = _find_block(text, 0)
        assert text[start:end] == text

    def test_string_with_escaped_quotes(self):
        text = r'(property "val with \"escaped\" quotes" "ok")'
        start, end = _find_block(text, 0)
        assert text[start:end] == text

    def test_raises_on_non_paren(self):
        with pytest.raises(ValueError):
            _find_block("hello", 0)


class TestReadSymbols:
    """Subtask 1.2 & 1.3: read symbols, skip lib_symbols."""

    def test_reads_correct_symbol_count(self, tmp_path: Path):
        sch = tmp_path / "test.kicad_sch"
        sch.write_text(MINIMAL_SCH, encoding="utf-8")
        symbols = read_symbols(sch)
        # Should find R1 and C1, NOT the lib_symbols definitions
        assert len(symbols) == 2

    def test_symbol_fields(self, tmp_path: Path):
        sch = tmp_path / "test.kicad_sch"
        sch.write_text(MINIMAL_SCH, encoding="utf-8")
        symbols = read_symbols(sch)

        r1 = next(s for s in symbols if s.reference == "R1")
        assert r1.lib_id == "Device:R"
        assert r1.value == "10K"
        assert r1.footprint == "Resistor_SMD:R_0402"
        assert r1.fields["Datasheet"] == "~"

    def test_custom_field_read(self, tmp_path: Path):
        sch = tmp_path / "test.kicad_sch"
        sch.write_text(MINIMAL_SCH, encoding="utf-8")
        symbols = read_symbols(sch)

        c1 = next(s for s in symbols if s.reference == "C1")
        assert c1.fields["MPN"] == "GRM21BR71C104KA01L"

    def test_symbol_without_custom_fields(self, tmp_path: Path):
        sch = tmp_path / "test.kicad_sch"
        sch.write_text(MINIMAL_SCH, encoding="utf-8")
        symbols = read_symbols(sch)

        r1 = next(s for s in symbols if s.reference == "R1")
        assert "MPN" not in r1.fields

    def test_skips_lib_symbols(self, tmp_path: Path):
        sch = tmp_path / "test.kicad_sch"
        sch.write_text(MINIMAL_SCH, encoding="utf-8")
        symbols = read_symbols(sch)
        # lib_symbols contains "Device:R" and "Device:C" sub-symbols
        # but those should NOT appear as placed symbols
        lib_ids = [s.lib_id for s in symbols]
        assert "Device:R" in lib_ids  # placed R1
        assert "Device:C" in lib_ids  # placed C1
        assert len(symbols) == 2  # only placed, not library defs

    def test_escaped_quotes_in_property_value(self, tmp_path: Path):
        """Property values containing escaped quotes must be read correctly."""
        sch_content = MINIMAL_SCH.replace(
            '(property "Datasheet" "~" (at 123.19 57.15 0)',
            '(property "Datasheet" "http://example.com/\\"quoted\\"" (at 123.19 57.15 0)',
        )
        sch = tmp_path / "test.kicad_sch"
        sch.write_text(sch_content, encoding="utf-8")
        symbols = read_symbols(sch)
        r1 = next(s for s in symbols if s.reference == "R1")
        assert r1.fields["Datasheet"] == 'http://example.com/\\"quoted\\"'


# ---------------------------------------------------------------------------
# Task 2: set_field
# ---------------------------------------------------------------------------


class TestSetField:
    """Subtask 2.1–2.3: add/update fields, byte-for-byte preservation."""

    def test_add_new_field(self, tmp_path: Path):
        sch = tmp_path / "test.kicad_sch"
        sch.write_text(MINIMAL_SCH, encoding="utf-8")

        result = set_field(sch, "R1", "MPN", "RC0402FR-071KL")
        assert result is True

        symbols = read_symbols(sch)
        r1 = next(s for s in symbols if s.reference == "R1")
        assert r1.fields["MPN"] == "RC0402FR-071KL"

    def test_no_overwrite_by_default(self, tmp_path: Path):
        sch = tmp_path / "test.kicad_sch"
        sch.write_text(MINIMAL_SCH, encoding="utf-8")

        # C1 already has MPN field
        result = set_field(sch, "C1", "MPN", "NEW_VALUE")
        assert result is False

        # Value should be unchanged
        symbols = read_symbols(sch)
        c1 = next(s for s in symbols if s.reference == "C1")
        assert c1.fields["MPN"] == "GRM21BR71C104KA01L"

    def test_overwrite_when_allowed(self, tmp_path: Path):
        sch = tmp_path / "test.kicad_sch"
        sch.write_text(MINIMAL_SCH, encoding="utf-8")

        result = set_field(sch, "C1", "MPN", "NEW_VALUE", allow_overwrite=True)
        assert result is True

        symbols = read_symbols(sch)
        c1 = next(s for s in symbols if s.reference == "C1")
        assert c1.fields["MPN"] == "NEW_VALUE"

    def test_preserves_other_content(self, tmp_path: Path):
        sch = tmp_path / "test.kicad_sch"
        sch.write_text(MINIMAL_SCH, encoding="utf-8")

        original = sch.read_text(encoding="utf-8")
        set_field(sch, "R1", "Manufacturer", "Yageo")
        modified = sch.read_text(encoding="utf-8")

        # C1 block should be completely unchanged
        c1_start = original.index('(symbol (lib_id "Device:C")')
        c1_original = original[c1_start:original.index("\n  )", c1_start) + 4]
        assert c1_original in modified

    def test_new_field_is_hidden(self, tmp_path: Path):
        sch = tmp_path / "test.kicad_sch"
        sch.write_text(MINIMAL_SCH, encoding="utf-8")

        set_field(sch, "R1", "MPN", "TEST123")
        content = sch.read_text(encoding="utf-8")
        # The new property should contain 'hide'
        idx = content.index('"MPN"')
        line_end = content.index("\n", idx)
        # Check within the property block for 'hide'
        prop_area = content[idx:idx + 200]
        assert "hide" in prop_area

    def test_overwrite_field_with_escaped_quotes(self, tmp_path: Path):
        """Overwriting a field whose old value has escaped quotes must work."""
        sch_content = MINIMAL_SCH.replace(
            '(property "MPN" "GRM21BR71C104KA01L"',
            '(property "MPN" "GRM\\"21BR\\"71"',
        )
        sch = tmp_path / "test.kicad_sch"
        sch.write_text(sch_content, encoding="utf-8")

        result = set_field(sch, "C1", "MPN", "NEW_CLEAN_VALUE", allow_overwrite=True)
        assert result is True

        symbols = read_symbols(sch)
        c1 = next(s for s in symbols if s.reference == "C1")
        assert c1.fields["MPN"] == "NEW_CLEAN_VALUE"

    def test_add_field_with_quotes_in_value(self, tmp_path: Path):
        """Values containing double-quotes must be escaped on write."""
        sch = tmp_path / "test.kicad_sch"
        sch.write_text(MINIMAL_SCH, encoding="utf-8")

        result = set_field(sch, "R1", "Description", 'Res 0.1" pitch')
        assert result is True

        symbols = read_symbols(sch)
        r1 = next(s for s in symbols if s.reference == "R1")
        assert r1.fields["Description"] == 'Res 0.1\\" pitch'

    def test_nonexistent_reference_returns_false(self, tmp_path: Path):
        sch = tmp_path / "test.kicad_sch"
        sch.write_text(MINIMAL_SCH, encoding="utf-8")

        result = set_field(sch, "U99", "MPN", "NOPART")
        assert result is False


# ---------------------------------------------------------------------------
# Task 3: Sub-sheet discovery
# ---------------------------------------------------------------------------


class TestFindSchematicFiles:
    """Subtask 3.1: discover root + sub-sheets."""

    def test_discovers_root_and_subsheets(self, tmp_path: Path):
        # Create project structure
        pro = tmp_path / "myboard.kicad_pro"
        pro.write_text("{}", encoding="utf-8")
        root_sch = tmp_path / "myboard.kicad_sch"
        root_sch.write_text(SCH_WITH_SHEETS, encoding="utf-8")
        (tmp_path / "power.kicad_sch").write_text(SUBSHEET_SCH, encoding="utf-8")
        (tmp_path / "audio.kicad_sch").write_text(SUBSHEET_SCH, encoding="utf-8")

        files = find_schematic_files(tmp_path)
        names = {f.name for f in files}
        assert "myboard.kicad_sch" in names
        assert "power.kicad_sch" in names
        assert "audio.kicad_sch" in names
        assert len(files) == 3

    def test_root_only_no_sheets(self, tmp_path: Path):
        pro = tmp_path / "simple.kicad_pro"
        pro.write_text("{}", encoding="utf-8")
        root_sch = tmp_path / "simple.kicad_sch"
        root_sch.write_text(MINIMAL_SCH, encoding="utf-8")

        files = find_schematic_files(tmp_path)
        assert len(files) == 1
        assert files[0].name == "simple.kicad_sch"


class TestFindSymbolSheet:
    """Subtask 3.2: locate which sheet contains a reference."""

    def test_find_in_root(self, tmp_path: Path):
        pro = tmp_path / "myboard.kicad_pro"
        pro.write_text("{}", encoding="utf-8")
        root_sch = tmp_path / "myboard.kicad_sch"
        root_sch.write_text(SCH_WITH_SHEETS, encoding="utf-8")
        (tmp_path / "power.kicad_sch").write_text(SUBSHEET_SCH, encoding="utf-8")
        (tmp_path / "audio.kicad_sch").write_text(SUBSHEET_SCH, encoding="utf-8")

        path = find_symbol_sheet(tmp_path, "R1")
        assert path is not None
        assert path.name == "myboard.kicad_sch"

    def test_find_in_subsheet(self, tmp_path: Path):
        pro = tmp_path / "myboard.kicad_pro"
        pro.write_text("{}", encoding="utf-8")
        root_sch = tmp_path / "myboard.kicad_sch"
        root_sch.write_text(SCH_WITH_SHEETS, encoding="utf-8")
        (tmp_path / "power.kicad_sch").write_text(SUBSHEET_SCH, encoding="utf-8")
        (tmp_path / "audio.kicad_sch").write_text(SUBSHEET_SCH, encoding="utf-8")

        path = find_symbol_sheet(tmp_path, "C10")
        assert path is not None
        # C10 is in the subsheet content (both power and audio have it)
        assert path.name in ("power.kicad_sch", "audio.kicad_sch")

    def test_not_found_returns_none(self, tmp_path: Path):
        pro = tmp_path / "myboard.kicad_pro"
        pro.write_text("{}", encoding="utf-8")
        root_sch = tmp_path / "myboard.kicad_sch"
        root_sch.write_text(SCH_WITH_SHEETS, encoding="utf-8")
        (tmp_path / "power.kicad_sch").write_text(SUBSHEET_SCH, encoding="utf-8")
        (tmp_path / "audio.kicad_sch").write_text(SUBSHEET_SCH, encoding="utf-8")

        path = find_symbol_sheet(tmp_path, "U99")
        assert path is None


# ---------------------------------------------------------------------------
# Lock-file detection
# ---------------------------------------------------------------------------


class TestIsSchematicLocked:
    """Lock-file detection for KiCad 9."""

    def test_not_locked(self, tmp_path: Path):
        sch = tmp_path / "board.kicad_sch"
        sch.write_text(MINIMAL_SCH, encoding="utf-8")
        assert is_schematic_locked(sch) is False

    def test_locked_when_lck_exists(self, tmp_path: Path):
        sch = tmp_path / "board.kicad_sch"
        sch.write_text(MINIMAL_SCH, encoding="utf-8")
        lock = tmp_path / "~board.kicad_sch.lck"
        lock.write_text("", encoding="utf-8")
        assert is_schematic_locked(sch) is True
