"""Tests for offline operation (Story 4.3)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kipart_search.core.cache import QueryCache, TTL_PARAMETRIC
from kipart_search.core.models import (
    Confidence,
    PartResult,
    part_result_to_dict,
)
from kipart_search.core.search import SearchOrchestrator
from kipart_search.core.sources import DataSource, JLCPCBSource


# ── Helpers ──


def _make_part(**overrides) -> PartResult:
    """Create a PartResult with sensible defaults."""
    defaults = dict(
        mpn="TEST-MPN-001",
        manufacturer="TestMfr",
        description="Test part",
        package="0805",
        category="Resistors",
        source="TestSource",
        source_part_id="TST001",
        source_url="",
        confidence=Confidence.AMBER,
    )
    defaults.update(overrides)
    return PartResult(**defaults)


class FakeLocalSource(DataSource):
    """A local source that always returns results."""

    name = "FakeLocal"

    @property
    def is_local(self) -> bool:
        return True

    def search(self, query, filters=None, limit=50):
        return [_make_part(source="FakeLocal", mpn=f"LOCAL-{query}")]

    def get_part(self, mpn, manufacturer=""):
        return _make_part(source="FakeLocal", mpn=mpn)


class FakeAPISource(DataSource):
    """An API source that raises connection errors (simulates offline)."""

    name = "FakeAPI"

    @property
    def is_local(self) -> bool:
        return False

    def search(self, query, filters=None, limit=50):
        raise ConnectionError("Network unreachable")

    def get_part(self, mpn, manufacturer=""):
        raise ConnectionError("Network unreachable")


class FakeWorkingAPISource(DataSource):
    """An API source that works normally."""

    name = "FakeOnlineAPI"

    def search(self, query, filters=None, limit=50):
        return [_make_part(source="FakeOnlineAPI", mpn=f"API-{query}")]

    def get_part(self, mpn, manufacturer=""):
        return _make_part(source="FakeOnlineAPI", mpn=mpn)


@pytest.fixture
def cache(tmp_path: Path) -> QueryCache:
    c = QueryCache(db_path=tmp_path / "test_cache.db")
    yield c
    c.close()


# ── Tests ──


class TestIsLocalProperty:
    """Test is_local property on DataSource and subclasses (5.3)."""

    def test_datasource_base_is_not_local(self):
        """DataSource.is_local defaults to False."""
        # Cannot instantiate ABC directly, use FakeWorkingAPISource
        source = FakeWorkingAPISource()
        assert source.is_local is False

    def test_jlcpcb_source_is_local(self, tmp_path: Path):
        """JLCPCBSource.is_local returns True."""
        source = JLCPCBSource(db_path=tmp_path / "nonexistent.db")
        assert source.is_local is True

    def test_fake_local_source_is_local(self):
        source = FakeLocalSource()
        assert source.is_local is True

    def test_fake_api_source_is_not_local(self):
        source = FakeAPISource()
        assert source.is_local is False


class TestSearchOrchestratorOfflineFallback:
    """Test that SearchOrchestrator handles offline sources gracefully (5.2)."""

    def test_search_continues_when_api_source_raises(self):
        """When an API source raises, local source results are still returned."""
        orch = SearchOrchestrator()
        orch.add_source(FakeLocalSource())
        orch.add_source(FakeAPISource())

        results = orch.search("100nF")
        assert len(results) > 0
        assert all(r.source == "FakeLocal" for r in results)

    def test_search_returns_empty_when_all_sources_offline(self):
        """When all sources fail, search returns empty list (no crash)."""
        orch = SearchOrchestrator()
        orch.add_source(FakeAPISource())

        results = orch.search("100nF")
        assert results == []

    def test_verify_mpn_continues_when_source_raises(self):
        """verify_mpn skips failing sources and tries the next (5.5)."""
        orch = SearchOrchestrator()
        orch.add_source(FakeAPISource())  # will fail
        orch.add_source(FakeLocalSource())  # will succeed

        result = orch.verify_mpn("TEST-001")
        assert result is not None
        assert result.source == "FakeLocal"

    def test_verify_mpn_returns_none_when_all_offline(self):
        """verify_mpn returns None when all sources fail."""
        orch = SearchOrchestrator()
        orch.add_source(FakeAPISource())

        result = orch.verify_mpn("TEST-001")
        assert result is None


class TestCachedResultsWhenOffline:
    """Test that cached results are served when source is offline (5.4)."""

    def test_cached_search_results_served_when_source_offline(self, cache: QueryCache, pro_license):
        """Pre-cached results are returned even if source is unreachable."""
        # Pre-populate cache with results for the API source
        part = _make_part(source="FakeAPI", mpn="CACHED-100nF")
        cache.put("FakeAPI", "search", "100nF", [part_result_to_dict(part)], TTL_PARAMETRIC)

        orch = SearchOrchestrator(cache=cache)
        orch.add_source(FakeAPISource())  # will fail on live query

        results = orch.search("100nF")
        # The cache entry should be found before the source is queried
        assert len(results) == 1
        assert results[0].mpn == "CACHED-100nF"

    def test_cached_verify_mpn_served_when_source_offline(self, cache: QueryCache):
        """Cached MPN verification results are served when source is offline."""
        part = _make_part(source="FakeAPI", mpn="CACHED-MPN")
        cache.put("FakeAPI", "get_part", "CACHED-MPN", part_result_to_dict(part), TTL_PARAMETRIC)

        orch = SearchOrchestrator(cache=cache)
        orch.add_source(FakeAPISource())

        result = orch.verify_mpn("CACHED-MPN")
        assert result is not None
        assert result.mpn == "CACHED-MPN"


class TestJLCPCBSourceOffline:
    """Test that JLCPCBSource works without network (5.1)."""

    def test_search_returns_empty_when_db_missing(self, tmp_path: Path):
        """JLCPCBSource.search returns [] when DB file doesn't exist."""
        source = JLCPCBSource(db_path=tmp_path / "nonexistent.db")
        results = source.search("100nF")
        assert results == []

    def test_get_part_returns_none_when_db_missing(self, tmp_path: Path):
        """JLCPCBSource.get_part returns None when DB file doesn't exist."""
        source = JLCPCBSource(db_path=tmp_path / "nonexistent.db")
        result = source.get_part("TEST-MPN")
        assert result is None

    def test_is_configured_false_when_db_missing(self, tmp_path: Path):
        source = JLCPCBSource(db_path=tmp_path / "nonexistent.db")
        assert source.is_configured() is False
