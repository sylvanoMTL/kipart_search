"""Tests for core/license.py — License class, feature registry, and gating."""

from __future__ import annotations

import pytest

from kipart_search.core.license import (
    ALL_FEATURES,
    FREE_FEATURES,
    PRO_FEATURES,
    FeatureNotAvailable,
    License,
    _machine_id,
    _sign_token,
    _verify_token,
)


# Note: License singleton is reset by conftest.py _reset_license_singleton fixture


# ── Feature registry ──────────────────────────────────────────────

class TestFeatureRegistry:
    def test_free_and_pro_are_disjoint(self):
        assert FREE_FEATURES & PRO_FEATURES == frozenset()

    def test_all_features_is_union(self):
        assert ALL_FEATURES == FREE_FEATURES | PRO_FEATURES

    def test_known_free_features(self):
        for f in ["jlcpcb_search", "kicad_scan", "basic_verification",
                   "single_assign", "csv_export", "kicad_highlight"]:
            assert f in FREE_FEATURES

    def test_known_pro_features(self):
        for f in ["multi_distributor_search", "cm_export", "excel_export",
                   "full_verification", "batch_writeback"]:
            assert f in PRO_FEATURES


# ── FeatureNotAvailable exception ─────────────────────────────────

class TestFeatureNotAvailable:
    def test_message(self):
        exc = FeatureNotAvailable("pro")
        assert "pro" in str(exc)
        assert exc.tier == "pro"


# ── License singleton ─────────────────────────────────────────────

class TestLicense:
    def test_singleton(self):
        a = License.instance()
        b = License.instance()
        assert a is b

    def test_default_free_tier(self):
        lic = License.instance()
        assert lic.tier == "free"
        assert not lic.is_pro

    def test_has_free_features(self):
        lic = License.instance()
        for f in FREE_FEATURES:
            assert lic.has(f)

    def test_lacks_pro_features_when_free(self):
        lic = License.instance()
        for f in PRO_FEATURES:
            assert not lic.has(f)

    def test_has_unknown_feature_returns_false(self):
        lic = License.instance()
        assert not lic.has("nonexistent_feature")

    def test_require_free_feature_does_not_raise(self):
        lic = License.instance()
        lic.require("jlcpcb_search")  # should not raise

    def test_require_pro_feature_raises_when_free(self):
        lic = License.instance()
        with pytest.raises(FeatureNotAvailable) as exc_info:
            lic.require("cm_export")
        assert exc_info.value.tier == "pro"

    def test_callback_on_activation(self, monkeypatch):
        """license_changed callback fires when tier changes."""
        lic = License.instance()
        calls = []
        lic.on_change(lambda: calls.append("changed"))

        # Mock online validation to succeed
        monkeypatch.setattr(
            License, "_validate_online",
            staticmethod(lambda key: (True, "OK")),
        )
        # Mock keyring
        monkeypatch.setattr("kipart_search.core.license._keyring_set", lambda *a: None)

        ok, _ = lic.activate("test-key")
        assert ok
        assert lic.is_pro
        assert calls == ["changed"]

    def test_callback_on_deactivation(self, monkeypatch):
        lic = License.instance()
        calls = []
        lic.on_change(lambda: calls.append("changed"))

        # Force pro first
        monkeypatch.setattr(
            License, "_validate_online",
            staticmethod(lambda key: (True, "OK")),
        )
        monkeypatch.setattr("kipart_search.core.license._keyring_set", lambda *a: None)
        monkeypatch.setattr("kipart_search.core.license._keyring_delete", lambda *a: None)

        lic.activate("test-key")
        calls.clear()

        lic.deactivate()
        assert lic.tier == "free"
        assert calls == ["changed"]

    def test_activate_empty_key(self):
        lic = License.instance()
        ok, msg = lic.activate("   ")
        assert not ok
        assert "empty" in msg.lower()

    def test_pro_tier_has_all_features(self, monkeypatch):
        """When Pro is active, all features are available."""
        lic = License.instance()
        monkeypatch.setattr(
            License, "_validate_online",
            staticmethod(lambda key: (True, "OK")),
        )
        monkeypatch.setattr("kipart_search.core.license._keyring_set", lambda *a: None)

        lic.activate("test-key")
        for f in ALL_FEATURES:
            assert lic.has(f), f"Pro tier should have {f}"

    def test_require_does_not_raise_when_pro(self, monkeypatch):
        lic = License.instance()
        monkeypatch.setattr(
            License, "_validate_online",
            staticmethod(lambda key: (True, "OK")),
        )
        monkeypatch.setattr("kipart_search.core.license._keyring_set", lambda *a: None)

        lic.activate("test-key")
        for f in PRO_FEATURES:
            lic.require(f)  # should not raise


