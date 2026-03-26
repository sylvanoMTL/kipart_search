# KiPart Search

Parametric electronic component search with KiCad integration.

## Install (development)

```bash
pip install -e .
python -m kipart_search
```

## License activation (development)

The app has a free/Pro tier split. Since no LemonSqueezy product is configured yet, use one of these methods to test Pro features:

| Method | How | Scope |
|--------|-----|-------|
| **Dev bypass key** | Preferences > License, enter `dev-pro-unlock`, click Activate | Source builds only |
| **Env var** | `KIPART_LICENSE_KEY=anything python -m kipart_search` | Any build |

The dev bypass key is rejected in compiled (Nuitka) binaries. Both methods cache a JWT in keyring, so Pro persists across restarts until you click Deactivate.

## Releasing

### Prerequisites

- Version must be bumped **before** releasing — edit the `version` field in both files:
  - `pyproject.toml` → `version = "X.Y.Z"`
  - `src/kipart_search/__init__.py` → `__version__ = "X.Y.Z"`

  These must match. The CI and `release.py` both verify the tag matches `pyproject.toml`
- All changes committed and pushed to `main`
- `gh` CLI installed and authenticated (for `clear_release.py`)

### Create a release

**Option A: Tag and let CI build everything** (recommended)

```bash
python release.py --tag
```

This runs the version gate (checks the tag doesn't match the latest GitHub release), creates a `v{version}` git tag, and pushes it. CI then builds the Nuitka binary, ZIP, Inno Setup installer, SHA256 checksums, and uploads them as GitHub Release assets.

**Option B: Full local build first, then publish**

```bash
python release.py           # local build: tests, GPL check, Nuitka, ZIP, installer, checksums
python release.py --tag     # tag + push to trigger CI
```

Useful flags:
- `--skip-tests` — skip pytest (for quick rebuilds)
- `--skip-version-gate` — skip GitHub version check (offline or re-building same version)
- `--output-dir build` — change output directory (default: `dist`)

### Delete a release

```bash
python clear_release.py             # deletes v{version} from pyproject.toml
python clear_release.py v0.1.0      # deletes a specific tag
```

Removes the GitHub release, remote tag, and local tag. Useful for cleaning up test releases.
