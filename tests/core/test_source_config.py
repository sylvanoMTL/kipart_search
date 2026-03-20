"""Tests for source configuration manager (Story 6.1)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kipart_search.core.source_config import (
    SOURCE_REGISTRY,
    SourceConfig,
    SourceConfigManager,
)


# ── SourceConfig dataclass ───────────────────────────────────────


class TestSourceConfig:
    def test_defaults(self):
        cfg = SourceConfig(source_name="Test")
        assert cfg.source_name == "Test"
        assert cfg.enabled is False
        assert cfg.status == "key_missing"
        assert cfg.is_default is False

    def test_custom_values(self):
        cfg = SourceConfig("JLCPCB", enabled=True, status="configured", is_default=True)
        assert cfg.enabled is True
        assert cfg.status == "configured"
        assert cfg.is_default is True


# ── SOURCE_REGISTRY ──────────────────────────────────────────────


class TestSourceRegistry:
    def test_four_sources_defined(self):
        assert len(SOURCE_REGISTRY) == 4

    def test_jlcpcb_no_key_needed(self):
        jlcpcb = [s for s in SOURCE_REGISTRY if s["name"] == "JLCPCB"][0]
        assert jlcpcb["needs_key"] is False
        assert jlcpcb["is_local"] is True
        assert jlcpcb["key_fields"] == []

    def test_digikey_needs_two_keys(self):
        dk = [s for s in SOURCE_REGISTRY if s["name"] == "DigiKey"][0]
        assert dk["needs_key"] is True
        assert dk["key_fields"] == ["client_id", "client_secret"]
        assert "KIPART_DIGIKEY_CLIENT_ID" in dk["env_var_names"].values()

    def test_mouser_needs_one_key(self):
        m = [s for s in SOURCE_REGISTRY if s["name"] == "Mouser"][0]
        assert m["needs_key"] is True
        assert m["key_fields"] == ["api_key"]

    def test_octopart_needs_two_keys(self):
        o = [s for s in SOURCE_REGISTRY if s["name"] == "Octopart"][0]
        assert o["needs_key"] is True
        assert len(o["key_fields"]) == 2


# ── SourceConfigManager — config.json persistence ───────────────


class TestConfigPersistence:
    def test_save_and_load_round_trip(self, tmp_path: Path):
        config_file = tmp_path / "config.json"
        mgr = SourceConfigManager(config_path=config_file)

        configs = [
            SourceConfig("JLCPCB", enabled=True, status="configured", is_default=False),
            SourceConfig("DigiKey", enabled=True, status="configured", is_default=True),
            SourceConfig("Mouser", enabled=False, status="key_missing", is_default=False),
            SourceConfig("Octopart", enabled=False, status="key_missing", is_default=False),
        ]
        mgr.save_configs(configs)

        # Read raw JSON to verify structure
        raw = json.loads(config_file.read_text(encoding="utf-8"))
        assert "sources" in raw
        assert raw["sources"]["JLCPCB"]["enabled"] is True
        assert raw["sources"]["DigiKey"]["is_default"] is True
        assert raw["sources"]["Mouser"]["enabled"] is False

    def test_no_secrets_in_config_json(self, tmp_path: Path):
        config_file = tmp_path / "config.json"
        mgr = SourceConfigManager(config_path=config_file)

        configs = [SourceConfig("DigiKey", enabled=True, status="configured")]
        mgr.save_configs(configs)

        raw = config_file.read_text(encoding="utf-8")
        assert "client_id" not in raw
        assert "client_secret" not in raw
        assert "api_key" not in raw

    def test_load_missing_config_returns_defaults(self, tmp_path: Path):
        config_file = tmp_path / "nonexistent.json"
        mgr = SourceConfigManager(config_path=config_file)
        saved = mgr._load_saved()
        assert saved == {}

    def test_load_corrupt_config_returns_defaults(self, tmp_path: Path):
        config_file = tmp_path / "config.json"
        config_file.write_text("not valid json!!!", encoding="utf-8")
        mgr = SourceConfigManager(config_path=config_file)
        saved = mgr._load_saved()
        assert saved == {}

    def test_get_all_configs_returns_all_sources(self, tmp_path: Path):
        config_file = tmp_path / "config.json"
        mgr = SourceConfigManager(config_path=config_file)
        with patch("kipart_search.core.source_config.SourceConfigManager.get_credential", return_value=None):
            configs = mgr.get_all_configs()
        assert len(configs) == 4
        names = [c.source_name for c in configs]
        assert names == ["JLCPCB", "DigiKey", "Mouser", "Octopart"]

    def test_jlcpcb_enabled_by_default(self, tmp_path: Path):
        config_file = tmp_path / "config.json"
        mgr = SourceConfigManager(config_path=config_file)
        with patch("kipart_search.core.source_config.SourceConfigManager.get_credential", return_value=None):
            configs = mgr.get_all_configs()
        jlcpcb = [c for c in configs if c.source_name == "JLCPCB"][0]
        assert jlcpcb.enabled is True

    def test_saved_configs_are_loaded(self, tmp_path: Path):
        config_file = tmp_path / "config.json"
        mgr = SourceConfigManager(config_path=config_file)

        # Save custom config
        configs = [
            SourceConfig("JLCPCB", enabled=False),
            SourceConfig("DigiKey", enabled=True, is_default=True),
            SourceConfig("Mouser", enabled=False),
            SourceConfig("Octopart", enabled=False),
        ]
        mgr.save_configs(configs)

        # Reload
        with patch("kipart_search.core.source_config.SourceConfigManager.get_credential", return_value=None):
            loaded = mgr.get_all_configs()
        jlcpcb = [c for c in loaded if c.source_name == "JLCPCB"][0]
        dk = [c for c in loaded if c.source_name == "DigiKey"][0]
        assert jlcpcb.enabled is False
        assert dk.enabled is True
        assert dk.is_default is True


# ── SourceConfigManager — credential management ─────────────────


class TestCredentialManagement:
    def test_env_var_takes_priority(self, tmp_path: Path):
        mgr = SourceConfigManager(config_path=tmp_path / "config.json")
        with patch.dict("os.environ", {"KIPART_DIGIKEY_CLIENT_ID": "env_value_123"}):
            result = mgr.get_credential("DigiKey", "client_id")
        assert result == "env_value_123"

    def test_keyring_fallback_when_no_env(self, tmp_path: Path):
        mgr = SourceConfigManager(config_path=tmp_path / "config.json")
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = "keyring_value"
        with patch.dict("os.environ", {}, clear=False), \
             patch.dict("sys.modules", {"keyring": mock_keyring}):
            # Remove env var if it exists
            import os
            os.environ.pop("KIPART_DIGIKEY_CLIENT_ID", None)
            result = mgr.get_credential("DigiKey", "client_id")
        # Should have tried keyring
        mock_keyring.get_password.assert_called_once_with("kipart-search", "DigiKey_client_id")

    def test_set_credential_calls_keyring(self, tmp_path: Path):
        mgr = SourceConfigManager(config_path=tmp_path / "config.json")
        mock_keyring = MagicMock()
        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            mgr.set_credential("Mouser", "api_key", "secret123")
        mock_keyring.set_password.assert_called_once_with(
            "kipart-search", "Mouser_api_key", "secret123"
        )

    def test_delete_credential_calls_keyring(self, tmp_path: Path):
        mgr = SourceConfigManager(config_path=tmp_path / "config.json")
        mock_keyring = MagicMock()
        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            mgr.delete_credential("Mouser", "api_key")
        mock_keyring.delete_password.assert_called_once_with(
            "kipart-search", "Mouser_api_key"
        )

    def test_get_credential_returns_none_for_unknown_source(self, tmp_path: Path):
        mgr = SourceConfigManager(config_path=tmp_path / "config.json")
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = None
        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            result = mgr.get_credential("Unknown", "key")
        assert result is None

    def test_get_credential_env_empty_string_falls_through(self, tmp_path: Path):
        """Empty env var should fall through to keyring."""
        mgr = SourceConfigManager(config_path=tmp_path / "config.json")
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = "from_keyring"
        with patch.dict("os.environ", {"KIPART_DIGIKEY_CLIENT_ID": ""}), \
             patch.dict("sys.modules", {"keyring": mock_keyring}):
            result = mgr.get_credential("DigiKey", "client_id")
        mock_keyring.get_password.assert_called_once()


# ── SourceConfigManager — status computation ────────────────────


class TestStatusComputation:
    def test_api_source_configured_when_all_keys_present(self, tmp_path: Path):
        mgr = SourceConfigManager(config_path=tmp_path / "config.json")
        entry = [e for e in SOURCE_REGISTRY if e["name"] == "Mouser"][0]
        with patch.object(mgr, "get_credential", return_value="some_value"):
            status = mgr.compute_status(entry, enabled=True)
        assert status == "configured"

    def test_api_source_key_missing_when_no_key(self, tmp_path: Path):
        mgr = SourceConfigManager(config_path=tmp_path / "config.json")
        entry = [e for e in SOURCE_REGISTRY if e["name"] == "Mouser"][0]
        with patch.object(mgr, "get_credential", return_value=None):
            status = mgr.compute_status(entry, enabled=True)
        assert status == "key_missing"

    def test_jlcpcb_not_downloaded(self, tmp_path: Path):
        mgr = SourceConfigManager(config_path=tmp_path / "config.json")
        entry = [e for e in SOURCE_REGISTRY if e["name"] == "JLCPCB"][0]
        with patch("kipart_search.core.sources.JLCPCBSource.default_db_path", return_value=tmp_path / "nonexistent.db"):
            status = mgr.compute_status(entry, enabled=True)
        assert status == "not_downloaded"

    def test_jlcpcb_configured_when_db_exists(self, tmp_path: Path):
        mgr = SourceConfigManager(config_path=tmp_path / "config.json")
        entry = [e for e in SOURCE_REGISTRY if e["name"] == "JLCPCB"][0]
        db_file = tmp_path / "parts-fts5.db"
        db_file.write_bytes(b"fake db")
        with patch("kipart_search.core.sources.JLCPCBSource.default_db_path", return_value=db_file):
            status = mgr.compute_status(entry, enabled=True)
        assert status == "configured"


# ── Registry lookup ──────────────────────────────────────────────


class TestRegistryLookup:
    def test_get_registry_entry_found(self):
        entry = SourceConfigManager.get_registry_entry("DigiKey")
        assert entry is not None
        assert entry["name"] == "DigiKey"

    def test_get_registry_entry_not_found(self):
        entry = SourceConfigManager.get_registry_entry("NonExistent")
        assert entry is None
