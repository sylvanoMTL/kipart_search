"""Nuitka build script for KiPart Search standalone binary.

Replaces: build_nuitka.py

CHANGES FROM ORIGINAL (2026-03-30)
====================================

1. build() function (line ~274): Added cross-platform Nuitka flag handling.
   - Windows flags (--windows-*): ACTIVE, same as before
   - macOS flags (--macos-*): COMMENTED stub with documentation
   - Linux: no special flags needed (just --standalone)

2. package() function: Added cross-platform packaging stubs.
   - Windows ZIP: ACTIVE, same as before
   - macOS DMG: COMMENTED stub (_package_macos_dmg)
   - Linux AppImage: COMMENTED stub (_package_linux_appimage)

3. compile_installer(): Added platform guard — Inno Setup is Windows-only.
   Prints a message and returns on non-Windows platforms.

4. Everything else is UNCHANGED: check_licenses, read_version, read_base_version,
   main, CLI argument parsing.

Usage:
    python build_nuitka.py
    python build_nuitka.py --package
    python build_nuitka.py --package-only
    python build_nuitka.py --installer
    python build_nuitka.py --installer-only
    python build_nuitka.py --skip-license-check --output-dir build
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _is_gpl_token(token: str) -> bool:
    """Return True if a single SPDX license token is GPL (not LGPL)."""
    return "GPL" in token and "LGPL" not in token


def _has_gpl_violation(license_str: str) -> bool:
    """Check whether a license expression forces GPL on the user.

    SPDX semantics:
    - OR: user picks one alternative → safe if ANY alternative is non-GPL
    - AND: all apply simultaneously → violation if ANY is GPL
    - Semicolons/commas: treated as AND (conservative)

    E.g. "LGPL-3.0-only OR GPL-2.0-only" → safe (choose LGPL)
         "LGPL-2.1 AND GPL-2.0" → violation (GPL applies regardless)
    """
    import re
    # Split on OR first — each alternative is independently choosable
    or_alternatives = [a.strip() for a in re.split(r"\bOR\b", license_str) if a.strip()]
    for alternative in or_alternatives:
        # Within each OR alternative, split on AND/semicolons/commas
        and_tokens = [t.strip() for t in re.split(r"\bAND\b|[;,]", alternative) if t.strip()]
        # This alternative is safe if NONE of its AND-joined tokens are GPL
        if not any(_is_gpl_token(t) for t in and_tokens):
            return False  # Found a non-GPL alternative — package is clean
    # Every OR alternative contains a GPL AND-token — violation
    return True


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
        if _has_gpl_violation(license_str):
            violations.append(f"  {name} ({pkg['License']})")
    if violations:
        print("GPL FIREWALL FAILED -- these packages have GPL licenses:")
        for v in violations:
            print(v)
        sys.exit(1)
    print(f"GPL firewall passed: {len(packages)} packages checked, all clean.")


def read_version() -> str:
    """Read version from pyproject.toml and return X.X.X.X quad format.

    The quad format is a Windows PE requirement for --windows-file-version.
    On macOS and Linux, use read_base_version() directly (semver X.Y.Z).
    """
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
    """Package the Nuitka build output into a distributable archive.

    Dispatches to the platform-specific packaging function.
    Currently only Windows ZIP is implemented.
    """
    if sys.platform == "win32":
        _package_windows_zip(output_dir)
    elif sys.platform == "darwin":
        # -----------------------------------------------------------------
        # macOS DMG packaging — FUTURE IMPLEMENTATION
        # -----------------------------------------------------------------
        # _package_macos_dmg(output_dir)
        # -----------------------------------------------------------------
        print("macOS DMG packaging not yet implemented.")
        sys.exit(1)
    elif sys.platform == "linux":
        # -----------------------------------------------------------------
        # Linux AppImage packaging — FUTURE IMPLEMENTATION
        # -----------------------------------------------------------------
        # _package_linux_appimage(output_dir)
        # -----------------------------------------------------------------
        print("Linux AppImage packaging not yet implemented.")
        sys.exit(1)
    else:
        print(f"Unsupported platform for packaging: {sys.platform}")
        sys.exit(1)


def _package_windows_zip(output_dir: str = "dist") -> None:
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
    print(f"Copying {nuitka_dist} -> {package_dir}")
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
kicad-python is bundled — no separate install needed.

DOCUMENTATION
-------------
https://github.com/sylvanoMTL/kipart_search

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


# ---------------------------------------------------------------------------
# macOS DMG packaging — FUTURE STUB
# ---------------------------------------------------------------------------
#
# def _package_macos_dmg(output_dir: str = "dist") -> None:
#     """Package Nuitka .app bundle into a .dmg disk image.
#
#     Prerequisites:
#       - Nuitka build with --macos-create-app-bundle produces:
#         dist/__main__.app/
#       - hdiutil is built into macOS (no install needed)
#       - Optional: create-dmg (npm package) for prettier DMGs with
#         background images and icon positioning
#
#     Steps:
#       1. Rename __main__.app → "KiPart Search.app"
#       2. Create DMG using hdiutil:
#          hdiutil create -volname "KiPart Search" \
#            -srcfolder "dist/KiPart Search.app" \
#            -ov -format UDZO \
#            "dist/kipart-search-{version}-macos.dmg"
#       3. Optional: add code signature
#          codesign --deep --force --sign "Developer ID Application: ..." \
#            "dist/KiPart Search.app"
#
#     The resulting .dmg is uploaded to GitHub Releases.
#     update_check.py matches it via name.endswith(".dmg").
#     update_shim.launch_installer() opens it via subprocess ["open", path].
#     """
#     output_path = Path(output_dir)
#     version = read_base_version()
#     app_bundle = output_path / "__main__.app"
#     branded = output_path / "KiPart Search.app"
#     dmg_path = output_path / f"kipart-search-{version}-macos.dmg"
#
#     if not app_bundle.exists():
#         print(f"ERROR: {app_bundle} not found. Run Nuitka with --macos-create-app-bundle.")
#         sys.exit(1)
#
#     if branded.exists():
#         shutil.rmtree(branded)
#     shutil.move(str(app_bundle), str(branded))
#
#     subprocess.run([
#         "hdiutil", "create",
#         "-volname", "KiPart Search",
#         "-srcfolder", str(branded),
#         "-ov", "-format", "UDZO",
#         str(dmg_path),
#     ], check=True)
#
#     size_mb = dmg_path.stat().st_size / (1024 * 1024)
#     print(f"DMG complete: {dmg_path}")
#     print(f"  Size: {size_mb:.1f} MB")


