"""Data source abstraction and adapters.

Each distributor/database is a subclass of DataSource with a common interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from kipart_search.core.models import PartResult


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
        """Return True if this source is ready to use (credentials set, DB available, etc.)."""
        return True


class JLCPCBSource(DataSource):
    """JLCPCB/LCSC offline SQLite FTS5 database.

    Search logic adapted from:
    https://github.com/Bouni/kicad-jlcpcb-tools (MIT License)
    Original author: Bouni
    """

    name = "JLCPCB"
    needs_key = False

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path
        self._conn = None

    def is_configured(self) -> bool:
        """Database file must exist."""
        return self.db_path is not None and self.db_path.exists()

    def search(
        self, query: str, filters: dict | None = None, limit: int = 50
    ) -> list[PartResult]:
        """Search the local JLCPCB database using FTS5."""
        if not self.is_configured():
            return []

        # TODO: Implement FTS5 search against local SQLite database
        # - Open connection to self.db_path
        # - Build FTS5 MATCH query from search terms
        # - Apply filters (category, package, etc.)
        # - Map rows to PartResult dataclass
        return []

    def get_part(self, mpn: str, manufacturer: str = "") -> PartResult | None:
        """Look up a specific MPN in the local database."""
        if not self.is_configured():
            return None

        # TODO: FTS5 query for exact MPN match
        return None

    @staticmethod
    def default_db_path() -> Path:
        """Default location for the JLCPCB database file."""
        return Path.home() / ".kipart-search" / "jlcpcb" / "parts-fts5.db"

    @staticmethod
    def db_needs_download(db_path: Path | None = None) -> bool:
        """Check if the database needs to be downloaded."""
        path = db_path or JLCPCBSource.default_db_path()
        return not path.exists()
