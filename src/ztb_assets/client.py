"""HTTP client for the ZTB API with transparent token refresh on 401.

This wraps a `requests.Session` and is the single point where bearer tokens
are attached to outgoing requests. The core reliability feature is automatic
retry on 401: if the cached delegate token has expired, the first request
will return 401, the client will force a fresh `login()`, and retry the same
request exactly once.

Error messages never include response headers or body text to avoid leaking
bearer tokens into logs.
"""
from __future__ import annotations

from typing import Any

import requests

from . import auth
from .config import Config


class APIError(Exception):
    """Raised when the API returns a non-2xx response (other than the handled 401)."""


class ZTBClient:
    def __init__(self, cfg: Config, *, timeout: float = 30.0) -> None:
        self.cfg = cfg
        self.timeout = timeout
        # A persistent session gives us HTTP keep-alive across paginated calls.
        self.session = requests.Session()
        # Lazy-loaded in-memory copy of the delegate token. We still write it
        # to disk via auth.save_token so other runs can reuse it.
        self._token: str | None = None

    def _auth_headers(self, force_refresh: bool = False) -> dict[str, str]:
        """Return an Authorization header, refreshing the token if needed."""
        if force_refresh or self._token is None:
            self._token = auth.get_token(self.cfg, force_refresh=force_refresh)
        return {"Authorization": f"Bearer {self._token}"}

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """Make an authenticated request, with one-shot 401 retry.

        Any non-2xx status other than the handled 401 raises `APIError`. The
        raised message intentionally excludes response bodies so that auth
        material echoed by the server cannot end up in logs.
        """
        url = f"{self.cfg.base_url}{path}"
        # Default timeout keeps misbehaving servers from hanging the CLI.
        kwargs.setdefault("timeout", self.timeout)

        # Allow callers to pass their own headers, but always overlay the
        # bearer token last so we're certain it is set.
        headers = dict(kwargs.pop("headers", {}) or {})
        headers.update(self._auth_headers())

        resp = self.session.request(method, url, headers=headers, **kwargs)

        # 401 == token expired/invalid. Force a fresh login and retry once.
        # A second 401 after a forced refresh indicates a genuine auth problem
        # (revoked key, etc.) and will fall through to the raise_for_status path.
        if resp.status_code == 401:
            headers.update(self._auth_headers(force_refresh=True))
            resp = self.session.request(method, url, headers=headers, **kwargs)

        if not resp.ok:
            # Do not include resp.text — response bodies can contain tokens.
            raise APIError(f"{method} {path} failed: HTTP {resp.status_code}")

        return resp

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        """Convenience wrapper around request() for GET calls."""
        return self.request("GET", path, **kwargs)