# ---------------------------------------------------------------------------
# Linux AppImage packaging — FUTURE STUB
# ---------------------------------------------------------------------------
#
# def _package_linux_appimage(output_dir: str = "dist") -> None:
#     """Package Nuitka standalone into an AppImage.
#
#     Prerequisites:
#       - appimagetool: download from
#         https://github.com/AppImage/appimagetool/releases
#       - A .desktop file and icon for the AppDir structure
#
#     AppDir structure:
#       AppDir/
#         AppRun                    → symlink to usr/bin/kipart-search
#         kipart-search.desktop     → freedesktop .desktop file
#         kipart-search.png         → application icon (256x256 recommended)
#         usr/
#           bin/                    → contents of __main__.dist/
#             kipart-search         → main executable
#             *.so                  → shared libraries
#             ...
#
#     Steps:
#       1. Create AppDir structure from __main__.dist/
#       2. Write .desktop file and symlink AppRun
#       3. Run: appimagetool AppDir/ kipart-search-{version}-linux.AppImage
#
#     The resulting .AppImage is uploaded to GitHub Releases.
#     update_check.py matches it via name.endswith(".AppImage").
#     update_shim.launch_installer() replaces the binary in place.
#     """
#     output_path = Path(output_dir)
#     version = read_base_version()
#     nuitka_dist = output_path / "__main__.dist"
#     appdir = output_path / "AppDir"
#     appimage_path = output_path / f"kipart-search-{version}-linux.AppImage"
#
#     if not nuitka_dist.exists():
#         print(f"ERROR: {nuitka_dist} not found.")
#         sys.exit(1)
#
#     # Create AppDir structure
#     usr_bin = appdir / "usr" / "bin"
#     if appdir.exists():
#         shutil.rmtree(appdir)
#     usr_bin.mkdir(parents=True)
#
#     # Copy Nuitka output
#     for item in nuitka_dist.iterdir():
#         dest = usr_bin / item.name
#         if item.is_dir():
#             shutil.copytree(item, dest)
#         else:
#             shutil.copy2(item, dest)
#
#     # Create AppRun symlink
#     apprun = appdir / "AppRun"
#     apprun.symlink_to("usr/bin/kipart-search")
#
#     # Create .desktop file
#     desktop = appdir / "kipart-search.desktop"
#     desktop.write_text(
#         "[Desktop Entry]\n"
#         "Type=Application\n"
#         "Name=KiPart Search\n"
#         "Exec=kipart-search\n"
#         "Icon=kipart-search\n"
#         "Categories=Electronics;Engineering;\n"
#     )
#
#     # TODO: Copy icon file (kipart-search.png) into appdir
#
#     # Build AppImage
#     subprocess.run(["appimagetool", str(appdir), str(appimage_path)], check=True)
#
#     size_mb = appimage_path.stat().st_size / (1024 * 1024)
#     print(f"AppImage complete: {appimage_path}")
#     print(f"  Size: {size_mb:.1f} MB")


