"""Fetch discovered devices (assets) and write them to CSV.

ZTB calls its discovered devices "assets" in the UI, but the API surfaces
them as "devices" under `/api/v2/devices/active` (or `/api/v3/device`).
This module paginates through the endpoint and flattens the resulting rows
into a CSV file.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable

from .client import APIError, ZTBClient

# Swagger: /api/v2/devices/active → DeviceGetResponseDto
# Response envelope: { "result": { "count": int, "rows": [ { ...device... }, ... ] } }
ASSETS_PATH = "/api/v2/devices/active"


def fetch_all_assets(client: ZTBClient, *, page_size: int = 100) -> list[dict[str, Any]]:
    """Page through /api/v2/devices/active until exhausted.

    Termination rule: stop as soon as a page returns fewer than `page_size`
    rows. This means the last full page costs one extra request, which is
    acceptable and avoids having to trust a `count` field we haven't observed.
    """
    # The ZTB API uses 0-indexed pagination — page=1 skips the first page of
    # results entirely, so we start at 0.
    all_rows: list[dict[str, Any]] = []
    page = 0
    while True:
        resp = client.get(ASSETS_PATH, params={"page": page, "limit": page_size})
        try:
            payload = resp.json()
        except ValueError:
            raise APIError(f"{ASSETS_PATH} returned non-JSON body")

        # Be defensive: a missing `result` key should not crash the CLI.
        result = payload.get("result") or {}
        rows = result.get("rows") or []
        if not isinstance(rows, list):
            raise APIError(f"{ASSETS_PATH} result.rows is not a list")

        all_rows.extend(rows)

        # Short page → last page. Done.
        if len(rows) < page_size:
            break
        page += 1

    return all_rows


def flatten_row(row: dict[str, Any]) -> dict[str, Any]:
    """Flatten one level of nested dicts so the output stays tabular.

    Example: {"a": {"b": 1}, "c": 2}  →  {"a.b": 1, "c": 2}

    Deeper structures (nested dicts-in-dicts, lists, list-of-dicts) are kept
    as single cells via `repr()`. This preserves the information without
    inventing extra columns — good enough for a report CSV.
    """
    flat: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                flat[f"{key}.{sub_key}"] = _stringify(sub_value)
        else:
            flat[key] = _stringify(value)
    return flat


def _stringify(value: Any) -> Any:
    """Collapse complex cell values to a repr string; leave scalars alone."""
    if isinstance(value, (dict, list)):
        return repr(value)
    return value


def write_csv(devices: Iterable[dict[str, Any]], out_path: Path) -> int:
    """Write flattened devices to `out_path` and return the row count.

    The column set is the stable-sorted union of keys across all rows, which
    makes the output resilient to schema drift — if ZTB adds/removes optional
    fields, the CSV just gains or loses columns without blowing up.
    """
    flat_rows = [flatten_row(d) for d in devices]
    if not flat_rows:
        # No devices → write an empty file rather than leaving a stale one.
        out_path.write_text("")
        return 0

    columns = sorted({k for row in flat_rows for k in row.keys()})
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in flat_rows:
            writer.writerow(row)
    return len(flat_rows)
