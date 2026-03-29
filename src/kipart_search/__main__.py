"""Entry point: python -m kipart_search"""

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
    update_failed = "--update-failed" in sys.argv
    from kipart_search.gui.main_window import run_app
    return run_app(update_failed=update_failed)


if __name__ == "__main__":
    sys.exit(main())
