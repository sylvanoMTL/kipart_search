"""Delete a GitHub release, remote tag, and local tag.

Usage:
    python clear_release.py              # deletes v{pyproject.toml version}
    python clear_release.py v0.1.0       # deletes specific tag
    python clear_release.py --yes        # skip confirmation prompt
"""
from __future__ import annotations

import re
import subprocess
import sys

from build_nuitka import read_base_version

TAG_PATTERN = re.compile(r"^v\d+\.\d+\.\d+")


def run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=check)
    if result.stderr.strip() and result.returncode == 0:
        print(f"  {result.stderr.strip()}")
    return result


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--yes"]
    skip_confirm = "--yes" in sys.argv[1:]

    if args:
        tag = args[0]
    else:
        tag = f"v{read_base_version()}"

    if not TAG_PATTERN.match(tag):
        print(f"Error: '{tag}' doesn't look like a version tag (expected vX.Y.Z...)")
        return 1

    print(f"This will delete release, remote tag, and local tag for: {tag}")
    if not skip_confirm:
        answer = input("Proceed? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted.")
            return 0
    print()

    ok = True

    # Step 1: Delete GitHub release
    print("Step 1/3: Delete GitHub release")
    result = run(["gh", "release", "delete", tag, "--yes", "--cleanup-tag"])
    if result.returncode == 0:
        print(f"  Deleted release {tag}")
    else:
        ok = False
        print(f"  No release found (or already deleted): {result.stderr.strip()}")
    print()

    # Step 2: Delete remote tag (in case --cleanup-tag didn't catch it)
    print("Step 2/3: Delete remote tag")
    result = run(["git", "push", "origin", f":refs/tags/{tag}"])
    if result.returncode == 0:
        print(f"  Deleted remote tag {tag}")
    else:
        ok = False
        print(f"  Remote tag not found (or already deleted): {result.stderr.strip()}")
    print()

    # Step 3: Delete local tag
    print("Step 3/3: Delete local tag")
    result = run(["git", "tag", "-d", tag])
    if result.returncode == 0:
        print(f"  Deleted local tag {tag}")
    else:
        ok = False
        print(f"  Local tag not found: {result.stderr.strip()}")
    print()

    if ok:
        print(f"Done. Tag {tag} fully cleared.")
    else:
        print(f"Done with warnings. Some steps failed for {tag} (see above).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