def compile_installer(output_dir: str = "dist") -> None:
    """Compile the Inno Setup installer from existing Nuitka build output.

    Requires Inno Setup 6 installed with iscc on PATH or at the default location.
    NOTE: Inno Setup is Windows-only.  macOS uses .dmg, Linux uses AppImage.
    """
    if sys.platform != "win32":
        print("Inno Setup installer is Windows-only. Skipping.")
        print("  macOS: use _package_macos_dmg() instead (future)")
        print("  Linux: use _package_linux_appimage() instead (future)")
        return

    version = read_base_version()
    iss_path = Path(__file__).parent / "installer" / "kipart-search.iss"

    if not iss_path.exists():
        print(f"ERROR: Inno Setup script not found at {iss_path}")
        sys.exit(1)

    # Verify Nuitka build output exists
    nuitka_dist = Path(output_dir) / "__main__.dist"
    if not (nuitka_dist / "kipart-search.exe").exists():
        print(f"ERROR: {nuitka_dist / 'kipart-search.exe'} not found.")
        print("Run a Nuitka build first, or use --installer instead of --installer-only.")
        sys.exit(1)

    # Find iscc — check PATH first, then default Inno Setup 6 install location
    iscc = shutil.which("iscc")
    if iscc is None:
        default_iscc = Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe")
        if default_iscc.exists():
            iscc = str(default_iscc)
        else:
            print("ERROR: iscc not found on PATH or at default location.")
            print("Install Inno Setup 6 from https://jrsoftware.org/isdl.php")
            print(f"Expected: {default_iscc}")
            sys.exit(1)

    # Compute paths relative to the .iss file's directory for iscc /D overrides.
    # Fall back to absolute paths when relpath fails (e.g. cross-drive on Windows).
    iss_dir = iss_path.parent.resolve()
    output_abs = Path(output_dir).resolve()
    source_abs = nuitka_dist.resolve()
    try:
        output_rel = os.path.relpath(output_abs, iss_dir)
        source_rel = os.path.relpath(source_abs, iss_dir)
    except ValueError:
        output_rel = str(output_abs)
        source_rel = str(source_abs)

    cmd = [
        iscc,
        f"/DMyAppVersion={version}",
        f"/DMyOutputDir={output_rel}",
        f"/DMySourceDir={source_rel}",
        str(iss_path),
    ]
    print(f"Compiling installer v{version}")
    print("  " + " ".join(cmd))
    print()
    subprocess.run(cmd, check=True)

    # Verify output and print summary
    installer_name = f"kipart-search-{version}-setup.exe"
    installer_path = Path(output_dir) / installer_name
    if installer_path.exists():
        size_mb = installer_path.stat().st_size / (1024 * 1024)
        print()
        print(f"Installer complete: {installer_path}")
        print(f"  Size: {size_mb:.1f} MB")
    else:
        print(f"ERROR: Expected installer {installer_path} not found.")
        sys.exit(1)


