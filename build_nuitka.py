"""Nuitka build script for KiPart Search standalone Windows binary.

Usage:
    python build_nuitka.py
    python build_nuitka.py --skip-license-check --output-dir build
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def check_licenses() -> None:
    """Fail build if any GPL runtime dependency found (NFR16). LGPL is allowed.

    Build-only tools (Nuitka, pip-licenses, pytest, etc.) are excluded because
    they are not bundled into the distributed binary.
    """
    # Build/dev tools that are never bundled in the standalone binary
    BUILD_ONLY = {"nuitka", "pip-licenses", "piplicenses", "pytest", "prettytable"}

    result = subprocess.run(
        [sys.executable, "-m", "piplicenses", "--format=json", "--with-system"],
        capture_output=True,
        text=True,
        check=True,
    )
    packages = json.loads(result.stdout)
    violations = []
    for pkg in packages:
        name = pkg.get("Name", "")
        if name.lower() in BUILD_ONLY:
            continue
        license_str = pkg.get("License", "").upper()
        # GPL but NOT LGPL
        if "GPL" in license_str and "LGPL" not in license_str:
            violations.append(f"  {name} ({pkg['License']})")
    if violations:
        print("GPL FIREWALL FAILED -- these packages have GPL licenses:")
        for v in violations:
            print(v)
        sys.exit(1)
    print(f"GPL firewall passed: {len(packages)} packages checked, all clean.")


def read_version() -> str:
    """Read version from pyproject.toml and return X.X.X.X quad format."""
    pyproject = Path(__file__).parent / "pyproject.toml"
    import tomllib
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    version = data.get("project", {}).get("version", "0.0.0")
    # Convert to quad format: 0.1.0 -> 0.1.0.0
    parts = version.split(".")
    while len(parts) < 4:
        parts.append("0")
    return ".".join(parts[:4])


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
        f"--windows-company-name=MecaFrog",
        f"--windows-product-name=KiPart Search",
        f"--windows-file-version={version_quad}",
        f"--windows-product-version={version_quad}",
        f"--windows-file-description=Parametric electronic component search",
        "src/kipart_search/__main__.py",
    ]

    print("Nuitka command:")
    print("  " + " ".join(nuitka_cmd))
    print()

    subprocess.run(nuitka_cmd, check=True)

    # Print summary
    dist_path = Path(output_dir) / "kipart-search.dist"
    if dist_path.exists():
        files = list(dist_path.rglob("*"))
        file_count = sum(1 for f in files if f.is_file())
        total_size = sum(f.stat().st_size for f in files if f.is_file())
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
    args = parser.parse_args()

    if not args.skip_license_check:
        check_licenses()
    else:
        print("Skipping GPL license check (--skip-license-check)")

    build(output_dir=args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
