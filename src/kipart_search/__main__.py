"""Entry point: python -m kipart_search"""

import sys


def main():
    from kipart_search.gui.main_window import run_app
    return run_app()


if __name__ == "__main__":
    sys.exit(main())
