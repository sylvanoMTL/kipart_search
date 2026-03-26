"""Delete a GitHub release, remote tag, and local tag.

Usage:
    python clear_release.py              # deletes v{pyproject.toml version}
    python clear_release.py v0.1.0       # deletes specific tag
"""
from __future__ import annotations

import subprocess
import sys

from build_nuitka import read_base_version


def run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def main() -> int:
    if len(sys.argv) > 1:
        tag = sys.argv[1]
    else:
        tag = f"v{read_base_version()}"

    print(f"Clearing release for tag: {tag}")
    print()

    # Step 1: Delete GitHub release
    print("Step 1/3: Delete GitHub release")
    result = run(["gh", "release", "delete", tag, "--yes", "--cleanup-tag"])
    if result.returncode == 0:
        print(f"  Deleted release {tag}")
    else:
        print(f"  No release found (or already deleted): {result.stderr.strip()}")
    print()

    # Step 2: Delete remote tag (in case --cleanup-tag didn't catch it)
    print("Step 2/3: Delete remote tag")
    result = run(["git", "push", "origin", f":{tag}"])
    if result.returncode == 0:
        print(f"  Deleted remote tag {tag}")
    else:
        print(f"  Remote tag not found (or already deleted): {result.stderr.strip()}")
    print()

    # Step 3: Delete local tag
    print("Step 3/3: Delete local tag")
    result = run(["git", "tag", "-d", tag])
    if result.returncode == 0:
        print(f"  Deleted local tag {tag}")
    else:
        print(f"  Local tag not found: {result.stderr.strip()}")
    print()

    print(f"Done. Tag {tag} fully cleared.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
