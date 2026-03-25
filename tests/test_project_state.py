"""Tests for core/project_state.py — per-project verification state persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kipart_search.core.models import UserVerificationStatus
from kipart_search.core.project_state import (
    load_user_statuses,
    project_state_path,
    save_user_statuses,
)


class TestProjectStatePath:
    """Test state path resolution."""

    def test_returns_path_under_kipart_search_dir(self, tmp_path):
        path = project_state_path(tmp_path)
        assert path == tmp_path / ".kipart-search" / "verification-state.json"

    def test_creates_kipart_search_dir(self, tmp_path):
        path = project_state_path(tmp_path)
        assert path.parent.is_dir()


class TestSaveAndLoadUserStatuses:
    """Test round-trip persistence of user verification statuses."""

    def test_save_and_load_round_trip(self, tmp_path):
        statuses = {
            "C12": UserVerificationStatus.VERIFIED,
            "U3": UserVerificationStatus.REJECTED,
            "R7": UserVerificationStatus.ATTENTION,
        }

        save_user_statuses(tmp_path, statuses)
        state_file = tmp_path / ".kipart-search" / "verification-state.json"
        assert state_file.exists()

        loaded = load_user_statuses(tmp_path)
        assert loaded == statuses

    def test_none_statuses_not_saved(self, tmp_path):
        statuses = {
            "C1": UserVerificationStatus.VERIFIED,
            "C2": UserVerificationStatus.NONE,
        }

        save_user_statuses(tmp_path, statuses)

        state_file = tmp_path / ".kipart-search" / "verification-state.json"
        data = json.loads(state_file.read_text())
        assert "C2" not in data["statuses"]
        assert data["statuses"]["C1"] == "verified"

    def test_load_empty_when_no_file(self, tmp_path):
        loaded = load_user_statuses(tmp_path)
        assert loaded == {}

    def test_load_handles_corrupt_json(self, tmp_path):
        state_dir = tmp_path / ".kipart-search"
        state_dir.mkdir()
        (state_dir / "verification-state.json").write_text("not valid json {{{")

        loaded = load_user_statuses(tmp_path)
        assert loaded == {}

    def test_load_skips_unknown_status_values(self, tmp_path):
        state_dir = tmp_path / ".kipart-search"
        state_dir.mkdir()
        (state_dir / "verification-state.json").write_text(json.dumps({
            "format_version": 1,
            "statuses": {
                "C1": "verified",
                "C2": "unknown_future_status",
            },
        }))

        loaded = load_user_statuses(tmp_path)
        assert loaded == {"C1": UserVerificationStatus.VERIFIED}

    def test_format_version_in_saved_file(self, tmp_path):
        save_user_statuses(tmp_path, {"C1": UserVerificationStatus.VERIFIED})

        state_file = tmp_path / ".kipart-search" / "verification-state.json"
        data = json.loads(state_file.read_text())
        assert data["format_version"] == 1
