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
    python release.py                        # full local build
    python release.py --tag                  # tag + push current version to trigger CI
    python release.py --tag --bump patch     # 0.1.0 → 0.1.1, commit, tag, push, watch CI
    python release.py --tag --bump minor     # 0.1.0 → 0.2.0
    python release.py --tag --bump major     # 0.1.0 → 1.0.0
    python release.py --skip-tests --skip-version-gate
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
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


def compute_next_version(current: str, part: str) -> str:
    """Compute the next semver version given a bump part (major/minor/patch)."""
    parts = [int(p) for p in current.split(".")]
    while len(parts) < 3:
        parts.append(0)
    if part == "major":
        parts = [parts[0] + 1, 0, 0]
    elif part == "minor":
        parts = [parts[0], parts[1] + 1, 0]
    elif part == "patch":
        parts = [parts[0], parts[1], parts[2] + 1]
    return ".".join(str(p) for p in parts)


def bump_version(part: str) -> str:
    """Bump the version in pyproject.toml and __init__.py, return the new version.

    Reads the current version, computes the next one, and writes it back
    to both files so they stay in sync.
    """
    import re

    current = read_base_version()
    new_version = compute_next_version(current, part)

    # --- pyproject.toml ---
    pyproject = Path("pyproject.toml")
    text = pyproject.read_text(encoding="utf-8")
    # Match only the first `version = "..."` after a [project] header to avoid
    # accidentally editing version fields in other TOML tables.
    updated = re.sub(
        r'(\[project\][^\[]*?^version\s*=\s*")[^"]*(")',
        rf"\g<1>{new_version}\2",
        text,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )
    if updated == text:
        print(f"ERROR: Could not find version field in pyproject.toml")
        sys.exit(1)
    pyproject.write_text(updated, encoding="utf-8")

    # --- src/kipart_search/__init__.py ---
    init_py = Path("src/kipart_search/__init__.py")
    if init_py.exists():
        init_text = init_py.read_text(encoding="utf-8")
        init_updated = re.sub(
            r'^(__version__\s*=\s*")[^"]*(")',
            rf"\g<1>{new_version}\2",
            init_text,
            count=1,
            flags=re.MULTILINE,
        )
        if init_updated != init_text:
            init_py.write_text(init_updated, encoding="utf-8")

    # --- installer/kipart-search.iss ---
    iss_file = Path("installer/kipart-search.iss")
    if iss_file.exists():
        iss_text = iss_file.read_text(encoding="utf-8")
        iss_updated = re.sub(
            r'(#define MyAppVersion ")[^"]*(")',
            rf"\g<1>{new_version}\2",
            iss_text,
            count=1,
        )
        if iss_updated != iss_text:
            iss_file.write_text(iss_updated, encoding="utf-8")

    print(f"  Bumped version: {current} -> {new_version}")
    return new_version


def stamp_changelog(version: str) -> bool:
    """Move [Unreleased] content into a new version section in CHANGELOG.md.

    Returns True if the changelog was modified, False if skipped.
    """
    from datetime import date

    changelog = Path("CHANGELOG.md")
    if not changelog.exists():
        return False

    text = changelog.read_text(encoding="utf-8")

    # Check there's an [Unreleased] section with content
    if "## [Unreleased]" not in text:
        return False

    today = date.today().isoformat()
    new_header = f"## [{version}] - {today}"

    # Find the [Unreleased] header and insert the new version header before
    # the first non-blank content line after it.  This keeps [Unreleased]
    # as an empty section and moves all its prior content under the new
    # version header.
    import re

    pattern = re.compile(r"(## \[Unreleased\][^\n]*\n(?:\s*\n)*)")
    m = pattern.search(text)
    if not m:
        return False

    insert_pos = m.end()
    updated = text[:insert_pos] + new_header + "\n" + text[insert_pos:]

    if updated == text:
        return False

    changelog.write_text(updated, encoding="utf-8")
    print(f"  Stamped CHANGELOG.md with [{version}] - {today}")
    return True


