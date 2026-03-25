"""Tests for core.paths — centralised path resolution and legacy migration."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import kipart_search.core.paths as paths_mod


# ---------------------------------------------------------------------------
# Task 1: path resolution functions
# ---------------------------------------------------------------------------

class TestDataDir:
    """data_dir() returns platform-correct path and creates it."""

    def test_returns_path_object(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "kipart_search.core.paths.platformdirs.user_data_dir",
            lambda name, appauthor: str(tmp_path / "KiPartSearch"),
        )
        from kipart_search.core.paths import data_dir
        result = data_dir()
        assert isinstance(result, Path)

    def test_creates_directory(self, monkeypatch, tmp_path):
        target = tmp_path / "KiPartSearch"
        monkeypatch.setattr(
            "kipart_search.core.paths.platformdirs.user_data_dir",
            lambda name, appauthor: str(target),
        )
        from kipart_search.core.paths import data_dir
        result = data_dir()
        assert result.is_dir()

    def test_windows_uses_localappdata(self, monkeypatch):
        """On Windows, platformdirs.user_data_dir returns LOCALAPPDATA path."""
        if sys.platform != "win32":
            pytest.skip("Windows-only test")
        import platformdirs
        result = platformdirs.user_data_dir("KiPartSearch", appauthor=False)
        assert "AppData" in result and "Local" in result


class TestSubdirFunctions:
    """config_path, cache_path, jlcpcb_dir, backups_dir, templates_dir."""

    def test_config_path_ends_with_config_json(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "kipart_search.core.paths.platformdirs.user_data_dir",
            lambda name, appauthor: str(tmp_path / "KiPartSearch"),
        )
        from kipart_search.core.paths import config_path
        assert config_path().name == "config.json"

    def test_cache_path_ends_with_cache_db(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "kipart_search.core.paths.platformdirs.user_data_dir",
            lambda name, appauthor: str(tmp_path / "KiPartSearch"),
        )
        from kipart_search.core.paths import cache_path
        assert cache_path().name == "cache.db"

    def test_jlcpcb_dir_creates_subdirectory(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "kipart_search.core.paths.platformdirs.user_data_dir",
            lambda name, appauthor: str(tmp_path / "KiPartSearch"),
        )
        from kipart_search.core.paths import jlcpcb_dir
        result = jlcpcb_dir()
        assert result.is_dir()
        assert result.name == "jlcpcb"

    def test_backups_dir_creates_subdirectory(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "kipart_search.core.paths.platformdirs.user_data_dir",
            lambda name, appauthor: str(tmp_path / "KiPartSearch"),
        )
        from kipart_search.core.paths import backups_dir
        result = backups_dir()
        assert result.is_dir()
        assert result.name == "backups"

    def test_templates_dir_creates_subdirectory(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "kipart_search.core.paths.platformdirs.user_data_dir",
            lambda name, appauthor: str(tmp_path / "KiPartSearch"),
        )
        from kipart_search.core.paths import templates_dir
        result = templates_dir()
        assert result.is_dir()
        assert result.name == "templates"


# ---------------------------------------------------------------------------
# Task 2: migrate_legacy_data
# ---------------------------------------------------------------------------

@pytest.fixture()
def migration_env(monkeypatch, tmp_path):
    """Set up isolated old + new dirs for migration tests."""
    old_dir = tmp_path / "old_home" / ".kipart-search"
    new_dir = tmp_path / "new_data" / "KiPartSearch"

    monkeypatch.setattr(paths_mod, "_LEGACY_DIR", old_dir)
    monkeypatch.setattr(
        "kipart_search.core.paths.platformdirs.user_data_dir",
        lambda name, appauthor: str(new_dir),
    )
    return old_dir, new_dir


class TestMigrateLegacyData:
    """migrate_legacy_data() copies files from old to new location."""

    def test_no_old_dir_is_noop(self, migration_env):
        """No legacy dir → nothing happens, no error."""
        _old, _new = migration_env
        paths_mod.migrate_legacy_data()
        # new dir should be created by data_dir() but no files in it
        assert not _new.exists() or not any(_new.iterdir())

    def test_migrates_flat_files(self, migration_env):
        old, new = migration_env
        old.mkdir(parents=True)
        (old / "config.json").write_text('{"a":1}')
        (old / "cache.db").write_bytes(b"\x00" * 100)

        paths_mod.migrate_legacy_data()

        assert (new / "config.json").read_text() == '{"a":1}'
        assert (new / "cache.db").stat().st_size == 100
        # Old files should be removed
        assert not (old / "config.json").exists()
        assert not (old / "cache.db").exists()

    def test_migrates_nested_files(self, migration_env):
        old, new = migration_env
        old.mkdir(parents=True)
        jlcpcb = old / "jlcpcb"
        jlcpcb.mkdir()
        (jlcpcb / "parts-fts5.db").write_bytes(b"DB")
        (jlcpcb / "db_meta.json").write_text("{}")

        paths_mod.migrate_legacy_data()

        assert (new / "jlcpcb" / "parts-fts5.db").read_bytes() == b"DB"
        assert (new / "jlcpcb" / "db_meta.json").read_text() == "{}"

    def test_removes_empty_old_dir(self, migration_env):
        old, new = migration_env
        old.mkdir(parents=True)
        (old / "config.json").write_text("{}")

        paths_mod.migrate_legacy_data()

        assert not old.exists()

    def test_skips_if_new_dir_has_content(self, migration_env):
        old, new = migration_env
        old.mkdir(parents=True)
        (old / "config.json").write_text('{"old":true}')
        new.mkdir(parents=True)
        (new / "config.json").write_text('{"new":true}')

        paths_mod.migrate_legacy_data()

        # Old file should be untouched
        assert (old / "config.json").read_text() == '{"old":true}'
        # New file should be untouched
        assert (new / "config.json").read_text() == '{"new":true}'

    def test_partial_failure_preserves_both(self, migration_env, monkeypatch):
        old, new = migration_env
        old.mkdir(parents=True)
        (old / "good.json").write_text("{}")
        (old / "bad.db").write_bytes(b"data")

        original_copy2 = paths_mod.shutil.copy2

        def failing_copy2(src, dst):
            if Path(src).name == "bad.db":
                raise OSError("Disk full")
            return original_copy2(src, dst)

        monkeypatch.setattr(paths_mod.shutil, "copy2", failing_copy2)

        paths_mod.migrate_legacy_data()

        # good.json migrated
        assert (new / "good.json").exists()
        assert not (old / "good.json").exists()
        # bad.db preserved in old location
        assert (old / "bad.db").exists()

    def test_old_dir_preserved_on_partial_migration(self, migration_env, monkeypatch):
        """Old dir not deleted if files remain."""
        old, new = migration_env
        old.mkdir(parents=True)
        (old / "good.json").write_text("{}")
        (old / "bad.db").write_bytes(b"data")

        original_copy2 = paths_mod.shutil.copy2

        def failing_copy2(src, dst):
            if Path(src).name == "bad.db":
                raise OSError("Disk full")
            return original_copy2(src, dst)

        monkeypatch.setattr(paths_mod.shutil, "copy2", failing_copy2)

        paths_mod.migrate_legacy_data()

        assert old.exists()
