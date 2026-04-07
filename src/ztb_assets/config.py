"""Configuration loading from environment variables.

Reads `.env` via python-dotenv and exposes an immutable `Config` dataclass.
Raises `ConfigError` on any missing or malformed value so the CLI can exit
cleanly with a dedicated exit code instead of crashing with a traceback.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(Exception):
    """Raised when required environment variables are missing or invalid."""


@dataclass(frozen=True)
class Config:
    # Base URL of the ZTB tenant API, e.g. https://<tenant>-api.goairgap.com.
    base_url: str
    # Raw API key used to obtain a delegate bearer token. Never logged.
    api_key: str
    # On-disk location of the cached delegate token (gitignored, chmod 0600).
    token_path: Path


def load_config() -> Config:
    # load_dotenv() is a no-op if .env is absent, so real env vars still work
    # (useful in CI where secrets may be injected directly).
    load_dotenv()

    # Normalize the base URL: strip whitespace and any trailing slash so callers
    # can safely build URLs via f"{base_url}{path}".
    base_url = os.getenv("ZTB_BASE_URL", "").strip().rstrip("/")
    api_key = os.getenv("ZTB_API_KEY", "").strip()

    if not base_url:
        raise ConfigError("ZTB_BASE_URL is not set. Copy .env.example to .env and fill it in.")
    if not api_key:
        raise ConfigError("ZTB_API_KEY is not set. Copy .env.example to .env and fill it in.")
    # Enforce HTTPS — plaintext transport of an API key or bearer token is a
    # hard no. This is a defensive check; misconfiguration should fail loudly.
    if not base_url.startswith("https://"):
        raise ConfigError(f"ZTB_BASE_URL must use https:// (got: {base_url})")

    # Token path is overridable for tests / alternate deployments, but defaults
    # to .token.json in the current working directory (which is gitignored).
    token_path = Path(os.getenv("ZTB_TOKEN_PATH", ".token.json")).resolve()

    return Config(base_url=base_url, api_key=api_key, token_path=token_path)