def commit_and_push_bump(version: str) -> None:
    """Commit the version bump and push to origin."""
    # Stage version files and changelog (only if they exist)
    files_to_stage = ["pyproject.toml"]
    for optional in ["src/kipart_search/__init__.py", "installer/kipart-search.iss", "CHANGELOG.md"]:
        if Path(optional).exists():
            files_to_stage.append(optional)
    subprocess.run(["git", "add", *files_to_stage], check=True)

    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
    )
    if result.returncode == 0:
        print("  No changes to commit (version already bumped?)")
        return

    subprocess.run(
        ["git", "commit", "-m", f"Bump version to {version}"],
        check=True,
    )
    print(f"  Committed version bump")

    result = subprocess.run(
        ["git", "push"], capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: Push failed: {result.stderr.strip()}")
        sys.exit(1)
    print(f"  Pushed to origin")


def extract_changelog(version: str, changelog_path: str = "CHANGELOG.md") -> str | None:
    """Extract the changelog section for a given version.

    Reads ``changelog_path`` (relative to CWD) and returns the content between
    the ``## [<version>]`` header and the next ``## [`` header (or EOF).
    Returns ``None`` if the file doesn't exist, the version isn't found,
    or the version section is empty (e.g. ``[Unreleased]`` with no content).
    """
    try:
        text = Path(changelog_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None

    lines = text.splitlines()
    collecting = False
    section_lines: list[str] = []

    for line in lines:
        if line.startswith(f"## [{version}]"):
            collecting = True
            continue
        if collecting and line.startswith("## ["):
            break
        if collecting:
            section_lines.append(line)

    if not section_lines:
        return None

    result = "\n".join(section_lines).strip()
    return result if result else None


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

    if shutil.which("gh"):
        watch_ci(tag)
    else:
        print("  Install GitHub CLI (gh) to watch CI progress here.")


def watch_ci(tag: str, max_minutes: int = 30) -> None:
    """Poll GitHub Actions until the workflow run triggered by *tag* completes.

    Gives up after *max_minutes* to avoid hanging indefinitely.
    """
    max_seconds = max_minutes * 60
    print()
    print(f"  Watching CI for {tag} (timeout: {max_minutes}m)...")

    # Wait for the run to appear (GitHub needs a few seconds)
    run_id = None
    for attempt in range(12):  # up to ~60s
        time.sleep(5)
        result = subprocess.run(
            ["gh", "run", "list", "--json=databaseId,headBranch,status",
             "--limit=5"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            continue
        try:
            runs = json.loads(result.stdout)
        except json.JSONDecodeError:
            continue
        for run in runs:
            if run.get("headBranch") == tag:
                run_id = run["databaseId"]
                break
        if run_id:
            break
    else:
        print("  Could not find CI run. Check manually:")
        print(f"    gh run list")
        return

    # Poll until completed or timeout
    poll_interval = 15
    last_status = None
    elapsed = 0
    while elapsed < max_seconds:
        result = subprocess.run(
            ["gh", "run", "view", str(run_id),
             "--json=status,conclusion,jobs"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  Could not query run {run_id}: {result.stderr.strip()}")
            break

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            print(f"  WARNING: Could not parse gh output, retrying...")
            time.sleep(poll_interval)
            elapsed += poll_interval
            continue

        status = data.get("status", "unknown")
        conclusion = data.get("conclusion", "")

        # Build a one-line summary from job statuses
        jobs = data.get("jobs", [])
        job_parts = []
        for job in jobs:
            j_name = job.get("name", "job")
            j_status = job.get("status", "?")
            j_conclusion = job.get("conclusion", "")
            if j_conclusion == "success":
                job_parts.append(f"{j_name}: done")
            elif j_conclusion == "failure":
                job_parts.append(f"{j_name}: FAILED")
            else:
                # Show step-level progress if available
                steps = job.get("steps", [])
                active = [s["name"] for s in steps if s.get("status") == "in_progress"]
                if active:
                    job_parts.append(f"{j_name}: {active[0]}")
                else:
                    job_parts.append(f"{j_name}: {j_status}")

        mins, secs = divmod(elapsed, 60)
        time_str = f"{mins}m {secs:02d}s" if mins else f"{secs}s"
        summary = ", ".join(job_parts) if job_parts else status
        line = f"    [{time_str}] {summary}"

        if line != last_status:
            print(line)
            last_status = line

        if status == "completed":
            print()
            if conclusion == "success":
                print(f"  CI passed! Release:")
                print(f"    https://github.com/{GITHUB_REPO}/releases/tag/{tag}")
            else:
                print(f"  CI finished with conclusion: {conclusion}")
                print(f"    gh run view {run_id} --log-failed")
            break

        time.sleep(poll_interval)
        elapsed += poll_interval
    else:
        print(f"\n  Timed out after {max_minutes} minutes. Check manually:")
        print(f"    gh run view {run_id}")


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
    parser.add_argument(
        "--bump",
        choices=["major", "minor", "patch"],
        help="Bump version before tagging (requires --tag)",
    )
    args = parser.parse_args()

    if args.bump and not args.tag:
        parser.error("--bump requires --tag")

    version = read_base_version()

    # --tag: just tag and push, no local build needed
    if args.tag:
        # Fail fast if working tree is dirty
        result = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True
        )
        if result.stdout.strip():
            print("ERROR: Uncommitted changes detected. Commit before releasing.")
            sys.exit(1)

        if args.bump:
            new_version = compute_next_version(version, args.bump)
            print(f"This will bump {version} -> {new_version}, commit, tag v{new_version}, and push.")
        else:
            print(f"This will create tag v{version} and push to trigger CI release.")
        answer = input("Proceed? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted.")
            return 0
        print()

        total_steps = 3 if args.bump else 2
        step = 0

        # Optional: bump version first
        if args.bump:
            step += 1
            print(f"Step {step}/{total_steps}: Bump version ({args.bump})")
            version = bump_version(args.bump)
            stamp_changelog(version)
            commit_and_push_bump(version)
            print()

        step += 1
        print(f"Releasing v{version}")
        print()
        if not args.skip_version_gate:
            print(f"Step {step}/{total_steps}: Version gate")
            check_version_gate(version)
        else:
            print(f"Step {step}/{total_steps}: Version gate (skipped)")
        if extract_changelog(version) is None:
            print(f"  WARNING: No CHANGELOG.md entry found for version {version}")
        print()

        step += 1
        print(f"Step {step}/{total_steps}: Tag and push")
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
    if extract_changelog(version) is None:
        print(f"  WARNING: No CHANGELOG.md entry found for version {version}")
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