def build(output_dir: str = "dist") -> None:
    """Run Nuitka standalone build with platform-appropriate flags."""
    version = read_base_version()

    # --- Common flags (all platforms) ---
    nuitka_cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--enable-plugin=pyside6",
        "--include-package=kipart_search",
        "--include-package=keyring.backends",
        "--include-package=kipy",
        "--assume-yes-for-downloads",
        "--output-filename=kipart-search",
        f"--output-dir={output_dir}",
        "src/kipart_search/__main__.py",
    ]

    # --- Platform-specific flags ---
    if sys.platform == "win32":
        version_quad = read_version()  # X.X.X.X format for Windows PE
        print(f"Building KiPart Search v{version_quad} (Windows)")
        nuitka_cmd += [
            "--windows-console-mode=disable",
            "--windows-company-name=MecaFrog",
            "--windows-product-name=KiPart Search",
            f"--windows-file-version={version_quad}",
            f"--windows-product-version={version_quad}",
            "--windows-file-description=Parametric electronic component search",
        ]

    elif sys.platform == "darwin":
        # ---------------------------------------------------------------
        # macOS — FUTURE IMPLEMENTATION
        # ---------------------------------------------------------------
        # Nuitka's --macos-create-app-bundle creates a proper .app bundle
        # with Info.plist, icon, and correct directory structure.
        #
        # To enable, uncomment:
        # print(f"Building KiPart Search v{version} (macOS)")
        # nuitka_cmd += [
        #     "--macos-create-app-bundle",
        #     "--macos-app-name=KiPart Search",
        #     f"--macos-app-version={version}",
        #     "--macos-disable-console",
        #     # Code signing (requires Apple Developer ID):
        #     # "--macos-sign-identity=Developer ID Application: MecaFrog",
        #     # "--macos-sign-notarization",
        # ]
        # ---------------------------------------------------------------
        print(f"Building KiPart Search v{version} (macOS)")
        print("NOTE: macOS-specific Nuitka flags not yet configured.")
        print("The build will produce a standalone folder, not a .app bundle.")

    elif sys.platform == "linux":
        # ---------------------------------------------------------------
        # Linux — FUTURE IMPLEMENTATION
        # ---------------------------------------------------------------
        # No special Nuitka flags needed for Linux — --standalone is
        # sufficient.  The packaging step (_package_linux_appimage) wraps
        # the output into an AppImage.
        #
        # For better desktop integration, consider:
        # nuitka_cmd += [
        #     "--linux-icon=assets/kipart-search.png",
        # ]
        # ---------------------------------------------------------------
        print(f"Building KiPart Search v{version} (Linux)")
        print("NOTE: Linux build produces a standalone folder.")
        print("Use --package to wrap it into an AppImage (future).")

    else:
        print(f"WARNING: Unsupported platform {sys.platform}")
        print(f"Building KiPart Search v{version} (generic)")

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
        if sys.platform == "win32":
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
    pkg_group.add_argument(
        "--installer",
        action="store_true",
        help="Build with Nuitka, package zip, then compile Inno Setup installer",
    )
    pkg_group.add_argument(
        "--installer-only",
        action="store_true",
        help="Compile Inno Setup installer only (requires prior Nuitka build)",
    )
    args = parser.parse_args()

    if args.package_only:
        # Skip license check and build — just package
        print("Packaging only (skipping Nuitka build)")
        package(output_dir=args.output_dir)
        return 0

    if args.installer_only:
        # Skip license check and build — just compile installer
        print("Installer only (skipping Nuitka build)")
        compile_installer(output_dir=args.output_dir)
        return 0

    if not args.skip_license_check:
        check_licenses()
    else:
        print("Skipping GPL license check (--skip-license-check)")

    build(output_dir=args.output_dir)

    if args.package:
        package(output_dir=args.output_dir)

    if args.installer:
        package(output_dir=args.output_dir)
        compile_installer(output_dir=args.output_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
