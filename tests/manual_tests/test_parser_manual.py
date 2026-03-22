"""Manual test GUI for core/kicad_sch.py against a real KiCad project.

Usage:
    python tests/manual_tests/test_parser_manual.py

Opens a folder picker, then displays parsed symbols in a table and runs
write-back tests on a temporary copy (original files are never touched).
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

# Add src to path so we can import without install
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from kipart_search.core.kicad_sch import (
    find_schematic_files,
    find_symbol_sheet,
    is_schematic_locked,
    read_symbols,
    set_field,
)


class ParserTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("kicad_sch.py — Manual Parser Test")
        self.resize(1000, 700)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Top bar: folder picker
        top = QHBoxLayout()
        self._path_label = QLabel("No project selected")
        self._path_label.setStyleSheet("font-weight: bold;")
        btn_browse = QPushButton("Select KiCad Project Folder...")
        btn_browse.clicked.connect(self._browse)
        self._btn_run_write = QPushButton("Run Write-Back Tests")
        self._btn_run_write.clicked.connect(self._run_write_tests)
        self._btn_run_write.setEnabled(False)
        top.addWidget(self._path_label, 1)
        top.addWidget(btn_browse)
        top.addWidget(self._btn_run_write)
        layout.addLayout(top)

        # Symbol table
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["Sheet", "Reference", "Value", "Footprint", "MPN", "Other Fields"]
        )
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        layout.addWidget(self._table, 1)

        # Log area
        layout.addWidget(QLabel("Log:"))
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(220)
        layout.addWidget(self._log)

        self._project_dir: Path | None = None
        self._populating = False  # guard to ignore signals during table fill

        # Connect cell edits — fires after user finishes editing a cell
        self._table.cellChanged.connect(self._on_cell_changed)

    def _log_msg(self, msg: str):
        self._log.append(msg)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select KiCad Project Folder"
        )
        if not folder:
            return
        self._project_dir = Path(folder)
        self._path_label.setText(str(self._project_dir))
        self._run_read()

    def _run_read(self):
        self._log.clear()
        self._table.setRowCount(0)

        project = self._project_dir
        self._log_msg(f"Project: {project}")

        # Discover sheets
        files = find_schematic_files(project)
        if not files:
            self._log_msg("ERROR: No .kicad_pro / .kicad_sch found in this folder.")
            self._btn_run_write.setEnabled(False)
            return

        self._log_msg(f"Found {len(files)} schematic file(s):")
        for f in files:
            self._log_msg(f"  {f.relative_to(project)}")

        # Read symbols
        rows = []
        for sch_file in files:
            symbols = read_symbols(sch_file)
            rel = str(sch_file.relative_to(project))
            for s in symbols:
                mpn = s.fields.get("MPN", "")
                others = {k: v for k, v in s.fields.items()
                          if k not in ("Reference", "Value", "Footprint", "Datasheet", "MPN")}
                rows.append((rel, s.reference, s.value, s.footprint, mpn, others))

        self._populating = True
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(rows))
        read_only = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        for i, (sheet, ref, val, fp, mpn, others) in enumerate(rows):
            # Read-only columns
            for col, text in [(0, sheet), (1, ref), (2, val), (3, fp), (5, str(others) if others else "")]:
                item = QTableWidgetItem(text)
                item.setFlags(read_only)
                self._table.setItem(i, col, item)
            # MPN column — editable
            item_mpn = QTableWidgetItem(mpn)
            if mpn:
                item_mpn.setBackground(Qt.GlobalColor.green)
            self._table.setItem(i, 4, item_mpn)
            # Store the absolute sheet path in the sheet item's data role
            self._table.item(i, 0).setData(Qt.ItemDataRole.UserRole, sheet)
        self._table.setSortingEnabled(True)
        self._table.resizeColumnsToContents()
        self._populating = False

        self._log_msg(f"\nTotal: {len(rows)} placed symbols")

        # Test find_symbol_sheet
        if rows:
            test_ref = rows[0][1]
            found = find_symbol_sheet(project, test_ref)
            if found:
                self._log_msg(
                    f"find_symbol_sheet('{test_ref}') -> {found.relative_to(project)}"
                )
            else:
                self._log_msg(f"WARNING: find_symbol_sheet('{test_ref}') returned None")

        self._btn_run_write.setEnabled(True)

    def _on_cell_changed(self, row: int, col: int):
        if self._populating or col != 4:
            return  # only react to MPN column edits

        ref = self._table.item(row, 1).text()
        new_mpn = self._table.item(row, 4).text().strip()
        sheet_rel = self._table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        sch_path = self._project_dir / sheet_rel

        if not new_mpn:
            self._log_msg(f"Ignored empty MPN for {ref}")
            return

        # Check if KiCad has the file open
        locked = is_schematic_locked(sch_path)
        self._log_msg(f"Lock check: {sch_path.name} locked={locked}")
        if locked:
            QMessageBox.warning(
                self,
                "Schematic is open in KiCad",
                f"Cannot write to:\n{sch_path.name}\n\n"
                f"KiCad has this schematic open. Close it in KiCad first, "
                f"then try again.",
            )
            self._log_msg(f"BLOCKED: {sch_path.name} is open in KiCad — close it first")
            # Revert cell
            old_symbols = read_symbols(sch_path)
            old = next((s for s in old_symbols if s.reference == ref), None)
            old_mpn = old.fields.get("MPN", "") if old else ""
            self._populating = True
            self._table.item(row, 4).setText(old_mpn)
            self._populating = False
            return

        # Confirm before writing to real file
        reply = QMessageBox.question(
            self,
            "Write MPN to schematic?",
            f"Write MPN = \"{new_mpn}\" to {ref} in:\n{sch_path}\n\n"
            f"This modifies the REAL .kicad_sch file.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            self._log_msg(f"Cancelled write for {ref}")
            # Revert cell to old value
            old_symbols = read_symbols(sch_path)
            old = next((s for s in old_symbols if s.reference == ref), None)
            old_mpn = old.fields.get("MPN", "") if old else ""
            self._populating = True
            self._table.item(row, 4).setText(old_mpn)
            self._populating = False
            return

        # Write to real file
        self._log_msg(f"Writing MPN=\"{new_mpn}\" to {ref} in {sch_path.name}...")
        result = set_field(sch_path, ref, "MPN", new_mpn, allow_overwrite=True)
        if result:
            self._log_msg(f"  PASS: wrote MPN to {ref}")
            # Verify round-trip
            syms = read_symbols(sch_path)
            s = next((x for x in syms if x.reference == ref), None)
            if s and s.fields.get("MPN") == new_mpn:
                self._log_msg(f"  Verified: re-read MPN = {s.fields['MPN']}")
                self._populating = True
                self._table.item(row, 4).setBackground(Qt.GlobalColor.green)
                self._populating = False
            else:
                self._log_msg(f"  WARNING: re-read did not match!")
        else:
            self._log_msg(f"  FAIL: set_field returned False for {ref}")

    def _run_write_tests(self):
        if not self._project_dir:
            return

        self._log_msg(f"\n{'='*50}")
        self._log_msg("WRITE-BACK TESTS (on temporary copy, originals safe)")
        self._log_msg(f"{'='*50}")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_project = Path(tmp) / self._project_dir.name
            shutil.copytree(self._project_dir, tmp_project)

            tmp_files = find_schematic_files(tmp_project)
            if not tmp_files:
                self._log_msg("ERROR: copy failed")
                return

            target_no_mpn = None
            target_has_mpn = None
            for sch_file in tmp_files:
                for sym in read_symbols(sch_file):
                    if "MPN" not in sym.fields and target_no_mpn is None:
                        target_no_mpn = (sch_file, sym.reference)
                    if sym.fields.get("MPN") and target_has_mpn is None:
                        target_has_mpn = (sch_file, sym.reference, sym.fields["MPN"])

            # Test 1: Add new MPN
            if target_no_mpn:
                sch, ref = target_no_mpn
                self._log_msg(f"\n1. Adding MPN to {ref} (no existing MPN)...")
                result = set_field(sch, ref, "MPN", "TEST-MPN-12345")
                self._log_msg(f"   set_field returned: {result}")
                syms = read_symbols(sch)
                s = next((x for x in syms if x.reference == ref), None)
                if s and s.fields.get("MPN") == "TEST-MPN-12345":
                    self._log_msg(f"   PASS: {ref} now has MPN = {s.fields['MPN']}")
                else:
                    self._log_msg(f"   FAIL: MPN not found after write")
            else:
                self._log_msg("\n1. SKIP: all symbols already have MPN")

            # Test 2: No-overwrite
            if target_has_mpn:
                sch, ref, old_mpn = target_has_mpn
                self._log_msg(f"\n2. No-overwrite on {ref} (existing MPN = {old_mpn})...")
                result = set_field(sch, ref, "MPN", "SHOULD-NOT-WRITE")
                self._log_msg(f"   set_field(allow_overwrite=False) returned: {result}")
                syms = read_symbols(sch)
                s = next((x for x in syms if x.reference == ref), None)
                if s and s.fields.get("MPN") == old_mpn:
                    self._log_msg(f"   PASS: MPN unchanged = {old_mpn}")
                else:
                    self._log_msg(f"   FAIL: MPN was overwritten!")

                # Test 3: Overwrite
                self._log_msg(f"\n3. Overwrite on {ref}...")
                result = set_field(sch, ref, "MPN", "OVERWRITTEN-MPN", allow_overwrite=True)
                self._log_msg(f"   set_field(allow_overwrite=True) returned: {result}")
                syms = read_symbols(sch)
                s = next((x for x in syms if x.reference == ref), None)
                if s and s.fields.get("MPN") == "OVERWRITTEN-MPN":
                    self._log_msg(f"   PASS: MPN updated to {s.fields['MPN']}")
                else:
                    self._log_msg(f"   FAIL: MPN not updated")
            else:
                self._log_msg("\n2-3. SKIP: no symbols with existing MPN")

        self._log_msg(f"\nAll done. Original files were NOT modified.")


def main():
    app = QApplication(sys.argv)
    window = ParserTestWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
