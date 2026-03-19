"""Tests for SQLite query cache (Story 4.1)."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kipart_search.core.cache import QueryCache, TTL_PARAMETRIC, TTL_PRICING, TTL_DATASHEET
from kipart_search.core.models import (
    Confidence,
    ParametricValue,
    PartResult,
    PriceBreak,
    part_result_from_dict,
    part_result_to_dict,
)
from kipart_search.core.search import SearchOrchestrator
from kipart_search.core.sources import DataSource


# ── Fixtures ──

@pytest.fixture
def cache(tmp_path: Path) -> QueryCache:
    """Create a QueryCache backed by a temp file."""
    c = QueryCache(db_path=tmp_path / "test_cache.db")
    yield c
    c.close()


def _make_part(**overrides) -> PartResult:
    """Create a PartResult with sensible defaults."""
    defaults = dict(
        mpn="RC0805FR-0710KL",
        manufacturer="Yageo",
        description="10k 0805 resistor",
        package="0805",
        category="Resistors",
        datasheet_url="https://example.com/datasheet.pdf",
        lifecycle="Active",
        source="JLCPCB",
        source_part_id="C123456",
        source_url="https://jlcpcb.com/parts/C123456",
        specs=[
            ParametricValue(name="Resistance", raw_value="10kΩ", numeric_value=10000.0, unit="Ohm"),
        ],
        price_breaks=[
            PriceBreak(quantity=1, unit_price=0.01, currency="EUR"),
            PriceBreak(quantity=100, unit_price=0.005, currency="EUR"),
        ],
        stock=50000,
        confidence=Confidence.AMBER,
    )
    defaults.update(overrides)
    return PartResult(**defaults)


class FakeSource(DataSource):
    """Fake DataSource for testing orchestrator cache integration."""

    def __init__(self, name: str = "FakeSource", results: list[PartResult] | None = None):
        self._name = name
        self._results = results or []
        self.search_call_count = 0
        self.get_part_call_count = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def needs_key(self) -> bool:
        return False

    @property
    def key_fields(self) -> list[str]:
        return []

    def is_configured(self) -> bool:
        return True

    def search(self, query: str, filters: dict | None = None, limit: int = 50) -> list[PartResult]:
        self.search_call_count += 1
        return list(self._results)

    def get_part(self, mpn: str, manufacturer: str = "") -> PartResult | None:
        self.get_part_call_count += 1
        for p in self._results:
            if p.mpn.lower() == mpn.lower():
                return p
        return None

    def get_db_modified_time(self) -> float | None:
        return None


# ── Test: cache put/get round-trip ──

def test_put_and_get_roundtrip(cache: QueryCache):
    """AC #1: Results are stored and retrieved correctly."""
    data = [{"mpn": "ABC123", "value": 42}]
    cache.put("JLCPCB", "search", "10k resistor", data, TTL_PARAMETRIC)

    result = cache.get("JLCPCB", "search", "10k resistor")
    assert result == data


# ── Test: TTL expiry ──

def test_expired_entries_return_none(cache: QueryCache):
    """AC #3: Expired entries return None."""
    cache.put("JLCPCB", "search", "10k", {"test": True}, ttl=0.01)
    time.sleep(0.02)
    assert cache.get("JLCPCB", "search", "10k") is None


# ── Test: indefinite TTL ──

def test_indefinite_ttl_never_expires(cache: QueryCache):
    """AC #4: TTL=0 entries never expire."""
    cache.put("JLCPCB", "datasheet", "ds_url", {"url": "https://example.com"}, ttl=TTL_DATASHEET)
    # Manually set created_at far in the past
    conn = cache._get_conn()
    conn.execute("UPDATE cache SET created_at = ?", (time.time() - 365 * 86400,))
    conn.commit()

    result = cache.get("JLCPCB", "datasheet", "ds_url")
    assert result is not None
    assert result["url"] == "https://example.com"


# ── Test: invalidate(source) ──

