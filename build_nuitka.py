"""Nuitka build script for KiPart Search standalone Windows binary.

Usage:
    python build_nuitka.py
    python build_nuitka.py --package
    python build_nuitka.py --package-only
    python build_nuitka.py --skip-license-check --output-dir build
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _split_license_tokens(license_str: str) -> list[str]:
    """Split an SPDX license expression into individual tokens.

    Handles combinators: AND, OR, semicolons, commas.
    E.g. "LGPL-2.1 AND GPL-2.0" -> ["LGPL-2.1", "GPL-2.0"]
    """
    import re
    return [t.strip() for t in re.split(r"\bAND\b|\bOR\b|[;,]", license_str) if t.strip()]


def check_licenses() -> None:
    """Fail build if any GPL runtime dependency found (NFR16). LGPL is allowed.

    Build-only tools (Nuitka, pip-licenses, pytest, etc.) are excluded because
    they are not bundled into the distributed binary.
    """
    # Build/dev tools that are never bundled in the standalone binary
    BUILD_ONLY = {"nuitka", "pip-licenses", "piplicenses", "pytest", "prettytable"}

    try:
        result = subprocess.run(
            [sys.executable, "-m", "piplicenses", "--format=json", "--with-system"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print("GPL firewall check failed — could not run piplicenses:")
        if exc.stderr:
            print(exc.stderr.strip())
        print("Install it with: pip install pip-licenses")
        sys.exit(1)
    packages = json.loads(result.stdout)
    violations = []
    for pkg in packages:
        name = pkg.get("Name", "")
        if name.lower() in BUILD_ONLY:
            continue
        license_str = pkg.get("License", "").upper()
        # Split on SPDX combinators to check each license token individually.
        # A dual-license like "LGPL-2.1 AND GPL-2.0" must flag on the GPL token
        # even though LGPL is also present.
        tokens = _split_license_tokens(license_str)
        for token in tokens:
            if "GPL" in token and "LGPL" not in token:
                violations.append(f"  {name} ({pkg['License']})")
                break
    if violations:
        print("GPL FIREWALL FAILED -- these packages have GPL licenses:")
        for v in violations:
            print(v)
        sys.exit(1)
    print(f"GPL firewall passed: {len(packages)} packages checked, all clean.")


def read_version() -> str:
    """Read version from pyproject.toml and return X.X.X.X quad format."""
    version = read_base_version()
    # Convert to quad format: 0.1.0 -> 0.1.0.0
    parts = version.split(".")
    while len(parts) < 4:
        parts.append("0")
    parts = parts[:4]
    for i, p in enumerate(parts):
        if not p.isdigit():
            raise ValueError(
                f"Version part '{p}' in '{version}' is not a non-negative integer. "
                f"Windows PE version requires X.X.X.X numeric format."
            )
    return ".".join(parts)


def read_base_version() -> str:
    """Read raw version string from pyproject.toml (e.g., '0.1.0')."""
    pyproject = Path(__file__).parent / "pyproject.toml"
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # Python 3.10 fallback
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    return data.get("project", {}).get("version", "0.0.0")


def package(output_dir: str = "dist") -> None:
    """Package the Nuitka build output into a distributable zip file.

    Copies __main__.dist/ → kipart-search/, adds README.txt,
    then creates kipart-search-{version}-windows.zip.
    """
    output_path = Path(output_dir)
    nuitka_dist = output_path / "__main__.dist"
    package_dir = output_path / "kipart-search"
    version = read_base_version()

    # Validate that Nuitka build output exists
    exe_path = nuitka_dist / "kipart-search.exe"
    if not exe_path.exists():
        print(f"ERROR: {exe_path} not found.")
        print("Run a Nuitka build first, or use --package instead of --package-only.")
        sys.exit(1)

    # Step 1: Copy __main__.dist/ → kipart-search/
    print(f"Copying {nuitka_dist} → {package_dir}")
    if package_dir.exists():
        shutil.rmtree(package_dir)
    shutil.copytree(nuitka_dist, package_dir)

    # Step 2: Verify kipart-search.exe exists in the copy
    if not (package_dir / "kipart-search.exe").exists():
        print(f"ERROR: kipart-search.exe not found in {package_dir}")
        sys.exit(1)

    # Step 3: Write README.txt
    readme_text = f"""\
