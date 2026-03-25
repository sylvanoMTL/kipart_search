"""Backup browser dialog — view, inspect and restore backups."""

from __future__ import annotations

import csv
import logging
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from kipart_search.core.backup import BackupManager

log = logging.getLogger(__name__)


class BackupBrowserDialog(QDialog):
    """Browse available backups, inspect undo logs, and restore snapshots."""

    restore_requested = Signal(list)  # list[dict] — component dicts to restore

    def __init__(
        self,
        backup_manager: BackupManager,
        project_name: str,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Backup Browser")
        self.setMinimumSize(700, 450)

        self._backup_manager = backup_manager
        self._project_name = project_name

        layout = QVBoxLayout(self)

        # Header
        layout.addWidget(QLabel(f"Backups for project: <b>{project_name}</b>"))

        # Backup table
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Timestamp", "Components", "Changes", "Path"])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(self._table)

        # Buttons
        btn_layout = QHBoxLayout()
        self._btn_view = QPushButton("View Undo Log")
        self._btn_view.clicked.connect(self._on_view_log)
        self._btn_view.setEnabled(False)
        btn_layout.addWidget(self._btn_view)

        self._btn_restore = QPushButton("Restore")
        self._btn_restore.clicked.connect(self._on_restore)
        self._btn_restore.setEnabled(False)
        btn_layout.addWidget(self._btn_restore)

        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._entries = []
        self._refresh()

    def _refresh(self):
        """Reload backup list from disk."""
        self._entries = self._backup_manager.list_backups(self._project_name)
        self._table.setRowCount(len(self._entries))
        for row, entry in enumerate(self._entries):
            self._table.setItem(row, 0, QTableWidgetItem(entry.timestamp))
            self._table.setItem(row, 1, QTableWidgetItem(str(entry.component_count)))
            self._table.setItem(row, 2, QTableWidgetItem(str(entry.change_count)))
            self._table.setItem(row, 3, QTableWidgetItem(str(entry.path)))

    def _on_selection_changed(self):
        has_sel = bool(self._table.selectedItems())
        self._btn_view.setEnabled(has_sel)
        self._btn_restore.setEnabled(has_sel)

    def _selected_entry(self):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return None
        return self._entries[rows[0].row()]

    def _on_view_log(self):
        """Show the undo log CSV for the selected backup as a collapsible tree."""
        entry = self._selected_entry()
        if entry is None:
            return

        csv_path = entry.path / "undo_log.csv"
        if not csv_path.exists():
            QMessageBox.information(self, "No Undo Log", "No undo log found for this backup.")
            return

        try:
            with open(csv_path, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Failed to read undo log: {exc}")
            return

        if not rows:
            QMessageBox.information(self, "Empty Log", "The undo log contains no changes.")
            return

        # Group rows by reference
        by_ref: OrderedDict[str, list[dict]] = OrderedDict()
        for row in rows:
            ref = row.get("reference", "?")
            by_ref.setdefault(ref, []).append(row)

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Undo Log \u2014 {entry.timestamp}")
        dlg.setMinimumSize(650, 450)
        layout = QVBoxLayout(dlg)

        tree = QTreeWidget()
        tree.setHeaderLabels(["Reference / Field", "Old Value", "New Value", "Timestamp"])
        tree.setAlternatingRowColors(True)
        tree.setRootIsDecorated(True)

        for ref, changes in by_ref.items():
            parent = QTreeWidgetItem(tree, [f"{ref}  ({len(changes)} change{'s' if len(changes) != 1 else ''})"])
            parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            font = parent.font(0)
            font.setBold(True)
            parent.setFont(0, font)

            for ch in changes:
                child = QTreeWidgetItem(parent, [
                    ch.get("field", ""),
                    ch.get("old_value", ""),
                    ch.get("new_value", ""),
                    ch.get("timestamp", ""),
                ])
            parent.setExpanded(True)

        tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(tree)

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(dlg.reject)
        layout.addWidget(close_box)
        dlg.exec()

    def _on_restore(self):
        """Restore component state from the selected backup."""
        entry = self._selected_entry()
        if entry is None:
            return

        data = self._backup_manager.load_backup(entry.path)
        if not data:
            QMessageBox.warning(self, "Empty Backup", "This backup contains no component data.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Restore",
            f"Restore {len(data)} components to state from {entry.timestamp}?\n\n"
            "A new backup will be created first as a safety net.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.restore_requested.emit(data)
        self.accept()