# ── JWT token helpers ─────────────────────────────────────────────

class TestJWT:
    def test_sign_and_verify_roundtrip(self):
        payload = {"tier": "pro", "machine_id": "abc123"}
        token = _sign_token(payload)
        result = _verify_token(token)
        assert result == payload

    def test_tampered_token_fails(self):
        payload = {"tier": "pro"}
        token = _sign_token(payload)
        tampered = token[:-3] + "xxx"
        assert _verify_token(tampered) is None

    def test_invalid_format_fails(self):
        assert _verify_token("not-a-token") is None
        assert _verify_token("") is None

    def test_machine_id_stable(self):
        assert _machine_id() == _machine_id()


# ── Activation with mocked API ────────────────────────────────────

class TestActivationFlow:
    def test_successful_activation_stores_jwt(self, monkeypatch):
        stored = {}

        def mock_set(username, value):
            stored[username] = value

        monkeypatch.setattr("kipart_search.core.license._keyring_set", mock_set)
        monkeypatch.setattr(
            License, "_validate_online",
            staticmethod(lambda key: (True, "OK")),
        )

        lic = License.instance()
        ok, msg = lic.activate("valid-key")
        assert ok
        assert "license-key" in stored
        assert "license-jwt" in stored
        # JWT should be verifiable
        payload = _verify_token(stored["license-jwt"])
        assert payload is not None
        assert payload["tier"] == "pro"

    def test_failed_activation_stays_free(self, monkeypatch):
        monkeypatch.setattr(
            License, "_validate_online",
            staticmethod(lambda key: (False, "Invalid")),
        )

        lic = License.instance()
        ok, msg = lic.activate("bad-key")
        assert not ok
        assert lic.tier == "free"

    def test_offline_jwt_restores_pro(self, monkeypatch):
        """Cached JWT restores Pro tier on startup."""
        # Create a valid JWT token
        from kipart_search.core.license import _sign_token, _machine_id
        payload = {
            "tier": "pro",
            "validated_at": 1234567890,
            "machine_id": _machine_id(),
        }
        token = _sign_token(payload)

        monkeypatch.setattr(
            "kipart_search.core.license._keyring_get",
            lambda username: token if username == "license-jwt" else None,
        )

        lic = License.instance()
        assert lic.tier == "pro"
        assert lic.is_pro

    def test_env_var_override(self, monkeypatch):
        monkeypatch.setenv("KIPART_LICENSE_KEY", "env-key")
        monkeypatch.setattr("kipart_search.core.license._keyring_get", lambda *a: None)

        lic = License.instance()
        assert lic.tier == "pro"

    def test_jwt_wrong_machine_stays_free(self, monkeypatch):
        """JWT from different machine doesn't grant Pro."""
        payload = {
            "tier": "pro",
            "validated_at": 1234567890,
            "machine_id": "wrong-machine-id",
        }
        token = _sign_token(payload)

        monkeypatch.setattr(
            "kipart_search.core.license._keyring_get",
            lambda username: token if username == "license-jwt" else None,
        )

        lic = License.instance()
        assert lic.tier == "free"


# ── Feature gates don't block free-tier ───────────────────────────

class TestFreeOperations:
    def test_free_features_always_available(self):
        lic = License.instance()
        assert lic.tier == "free"
        for f in FREE_FEATURES:
            assert lic.has(f)
            lic.require(f)  # must not raise


# ── Feature gate integration tests ───────────────────────────────

