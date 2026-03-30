"""Entry point: python -m kipart_search

Replaces: src/kipart_search/__main__.py

CHANGES FROM ORIGINAL (2026-03-30)
====================================

1. REMOVED: --update-failed flag handling (line 52 in original)
   The old .bat shim would relaunch the app with --update-failed if the
   installer failed, triggering _show_update_failed_dialog() in MainWindow.
   With os.startfile(), there is no shim to detect or signal failure.
   If the installer fails, the user simply runs it again manually (the
   downloaded .exe remains in %TEMP%).

2. REMOVED: update_failed parameter from run_app() call (line 54 in original)
   run_app() in main_window.py should also have its update_failed parameter
   removed (or left with default=False, since no caller passes True anymore).

3. Everything else is UNCHANGED.
"""

import sys


def _check_version_flag() -> None:
    """Print version and exit if --version is passed. No GUI, no imports."""
    if "--version" in sys.argv:
        from kipart_search import __version__
        print(f"kipart-search {__version__}")
        sys.exit(0)


def _init_keyring_compiled() -> None:
    """Force Windows keyring backend when running as Nuitka-compiled binary.

    Nuitka does not replicate Python entry points, so keyring fails to
    discover backends via importlib.metadata at runtime.
    """
    if "__compiled__" not in globals() and not getattr(sys, "frozen", False):
        return
    try:
        import keyring
        from keyring.backends.Windows import WinVaultKeyring

        keyring.set_keyring(WinVaultKeyring())
    except ImportError:
        pass  # Non-Windows or keyring not available


def _migrate_data() -> None:
    """Run one-time data migration and ensure config.json exists."""
    from kipart_search.core.paths import migrate_legacy_data, ensure_config
    migrate_legacy_data()
    ensure_config()


def _cleanup_partial_downloads() -> None:
    """Remove stale update .partial files from temp dir. Non-blocking."""
    try:
        from kipart_search.core.update_shim import cleanup_stale_partial_downloads
        cleanup_stale_partial_downloads()
    except Exception:
        pass  # Never block startup


def main():
    _check_version_flag()
    _migrate_data()
    _init_keyring_compiled()
    _cleanup_partial_downloads()
    # NOTE: The --update-failed flag was removed in the os.startfile() update
    # simplification (2026-03-30).  The old .bat shim would relaunch the app
    # with this flag when the installer failed, triggering a special dialog.
    # With os.startfile(), there is no shim to detect or signal failure —
    # if the installer fails, the user simply runs it again manually (the
    # downloaded .exe remains in %TEMP%).
    from kipart_search.gui.main_window import run_app
    return run_app()


if __name__ == "__main__":
    sys.exit(main())
