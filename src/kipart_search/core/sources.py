"""Data source abstraction and adapters.

Each distributor/database is a subclass of DataSource with a common interface.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable

from kipart_search.core.models import Confidence, PartResult

log = logging.getLogger(__name__)

# JLCPCB database columns
JLCPCB_COLUMNS = [
    "LCSC Part",
    "MFR.Part",
    "Package",
    "Solder Joint",
    "Library Type",
    "Stock",
    "Manufacturer",
    "Description",
    "Price",
    "First Category",
]


class DataSource(ABC):
    """Abstract base class for all data sources."""

    name: str = ""
    needs_key: bool = False
    key_fields: list[str] = []

    @abstractmethod
    def search(
        self, query: str, filters: dict | None = None, limit: int = 50
    ) -> list[PartResult]:
        """Search for parts matching query and optional parametric filters."""
        ...

    @abstractmethod
    def get_part(self, mpn: str, manufacturer: str = "") -> PartResult | None:
        """Look up a specific part by MPN."""
        ...

    @property
    def is_local(self) -> bool:
        """Whether this source works without network access."""
        return False

    def is_configured(self) -> bool:
        """Return True if this source is ready to use."""
        return True

    def get_db_modified_time(self) -> float | None:
        """Return the database file modification time, or None if not applicable."""
        return None


class JLCPCBSource(DataSource):
    """JLCPCB/LCSC offline SQLite FTS5 database.

    Search logic adapted from:
    https://github.com/Bouni/kicad-jlcpcb-tools (MIT License)
    Original author: Bouni
    """

    name = "JLCPCB"
    needs_key = False

    @property
    def is_local(self) -> bool:
        return True

    # Database hosting
    URL_BASE = "https://bouni.github.io/kicad-jlcpcb-tools/"
    CHUNK_COUNT_FILE = "chunk_num_fts5.txt"
    CHUNK_FILE_STUB = "parts-fts5.db.zip."

    # The DB uses ASCII for capacitors/inductors (uF, nF, uH) but Unicode Ω
    # for resistors (10kΩ). The query_transform converts uF→µF and Ohm→Ω.
    # Reverse µ→u for cap/inductor units; keep Ω as-is (DB uses it).
    # Also strip "ohm" since DB stores "10kΩ" not "10kohm".
    _QUERY_FIXUPS: list[tuple[str, str]] = [
        ("\u00b5F", "uF"), ("\u00b5H", "uH"), ("\u00b5A", "uA"), ("\u00b5V", "uV"),
        ("kohm", "k\u03a9"), ("Mohm", "M\u03a9"), ("mohm", "m\u03a9"),
        ("Ohm", "\u03a9"),
    ]

    @staticmethod
    def _to_db_query(query: str) -> str:
        """Normalize query to match the JLCPCB DB's unit conventions."""
        for src, dst in JLCPCBSource._QUERY_FIXUPS:
            query = query.replace(src, dst)
        return query

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or self.default_db_path()
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create a database connection.

        Uses check_same_thread=False because searches run in QThread workers.
        The connection is only used for read-only queries, so this is safe.
        """
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path), check_same_thread=False
            )
            self._conn.create_collation("naturalsort", _natural_sort_collation)
        return self._conn

    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def is_configured(self) -> bool:
        """Database file must exist."""
        return self.db_path is not None and self.db_path.exists()

    def get_db_modified_time(self) -> float | None:
        """Return the mtime of the JLCPCB database file."""
        if self.db_path is None or not self.db_path.exists():
            return None
        try:
            return os.path.getmtime(self.db_path)
        except OSError:
            return None

    def search(
        self, query: str, filters: dict | None = None, limit: int = 50
    ) -> list[PartResult]:
        """Search the local JLCPCB database using FTS5.

        Adapted from kicad-jlcpcb-tools library.py search method.
        """
        if not self.is_configured():
            return []

        query = self._to_db_query(query.strip())
        if not query:
            return []

        conn = self._get_conn()
        columns = ", ".join(f'"{c}"' for c in JLCPCB_COLUMNS)

        # Build FTS5 MATCH query
        # For short terms (< 3 chars), FTS5 doesn't work well.
        # Use instr() instead of LIKE — LIKE has a bug with multi-byte
        # UTF-8 characters (e.g. kΩ) on FTS5 virtual tables.
        terms = query.split()
        short_terms = [t for t in terms if len(t) < 3]
        long_terms = [t for t in terms if len(t) >= 3]

        if long_terms:
            # FTS5 match: each term with wildcard
            match_expr = " ".join(f'"{t}"*' for t in long_terms)
            sql = f'SELECT {columns} FROM parts WHERE parts MATCH ? '

            # Add instr() clauses for short terms
            for _t in short_terms:
                sql += 'AND instr("Description", ?) > 0 '

            sql += f"LIMIT {limit}"

            params: list[str] = [match_expr]
            params.extend(short_terms)
        elif short_terms:
            # All terms are short, use instr() only
            sql = f"SELECT {columns} FROM parts WHERE 1=1 "
            for _t in short_terms:
                sql += 'AND instr("Description", ?) > 0 '
            sql += f"LIMIT {limit}"
            params = list(short_terms)
        else:
            return []

        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as e:
            log.warning("JLCPCB search error: %s", e)
            return []

        return [self._row_to_part(row) for row in rows]

    def get_part(self, mpn: str, manufacturer: str = "") -> PartResult | None:
        """Look up a specific MPN in the local database."""
        if not self.is_configured():
            return None

        conn = self._get_conn()
        columns = ", ".join(f'"{c}"' for c in JLCPCB_COLUMNS)

        try:
            # Try exact match on MFR.Part first
            row = conn.execute(
                f'SELECT {columns} FROM parts WHERE "MFR.Part" = ? LIMIT 1',
                (mpn,),
            ).fetchone()

            if row is None:
                # Try FTS5 match
                row = conn.execute(
                    f"SELECT {columns} FROM parts WHERE parts MATCH ? LIMIT 1",
                    (f'"{mpn}"',),
                ).fetchone()
        except sqlite3.OperationalError as e:
            log.warning("JLCPCB get_part error: %s", e)
            return None

        if row is None:
            return None

        result = self._row_to_part(row)
        result.confidence = Confidence.GREEN  # Exact MPN match
        return result

    @staticmethod
    def _row_to_part(row: tuple) -> PartResult:
        """Convert a database row to a PartResult."""
        lcsc, mfr_part, package, solder_joint, lib_type, stock, manufacturer, description, price, category = row
        return PartResult(
            mpn=mfr_part or "",
            manufacturer=manufacturer or "",
            description=description or "",
            package=package or "",
            category=category or "",
            source="JLCPCB",
            source_part_id=lcsc or "",
            source_url=f"https://jlcpcb.com/partdetail/{lcsc}" if lcsc else "",
            stock=int(stock) if stock else None,
            confidence=Confidence.AMBER,
        )

    @staticmethod
    def check_database_integrity(db_path: Path | None = None) -> tuple[bool, str]:
        """Check if the JLCPCB database is readable and has the expected structure."""
        path = db_path or JLCPCBSource.default_db_path()
        if not path.exists():
            return False, "Database file not found"
        conn = None
        try:
            conn = sqlite3.connect(str(path))
            row = conn.execute("SELECT count(*) FROM parts LIMIT 1").fetchone()
            return True, f"Database OK ({row[0]} parts)"
        except sqlite3.DatabaseError as e:
            return False, f"Database corrupted: {e}"
        finally:
            if conn:
                conn.close()

    @staticmethod
    def default_db_path() -> Path:
        """Default location for the JLCPCB database file."""
        return Path.home() / ".kipart-search" / "jlcpcb" / "parts-fts5.db"

    @staticmethod
    def db_needs_download(db_path: Path | None = None) -> bool:
        """Check if the database needs to be downloaded."""
        path = db_path or JLCPCBSource.default_db_path()
        return not path.exists()

    @staticmethod
    def check_for_update(db_path: Path | None = None) -> tuple[bool, str]:
        """Check if a newer database is available remotely.

        Returns (update_available, message).
        Uses the HTTP Last-Modified header on the chunk count file as
        the remote build date, and compares with local metadata.
        """
        import json

        import httpx

        path = db_path or JLCPCBSource.default_db_path()
        meta_path = path.parent / "db_meta.json"

        if not path.exists():
            return True, "No local database found."

        # Read local metadata
        local_chunks = None
        local_date = None
        local_remote_date = None
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
                local_chunks = meta.get("chunk_count")
                local_date = meta.get("downloaded_at", "unknown")
                local_remote_date = meta.get("remote_last_modified")
            except Exception:
                pass

        # Fetch remote chunk count and Last-Modified header
        try:
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                r = client.get(JLCPCBSource.URL_BASE + JLCPCBSource.CHUNK_COUNT_FILE)
                r.raise_for_status()
                remote_chunks = int(r.text.strip())
                remote_last_modified = r.headers.get("last-modified", "")
        except Exception as e:
            return False, f"Could not check for updates: {e}"

        if local_chunks is None:
            return True, (
                f"Local database exists but has no version info.\n"
                f"Remote: {remote_chunks} chunks"
                f" (built {remote_last_modified})." if remote_last_modified else "."
            )

        # Compare: either chunk count changed or remote was rebuilt
        if remote_chunks != local_chunks:
            return True, (
                f"Update available: remote has {remote_chunks} chunks "
                f"(built {remote_last_modified}),\n"
                f"local has {local_chunks} chunks (downloaded {local_date})."
            )

        if remote_last_modified and local_remote_date and remote_last_modified != local_remote_date:
            return True, (
                f"Database was rebuilt on the server.\n"
                f"Remote: {remote_last_modified}\n"
                f"Local: downloaded {local_date} (server was {local_remote_date})."
            )

        return False, (
            f"Database is up to date.\n"
            f"Chunks: {local_chunks} | Downloaded: {local_date}"
            + (f" | Server build: {local_remote_date}" if local_remote_date else "")
        )

    @staticmethod
    def _save_db_metadata(db_path: Path, chunk_count: int, remote_last_modified: str = ""):
        """Save metadata alongside the database after download."""
        import json
        from datetime import datetime, timezone

        meta_path = db_path.parent / "db_meta.json"
        meta = {
            "chunk_count": chunk_count,
            "downloaded_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "remote_last_modified": remote_last_modified,
            "db_file": db_path.name,
        }
        meta_path.write_text(json.dumps(meta, indent=2))

    @staticmethod
    def download_database(
        target_dir: Path | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> Path:
        """Download the JLCPCB FTS5 database with atomic replacement.

        Downloads to a temporary directory first, then swaps the database
        file atomically. If an existing database is present, it is backed
        up and only removed after the new one is successfully in place.

        Args:
            target_dir: Directory to save the database. Defaults to ~/.kipart-search/jlcpcb/
            progress_callback: Called with (current_step, total_steps, message)
            cancel_check: Called between chunks; if it returns True, download
                is aborted and partial files are cleaned up.

        Returns:
            Path to the downloaded database file.

        Raises:
            RuntimeError: If download, extraction, or cancellation occurs.
        """
        import shutil
        import zipfile

        import httpx

        target_dir = target_dir or JLCPCBSource.default_db_path().parent
        target_dir.mkdir(parents=True, exist_ok=True)

        tmp_dir = target_dir / ".download-tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        db_file = target_dir / "parts-fts5.db"
        zip_file = tmp_dir / "parts-fts5.db.zip"

        def _report(step: int, total: int, msg: str):
            if progress_callback:
                progress_callback(step, total, msg)
            log.info("Download [%d/%d]: %s", step, total, msg)

        def _check_cancel():
            if cancel_check and cancel_check():
                shutil.rmtree(tmp_dir, ignore_errors=True)
                raise RuntimeError("Download cancelled")

        try:
            # Step 1: Get chunk count and server build date
            _report(0, 1, "Checking database version...")
            _check_cancel()
            with httpx.Client(timeout=60, follow_redirects=True) as client:
                r = client.get(JLCPCBSource.URL_BASE + JLCPCBSource.CHUNK_COUNT_FILE)
                r.raise_for_status()
                total_chunks = int(r.text.strip())
                remote_last_modified = r.headers.get("last-modified", "")

            _report(0, total_chunks + 2, f"Downloading {total_chunks} chunks...")

            # Step 2: Download chunks to tmp_dir
            with httpx.Client(timeout=300, follow_redirects=True) as client:
                for i in range(1, total_chunks + 1):
                    _check_cancel()
                    chunk_name = f"{JLCPCBSource.CHUNK_FILE_STUB}{i:03d}"
                    _report(i, total_chunks + 2, f"Downloading {chunk_name}...")

                    chunk_path = tmp_dir / chunk_name
                    url = JLCPCBSource.URL_BASE + chunk_name

                    with client.stream("GET", url) as response:
                        response.raise_for_status()
                        with open(chunk_path, "wb") as f:
                            for data in response.iter_bytes(chunk_size=1024 * 1024):
                                f.write(data)

            _check_cancel()

            # Step 3: Combine chunks into zip
            _report(total_chunks + 1, total_chunks + 2, "Combining chunks...")
            with open(zip_file, "wb") as combined:
                for i in range(1, total_chunks + 1):
                    chunk_path = tmp_dir / f"{JLCPCBSource.CHUNK_FILE_STUB}{i:03d}"
                    with open(chunk_path, "rb") as chunk:
                        while data := chunk.read(1024 * 1024):
                            combined.write(data)
                    chunk_path.unlink()  # Delete chunk after merging

            # Step 4: Extract database from zip into tmp_dir
            _report(total_chunks + 2, total_chunks + 2, "Extracting database...")
            with zipfile.ZipFile(zip_file, "r") as zf:
                names = zf.namelist()
                if not names:
                    raise RuntimeError("Empty zip archive")
                zf.extract(names[0], tmp_dir)

            zip_file.unlink()

            # Step 5: Atomic swap — backup old, move new, clean up
            tmp_db = tmp_dir / names[0]
            if tmp_db.name != "parts-fts5.db":
                final_tmp = tmp_dir / "parts-fts5.db"
                tmp_db.rename(final_tmp)
                tmp_db = final_tmp

            backup_db = target_dir / "parts-fts5.db.bak"
            if db_file.exists():
                db_file.rename(backup_db)
            try:
                tmp_db.rename(db_file)
                if backup_db.exists():
                    backup_db.unlink()
            except Exception:
                # Restore backup on failure
                if backup_db.exists():
                    backup_db.rename(db_file)
                raise

        except Exception:
            # Clean up tmp_dir on any failure (including cancellation)
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise
        else:
            # Clean up tmp_dir on success
            shutil.rmtree(tmp_dir, ignore_errors=True)

        JLCPCBSource._save_db_metadata(db_file, total_chunks, remote_last_modified)
        _report(total_chunks + 2, total_chunks + 2, "Database ready!")
        return db_file


def _natural_sort_collation(a: str, b: str) -> int:
    """Natural sort collation for SQLite (e.g. C1 < C2 < C10)."""
    import re

    def _key(s: str):
        return [
            int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", s)
        ]

    ka, kb = _key(a), _key(b)
    if ka < kb:
        return -1
    if ka > kb:
        return 1
    return 0