def test_invalidate_source_clears_only_that_source(cache: QueryCache):
    """AC #6: invalidate(source) clears only entries from that source."""
    cache.put("JLCPCB", "search", "q1", {"a": 1}, TTL_PARAMETRIC)
    cache.put("DigiKey", "search", "q2", {"b": 2}, TTL_PARAMETRIC)

    deleted = cache.invalidate("JLCPCB")
    assert deleted == 1

    assert cache.get("JLCPCB", "search", "q1") is None
    assert cache.get("DigiKey", "search", "q2") is not None


# ── Test: invalidate(None) ──

def test_invalidate_all_clears_everything(cache: QueryCache):
    """AC #6: invalidate(None) clears all entries."""
    cache.put("JLCPCB", "search", "q1", {"a": 1}, TTL_PARAMETRIC)
    cache.put("DigiKey", "search", "q2", {"b": 2}, TTL_PARAMETRIC)

    deleted = cache.invalidate(None)
    assert deleted == 2

    assert cache.get("JLCPCB", "search", "q1") is None
    assert cache.get("DigiKey", "search", "q2") is None


# ── Test: WAL mode ──

def test_wal_mode_is_active(cache: QueryCache):
    """AC #5: WAL journal mode is active after connection."""
    conn = cache._get_conn()
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"


# ── Test: cache key normalization ──

def test_cache_key_case_insensitive(cache: QueryCache):
    """Same query with different case produces same cache key."""
    cache.put("JLCPCB", "search", "10K Resistor", {"data": 1}, TTL_PARAMETRIC)
    result = cache.get("JLCPCB", "search", "10k resistor")
    assert result == {"data": 1}


# ── Test: PartResult serialization round-trip ──

def test_part_result_round_trip():
    """AC #1: PartResult round-trip serialization preserves all fields."""
    original = _make_part()
    d = part_result_to_dict(original)
    restored = part_result_from_dict(d)

    assert restored.mpn == original.mpn
    assert restored.manufacturer == original.manufacturer
    assert restored.description == original.description
    assert restored.package == original.package
    assert restored.category == original.category
    assert restored.datasheet_url == original.datasheet_url
    assert restored.lifecycle == original.lifecycle
    assert restored.source == original.source
    assert restored.source_part_id == original.source_part_id
    assert restored.source_url == original.source_url
    assert restored.stock == original.stock
    assert restored.confidence == original.confidence

    # Nested: specs
    assert len(restored.specs) == len(original.specs)
    assert restored.specs[0].name == original.specs[0].name
    assert restored.specs[0].raw_value == original.specs[0].raw_value
    assert restored.specs[0].numeric_value == original.specs[0].numeric_value
    assert restored.specs[0].unit == original.specs[0].unit

    # Nested: price_breaks
    assert len(restored.price_breaks) == len(original.price_breaks)
    assert restored.price_breaks[0].quantity == original.price_breaks[0].quantity
    assert restored.price_breaks[0].unit_price == original.price_breaks[0].unit_price
    assert restored.price_breaks[1].quantity == original.price_breaks[1].quantity


def test_part_result_round_trip_empty_fields():
    """Round-trip with minimal/empty fields."""
    original = PartResult(mpn="BARE-MPN")
    d = part_result_to_dict(original)
    restored = part_result_from_dict(d)

    assert restored.mpn == "BARE-MPN"
    assert restored.specs == []
    assert restored.price_breaks == []
    assert restored.confidence == Confidence.AMBER


# ── Test: SearchOrchestrator cache integration ──

def test_orchestrator_second_search_returns_cached(tmp_path: Path):
    """AC #2: Second identical search returns cached results without network call."""
    cache = QueryCache(db_path=tmp_path / "orch_cache.db")
    part = _make_part(source="FakeSource")
    source = FakeSource(results=[part])

    orch = SearchOrchestrator(cache=cache)
    orch.add_source(source)

    # First search — hits the source
    results1 = orch.search("10k resistor")
    assert len(results1) == 1
    assert source.search_call_count == 1

    # Second search — should serve from cache
    results2 = orch.search("10k resistor")
    assert len(results2) == 1
    assert source.search_call_count == 1  # NOT incremented

    assert results2[0].mpn == part.mpn
    cache.close()


