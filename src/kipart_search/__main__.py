"""Entry point: python -m kipart_search"""

import sys


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


def main():
    _init_keyring_compiled()
    from kipart_search.gui.main_window import run_app
    return run_app()


if __name__ == "__main__":
    sys.exit(main())
