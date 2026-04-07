"""API key authentication and delegate token caching.

The ZTB API uses a two-step auth model: you POST a long-lived API key to the
api-key-auth/login endpoint and receive a short-lived "delegate token" that
must be sent as a Bearer token on every subsequent request.

This module owns the full lifecycle of that delegate token:
  - login()      — exchange API key for delegate token
  - load_token() — read cached token from disk
  - save_token() — atomically write token to disk with 0600 permissions
  - get_token()  — high-level helper that caches transparently

The login response does *not* include an `expires_in` field, so expiry is
detected downstream in `client.py` via 401 retry rather than a TTL check here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import requests

from .config import Config

# Swagger: /api/v3/api-key-auth/login — schema AuthKeyLoginDto → DelegateTokenResponseDto
AUTH_PATH = "/api/v3/api-key-auth/login"


class AuthError(Exception):
    """Raised when the API key exchange fails for any reason."""


def login(base_url: str, api_key: str, *, timeout: float = 30.0) -> str:
    """POST the API key and return the delegate token string.

    Any network or HTTP failure is re-raised as `AuthError` with a generic
    message — we intentionally do not include the response body because it
    may echo back sensitive auth details.
    """
    url = f"{base_url}{AUTH_PATH}"
    try:
        resp = requests.post(url, json={"api_key": api_key}, timeout=timeout)
    except requests.RequestException as e:
        # `from None` suppresses the original traceback so stack traces in logs
        # cannot accidentally leak request internals.
        raise AuthError(f"Auth request failed: {e}") from None

    if resp.status_code != 200:
        # Deliberately omit resp.text — may contain sensitive details.
        raise AuthError(f"Auth failed with HTTP {resp.status_code}")

    try:
        data = resp.json()
        # Shape: { "result": { "customer_name": "...", "delegate_token": "..." } }
        token = data["result"]["delegate_token"]
    except (ValueError, KeyError, TypeError):
        raise AuthError("Auth response did not contain result.delegate_token") from None

    if not isinstance(token, str) or not token:
        raise AuthError("Auth response delegate_token is empty")

    return token


def load_token(path: Path) -> str | None:
    """Return the cached delegate token, or None if unavailable/corrupt.

    Corrupt cache files are treated the same as "no cache" so that a bad file
    never prevents a fresh login from succeeding.
    """
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        token = data.get("delegate_token")
        return token if isinstance(token, str) and token else None
    except (OSError, ValueError):
        return None


def save_token(path: Path, token: str) -> None:
    """Atomically persist the delegate token with owner-only permissions.

    The token is written to a sibling `.tmp` file first, chmod'd to 0600, then
    renamed into place. This avoids any window where the final file exists with
    default (world-readable) permissions.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps({"delegate_token": token}))
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def get_token(cfg: Config, *, force_refresh: bool = False) -> str:
    """High-level helper: return a valid delegate token, using cache when possible.

    Pass `force_refresh=True` to bypass the cache — this is what `ZTBClient`
    does after a 401 response to recover from an expired token.
    """
    if not force_refresh:
        cached = load_token(cfg.token_path)
        if cached:
            return cached
    token = login(cfg.base_url, cfg.api_key)
    save_token(cfg.token_path, token)
    return token