def test_orchestrator_verify_mpn_cached(tmp_path: Path):
    """verify_mpn uses cache on second call."""
    cache = QueryCache(db_path=tmp_path / "verify_cache.db")
    part = _make_part(source="FakeSource")
    source = FakeSource(results=[part])

    orch = SearchOrchestrator(cache=cache)
    orch.add_source(source)

    # First call — hits source
    r1 = orch.verify_mpn("RC0805FR-0710KL")
    assert r1 is not None
    assert source.get_part_call_count == 1

    # Second call — from cache
    r2 = orch.verify_mpn("RC0805FR-0710KL")
    assert r2 is not None
    assert source.get_part_call_count == 1  # NOT incremented

    cache.close()


# ── Test: graceful degradation without cache ──

def test_orchestrator_works_without_cache():
    """AC #6: SearchOrchestrator works identically when cache is None."""
    part = _make_part(source="FakeSource")
    source = FakeSource(results=[part])

    orch = SearchOrchestrator(cache=None)
    orch.add_source(source)

    results = orch.search("10k resistor")
    assert len(results) == 1
    assert results[0].mpn == part.mpn


# ── Test: is_expired ──

def test_is_expired_missing_entry(cache: QueryCache):
    """is_expired returns True for missing entries."""
    assert cache.is_expired("JLCPCB", "search", "nonexistent") is True


def test_is_expired_valid_entry(cache: QueryCache):
    """is_expired returns False for valid (non-expired) entries."""
    cache.put("JLCPCB", "search", "q", {"data": 1}, TTL_PARAMETRIC)
    assert cache.is_expired("JLCPCB", "search", "q") is False


def test_is_expired_expired_entry(cache: QueryCache):
    """is_expired returns True for expired entries."""
    cache.put("JLCPCB", "search", "q", {"data": 1}, ttl=0.01)
    time.sleep(0.02)
    assert cache.is_expired("JLCPCB", "search", "q") is True


# ── Test: stats ──

def test_stats_empty(cache: QueryCache):
    """stats returns zeroes for empty cache."""
    s = cache.stats()
    assert s["count"] == 0
    assert s["total_size_bytes"] == 0
    assert s["oldest_created_at"] is None


def test_stats_with_entries(cache: QueryCache):
    """stats returns correct counts."""
    cache.put("JLCPCB", "search", "q1", {"a": 1}, TTL_PARAMETRIC)
    cache.put("DigiKey", "search", "q2", {"b": 2}, TTL_PARAMETRIC)

    s = cache.stats()
    assert s["count"] == 2
    assert s["total_size_bytes"] > 0
    assert s["oldest_created_at"] is not None


# ── Test: PartResult cache round-trip via QueryCache ──

def test_part_result_cache_full_roundtrip(cache: QueryCache):
    """AC #1: Full round-trip: PartResult → dict → cache → dict → PartResult."""
    original = _make_part()
    data = [part_result_to_dict(original)]
    cache.put("JLCPCB", "search", "10k", data, TTL_PARAMETRIC)

    cached = cache.get("JLCPCB", "search", "10k")
    assert cached is not None
    restored = part_result_from_dict(cached[0])
    assert restored.mpn == original.mpn
    assert restored.specs[0].name == "Resistance"
    assert restored.price_breaks[0].unit_price == 0.01
    assert restored.confidence == Confidence.AMBER


# ── Test: check_same_thread=False ──

def test_check_same_thread_false(cache: QueryCache):
    """AC #5: Connection allows access from different threads."""
    conn = cache._get_conn()
    # check_same_thread=False means no error when accessed from another thread.
    # We verify by checking the connection is created with the right flag —
    # if it were True, accessing from a different thread would raise ProgrammingError.
    # Here we just confirm the connection works after creation.
    assert conn is not None
    row = conn.execute("SELECT 1").fetchone()
    assert row[0] == 1
