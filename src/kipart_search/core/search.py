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
        variants = generate_query_variants(query)
        seen_mpns: set[str] = set()
        results: list[PartResult] = []

        for variant in variants:
            for source in self.active_sources:
                source_results = source.search(variant, filters, limit)
                for part in source_results:
                    key = (part.mpn, part.source)
                    if key not in seen_mpns:
                        seen_mpns.add(key)
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