KiPart Search v{version}
========================

Parametric electronic component search with KiCad integration.

QUICK START
-----------
Double-click kipart-search.exe to launch the application.

No Python installation is required.

SYSTEM REQUIREMENTS
-------------------
- Windows 10 or Windows 11
- ~120 MB disk space
- Internet connection for distributor searches (JLCPCB offline database
  works without internet after first download)

KICAD INTEGRATION
-----------------
For KiCad integration, KiCad 9.0+ must be running with IPC API enabled.
Install kicad-python separately: pip install kicad-python

DOCUMENTATION
-------------
https://github.com/sylvanoMTL/kipart-search

LICENSE
-------
MIT License - Copyright (c) 2026 Sylvain Boyer (MecaFrog)
"""
    readme_path = package_dir / "README.txt"
    readme_path.write_text(readme_text, encoding="utf-8")
    print(f"Created {readme_path}")

    # Step 4: Create zip file
    zip_name = f"kipart-search-{version}-windows.zip"
    zip_path = output_path / zip_name
    if zip_path.exists():
        zip_path.unlink()

    print(f"Creating {zip_path}")
    shutil.make_archive(
        base_name=str(output_path / f"kipart-search-{version}-windows"),
        format="zip",
        root_dir=str(output_path),
        base_dir="kipart-search",
    )

    # Step 5: Print zip file size
    zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
    print()
    print(f"Package complete: {zip_path}")
    print(f"  Zip size: {zip_size_mb:.1f} MB")


def build(output_dir: str = "dist") -> None:
    """Run Nuitka standalone build."""
    version_quad = read_version()
    print(f"Building KiPart Search v{version_quad}")

    nuitka_cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--enable-plugin=pyside6",
        "--include-package=kipart_search",
        "--include-package=keyring.backends",
        "--assume-yes-for-downloads",
        "--windows-console-mode=disable",
        "--output-filename=kipart-search",
        f"--output-dir={output_dir}",
        "--windows-company-name=MecaFrog",
        "--windows-product-name=KiPart Search",
        f"--windows-file-version={version_quad}",
        f"--windows-product-version={version_quad}",
        "--windows-file-description=Parametric electronic component search",
        "src/kipart_search/__main__.py",
    ]

    print("Nuitka command:")
    print("  " + " ".join(nuitka_cmd))
    print()

    subprocess.run(nuitka_cmd, check=True)

    # Print summary — Nuitka names the folder after the entry-point module
    # (__main__.py → __main__.dist), not the --output-filename.
    dist_path = Path(output_dir) / "__main__.dist"
    if dist_path.exists():
        file_count = 0
        total_size = 0
        for f in dist_path.rglob("*"):
            if f.is_file():
                file_count += 1
                total_size += f.stat().st_size
        size_mb = total_size / (1024 * 1024)
        print()
        print(f"Build complete: {dist_path}")
        print(f"  Files: {file_count}")
        print(f"  Total size: {size_mb:.1f} MB")
        print()
        print("NOTE: Windows Defender may flag Nuitka-compiled executables.")
        print("Code signing with an EV certificate is the only reliable fix.")
    else:
        print(f"WARNING: Expected output directory {dist_path} not found.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build KiPart Search with Nuitka")
    parser.add_argument(
        "--skip-license-check",
        action="store_true",
        help="Skip GPL firewall license check",
    )
    parser.add_argument(
        "--output-dir",
        default="dist",
        help="Output directory (default: dist)",
    )
    pkg_group = parser.add_mutually_exclusive_group()
    pkg_group.add_argument(
        "--package",
        action="store_true",
        help="Build with Nuitka, then package into a distributable zip",
    )
    pkg_group.add_argument(
        "--package-only",
        action="store_true",
        help="Skip Nuitka build; only run the packaging step (requires prior build)",
    )
    args = parser.parse_args()

    if args.package_only:
        # Skip license check and build — just package
        print("Packaging only (skipping Nuitka build)")
        package(output_dir=args.output_dir)
        return 0

    if not args.skip_license_check:
        check_licenses()
    else:
        print("Skipping GPL license check (--skip-license-check)")

    build(output_dir=args.output_dir)

    if args.package:
        package(output_dir=args.output_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
