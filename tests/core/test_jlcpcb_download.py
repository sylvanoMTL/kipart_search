"""Tests for JLCPCB database download and refresh (Story 4.2)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kipart_search.core.sources import JLCPCBSource


# ── Fixtures ──


@pytest.fixture
def valid_db(tmp_path: Path) -> Path:
    """Create a minimal valid JLCPCB-like SQLite FTS5 database."""
    db_path = tmp_path / "jlcpcb" / "parts-fts5.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE VIRTUAL TABLE parts USING fts5("
        '"LCSC Part", "MFR.Part", "Package", "Solder Joint", '
        '"Library Type", "Stock", "Manufacturer", "Description", '
        '"Price", "First Category"'
        ")"
    )
    conn.execute(
        "INSERT INTO parts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("C123", "RC0805", "0805", "2", "Basic", "1000", "Yageo", "10k resistor", "0.01", "Resistors"),
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def corrupt_db(tmp_path: Path) -> Path:
    """Create a corrupt database file."""
    db_path = tmp_path / "jlcpcb" / "parts-fts5.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_bytes(b"this is not a valid sqlite database")
    return db_path


@pytest.fixture
def empty_file_db(tmp_path: Path) -> Path:
    """Create an empty file pretending to be a database."""
    db_path = tmp_path / "jlcpcb" / "parts-fts5.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_bytes(b"")
    return db_path


# ── check_database_integrity tests ──


class TestCheckDatabaseIntegrity:
    """Tests for JLCPCBSource.check_database_integrity()."""

    def test_valid_db_returns_true(self, valid_db: Path):
        ok, msg = JLCPCBSource.check_database_integrity(valid_db)
        assert ok is True
        assert "1 parts" in msg

    def test_corrupt_file_returns_false(self, corrupt_db: Path):
        ok, msg = JLCPCBSource.check_database_integrity(corrupt_db)
        assert ok is False
        assert "corrupted" in msg.lower() or "corrupt" in msg.lower()

    def test_empty_file_returns_false(self, empty_file_db: Path):
        ok, msg = JLCPCBSource.check_database_integrity(empty_file_db)
        assert ok is False

    def test_nonexistent_file_returns_false(self, tmp_path: Path):
        ok, msg = JLCPCBSource.check_database_integrity(tmp_path / "nonexistent.db")
        assert ok is False
        assert "not found" in msg.lower()

    def test_uses_fresh_connection(self, valid_db: Path):
        """Integrity check uses its own connection, not the source's shared one."""
        source = JLCPCBSource(valid_db)
        # Access the shared connection
        source._get_conn()
        # Integrity check should still work (uses its own connection)
        ok, _ = JLCPCBSource.check_database_integrity(valid_db)
        assert ok is True
        source.close()


# ── Download cancellation tests ──


class TestDownloadCancellation:
    """Tests for download cancellation and cleanup."""

    def test_cancel_check_stops_download(self, tmp_path: Path):
        """Cancellation raises RuntimeError and cleans up."""
        target_dir = tmp_path / "jlcpcb"
        target_dir.mkdir(parents=True, exist_ok=True)

        call_count = 0

        def cancel_after_first():
            nonlocal call_count
            call_count += 1
            return call_count > 1  # Cancel on second check

        mock_response = MagicMock()
        mock_response.text = "3"
        mock_response.headers = {"last-modified": ""}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            client.get.return_value = mock_response

            with pytest.raises(RuntimeError, match="cancelled"):
                JLCPCBSource.download_database(
                    target_dir=target_dir,
                    cancel_check=cancel_after_first,
                )

        # Temp dir should be cleaned up
        tmp_download = target_dir / ".download-tmp"
        assert not tmp_download.exists()

    def test_cancel_preserves_existing_db(self, tmp_path: Path, valid_db: Path):
        """Cancellation does not remove an existing database."""
        # valid_db is in tmp_path/jlcpcb/parts-fts5.db
        target_dir = valid_db.parent
        original_size = valid_db.stat().st_size

        with patch("httpx.Client") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.text = "3"
            mock_response.headers = {"last-modified": ""}
            mock_response.raise_for_status = MagicMock()

            client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            client.get.return_value = mock_response

            with pytest.raises(RuntimeError, match="cancelled"):
                JLCPCBSource.download_database(
                    target_dir=target_dir,
                    cancel_check=lambda: True,  # Cancel immediately
                )

        # Original DB must still be intact
        assert valid_db.exists()
        assert valid_db.stat().st_size == original_size


# ── Atomic replacement tests ──


