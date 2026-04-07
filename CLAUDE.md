# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Small Python CLI that calls the Zscaler Zero Trust Branch (ZTB / Airgap) API to fetch discovered devices ("assets") and write them to a CSV file. Secrets live in `.env`; the delegate bearer token is cached in `.token.json` (both gitignored).

## Commands

Dependency management and execution use **uv** (Python 3.14+).

```bash
uv sync                                    # install deps from lockfile
uv add <package>                           # add a runtime dep
uv run ztb-assets                          # run CLI (entry point in pyproject.toml)
uv run python -m ztb_assets                # equivalent module invocation
uv run ztb-assets -o out.csv --page-size 200
```

There are no tests, linters, or formatters configured in this repo yet. Don't assume a test runner exists — check `pyproject.toml` before running one.

## Configuration

Copy `.env.example` → `.env` and fill in:
- `ZTB_BASE_URL` — must start with `https://` (enforced in `config.py`). Example: `https://<tenant>-api.goairgap.com`
- `ZTB_API_KEY` — raw API key, POSTed as `{"api_key": "..."}` to `/api/v3/api-key-auth/login`
- `ZTB_TOKEN_PATH` (optional) — override cached token location, default `./.token.json`

## Architecture

The flow is strictly linear: `cli → config → client → auth → assets → csv`.

- **`config.py`** — `load_config()` reads `.env` via `python-dotenv`, validates `ZTB_BASE_URL` scheme, returns an immutable `Config` dataclass. Raises `ConfigError` (exit code 1).
- **`auth.py`** — Owns the token lifecycle. `get_token(cfg, force_refresh=...)` is the only function the client calls. It reads `.token.json` if present, otherwise POSTs the API key to `/api/v3/api-key-auth/login` and extracts `result.delegate_token`. `save_token()` does an atomic write via temp-file + `os.replace`, then `chmod 0600`. Raises `AuthError` (exit code 2).
- **`client.py`** — `ZTBClient.request()` is the central reliability point. It attaches `Authorization: Bearer <token>` using a cached token, and **on HTTP 401 it calls `get_token(force_refresh=True)` exactly once and retries**. This is how expired tokens are handled — there is no proactive TTL check (the API's login response does not expose `expires_in`). Error messages deliberately never include the response body or header so bearer tokens cannot leak into logs. Raises `APIError` (exit code 3).
- **`assets.py`** — `fetch_all_assets()` pages through `GET /api/v2/devices/active` using `page`/`limit` query params. Stops when a page returns fewer than `page_size` rows. The response envelope is `{"result": {"count": N, "rows": [...]}}`. `write_csv()` flattens one level of nested dicts (`key.subkey` columns) and stringifies deeper structures with `repr()` so the output stays tabular and resilient to schema drift (the column set is the sorted union across all rows).
- **`cli.py`** — `argparse` front-end. Exit codes: `0` success, `1` config error, `2` auth error, `3` API error.

### Things to know when editing

- Token refresh is intentionally 401-driven, not TTL-driven. Don't add a TTL field to `.token.json` unless the API starts exposing one — that would only duplicate what the 401 retry already handles.
- `swagger.json` (~1.7 MB) is reference-only. **Never parse it whole.** Use targeted `Grep` for specific schema names or paths.
- Known swagger landmarks (line numbers may drift if swagger is regenerated): `AuthKeyLoginDto` (~1980), `DelegateTokenResponse` (~5784), `DeviceGetDto` (~6490), `/api/v3/api-key-auth/login` (~42440), `/api/v2/devices/active` (~33315).
- `.gitignore` already excludes `.env`, `.token.json`, and `*.csv`. Keep it that way — the default output path is `assets.csv` in the repo root.
- Error paths in `auth.py` and `client.py` deliberately avoid echoing response bodies. Preserve that when adding new error handling.
