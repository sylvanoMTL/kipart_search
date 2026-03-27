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
    load_skipped_version,
    save_skipped_version,
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


# ── save / load skipped version ──────────────────────────────────


class TestSkippedVersion:
    def test_round_trip(self, tmp_path):
        cfg = tmp_path / "config.json"
        save_skipped_version(cfg, "0.3.0")
        assert load_skipped_version(cfg) == "0.3.0"

    def test_load_missing_file(self, tmp_path):
        cfg = tmp_path / "config.json"
        assert load_skipped_version(cfg) is None

    def test_load_no_skipped_key(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text('{"update_check": {}}', encoding="utf-8")
        assert load_skipped_version(cfg) is None

    def test_preserves_existing_config(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text(
            '{"welcome_version": "0.1", "update_check": {"latest_version": "0.2.0"}}',
            encoding="utf-8",
        )
        save_skipped_version(cfg, "0.2.0")
        raw = json.loads(cfg.read_text(encoding="utf-8"))
        assert raw["welcome_version"] == "0.1"
        assert raw["update_check"]["latest_version"] == "0.2.0"
        assert raw["update_check"]["skipped_version"] == "0.2.0"

    def test_corrupted_json_returns_none(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text("not json {{{", encoding="utf-8")
        assert load_skipped_version(cfg) is None


# ── check_for_update with skipped_version ────────────────────────


class TestCheckForUpdateSkipped:
    def _mock_response(self, tag="v0.2.0", assets=None):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "tag_name": tag,
            "html_url": "https://github.com/r",
            "body": "notes",
            "assets": assets or [],
        }
        return resp

    @patch("kipart_search.core.update_check.httpx.get")
    def test_skipped_returns_none(self, mock_get):
        mock_get.return_value = self._mock_response(tag="v0.2.0")
        result = check_for_update("0.1.0", skipped_version="0.2.0")
        assert result is None

    @patch("kipart_search.core.update_check.httpx.get")
    def test_newer_than_skipped_returns_info(self, mock_get):
        mock_get.return_value = self._mock_response(tag="v0.3.0")
        result = check_for_update("0.1.0", skipped_version="0.2.0")
        assert result is not None
        assert result.latest_version == "0.3.0"

    @patch("kipart_search.core.update_check.httpx.get")
    def test_no_skipped_version_still_works(self, mock_get):
        mock_get.return_value = self._mock_response(tag="v0.2.0")
        result = check_for_update("0.1.0", skipped_version=None)
        assert result is not None


# ── asset URL resolution ─────────────────────────────────────────


class TestAssetResolution:
    def _mock_response_with_assets(self, assets):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "tag_name": "v0.2.0",
            "html_url": "https://github.com/r",
            "body": "notes",
            "assets": assets,
        }
        return resp

    @patch("kipart_search.core.update_check.sys")
    @patch("kipart_search.core.update_check.httpx.get")
    def test_selects_setup_exe_on_windows(self, mock_get, mock_sys):
        mock_sys.platform = "win32"
        mock_get.return_value = self._mock_response_with_assets([
            {
                "name": "kipart-search-0.2.0-windows.zip",
                "browser_download_url": "https://github.com/zip",
                "size": 43210000,
            },
            {
                "name": "kipart-search-0.2.0-setup.exe",
                "browser_download_url": "https://github.com/setup",
                "size": 45678912,
            },
        ])
        result = check_for_update("0.1.0")
        assert result is not None
        assert result.asset_url == "https://github.com/setup"
        assert result.asset_size == 45678912

    @patch("kipart_search.core.update_check.sys")
    @patch("kipart_search.core.update_check.httpx.get")
    def test_no_matching_asset(self, mock_get, mock_sys):
        mock_sys.platform = "win32"
        mock_get.return_value = self._mock_response_with_assets([
            {
                "name": "kipart-search-0.2.0-source.tar.gz",
                "browser_download_url": "https://github.com/tarball",
                "size": 1000,
            },
        ])
        result = check_for_update("0.1.0")
        assert result is not None
        assert result.asset_url == ""
        assert result.asset_size == 0

    @patch("kipart_search.core.update_check.httpx.get")
    def test_no_assets_array(self, mock_get):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "tag_name": "v0.2.0",
            "html_url": "https://github.com/r",
            "body": "notes",
        }
        mock_get.return_value = resp
        result = check_for_update("0.1.0")
        assert result is not None
        assert result.asset_url == ""
        assert result.asset_size == 0


# ── backward compatibility ───────────────────────────────────────


class TestBackwardCompatibility:
    def test_cached_without_asset_fields(self, tmp_path):
        """Cache from Story 8.5 (no asset_url/asset_size) loads gracefully."""
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({
            "update_check": {
                "latest_version": "0.2.0",
                "release_url": "https://github.com/r",
                "release_notes": "notes",
                "check_time": 1234567890.0,
            }
        }), encoding="utf-8")
        loaded = load_cached_update(cfg)
        assert loaded is not None
        assert loaded.latest_version == "0.2.0"
        assert loaded.asset_url == ""
        assert loaded.asset_size == 0

    def test_round_trip_with_asset_fields(self, tmp_path):
        cfg = tmp_path / "config.json"
        info = UpdateInfo(
            "0.2.0", "https://github.com/r", "notes", 1234567890.0,
            asset_url="https://github.com/setup", asset_size=45678912,
        )
        save_update_cache(cfg, info)
        loaded = load_cached_update(cfg)
        assert loaded is not None
        assert loaded.asset_url == "https://github.com/setup"
        assert loaded.asset_size == 45678912
