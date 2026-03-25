"""Source configuration model and credential persistence.

Manages enabled/disabled state, default source, and secure API key
storage via keyring with environment variable overrides.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


# ── Source registry ──────────────────────────────────────────────
# Static list of all known sources with metadata.

SOURCE_REGISTRY: list[dict] = [
    {
        "name": "JLCPCB",
        "needs_key": False,
        "key_fields": [],
        "env_var_names": {},
        "is_local": True,
    },
    {
        "name": "DigiKey",
        "needs_key": True,
        "key_fields": ["client_id", "client_secret"],
        "env_var_names": {
            "client_id": "KIPART_DIGIKEY_CLIENT_ID",
            "client_secret": "KIPART_DIGIKEY_CLIENT_SECRET",
        },
        "is_local": False,
    },
    {
        "name": "Mouser",
        "needs_key": True,
        "key_fields": ["api_key"],
        "env_var_names": {
            "api_key": "KIPART_MOUSER_API_KEY",
        },
        "is_local": False,
    },
    {
        "name": "Octopart",
        "needs_key": True,
        "key_fields": ["client_id", "client_secret"],
        "env_var_names": {
            "client_id": "KIPART_NEXAR_CLIENT_ID",
            "client_secret": "KIPART_NEXAR_CLIENT_SECRET",
        },
        "is_local": False,
    },
]


@dataclass
class SourceConfig:
    """Configuration state for a single data source."""

    source_name: str
    enabled: bool = False
    status: str = "key_missing"  # configured | key_missing | key_invalid | not_downloaded
    is_default: bool = False


# ── Config manager ───────────────────────────────────────────────

_KEYRING_SERVICE = "kipart-search"


def _config_dir() -> Path:
    """Return the config directory, creating it if needed."""
    from kipart_search.core.paths import data_dir
    return data_dir()


def _config_path() -> Path:
    from kipart_search.core.paths import config_path
    return config_path()


class SourceConfigManager:
    """Read/write source configuration and credentials.

    Non-secret settings (enabled, is_default) go to config.json.
    API keys are stored in the OS keyring via the `keyring` library,
    with environment variable overrides checked first.
    """

    def __init__(self, config_path: Path | None = None):
        self._config_path = config_path or _config_path()

    # ── Welcome version tracking ────────────────────────────────

    @staticmethod
    def current_major_minor() -> str:
        """Return current app version as 'major.minor' string.

        Handles PEP 440 versions: '0.1.0', '0.1.0b1', '0.2a1', '1.0.0.dev3'.
        Strips pre-release/dev suffixes from the minor segment.
        """
        import re
        from kipart_search import __version__
        parts = __version__.split(".")
        if len(parts) < 2:
            return __version__
        major = parts[0]
        # Strip any pre-release suffix (a1, b2, rc1, dev3) from minor
        minor = re.match(r"(\d+)", parts[1])
        return f"{major}.{minor.group(1)}" if minor else f"{major}.{parts[1]}"

    def get_welcome_version(self) -> str | None:
        """Return the version string when welcome was last shown, or None."""
        if not self._config_path.exists():
            return None
        try:
            raw = json.loads(self._config_path.read_text(encoding="utf-8"))
            return raw.get("welcome_version")
        except (json.JSONDecodeError, OSError):
            return None

    def set_welcome_version(self, version: str) -> None:
        """Persist the welcome_version string without overwriting other settings."""
        raw: dict = {}
        if self._config_path.exists():
            try:
                raw = json.loads(self._config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                raw = {}
        raw["welcome_version"] = version
        # Remove legacy boolean flag if present
        raw.pop("welcome_shown", None)
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    def clear_welcome_version(self) -> None:
        """Remove welcome_version to force re-show on next launch."""
        raw: dict = {}
        if self._config_path.exists():
            try:
                raw = json.loads(self._config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                raw = {}
        raw.pop("welcome_version", None)
        raw.pop("welcome_shown", None)
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    def get_welcome_shown(self) -> bool:
        """Legacy compat: returns True only if welcome_version matches current major.minor."""
        saved = self.get_welcome_version()
        if saved is None:
            return False
        return saved == self.current_major_minor()

    def set_welcome_shown(self, value: bool) -> None:
        """Legacy compat: sets welcome_version to current major.minor if True."""
        if value:
            self.set_welcome_version(self.current_major_minor())
        else:
            self.clear_welcome_version()

    # ── Credentials ──────────────────────────────────────────────

    def get_credential(self, source_name: str, field_name: str) -> str | None:
        """Get a credential value. Checks env var first, then keyring."""
        # Find the env var name from registry
        entry = self._registry_entry(source_name)
        if entry:
            env_var = entry["env_var_names"].get(field_name)
            if env_var:
                value = os.environ.get(env_var)
                if value:
                    return value

        # Fall back to keyring
        try:
            import keyring

            key = f"{source_name}_{field_name}"
            return keyring.get_password(_KEYRING_SERVICE, key)
        except Exception:
            log.debug("keyring lookup failed for %s/%s", source_name, field_name)
            return None

    def set_credential(self, source_name: str, field_name: str, value: str) -> None:
        """Store a credential in the OS keyring."""
        try:
            import keyring

            key = f"{source_name}_{field_name}"
            keyring.set_password(_KEYRING_SERVICE, key, value)
        except Exception:
            log.warning("Failed to store credential %s/%s in keyring", source_name, field_name)
            raise

    def delete_credential(self, source_name: str, field_name: str) -> None:
        """Remove a credential from the OS keyring."""
        try:
            import keyring

            key = f"{source_name}_{field_name}"
            keyring.delete_password(_KEYRING_SERVICE, key)
        except Exception:
            log.debug("keyring delete failed for %s/%s", source_name, field_name)

    # ── Config persistence ───────────────────────────────────────

    def get_all_configs(self) -> list[SourceConfig]:
        """Return config for every known source, merged with saved state."""
        saved = self._load_saved()
        configs: list[SourceConfig] = []
        for entry in SOURCE_REGISTRY:
            name = entry["name"]
            saved_entry = saved.get(name, {})
            enabled = saved_entry.get("enabled", name == "JLCPCB")
            is_default = saved_entry.get("is_default", False)
            status = self.compute_status(entry, enabled)
            configs.append(SourceConfig(
                source_name=name,
                enabled=enabled,
                status=status,
                is_default=is_default,
            ))
        return configs

    def save_configs(self, configs: list[SourceConfig]) -> None:
        """Persist enabled/default state to config.json. Never stores secrets."""
        # Load existing file to preserve non-source keys (e.g. welcome_shown)
        raw: dict = {}
        if self._config_path.exists():
            try:
                raw = json.loads(self._config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                raw = {}
        data: dict[str, dict] = {}
        for cfg in configs:
            data[cfg.source_name] = {
                "enabled": cfg.enabled,
                "is_default": cfg.is_default,
            }
        raw["sources"] = data
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    # ── Helpers ──────────────────────────────────────────────────

    def _load_saved(self) -> dict[str, dict]:
        """Load saved source config from config.json."""
        if not self._config_path.exists():
            return {}
        try:
            raw = json.loads(self._config_path.read_text(encoding="utf-8"))
            return raw.get("sources", {})
        except (json.JSONDecodeError, OSError):
            log.warning("Failed to read config.json, using defaults")
            return {}

    def compute_status(self, entry: dict, enabled: bool) -> str:
        """Compute current status for a source."""
        if entry["is_local"]:
            # JLCPCB: check if database is downloaded
            from kipart_search.core.sources import JLCPCBSource

            db_path = JLCPCBSource.default_db_path()
            if db_path.exists():
                return "configured"
            return "not_downloaded"

        if not entry["needs_key"]:
            return "configured"

        # API source: check if all key_fields have values
        for kf in entry["key_fields"]:
            val = self.get_credential(entry["name"], kf)
            if not val:
                return "key_missing"
        return "configured"

    @staticmethod
    def _registry_entry(source_name: str) -> dict | None:
        """Find a source entry in the registry by name."""
        for entry in SOURCE_REGISTRY:
            if entry["name"] == source_name:
                return entry
        return None

    @staticmethod
    def get_registry_entry(source_name: str) -> dict | None:
        """Public access to registry entry lookup."""
        return SourceConfigManager._registry_entry(source_name)
