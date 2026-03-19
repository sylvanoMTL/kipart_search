"""Search orchestrator — queries sources and merges results."""

from __future__ import annotations

from kipart_search.core.models import Confidence, PartResult
from kipart_search.core.sources import DataSource
from kipart_search.core.units import generate_query_variants


class SearchOrchestrator:
    """Coordinates searches across multiple data sources."""

    def __init__(self):
        self._sources: list[DataSource] = []

    def add_source(self, source: DataSource) -> None:
        """Register a data source."""
        self._sources.append(source)

    @property
    def active_sources(self) -> list[DataSource]:
        """Return sources that are configured and ready."""
        return [s for s in self._sources if s.is_configured()]

    def get_source_names(self) -> list[str]:
        """Return names of all configured sources."""
        return [s.name for s in self.active_sources]

    def search_source(
        self, query: str, source_name: str, filters: dict | None = None, limit: int = 50
    ) -> list[PartResult]:
        """Search a single named source."""
        source = next((s for s in self.active_sources if s.name == source_name), None)
        if source is None:
            return []
        return self._search_sources([source], query, filters, limit)

    def search(
        self, query: str, filters: dict | None = None, limit: int = 50
    ) -> list[PartResult]:
        """Search all active sources and merge results.

        Generates equivalent unit variants (e.g. 0.1µF → 100nF) and
        searches each variant, deduplicating by MPN.

        TODO:
        - Run searches in parallel (QThread workers)
        - Calculate confidence score per result
        - Apply parameter template filtering
        """
        return self._search_sources(self.active_sources, query, filters, limit)

    def _search_sources(
        self, sources: list[DataSource], query: str, filters: dict | None, limit: int
    ) -> list[PartResult]:
        """Search given sources with unit-variant expansion, deduplicating by (MPN, source)."""
        variants = generate_query_variants(query)
        seen: set[tuple[str, str]] = set()
        results: list[PartResult] = []

        for variant in variants:
            for source in sources:
                for part in source.search(variant, filters, limit):
                    key = (part.mpn, part.source)
                    if key not in seen:
                        seen.add(key)
                        results.append(part)

        return results

    def verify_mpn(self, mpn: str, manufacturer: str = "") -> PartResult | None:
        """Look up MPN across all sources for verification.

        Returns the best match with confidence score:
        - Found on multiple sources with consistent data → GREEN
        - Found on one source → AMBER
        - Not found → RED
        """
        for source in self.active_sources:
            result = source.get_part(mpn, manufacturer)
            if result:
                result.confidence = Confidence.AMBER  # Single source
                return result
        return None
