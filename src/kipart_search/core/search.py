"""Search orchestrator — queries sources and merges results."""

from __future__ import annotations

import logging
import sqlite3

from kipart_search.core.cache import QueryCache, TTL_PARAMETRIC
from kipart_search.core.models import (
    Confidence,
    PartResult,
    part_result_from_dict,
    part_result_to_dict,
)
from kipart_search.core.sources import DataSource
from kipart_search.core.units import generate_query_variants

log = logging.getLogger(__name__)


class SearchOrchestrator:
    """Coordinates searches across multiple data sources."""

    def __init__(self, cache: QueryCache | None = None):
        self._sources: list[DataSource] = []
        self._cache = cache

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
        """Search given sources with unit-variant expansion, deduplicating by (MPN, source).

        Uses cache-aside pattern: check cache before querying source, store results after.
        """
        # TODO: When API sources with server-side filtering are added (Phase 2),
        # the cache key must incorporate filter parameters.
        variants = generate_query_variants(query)
        seen: set[tuple[str, str]] = set()
        results: list[PartResult] = []

        for variant in variants:
            for source in sources:
                # Check cache first
                cached = self._cache_get(source.name, "search", variant)
                if cached is not None:
                    for d in cached:
                        part = part_result_from_dict(d)
                        key = (part.mpn, part.source)
                        if key not in seen:
                            seen.add(key)
                            results.append(part)
                    log.info("%s: served from cache", source.name)
                    continue

                # Cache miss — query source
                parts = source.search(variant, filters, limit)

                # Store in cache
                if self._cache and parts:
                    self._cache_put(
                        source.name, "search", variant,
                        [part_result_to_dict(p) for p in parts],
                        TTL_PARAMETRIC,
                    )

                for part in parts:
                    key = (part.mpn, part.source)
                    if key not in seen:
                        seen.add(key)
                        results.append(part)

        return results

    def get_db_modified_time(self, source_name: str) -> float | None:
        """Return the database modified time for a named source."""
        source = next((s for s in self._sources if s.name == source_name), None)
        if source is None:
            return None
        return source.get_db_modified_time()

    def verify_mpn(self, mpn: str, manufacturer: str = "") -> PartResult | None:
        """Look up MPN across all sources for verification.

        Returns the best match with confidence score:
        - Found on multiple sources with consistent data → GREEN
        - Found on one source → AMBER
        - Not found → RED
        """
        for source in self.active_sources:
            # Check cache first
            cached = self._cache_get(source.name, "get_part", mpn)
            if cached is not None:
                log.info("%s: MPN '%s' served from cache", source.name, mpn)
                result = part_result_from_dict(cached)
                result.confidence = Confidence.AMBER
                return result

            result = source.get_part(mpn, manufacturer)
            if result:
                result.confidence = Confidence.AMBER  # Single source
                # Store in cache
                self._cache_put(
                    source.name, "get_part", mpn,
                    part_result_to_dict(result),
                    TTL_PARAMETRIC,
                )
                return result
        return None

    # --- Cache helpers with graceful error handling ---

    def _cache_get(self, source: str, query_type: str, query: str) -> dict | list | None:
        """Read from cache, returning None on any error."""
        if not self._cache:
            return None
        try:
            return self._cache.get(source, query_type, query)
        except sqlite3.OperationalError:
            log.warning("Cache read failed, querying source directly")
            return None

    def _cache_put(
        self, source: str, query_type: str, query: str,
        value: dict | list, ttl: float,
    ) -> None:
        """Write to cache, silently ignoring errors."""
        if not self._cache:
            return
        try:
            self._cache.put(source, query_type, query, value, ttl)
        except sqlite3.OperationalError:
            log.warning("Cache write failed, continuing without caching")
