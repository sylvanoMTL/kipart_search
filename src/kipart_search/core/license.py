"""License module — tier validation and feature gating.

One-time license key validated via LemonSqueezy API. Offline fallback
uses HMAC-signed JWT cached in keyring. No expiry checks — one-time fee.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import threading
import time
import uuid

log = logging.getLogger(__name__)


# ── Feature registry ─────────────────────────────────────────────

FREE_FEATURES: frozenset[str] = frozenset({
    "jlcpcb_search",
    "kicad_scan",
    "kicad_highlight",
    "basic_verification",
    "single_assign",
    "csv_export",
})

PRO_FEATURES: frozenset[str] = frozenset({
    "multi_distributor_search",
    "cm_export",
    "excel_export",
    "full_verification",
    "batch_writeback",
})

ALL_FEATURES: frozenset[str] = FREE_FEATURES | PRO_FEATURES


# ── Exception ─────────────────────────────────────────────────────

class FeatureNotAvailable(Exception):
    """Raised when a feature requires a higher license tier."""

    def __init__(self, tier: str):
        super().__init__(f"Feature requires {tier} license")
        self.tier = tier


# ── Offline JWT helpers ───────────────────────────────────────────
# Simple HMAC-SHA256 signed token using stdlib only (no PyJWT).

def _jwt_secret() -> bytes:
    """Derive the HMAC signing key at runtime (XOR-deobfuscated).

    Not DRM — just prevents trivial extraction via ``strings`` on the
    compiled binary.
    """
    # XOR mask applied to b"kipart-search-license-v1-hmac-key"
    _MASK = 0xA7
    _ENC = bytes([
        0xCC, 0xCE, 0xD7, 0xC6, 0xD5, 0xD3, 0x8A, 0xD4, 0xC2, 0xC6,
        0xD5, 0xC4, 0xCF, 0x8A, 0xCB, 0xCE, 0xC4, 0xC2, 0xC9, 0xD4,
        0xC2, 0x8A, 0xD1, 0x96, 0x8A, 0xCF, 0xCA, 0xC6, 0xC4, 0x8A,
        0xCC, 0xC2, 0xDE,
    ])
    return bytes(b ^ _MASK for b in _ENC)


def _machine_id() -> str:
    """Return a stable per-machine identifier."""
    return hashlib.sha256(uuid.getnode().to_bytes(8, "big")).hexdigest()[:16]


def _sign_token(payload: dict) -> str:
    """Create an HMAC-signed base64 token from *payload*."""
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = hmac.new(_jwt_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def _verify_token(token: str) -> dict | None:
    """Verify and decode an HMAC-signed token. Returns payload or None."""
    parts = token.split(".", 1)
    if len(parts) != 2:
        return None
    body, sig = parts
    expected = hmac.new(_jwt_secret(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(body))
    except (json.JSONDecodeError, Exception):
        return None


# ── Keyring helpers ───────────────────────────────────────────────

_KEYRING_SERVICE = "kipart-search"
_KEY_LICENSE = "license-key"
_KEY_JWT = "license-jwt"


def _keyring_get(username: str) -> str | None:
    try:
        import keyring
        return keyring.get_password(_KEYRING_SERVICE, username)
    except Exception:
        log.debug("keyring get failed for %s", username)
        return None


def _keyring_set(username: str, value: str) -> None:
    try:
        import keyring
        keyring.set_password(_KEYRING_SERVICE, username, value)
    except Exception:
        log.warning("keyring set failed for %s", username)


def _keyring_delete(username: str) -> None:
    try:
        import keyring
        keyring.delete_password(_KEYRING_SERVICE, username)
    except Exception:
        log.debug("keyring delete failed for %s", username)


# ── License class ─────────────────────────────────────────────────

class License:
    """Singleton managing license tier and feature access.

    Default tier is ``"free"``. Calling ``activate(key)`` validates the
    key online (LemonSqueezy), caches a signed JWT for offline use,
    and promotes the tier to ``"pro"``.
    """

    _instance: License | None = None

    @classmethod
    def instance(cls) -> License:
        """Return the global License singleton, creating it on first call."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def _reset(cls) -> None:
        """Reset singleton — for testing only."""
        cls._instance = None

    def __init__(self) -> None:
        self._tier: str = "free"
        self._license_key: str | None = None
        self._callbacks: list = []
        self._cb_lock = threading.Lock()
        self._load_cached()

    # ── Tier queries ──────────────────────────────────────────────

    @property
    def tier(self) -> str:
        """Current license tier: ``"free"`` or ``"pro"``."""
        return self._tier

    @property
    def is_pro(self) -> bool:
        return self._tier == "pro"

    @property
    def masked_key(self) -> str:
        """Return the stored key with all but the last 4 characters masked."""
        key = self._license_key
        if not key or len(key) <= 4:
            return key or ""
        return "\u2022" * (len(key) - 4) + key[-4:]

    def has(self, feature: str) -> bool:
        """Return True if *feature* is available in the current tier."""
        if feature in FREE_FEATURES:
            return True
        if feature in PRO_FEATURES:
            return self._tier == "pro"
        # Unknown feature — deny by default
        return False

    def require(self, feature: str) -> None:
        """Raise ``FeatureNotAvailable`` if *feature* is not available."""
        if not self.has(feature):
            raise FeatureNotAvailable("pro")

    # ── Activation ────────────────────────────────────────────────

    def activate(self, key: str, *, _skip_validation: bool = False) -> tuple[bool, str]:
        """Validate *key* online and activate Pro tier.

        When *_skip_validation* is True the online check is skipped —
        used by the GUI when the worker already validated in a background
        thread and activation must happen on the main thread.

        Returns ``(success, message)``.
        """
        key = key.strip()
        if not key:
            return False, "License key cannot be empty"

        if not _skip_validation:
            ok, msg = self._validate_online(key)
            if not ok:
                return False, msg

        self._tier = "pro"
        self._license_key = key
        _keyring_set(_KEY_LICENSE, key)
        self._cache_jwt()
        self._notify()
        return True, "License activated successfully"

    def deactivate(self) -> None:
        """Remove license and revert to free tier."""
        self._tier = "free"
        self._license_key = None
        _keyring_delete(_KEY_LICENSE)
        _keyring_delete(_KEY_JWT)
        self._notify()

    # ── Callbacks ─────────────────────────────────────────────────

    def on_change(self, callback) -> None:
        """Register a callback invoked when the tier changes."""
        with self._cb_lock:
            self._callbacks.append(callback)

    def _notify(self) -> None:
        with self._cb_lock:
            cbs = list(self._callbacks)
        for cb in cbs:
            try:
                cb()
            except Exception:
                log.debug("license_changed callback failed", exc_info=True)

    # ── Online validation ─────────────────────────────────────────

    # Dev-only bypass key — only works in non-compiled (source) builds.
    _DEV_KEY = "dev-pro-unlock"
    # Golden key — works in ALL builds (source + compiled) for testing.
    _GOLDEN_KEY = "kipart-golden-2026"

    @staticmethod
    def _validate_online(key: str) -> tuple[bool, str]:
        """Validate key via LemonSqueezy API.

        Returns ``(success, message)``.
        """
        # Golden key: works in all builds (source + compiled)
        if key == License._GOLDEN_KEY:
            return True, "License activated (golden key)"

        # Dev bypass: accept a magic key when running from source only
        if key == License._DEV_KEY and "__compiled__" not in globals():
            return True, "License activated (dev bypass)"

        try:
            import httpx
        except ImportError:
            return False, "httpx not installed — cannot validate online"

        try:
            resp = httpx.post(
                "https://api.lemonsqueezy.com/v1/licenses/validate",
                json={
                    "license_key": key,
                    "instance_name": _machine_id(),
                },
                timeout=15.0,
            )
            data = resp.json()

            if resp.status_code == 200 and data.get("valid"):
                return True, "License activated successfully"

            # Handle specific error reasons
            error = data.get("error", "")
            if "expired" in str(error).lower():
                return False, "License key has expired"
            if "invalid" in str(error).lower() or not data.get("valid"):
                return False, "Invalid license key"

            return False, f"Validation failed: {error or resp.status_code}"

        except httpx.TimeoutException:
            return False, "Validation timed out — check your internet connection"
        except httpx.ConnectError:
            return False, "Cannot reach license server — check your internet connection"
        except Exception as exc:
            log.debug("Online validation error: %s", exc)
            return False, f"Validation error: {exc}"

    # ── Offline JWT cache ─────────────────────────────────────────

    def _cache_jwt(self) -> None:
        """Create and store an HMAC-signed JWT for offline validation."""
        origin = "production"
        if self._license_key == self._DEV_KEY:
            origin = "dev"
        elif self._license_key == self._GOLDEN_KEY:
            origin = "golden"
        payload = {
            "tier": "pro",
            "validated_at": time.time(),
            "machine_id": _machine_id(),
            "origin": origin,
        }
        token = _sign_token(payload)
        _keyring_set(_KEY_JWT, token)

    def _load_cached(self) -> None:
        """Try to restore Pro tier from env var or cached JWT."""
        # Environment variable override
        env_key = os.environ.get("KIPART_LICENSE_KEY")
        if env_key:
            self._license_key = env_key
            self._tier = "pro"
            log.debug("License activated via KIPART_LICENSE_KEY env var")
            return

        # Stored license key
        stored_key = _keyring_get(_KEY_LICENSE)
        if stored_key:
            self._license_key = stored_key

        # Offline JWT fallback
        token = _keyring_get(_KEY_JWT)
        if token:
            payload = _verify_token(token)
            if payload and payload.get("tier") == "pro":
                # Reject dev-bypass tokens in compiled builds
                origin = payload.get("origin", "production")
                is_compiled = "__compiled__" in globals() or getattr(
                    __import__("sys"), "frozen", False
                )
                if origin == "dev" and is_compiled:
                    log.debug("Dev-bypass JWT rejected in compiled build")
                    _keyring_delete(_KEY_JWT)
                    _keyring_delete(_KEY_LICENSE)
                    self._license_key = None
                    return
                machine = payload.get("machine_id")
                if machine == _machine_id():
                    self._tier = "pro"
                    log.debug("License restored from cached JWT")
                    return
                log.debug("JWT machine_id mismatch — ignoring cached license")
            else:
                log.debug("JWT verification failed — staying on free tier")
