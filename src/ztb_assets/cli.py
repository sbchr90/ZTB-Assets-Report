"""Command-line entry point.

Orchestrates the top-level flow: load config → build client → fetch assets →
write CSV. Every failure mode maps to a distinct exit code so that this tool
can be used reliably from shell scripts and CI pipelines.

Exit codes:
  0 — success
  1 — config error (missing or invalid .env)
  2 — auth error (API key rejected or login endpoint unreachable)
  3 — API error (non-2xx response after retry, unexpected payload shape)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .assets import fetch_all_assets, write_csv
from .auth import AuthError
from .client import APIError, ZTBClient
from .config import ConfigError, load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ztb-assets",
        description="Fetch discovered devices from Zscaler ZTB and write them to a CSV file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("assets.csv"),
        help="Output CSV path (default: assets.csv)",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=100,
        help="Page size for the devices API (default: 100)",
    )
    # nargs="?" lets the user pass either bare `--html` (uses const default)
    # or `--html my-report.html`. Without the flag, args.html is None.
    parser.add_argument(
        "--html",
        nargs="?",
        const=Path("assets.html"),
        default=None,
        type=Path,
        metavar="PATH",
        help="Also write an interactive HTML report (default path: assets.html).",
    )
    args = parser.parse_args(argv)

    # Each try/except pairs one exception type with one exit code so callers
    # (scripts, CI) can react differently to config vs. auth vs. API errors.
    try:
        cfg = load_config()
    except ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        return 1

    try:
        client = ZTBClient(cfg)
        devices = fetch_all_assets(client, page_size=args.page_size)
    except AuthError as e:
        print(f"Auth error: {e}", file=sys.stderr)
        return 2
    except APIError as e:
        print(f"API error: {e}", file=sys.stderr)
        return 3

    count = write_csv(devices, args.output)
    print(f"Wrote {count} devices to {args.output}")

    if args.html is not None:
        # Local import keeps the default code path's import cost unchanged
        # for users who never use --html.
        from .html_report import write_html

        html_count = write_html(devices, args.html)
        print(f"Wrote {html_count} devices to {args.html}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
