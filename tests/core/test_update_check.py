"""Tests for core/update_check.py — version check, caching, comparison."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from kipart_search.core.update_check import (
    UpdateInfo,
    _compare_versions,
    check_for_update,
    load_cached_update,
    save_update_cache,
    should_check,
)


# ── _compare_versions ────────────────────────────────────────────


class TestCompareVersions:
    def test_newer(self):
        assert _compare_versions("0.1.0", "0.2.0") is True

    def test_same(self):
        assert _compare_versions("0.2.0", "0.2.0") is False

    def test_older(self):
        assert _compare_versions("0.3.0", "0.2.0") is False

    def test_newer_patch(self):
        assert _compare_versions("0.1.0", "0.1.1") is True

    def test_newer_major(self):
        assert _compare_versions("0.9.9", "1.0.0") is True

    def test_prerelease_stripped(self):
        # "0.2.0b1" → parsed as (0, 2, 0) — pre-release suffix ignored
        assert _compare_versions("0.1.0", "0.2.0b1") is True

    def test_same_with_prerelease(self):
        assert _compare_versions("0.2.0", "0.2.0a1") is False


# ── should_check ─────────────────────────────────────────────────


class TestShouldCheck:
    def test_no_cache_file(self, tmp_path):
        cfg = tmp_path / "config.json"
        assert should_check(cfg) is True

    def test_fresh_cache(self, tmp_path):
        cfg = tmp_path / "config.json"
        info = UpdateInfo("0.2.0", "https://example.com", "", time.time())
        save_update_cache(cfg, info)
        assert should_check(cfg) is False

    def test_expired_cache(self, tmp_path):
        cfg = tmp_path / "config.json"
        old_time = time.time() - (25 * 3600)  # 25 hours ago
        info = UpdateInfo("0.2.0", "https://example.com", "", old_time)
        save_update_cache(cfg, info)
        assert should_check(cfg) is True

    def test_custom_ttl(self, tmp_path):
        cfg = tmp_path / "config.json"
        recent = time.time() - (2 * 3600)  # 2 hours ago
        info = UpdateInfo("0.2.0", "https://example.com", "", recent)
        save_update_cache(cfg, info)
        assert should_check(cfg, ttl_hours=1) is True
        assert should_check(cfg, ttl_hours=4) is False


# ── load / save cache round-trip ─────────────────────────────────


class TestCacheRoundTrip:
    def test_round_trip(self, tmp_path):
        cfg = tmp_path / "config.json"
        original = UpdateInfo("0.3.0", "https://example.com/release", "notes", 1234567890.0)
        save_update_cache(cfg, original)
        loaded = load_cached_update(cfg)
        assert loaded is not None
        assert loaded.latest_version == "0.3.0"
        assert loaded.release_url == "https://example.com/release"
        assert loaded.release_notes == "notes"
        assert loaded.check_time == 1234567890.0

    def test_missing_file(self, tmp_path):
        cfg = tmp_path / "config.json"
        assert load_cached_update(cfg) is None

    def test_corrupted_json(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text("not valid json {{{", encoding="utf-8")
        assert load_cached_update(cfg) is None

    def test_missing_update_check_key(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text('{"welcome_version": "0.1"}', encoding="utf-8")
        assert load_cached_update(cfg) is None

    def test_preserves_other_config_keys(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text('{"welcome_version": "0.1", "sources": {}}', encoding="utf-8")
        info = UpdateInfo("0.2.0", "https://example.com", "", time.time())
        save_update_cache(cfg, info)
        raw = json.loads(cfg.read_text(encoding="utf-8"))
        assert raw["welcome_version"] == "0.1"
        assert raw["sources"] == {}
        assert "update_check" in raw


# ── check_for_update (mocked httpx) ─────────────────────────────


class TestCheckForUpdate:
    def _mock_response(self, tag="v0.2.0", url="https://github.com/r", body="notes"):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "tag_name": tag,
            "html_url": url,
            "body": body,
        }
        return resp

    @patch("kipart_search.core.update_check.httpx.get")
    def test_newer_version_available(self, mock_get):
        mock_get.return_value = self._mock_response(tag="v0.2.0")
        result = check_for_update("0.1.0")
        assert result is not None
        assert result.latest_version == "0.2.0"
        assert result.release_url == "https://github.com/r"

    @patch("kipart_search.core.update_check.httpx.get")
    def test_same_version(self, mock_get):
        mock_get.return_value = self._mock_response(tag="v0.1.0")
        result = check_for_update("0.1.0")
        assert result is None

    @patch("kipart_search.core.update_check.httpx.get")
    def test_timeout(self, mock_get):
        import httpx as httpx_mod
        mock_get.side_effect = httpx_mod.TimeoutException("timeout")
        result = check_for_update("0.1.0")
        assert result is None

    @patch("kipart_search.core.update_check.httpx.get")
    def test_http_error_403(self, mock_get):
        import httpx as httpx_mod
        mock_get.side_effect = httpx_mod.HTTPStatusError(
            "rate limited",
            request=MagicMock(),
            response=MagicMock(status_code=403),
        )
        result = check_for_update("0.1.0")
        assert result is None

    @patch("kipart_search.core.update_check.httpx.get")
    def test_no_releases_404(self, mock_get):
        import httpx as httpx_mod
        mock_get.side_effect = httpx_mod.HTTPStatusError(
            "not found",
            request=MagicMock(),
            response=MagicMock(status_code=404),
        )
        result = check_for_update("0.1.0")
        assert result is None