class TestAtomicReplacement:
    """Tests for atomic database replacement during refresh."""

    @staticmethod
    def _make_mock_http(tmp_path: Path):
        """Create mock HTTP client that serves a valid chunked JLCPCB zip.

        Returns a context-manager mock for httpx.Client that serves:
        - chunk_num_fts5.txt → "1"
        - parts-fts5.db.zip.001 → a zip containing a valid SQLite FTS5 DB
        """
        import io
        import zipfile

        # Build a valid SQLite DB in memory, zip it
        db_path = tmp_path / "_build_db.tmp"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE VIRTUAL TABLE parts USING fts5("
            '"LCSC Part", "MFR.Part", "Package", "Solder Joint", '
            '"Library Type", "Stock", "Manufacturer", "Description", '
            '"Price", "First Category"'
            ")"
        )
        conn.execute(
            "INSERT INTO parts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("C999", "NEW_PART", "0402", "2", "Basic", "500",
             "Murata", "New part", "0.02", "Capacitors"),
        )
        conn.commit()
        conn.close()

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            zf.write(db_path, "parts-fts5.db")
        zip_bytes = zip_buf.getvalue()
        db_path.unlink()

        chunk_count_resp = MagicMock()
        chunk_count_resp.text = "1"
        chunk_count_resp.headers = {"last-modified": "Thu, 01 Jan 2026 00:00:00 GMT"}
        chunk_count_resp.raise_for_status = MagicMock()

        chunk_resp = MagicMock()
        chunk_resp.raise_for_status = MagicMock()
        chunk_resp.iter_bytes = MagicMock(return_value=[zip_bytes])
        chunk_resp.__enter__ = MagicMock(return_value=chunk_resp)
        chunk_resp.__exit__ = MagicMock(return_value=False)

        client = MagicMock()
        client.get.return_value = chunk_count_resp
        client.stream.return_value = chunk_resp

        mock_client_cls = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        return mock_client_cls

    def test_successful_replacement_removes_old_db(self, tmp_path: Path):
        """On success, old DB is replaced, backup and tmp dir are removed."""
        target_dir = tmp_path / "jlcpcb"
        target_dir.mkdir(parents=True, exist_ok=True)

        # Create an "old" database
        old_db = target_dir / "parts-fts5.db"
        old_db.write_text("old database content")

        mock_client_cls = self._make_mock_http(tmp_path)
        with patch("httpx.Client", mock_client_cls):
            result = JLCPCBSource.download_database(target_dir=target_dir)

        assert result.exists()
        assert not (target_dir / "parts-fts5.db.bak").exists()
        assert not (target_dir / ".download-tmp").exists()

        # Verify new content is actually the new DB
        conn = sqlite3.connect(str(result))
        row = conn.execute('SELECT "MFR.Part" FROM parts LIMIT 1').fetchone()
        conn.close()
        assert row[0] == "NEW_PART"

    def test_failed_replacement_restores_backup(self, tmp_path: Path):
        """On failure during swap, old DB is restored from backup."""
        target_dir = tmp_path / "jlcpcb"
        target_dir.mkdir(parents=True, exist_ok=True)

        # Create an "old" database with known content
        old_db = target_dir / "parts-fts5.db"
        old_db.write_text("old database content")
        original_content = old_db.read_text()

        mock_client_cls = self._make_mock_http(tmp_path)

        # Patch Path.rename to fail only on the tmp_db → final_db rename
        original_rename = Path.rename

        def sabotaged_rename(self_path, target):
            # Allow backup rename (old → .bak), but fail when moving new DB into place
            if self_path.parent.name == ".download-tmp" and target.name == "parts-fts5.db":
                raise OSError("Simulated rename failure")
            return original_rename(self_path, target)

        with patch("httpx.Client", mock_client_cls), \
             patch.object(Path, "rename", sabotaged_rename):
            with pytest.raises(OSError, match="Simulated rename failure"):
                JLCPCBSource.download_database(target_dir=target_dir)

        # Old DB must be restored from backup
        assert old_db.exists()
        assert old_db.read_text() == original_content
        assert not (target_dir / "parts-fts5.db.bak").exists()

    def test_cache_db_not_affected(self, tmp_path: Path):
        """Download/refresh operations never touch cache.db."""
        # Set up cache.db at the parent level
        kipart_dir = tmp_path / "KiPartSearch"
        kipart_dir.mkdir()
        cache_db = kipart_dir / "cache.db"
        cache_db.write_text("cache data")

        # Set up jlcpcb dir
        jlcpcb_dir = kipart_dir / "jlcpcb"
        jlcpcb_dir.mkdir()

        mock_client_cls = self._make_mock_http(tmp_path)
        with patch("httpx.Client", mock_client_cls):
            JLCPCBSource.download_database(target_dir=jlcpcb_dir)

        # Cache file should be untouched
        assert cache_db.exists()
        assert cache_db.read_text() == "cache data"