class TestSearchOrchestratorGating:
    """Test that SearchOrchestrator respects license tier."""

    def test_free_tier_filters_to_local_sources(self):
        from kipart_search.core.search import SearchOrchestrator
        from kipart_search.core.sources import DataSource

        class LocalSource(DataSource):
            name = "Local"

            @property
            def is_local(self) -> bool:
                return True

            def search(self, query, filters=None, limit=50):
                from kipart_search.core.models import PartResult, Confidence
                return [PartResult(
                    mpn="LOCAL-1", manufacturer="Mfr", description="Part",
                    package="0805", category="Resistors", source="Local",
                    source_part_id="L1", source_url="",
                    confidence=Confidence.AMBER,
                )]

            def get_part(self, mpn, manufacturer=""):
                return None

            def is_configured(self):
                return True

        class APISource(DataSource):
            name = "API"

            @property
            def is_local(self) -> bool:
                return False

            def search(self, query, filters=None, limit=50):
                from kipart_search.core.models import PartResult, Confidence
                return [PartResult(
                    mpn="API-1", manufacturer="Mfr", description="Part",
                    package="0805", category="Resistors", source="API",
                    source_part_id="A1", source_url="",
                    confidence=Confidence.AMBER,
                )]

            def get_part(self, mpn, manufacturer=""):
                return None

            def is_configured(self):
                return True

        orch = SearchOrchestrator()
        orch.add_source(LocalSource())
        orch.add_source(APISource())

        # Free tier — only local source should be queried
        results = orch.search("test")
        mpns = [r.mpn for r in results]
        assert "LOCAL-1" in mpns
        assert "API-1" not in mpns

    def test_pro_tier_includes_all_sources(self, pro_license):
        from kipart_search.core.search import SearchOrchestrator
        from kipart_search.core.sources import DataSource

        class LocalSource(DataSource):
            name = "Local"

            @property
            def is_local(self) -> bool:
                return True

            def search(self, query, filters=None, limit=50):
                from kipart_search.core.models import PartResult, Confidence
                return [PartResult(
                    mpn="LOCAL-1", manufacturer="Mfr", description="Part",
                    package="0805", category="Resistors", source="Local",
                    source_part_id="L1", source_url="",
                    confidence=Confidence.AMBER,
                )]

            def get_part(self, mpn, manufacturer=""):
                return None

            def is_configured(self):
                return True

        class APISource(DataSource):
            name = "API"

            @property
            def is_local(self) -> bool:
                return False

            def search(self, query, filters=None, limit=50):
                from kipart_search.core.models import PartResult, Confidence
                return [PartResult(
                    mpn="API-1", manufacturer="Mfr", description="Part",
                    package="0805", category="Resistors", source="API",
                    source_part_id="A1", source_url="",
                    confidence=Confidence.AMBER,
                )]

            def get_part(self, mpn, manufacturer=""):
                return None

            def is_configured(self):
                return True

        orch = SearchOrchestrator()
        orch.add_source(LocalSource())
        orch.add_source(APISource())

        results = orch.search("test")
        mpns = [r.mpn for r in results]
        assert "LOCAL-1" in mpns
        assert "API-1" in mpns


class TestBOMExportGating:
    """Test that BOM export respects license tier."""

    def test_csv_export_free_tier(self, tmp_path):
        from kipart_search.core.bom_export import JLCPCB_TEMPLATE, export_bom
        from kipart_search.core.models import BoardComponent

        comps = [BoardComponent(
            reference="R1", value="10k",
            footprint="Resistor_SMD:R_0805_2012Metric",
            mpn="RC0805", extra_fields={},
        )]
        out = tmp_path / "free.csv"
        # JLCPCB CSV should work on free tier
        export_bom(comps, JLCPCB_TEMPLATE, out)
        assert out.exists()

    def test_excel_export_blocked_free_tier(self, tmp_path):
        from kipart_search.core.bom_export import PCBWAY_TEMPLATE, export_bom
        from kipart_search.core.models import BoardComponent

        comps = [BoardComponent(
            reference="R1", value="10k",
            footprint="Resistor_SMD:R_0805_2012Metric",
            mpn="RC0805", extra_fields={},
        )]
        out = tmp_path / "blocked.xlsx"
        with pytest.raises(FeatureNotAvailable):
            export_bom(comps, PCBWAY_TEMPLATE, out)

    def test_cm_template_blocked_free_tier(self, tmp_path):
        from kipart_search.core.bom_export import NEWBURY_TEMPLATE, BOMTemplate, export_bom
        from kipart_search.core.models import BoardComponent
        from dataclasses import replace

        comps = [BoardComponent(
            reference="R1", value="10k",
            footprint="Resistor_SMD:R_0805_2012Metric",
            mpn="RC0805", extra_fields={},
        )]
        # Newbury as CSV still requires cm_export
        csv_newbury = replace(NEWBURY_TEMPLATE, file_format="csv")
        out = tmp_path / "blocked.csv"
        with pytest.raises(FeatureNotAvailable):
            export_bom(comps, csv_newbury, out)
