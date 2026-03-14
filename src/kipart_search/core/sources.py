"""Data source abstraction and adapters.

Each distributor/database is a subclass of DataSource with a common interface.
"""

from __future__ import annotations

import logging
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

    def is_configured(self) -> bool:
        """Return True if this source is ready to use."""
        return True


class JLCPCBSource(DataSource):
    """JLCPCB/LCSC offline SQLite FTS5 database.

    Search logic adapted from:
    https://github.com/Bouni/kicad-jlcpcb-tools (MIT License)
    Original author: Bouni
    """

    name = "JLCPCB"
    needs_key = False

    # Database hosting
    URL_BASE = "https://bouni.github.io/kicad-jlcpcb-tools/"
    CHUNK_COUNT_FILE = "chunk_num_fts5.txt"
    CHUNK_FILE_STUB = "parts-fts5.db.zip."

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or self.default_db_path()
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create a database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
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

    def search(
        self, query: str, filters: dict | None = None, limit: int = 50
    ) -> list[PartResult]:
        """Search the local JLCPCB database using FTS5.

        Adapted from kicad-jlcpcb-tools library.py search method.
        """
        if not self.is_configured():
            return []

        query = query.strip()
        if not query:
            return []

        conn = self._get_conn()
        columns = ", ".join(f'"{c}"' for c in JLCPCB_COLUMNS)

        # Build FTS5 MATCH query
        # For short terms (< 3 chars), FTS5 doesn't work well, use LIKE
        terms = query.split()
        short_terms = [t for t in terms if len(t) < 3]
        long_terms = [t for t in terms if len(t) >= 3]

        if long_terms:
            # FTS5 match: each term with wildcard
            match_expr = " ".join(f'"{t}"*' for t in long_terms)
            sql = f'SELECT {columns} FROM parts WHERE parts MATCH ? '

            # Add LIKE clauses for short terms
            for i, t in enumerate(short_terms):
                sql += f'AND "Description" LIKE ? '

            sql += f"LIMIT {limit}"

            params: list[str] = [match_expr]
            params.extend(f"%{t}%" for t in short_terms)
        elif short_terms:
            # All terms are short, use LIKE only
            sql = f"SELECT {columns} FROM parts WHERE 1=1 "
            for t in short_terms:
                sql += f'AND "Description" LIKE ? '
            sql += f"LIMIT {limit}"
            params = [f"%{t}%" for t in short_terms]
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
    def default_db_path() -> Path:
        """Default location for the JLCPCB database file."""
        return Path.home() / ".kipart-search" / "jlcpcb" / "parts-fts5.db"

    @staticmethod
    def db_needs_download(db_path: Path | None = None) -> bool:
        """Check if the database needs to be downloaded."""
        path = db_path or JLCPCBSource.default_db_path()
        return not path.exists()

    @staticmethod
    def download_database(
        target_dir: Path | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> Path:
        """Download the JLCPCB FTS5 database.

        Args:
            target_dir: Directory to save the database. Defaults to ~/.kipart-search/jlcpcb/
            progress_callback: Called with (current_step, total_steps, message)

        Returns:
            Path to the downloaded database file.

        Raises:
            RuntimeError: If download or extraction fails.
        """
        import zipfile

        import httpx

        target_dir = target_dir or JLCPCBSource.default_db_path().parent
        target_dir.mkdir(parents=True, exist_ok=True)

        db_file = target_dir / "parts-fts5.db"
        zip_file = target_dir / "parts-fts5.db.zip"

        def _report(step: int, total: int, msg: str):
            if progress_callback:
                progress_callback(step, total, msg)
            log.info("Download [%d/%d]: %s", step, total, msg)

        # Step 1: Get chunk count
        _report(0, 1, "Checking database version...")
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            r = client.get(JLCPCBSource.URL_BASE + JLCPCBSource.CHUNK_COUNT_FILE)
            r.raise_for_status()
            total_chunks = int(r.text.strip())

        _report(0, total_chunks + 2, f"Downloading {total_chunks} chunks...")

        # Step 2: Download chunks
        with httpx.Client(timeout=300, follow_redirects=True) as client:
            for i in range(1, total_chunks + 1):
                chunk_name = f"{JLCPCBSource.CHUNK_FILE_STUB}{i:03d}"
                _report(i, total_chunks + 2, f"Downloading {chunk_name}...")

                chunk_path = target_dir / chunk_name
                url = JLCPCBSource.URL_BASE + chunk_name

                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    with open(chunk_path, "wb") as f:
                        for data in response.iter_bytes(chunk_size=1024 * 1024):
                            f.write(data)

        # Step 3: Combine chunks into zip
        _report(total_chunks + 1, total_chunks + 2, "Combining chunks...")
        with open(zip_file, "wb") as combined:
            for i in range(1, total_chunks + 1):
                chunk_path = target_dir / f"{JLCPCBSource.CHUNK_FILE_STUB}{i:03d}"
                with open(chunk_path, "rb") as chunk:
                    while data := chunk.read(1024 * 1024):
                        combined.write(data)
                chunk_path.unlink()  # Delete chunk after merging

        # Step 4: Extract database from zip
        _report(total_chunks + 2, total_chunks + 2, "Extracting database...")
        with zipfile.ZipFile(zip_file, "r") as zf:
            names = zf.namelist()
            if not names:
                raise RuntimeError("Empty zip archive")
            zf.extract(names[0], target_dir)
            # Rename if needed
            extracted = target_dir / names[0]
            if extracted != db_file:
                if db_file.exists():
                    db_file.unlink()
                extracted.rename(db_file)

        zip_file.unlink()  # Clean up zip

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
