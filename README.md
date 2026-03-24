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
