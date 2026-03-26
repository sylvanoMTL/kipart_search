"""Automated release build script for KiPart Search.

Orchestrates the full release pipeline:
  1. Version gate (GitHub API check)
  2. Test suite (pytest)
  3. GPL firewall (pip-licenses)
  4. Nuitka standalone build
  5. ZIP packaging
  6. Inno Setup installer
  7. SHA256 checksums

Usage:
    python release.py                # full local build
    python release.py --tag          # tag + push to trigger CI release
    python release.py --skip-tests --skip-version-gate
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

import httpx

from build_nuitka import (
    build,
    check_licenses,
    compile_installer,
    package,
    read_base_version,
)


GITHUB_REPO = "sylvanoMTL/kipart-search"


def check_version_gate(version: str) -> None:
    """Refuse to build if version matches the latest GitHub release tag."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        resp = httpx.get(url, timeout=10, follow_redirects=True)
        if resp.status_code == 404:
            print("No previous releases found -- version gate passed.")
            return
        resp.raise_for_status()
        latest_tag = resp.json().get("tag_name", "")
        latest_version = latest_tag.lstrip("v")
        if latest_version == version:
            print(f"ERROR: Version {version} matches latest release {latest_tag}.")
            print("Bump version in pyproject.toml before building a release.")
            sys.exit(1)
        print(f"Version gate passed: {version} (latest release: {latest_tag})")
    except httpx.HTTPError as exc:
        print(f"WARNING: Could not check GitHub releases: {exc}")
        print("Proceeding without version gate check.")


def run_tests() -> None:
    """Run the test suite and fail fast on any failure."""
    print("Running test suite...")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-x", "-q"],
    )
    if result.returncode != 0:
        print("ERROR: Test suite failed. Fix tests before building a release.")
        sys.exit(1)
    print("Test suite passed.")


def generate_checksums(output_dir: str, version: str) -> None:
    """Generate SHA256 checksums for all release artifacts."""
    dist = Path(output_dir)
    artifacts = [
        dist / f"kipart-search-{version}-windows.zip",
        dist / f"kipart-search-{version}-setup.exe",
    ]
    checksum_file = dist / f"checksums-{version}-sha256.txt"
    lines = []
    for artifact in artifacts:
        if artifact.exists():
            sha256 = hashlib.sha256(artifact.read_bytes()).hexdigest()
            lines.append(f"{sha256}  {artifact.name}")
            print(f"  {sha256}  {artifact.name}")
    if not lines:
        print("WARNING: No artifacts found for checksum generation.")
        return
    checksum_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Checksums written to {checksum_file}")


def tag_and_push(version: str) -> None:
    """Create a git tag and push it to trigger the CI release pipeline."""
    tag = f"v{version}"

    # Check for uncommitted changes
    result = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True
    )
    if result.stdout.strip():
        print("ERROR: Uncommitted changes detected. Commit before tagging.")
        sys.exit(1)

    # Check tag doesn't already exist
    result = subprocess.run(
        ["git", "tag", "-l", tag], capture_output=True, text=True
    )
    if result.stdout.strip():
        print(f"ERROR: Tag {tag} already exists. Delete it first or bump version.")
        sys.exit(1)

    print(f"  Creating tag {tag}...")
    subprocess.run(["git", "tag", tag], check=True)

    print(f"  Pushing {tag} to origin...")
    result = subprocess.run(
        ["git", "push", "origin", tag], capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ERROR: Push failed: {result.stderr.strip()}")
        # Clean up local tag
        subprocess.run(["git", "tag", "-d", tag])
        sys.exit(1)

    print(f"  Tag {tag} pushed -- CI will build and create the GitHub Release.")


def print_checklist(version: str, output_dir: str) -> None:
    """Print a human checklist for post-build steps."""
    print()
    print("=" * 60)
    print(f"Release v{version} build complete!")
    print("=" * 60)
    print()
    print("Output files:")
    print(f"  {output_dir}/kipart-search-{version}-windows.zip")
    print(f"  {output_dir}/kipart-search-{version}-setup.exe")
    print(f"  {output_dir}/checksums-{version}-sha256.txt")
    print()
    print("Next steps:")
    print(f"  Run: python release.py --tag")
    print("  Or manually:")
    print(f"    1. git tag v{version}")
    print(f"    2. git push origin v{version}")
    print("       -> CI will build and upload to GitHub Release automatically")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Automated release build for KiPart Search"
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip pytest step (for quick rebuilds during debugging)",
    )
    parser.add_argument(
        "--skip-version-gate",
        action="store_true",
        help="Skip GitHub version check (for offline use or re-building same version)",
    )
    parser.add_argument(
        "--output-dir",
        default="dist",
        help="Output directory (default: dist)",
    )
    parser.add_argument(
        "--tag",
        action="store_true",
        help="Create git tag and push to trigger CI release (skips local build)",
    )
    args = parser.parse_args()

    version = read_base_version()

    # --tag: just tag and push, no local build needed
    if args.tag:
        print(f"Tagging and pushing release v{version}")
        print()
        if not args.skip_version_gate:
            print("Step 1/2: Version gate")
            check_version_gate(version)
        else:
            print("Step 1/2: Version gate (skipped)")
        print()
        print("Step 2/2: Tag and push")
        tag_and_push(version)
        return 0

    print(f"Building KiPart Search release v{version}")
    print()

    # Step 1: Version gate
    if not args.skip_version_gate:
        print("Step 1/7: Version gate")
        check_version_gate(version)
    else:
        print("Step 1/7: Version gate (skipped)")
    print()

    # Step 2: Test suite
    if not args.skip_tests:
        print("Step 2/7: Test suite")
        run_tests()
    else:
        print("Step 2/7: Test suite (skipped)")
    print()

    # Step 3: GPL firewall
    print("Step 3/7: GPL firewall")
    check_licenses()
    print()

    # Step 4: Nuitka build
    print("Step 4/7: Nuitka build")
    build(output_dir=args.output_dir)
    print()

    # Step 5: ZIP packaging
    print("Step 5/7: ZIP packaging")
    package(output_dir=args.output_dir)
    print()

    # Step 6: Inno Setup installer
    print("Step 6/7: Inno Setup installer")
    compile_installer(output_dir=args.output_dir)
    print()

    # Step 7: SHA256 checksums
    print("Step 7/7: SHA256 checksums")
    generate_checksums(args.output_dir, version)
    print()

    # Final checklist
    print_checklist(version, args.output_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
