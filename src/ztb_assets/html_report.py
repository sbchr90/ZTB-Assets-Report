"""Generate a self-contained interactive HTML report from device data.

The report embeds the device list as a JSON island inside a `<script>` tag
rather than fetching a sibling CSV. Browsers block `fetch('./assets.csv')`
when an HTML file is opened via `file://` (same-origin policy), so a
self-contained HTML is the only approach that works by simple double-click.

The output is a single HTML file with no external assets, no CDNs, and no
network calls — it can be emailed, dropped on a share, or opened offline.

Features:
  - Sortable, alphabetically ordered columns matching the CSV exactly
  - Per-column free-text filters (case-insensitive substring match)
  - Special "tags" filter: dropdown of every unique tag in the dataset,
    multi-select with AND semantics. Clicking a tag chip inside any row
    also toggles it in the filter.
  - "Reset filters" button
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .assets import flatten_row

TAGS_COLUMN = "tags"


def write_html(
    devices: list[dict[str, Any]],
    out_path: Path,
    *,
    generated_at: datetime | None = None,
) -> int:
    """Render `devices` to a self-contained interactive HTML file.

    Returns the number of devices written. The column set, ordering, and
    cell values mirror what `assets.write_csv` produces, so the HTML and
    CSV reports are always consistent.
    """
    flat_rows = [flatten_row(d) for d in devices]

    # Same column derivation as write_csv: sorted union of all keys.
    columns = sorted({k for row in flat_rows for k in row.keys()})

    # Collect every unique tag token from the tags column. Tag values look
    # like "category:computers,manufacturer:proxmox,..." — split on comma,
    # strip, drop empties, dedupe, sort.
    unique_tags: set[str] = set()
    for row in flat_rows:
        for tag in _split_tags(row.get(TAGS_COLUMN)):
            unique_tags.add(tag)
    tags_sorted = sorted(unique_tags)

    timestamp = (generated_at or datetime.now()).isoformat(timespec="seconds")
    count = len(flat_rows)

    html = _TEMPLATE.format(
        title="ZTB Assets Report",
        generated_at=timestamp,
        count=count,
        columns_json=_safe_json(columns),
        data_json=_safe_json(flat_rows),
        tags_json=_safe_json(tags_sorted),
        tags_column=json.dumps(TAGS_COLUMN),
    )

    out_path.write_text(html, encoding="utf-8")
    return count


def _split_tags(value: Any) -> list[str]:
    """Split a comma-separated tag string into a list of trimmed tokens."""
    if not isinstance(value, str) or not value:
        return []
    return [t.strip() for t in value.split(",") if t.strip()]


def _safe_json(value: Any) -> str:
    """JSON-encode and escape any literal `</` so it cannot break out of <script>.

    Without this, a device field containing the substring `</script>` would
    end the embedded JSON island and corrupt the page. Replacing `</` with
    `<\\/` is safe inside JSON strings (the JSON parser unescapes it back)
    and is the standard mitigation for inline JSON-in-HTML payloads.
    """
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


# Single-file HTML template. Uses str.format() for substitution, so any
# literal `{` / `}` in the JS/CSS must be doubled to `{{` / `}}`.
_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{
    --bg: #f6f7fb;
    --panel: #ffffff;
    --border: #e3e6ef;
    --text: #1d2433;
    --muted: #6b7280;
    --accent: #2563eb;
    --accent-soft: #dbeafe;
    --row-alt: #fafbfd;
    --chip-bg: #eef2ff;
    --chip-text: #3730a3;
    --chip-active-bg: #2563eb;
    --chip-active-text: #ffffff;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    font-size: 14px;
  }}
  header.page {{
    padding: 24px 32px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
  }}
  header.page h1 {{
    margin: 0;
    font-size: 20px;
    font-weight: 600;
  }}
  header.page .meta {{
    color: var(--muted);
    font-size: 13px;
  }}
  header.page .spacer {{ flex: 1; }}
  button.reset {{
    background: var(--accent);
    color: #fff;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 13px;
    cursor: pointer;
  }}
  button.reset:hover {{ background: #1d4ed8; }}

  main {{ padding: 16px 32px 48px; }}

  .table-wrap {{
    overflow: auto;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    max-height: calc(100vh - 160px);
  }}
  table {{
    border-collapse: separate;
    border-spacing: 0;
    width: 100%;
    font-size: 13px;
  }}
  thead th {{
    background: #f1f3f9;
    text-align: left;
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
  }}
  thead th .sort-arrow {{
    color: var(--muted);
    margin-left: 4px;
    font-size: 11px;
  }}
  thead tr.filters th {{
    position: sticky;
    top: 36px;
    background: #f8f9fc;
    padding: 6px 8px;
    border-bottom: 1px solid var(--border);
    cursor: default;
  }}
  thead tr.filters input {{
    width: 100%;
    padding: 4px 8px;
    border: 1px solid var(--border);
    border-radius: 4px;
    font-size: 12px;
    background: #fff;
  }}
  tbody td {{
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
    max-width: 320px;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  tbody tr:nth-child(even) {{ background: var(--row-alt); }}
  tbody tr.hidden {{ display: none; }}

  .tag-chip {{
    display: inline-block;
    background: var(--chip-bg);
    color: var(--chip-text);
    border-radius: 999px;
    padding: 2px 10px;
    margin: 2px 4px 2px 0;
    font-size: 11px;
    cursor: pointer;
    border: 1px solid transparent;
    white-space: nowrap;
  }}
  .tag-chip:hover {{ border-color: var(--accent); }}
  .tag-chip.active {{
    background: var(--chip-active-bg);
    color: var(--chip-active-text);
  }}

  .tag-filter-wrap {{ position: relative; }}
  .tag-filter-btn {{
    width: 100%;
    text-align: left;
    padding: 4px 8px;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: #fff;
    font-size: 12px;
    cursor: pointer;
  }}
  .tag-filter-btn .count {{
    color: var(--muted);
    margin-left: 4px;
  }}
  .tag-filter-panel {{
    display: none;
    position: absolute;
    top: 100%;
    left: 0;
    margin-top: 4px;
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 6px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.08);
    padding: 10px;
    z-index: 10;
    min-width: 280px;
    max-width: 420px;
    max-height: 320px;
    overflow: auto;
  }}
  .tag-filter-panel.open {{ display: block; }}
  .tag-filter-panel .hint {{
    font-size: 11px;
    color: var(--muted);
    margin-bottom: 6px;
  }}

  .empty {{
    padding: 40px;
    text-align: center;
    color: var(--muted);
  }}

  /* Column visibility — hides matching <th> and every <td> in that column. */
  [data-col-hidden] {{ display: none !important; }}

  .cols-wrap {{ position: relative; }}
  .cols-btn {{
    background: #fff;
    color: var(--text);
    border: 1px solid var(--border);
    padding: 8px 14px;
    border-radius: 6px;
    font-size: 13px;
    cursor: pointer;
  }}
  .cols-btn:hover {{ border-color: var(--accent); }}
  .cols-panel {{
    display: none;
    position: absolute;
    top: 100%;
    right: 0;
    margin-top: 6px;
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 6px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.08);
    padding: 10px;
    z-index: 10;
    min-width: 240px;
    max-height: 60vh;
    overflow: auto;
  }}
  .cols-panel.open {{ display: block; }}
  .cols-panel .row-buttons {{
    display: flex;
    gap: 6px;
    margin-bottom: 8px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }}
  .cols-panel .row-buttons button {{
    flex: 1;
    font-size: 11px;
    padding: 5px;
    background: #f1f3f9;
    border: 1px solid var(--border);
    border-radius: 4px;
    cursor: pointer;
  }}
  .cols-panel .row-buttons button:hover {{ background: #e5e9f3; }}
  .cols-panel label {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 2px;
    font-size: 12px;
    cursor: pointer;
    user-select: none;
  }}
  .cols-panel label:hover {{ color: var(--accent); }}

  /* ---- Tabs ---------------------------------------------------------- */
  nav.tabs {{
    display: flex;
    gap: 4px;
    padding: 0 32px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
  }}
  .tab {{
    background: none;
    border: none;
    padding: 12px 18px;
    font-size: 14px;
    cursor: pointer;
    color: var(--muted);
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
  }}
  .tab:hover {{ color: var(--text); }}
  .tab.active {{
    color: var(--accent);
    border-bottom-color: var(--accent);
    font-weight: 600;
  }}
  .tab-panel {{ display: none; }}
  .tab-panel.active {{ display: block; }}
  /* Hide list-only header controls when the report tab is active. */
  body[data-active-tab="report"] .cols-wrap,
  body[data-active-tab="report"] #reset-btn {{ display: none; }}

  /* ---- Stat cards (Assets Report header row) ------------------------ */
  .stat-row {{
    display: flex;
    gap: 16px;
    margin-bottom: 16px;
    flex-wrap: wrap;
  }}
  .stat-card {{
    flex: 0 0 auto;
    min-width: 200px;
    padding: 16px 24px;
  }}
  .stat-card .label {{
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--muted);
  }}
  .stat-card .value {{
    font-size: 32px;
    font-weight: 600;
    color: var(--text);
    margin-top: 4px;
    line-height: 1.1;
  }}
  .stat-card .value.warn {{ color: #ef4444; }}

  /* ---- Report tab (cards + charts) ----------------------------------- */
  .report-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
    gap: 16px;
  }}
  .card {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
  }}
  .card h2 {{
    margin: 0 0 16px;
    font-size: 15px;
    font-weight: 600;
  }}
  .chart-empty {{
    color: var(--muted);
    font-style: italic;
    padding: 30px 10px;
    text-align: center;
  }}
  .pie-wrap {{
    display: flex;
    align-items: center;
    gap: 20px;
    flex-wrap: wrap;
  }}
  .pie-wrap svg {{ flex-shrink: 0; }}
  .pie-wrap svg path {{
    cursor: pointer;
    stroke: var(--panel);
    stroke-width: 2;
    transition: opacity 0.15s;
  }}
  .pie-wrap svg path:hover {{ opacity: 0.8; }}
  .legend {{
    list-style: none;
    margin: 0;
    padding: 0;
    font-size: 12px;
    flex: 1;
    min-width: 140px;
  }}
  .legend li {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 0;
    cursor: pointer;
  }}
  .legend li:hover {{ color: var(--accent); }}
  .legend .swatch {{
    width: 12px;
    height: 12px;
    border-radius: 2px;
    flex-shrink: 0;
  }}
  .legend .label {{ flex: 1; }}
  .legend .count {{ color: var(--muted); }}
  /* Split-legend variant: two legend columns flanking the pie. */
  .pie-wrap.split {{ justify-content: center; }}
  .pie-wrap .legend-left {{ text-align: right; }}
  .pie-wrap .legend-left li {{ flex-direction: row-reverse; }}
  .pie-wrap .legend-left li,
  .pie-wrap .legend-right li {{ min-width: 0; }}
  .pie-wrap .legend .label.truncate {{
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 140px;
    display: inline-block;
  }}

  .bar-chart svg {{
    width: 100%;
    max-width: 440px;
    height: auto;
    display: block;
  }}
  .bar-chart .bar {{
    cursor: pointer;
    transition: opacity 0.15s;
  }}
  .bar-chart .bar:hover {{ opacity: 0.8; }}
  .bar-chart text {{ font-size: 12px; fill: var(--text); }}
  .bar-chart text.count {{ fill: var(--muted); }}

  /* ---- Synthetic OS filter banner ------------------------------------ */
  /* Note: use :not([hidden]) so the explicit display value doesn't
     override the user-agent [hidden] display:none rule. */
  #os-filter-banner:not([hidden]),
  #location-filter-banner:not([hidden]),
  #manufacturer-filter-banner:not([hidden]),
  #protection-filter-banner:not([hidden]) {{
    margin-bottom: 8px;
    margin-right: 8px;
    padding: 8px 14px;
    background: var(--accent-soft);
    border: 1px solid var(--accent);
    border-radius: 6px;
    font-size: 13px;
    color: var(--chip-text);
    display: inline-flex;
    align-items: center;
    gap: 10px;
  }}
  #os-filter-banner button,
  #location-filter-banner button,
  #manufacturer-filter-banner button,
  #protection-filter-banner button {{
    background: none;
    border: none;
    color: inherit;
    cursor: pointer;
    font-size: 16px;
    line-height: 1;
    padding: 0 4px;
  }}
  #os-filter-banner button:hover,
  #location-filter-banner button:hover,
  #manufacturer-filter-banner button:hover,
  #protection-filter-banner button:hover {{ color: #1d4ed8; }}
</style>
</head>
<body data-active-tab="report">
<header class="page">
  <h1>{title}</h1>
  <div class="meta">
    Generated <time>{generated_at}</time> &middot;
    <strong id="visible-count">{count}</strong> / {count} devices
  </div>
  <div class="spacer"></div>
  <div class="cols-wrap">
    <button type="button" class="cols-btn" id="cols-btn">Columns &#9662;</button>
    <div class="cols-panel" id="cols-panel"></div>
  </div>
  <button class="reset" id="reset-btn">Reset filters</button>
</header>

<nav class="tabs">
  <button type="button" class="tab active" data-tab="report" id="tab-report">Assets Report</button>
  <button type="button" class="tab" data-tab="list" id="tab-list">Assets List</button>
</nav>

<main>
  <section class="tab-panel active" id="panel-report">
    <div class="stat-row">
      <section class="card stat-card" id="stat-total">
        <div class="label">Total devices</div>
        <div class="value">&mdash;</div>
      </section>
      <section class="card stat-card" id="stat-quarantined">
        <div class="label">Quarantined</div>
        <div class="value">&mdash;</div>
      </section>
    </div>
    <div class="report-grid">
      <section class="card">
        <h2>Operating systems</h2>
        <div id="chart-os"></div>
      </section>
      <section class="card">
        <h2>Top 10 manufacturers</h2>
        <div id="chart-mfr"></div>
      </section>
      <section class="card">
        <h2>Devices by Site</h2>
        <div id="chart-sites"></div>
      </section>
      <section class="card">
        <h2>Protection Status</h2>
        <div id="chart-protection"></div>
      </section>
    </div>
  </section>

  <section class="tab-panel" id="panel-list">
    <div id="os-filter-banner" hidden></div>
    <div id="location-filter-banner" hidden></div>
    <div id="manufacturer-filter-banner" hidden></div>
    <div id="protection-filter-banner" hidden></div>
    <div class="table-wrap">
      <table id="assets-table">
        <thead>
          <tr id="header-row"></tr>
          <tr class="filters" id="filter-row"></tr>
        </thead>
        <tbody id="rows"></tbody>
      </table>
      <div class="empty" id="empty-msg" hidden>No devices match the current filters.</div>
    </div>
  </section>
</main>

<noscript>
  <p style="padding:32px;text-align:center;color:#b91c1c;">
    This report needs JavaScript enabled to display the device table and filters.
  </p>
</noscript>

<script id="ztb-data" type="application/json">{data_json}</script>
<script id="ztb-columns" type="application/json">{columns_json}</script>
<script id="ztb-tags" type="application/json">{tags_json}</script>

<script>
(function () {{
  "use strict";

  const TAGS_COLUMN = {tags_column};
  const data = JSON.parse(document.getElementById("ztb-data").textContent);
  const columns = JSON.parse(document.getElementById("ztb-columns").textContent);
  const allTags = JSON.parse(document.getElementById("ztb-tags").textContent);

  const headerRow = document.getElementById("header-row");
  const filterRow = document.getElementById("filter-row");
  const tbody = document.getElementById("rows");
  const visibleCount = document.getElementById("visible-count");
  const emptyMsg = document.getElementById("empty-msg");
  const resetBtn = document.getElementById("reset-btn");

  // Active state shared across handlers.
  const filterInputs = {{}};   // column name -> <input>
  const activeTags = new Set();
  let sortColumn = null;
  let sortDir = 1;             // 1 = asc, -1 = desc
  let workingRows = data.slice();
  // Synthetic OS filter set by clicking a pie slice. null when inactive.
  // Bypasses the regular tag dropdown so that clicking the "Linux" slice
  // catches all distros (debian, ubuntu, ...) folded into that bucket.
  let activeOSFilter = null;
  // Synthetic location filter set by clicking a Sites pie slice. Exact
  // match against row.location, so "HQ" never collides with "HQ-Branch".
  let activeLocationFilter = null;
  // Synthetic manufacturer filter set by clicking a manufacturer bar.
  let activeManufacturerFilter = null;
  // Synthetic protection filter set by clicking a Protection Status slice.
  let activeProtectionFilter = null;

  // Column-visibility state. Persisted in localStorage so the viewer's
  // preference survives a page refresh. Stale entries (columns that no
  // longer exist in this report) are filtered out on load.
  const STORAGE_KEY = "ztb-assets:hidden-columns";
  function loadHiddenColumns() {{
    try {{
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    }} catch (e) {{
      return [];
    }}
  }}
  function saveHiddenColumns() {{
    try {{
      localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(hiddenColumns)));
    }} catch (e) {{ /* private mode / disabled — silently no-op */ }}
  }}
  const hiddenColumns = new Set(loadHiddenColumns().filter(c => columns.includes(c)));

  function escapeHtml(s) {{
    if (s === null || s === undefined) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }}

  function splitTags(value) {{
    if (!value) return [];
    return String(value).split(",").map(t => t.trim()).filter(Boolean);
  }}

  // ---- OS normalization (shared by chart and filter) -------------------
  // Linux distributions are folded into a single "linux" bucket so the
  // pie chart isn't fragmented and clicking the Linux slice catches every
  // distro the dataset contains.
  const LINUX_DISTROS = new Set([
    "linux", "debian", "ubuntu", "fedora", "centos", "rhel", "redhat",
    "arch", "alpine", "suse", "opensuse", "kali", "mint", "rocky"
  ]);
  // Priority used to pick a single bucket per device when multiple
  // operating_system tags are present (e.g. linux + debian).
  const OS_PRIORITY = ["linux", "windows", "macos", "ios", "android"];
  const OS_LABELS = {{
    linux: "Linux",
    windows: "Windows",
    macos: "macOS",
    ios: "iOS",
    android: "Android",
    unknown: "Unknown",
  }};
  const PIE_PALETTE = [
    "#2563eb", "#10b981", "#f59e0b", "#ef4444",
    "#8b5cf6", "#ec4899", "#14b8a6", "#6b7280"
  ];

  function osLabel(bucket) {{
    return OS_LABELS[bucket] || (bucket.charAt(0).toUpperCase() + bucket.slice(1));
  }}

  function normalizedOS(row) {{
    // Collect every operating_system:* tag value, lowercased and folded
    // through LINUX_DISTROS. Returns the highest-priority bucket key, or
    // "unknown" when the row has no operating_system tag at all.
    const buckets = new Set();
    splitTags(row[TAGS_COLUMN]).forEach(tag => {{
      if (!tag.startsWith("operating_system:")) return;
      const raw = tag.slice("operating_system:".length).trim().toLowerCase();
      if (!raw) return;
      buckets.add(LINUX_DISTROS.has(raw) ? "linux" : raw);
    }});
    if (buckets.size === 0) return "unknown";
    for (const p of OS_PRIORITY) {{
      if (buckets.has(p)) return p;
    }}
    // Stable fallback for unknown OSes — first alphabetical.
    return Array.from(buckets).sort()[0];
  }}

  function buildHeaders() {{
    columns.forEach(col => {{
      const th = document.createElement("th");
      th.dataset.col = col;
      th.textContent = col;
      const arrow = document.createElement("span");
      arrow.className = "sort-arrow";
      arrow.textContent = "";
      th.appendChild(arrow);
      th.addEventListener("click", () => onSort(col, arrow));
      headerRow.appendChild(th);

      const fth = document.createElement("th");
      fth.dataset.col = col;
      if (col === TAGS_COLUMN) {{
        fth.appendChild(buildTagFilter());
      }} else {{
        const input = document.createElement("input");
        input.type = "text";
        input.placeholder = "Filter\u2026";
        input.addEventListener("input", applyFilters);
        filterInputs[col] = input;
        fth.appendChild(input);
      }}
      filterRow.appendChild(fth);
    }});
  }}

  function buildTagFilter() {{
    const wrap = document.createElement("div");
    wrap.className = "tag-filter-wrap";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tag-filter-btn";
    btn.innerHTML = "Tags<span class='count' id='tag-filter-count'></span>";

    const panel = document.createElement("div");
    panel.className = "tag-filter-panel";
    panel.id = "tag-filter-panel";

    const hint = document.createElement("div");
    hint.className = "hint";
    hint.textContent = "Click tags to filter (matches rows containing ALL selected).";
    panel.appendChild(hint);

    allTags.forEach(tag => {{
      const chip = document.createElement("span");
      chip.className = "tag-chip";
      chip.dataset.tag = tag;
      chip.textContent = tag;
      chip.addEventListener("click", e => {{
        e.stopPropagation();
        toggleTag(tag);
      }});
      panel.appendChild(chip);
    }});

    btn.addEventListener("click", e => {{
      e.stopPropagation();
      panel.classList.toggle("open");
    }});
    document.addEventListener("click", e => {{
      if (!panel.contains(e.target) && e.target !== btn) {{
        panel.classList.remove("open");
      }}
    }});

    wrap.appendChild(btn);
    wrap.appendChild(panel);
    return wrap;
  }}

  function toggleTag(tag) {{
    if (activeTags.has(tag)) activeTags.delete(tag);
    else activeTags.add(tag);
    syncTagChipStates();
    applyFilters();
  }}

  function syncTagChipStates() {{
    document.querySelectorAll(".tag-chip").forEach(el => {{
      if (activeTags.has(el.dataset.tag)) el.classList.add("active");
      else el.classList.remove("active");
    }});
    const counter = document.getElementById("tag-filter-count");
    if (counter) counter.textContent = activeTags.size ? "(" + activeTags.size + ")" : "";
  }}

  function onSort(col, arrowEl) {{
    if (sortColumn === col) {{
      sortDir = -sortDir;
    }} else {{
      sortColumn = col;
      sortDir = 1;
    }}
    document.querySelectorAll(".sort-arrow").forEach(el => {{ el.textContent = ""; }});
    arrowEl.textContent = sortDir === 1 ? "\u25B2" : "\u25BC";

    workingRows.sort((a, b) => {{
      const av = a[col] === null || a[col] === undefined ? "" : String(a[col]);
      const bv = b[col] === null || b[col] === undefined ? "" : String(b[col]);
      return av.localeCompare(bv, undefined, {{ numeric: true, sensitivity: "base" }}) * sortDir;
    }});
    renderRows();
  }}

  function rowMatchesFilters(row) {{
    // Synthetic OS filter (driven by the OS pie chart click).
    if (activeOSFilter !== null && normalizedOS(row) !== activeOSFilter) {{
      return false;
    }}
    // Synthetic location filter (driven by the Sites pie chart click).
    // Exact match; empty/missing location maps to "Unknown".
    if (activeLocationFilter !== null) {{
      const loc = (row.location === null || row.location === undefined || row.location === "")
        ? "Unknown"
        : String(row.location);
      if (loc !== activeLocationFilter) return false;
    }}
    // Synthetic manufacturer filter (driven by the bar chart click).
    if (activeManufacturerFilter !== null) {{
      const mfr = splitTags(row[TAGS_COLUMN])
        .find(t => t.startsWith("manufacturer:"));
      const mfrName = mfr ? mfr.slice("manufacturer:".length).trim() : "";
      if (mfrName !== activeManufacturerFilter) return false;
    }}
    // Synthetic protection filter (driven by Protection Status chart).
    if (activeProtectionFilter !== null) {{
      const prot = (row.protection === null || row.protection === undefined || String(row.protection).trim() === "")
        ? "unknown"
        : String(row.protection).trim().toLowerCase();
      if (prot !== activeProtectionFilter) return false;
    }}
    // Per-column substring filters
    for (const col of columns) {{
      if (col === TAGS_COLUMN) continue;
      const input = filterInputs[col];
      if (!input || !input.value) continue;
      const cell = row[col] === null || row[col] === undefined ? "" : String(row[col]);
      if (!cell.toLowerCase().includes(input.value.toLowerCase())) return false;
    }}
    // Tag filter (AND semantics)
    if (activeTags.size > 0) {{
      const rowTags = new Set(splitTags(row[TAGS_COLUMN]));
      for (const tag of activeTags) {{
        if (!rowTags.has(tag)) return false;
      }}
    }}
    return true;
  }}

  function renderRows() {{
    tbody.innerHTML = "";
    let visible = 0;
    workingRows.forEach(row => {{
      if (!rowMatchesFilters(row)) return;
      visible++;
      const tr = document.createElement("tr");
      columns.forEach(col => {{
        const td = document.createElement("td");
        td.dataset.col = col;
        const value = row[col];
        if (col === TAGS_COLUMN) {{
          splitTags(value).forEach(tag => {{
            const chip = document.createElement("span");
            chip.className = "tag-chip" + (activeTags.has(tag) ? " active" : "");
            chip.dataset.tag = tag;
            chip.textContent = tag;
            chip.addEventListener("click", e => {{
              e.stopPropagation();
              toggleTag(tag);
            }});
            td.appendChild(chip);
          }});
        }} else {{
          td.textContent = value === null || value === undefined ? "" : String(value);
        }}
        tr.appendChild(td);
      }});
      tbody.appendChild(tr);
    }});
    visibleCount.textContent = visible;
    emptyMsg.hidden = visible !== 0;
    // Re-apply column visibility because tbody was rebuilt from scratch and
    // the new <td> elements don't carry the [data-col-hidden] marker yet.
    applyColumnVisibility();
  }}

  function applyFilters() {{ renderRows(); }}

  // ---- Column visibility -------------------------------------------------

  function applyColumnVisibility() {{
    // For every column, mark or unmark every header / filter / body cell
    // with [data-col-hidden] in one pass. CSS does the actual hiding.
    columns.forEach(col => {{
      const hide = hiddenColumns.has(col);
      document
        .querySelectorAll('[data-col="' + cssEscape(col) + '"]')
        .forEach(el => {{
          if (hide) el.setAttribute("data-col-hidden", "");
          else el.removeAttribute("data-col-hidden");
        }});
    }});
  }}

  // Minimal CSS attribute-selector escape for column names. The CSV columns
  // we generate are simple identifiers (letters, digits, dot, underscore),
  // but this keeps us safe if a future ZTB schema introduces special chars.
  function cssEscape(value) {{
    if (window.CSS && typeof window.CSS.escape === "function") {{
      return window.CSS.escape(value);
    }}
    return String(value).replace(/(["\\\\])/g, "\\\\$1");
  }}

  function buildColumnsPanel() {{
    const panel = document.getElementById("cols-panel");
    const btn = document.getElementById("cols-btn");
    panel.innerHTML = "";

    // Show all / Hide all convenience row.
    const buttonRow = document.createElement("div");
    buttonRow.className = "row-buttons";
    const showAll = document.createElement("button");
    showAll.type = "button";
    showAll.textContent = "Show all";
    showAll.addEventListener("click", () => {{
      hiddenColumns.clear();
      saveHiddenColumns();
      applyColumnVisibility();
      syncCheckboxes();
    }});
    const hideAll = document.createElement("button");
    hideAll.type = "button";
    hideAll.textContent = "Hide all";
    hideAll.addEventListener("click", () => {{
      columns.forEach(c => hiddenColumns.add(c));
      saveHiddenColumns();
      applyColumnVisibility();
      syncCheckboxes();
    }});
    buttonRow.appendChild(showAll);
    buttonRow.appendChild(hideAll);
    panel.appendChild(buttonRow);

    // One checkbox per column.
    const checkboxes = {{}};
    columns.forEach(col => {{
      const label = document.createElement("label");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = !hiddenColumns.has(col);
      cb.addEventListener("change", () => {{
        if (cb.checked) hiddenColumns.delete(col);
        else hiddenColumns.add(col);
        saveHiddenColumns();
        applyColumnVisibility();
      }});
      const span = document.createElement("span");
      span.textContent = col;
      label.appendChild(cb);
      label.appendChild(span);
      panel.appendChild(label);
      checkboxes[col] = cb;
    }});

    function syncCheckboxes() {{
      columns.forEach(col => {{ checkboxes[col].checked = !hiddenColumns.has(col); }});
    }}

    // Open / close behavior mirroring the tag-filter dropdown.
    btn.addEventListener("click", e => {{
      e.stopPropagation();
      panel.classList.toggle("open");
    }});
    document.addEventListener("click", e => {{
      if (!panel.contains(e.target) && e.target !== btn) {{
        panel.classList.remove("open");
      }}
    }});
  }}

  // ---- Tabs --------------------------------------------------------------

  function switchTab(name) {{
    document.body.dataset.activeTab = name;
    document.querySelectorAll(".tab").forEach(b => {{
      b.classList.toggle("active", b.dataset.tab === name);
    }});
    document.querySelectorAll(".tab-panel").forEach(p => {{
      p.classList.toggle("active", p.id === "panel-" + name);
    }});
  }}

  function wireTabs() {{
    document.querySelectorAll(".tab").forEach(b => {{
      b.addEventListener("click", () => switchTab(b.dataset.tab));
    }});
  }}

  // ---- Synthetic OS filter banner ----------------------------------------

  function setOSFilter(bucket) {{
    // Toggle: clicking the same bucket clears it.
    if (activeOSFilter === bucket) {{
      activeOSFilter = null;
    }} else {{
      activeOSFilter = bucket;
    }}
    updateOSBanner();
    applyFilters();
  }}

  function clearOSFilter() {{
    activeOSFilter = null;
    updateOSBanner();
    applyFilters();
  }}

  function updateOSBanner() {{
    const banner = document.getElementById("os-filter-banner");
    if (activeOSFilter === null) {{
      banner.hidden = true;
      banner.textContent = "";
      return;
    }}
    banner.hidden = false;
    banner.innerHTML = "";
    const text = document.createElement("span");
    text.textContent = "Filtered by OS: " + osLabel(activeOSFilter);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.setAttribute("aria-label", "Clear OS filter");
    btn.textContent = "\u2715";
    btn.addEventListener("click", clearOSFilter);
    banner.appendChild(text);
    banner.appendChild(btn);
  }}

  // ---- Synthetic location filter (driven by the Sites chart) ------------

  function setLocationFilter(site) {{
    // Toggle: clicking the same site clears it.
    activeLocationFilter = (activeLocationFilter === site) ? null : site;
    updateLocationBanner();
    applyFilters();
  }}

  function clearLocationFilter() {{
    activeLocationFilter = null;
    updateLocationBanner();
    applyFilters();
  }}

  function updateLocationBanner() {{
    const banner = document.getElementById("location-filter-banner");
    if (activeLocationFilter === null) {{
      banner.hidden = true;
      banner.textContent = "";
      return;
    }}
    banner.hidden = false;
    banner.innerHTML = "";
    const text = document.createElement("span");
    text.textContent = "Filtered by Site: " + activeLocationFilter;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.setAttribute("aria-label", "Clear site filter");
    btn.textContent = "\u2715";
    btn.addEventListener("click", clearLocationFilter);
    banner.appendChild(text);
    banner.appendChild(btn);
  }}

  // ---- Charts ------------------------------------------------------------

  function emptyChart(container, msg) {{
    container.innerHTML = "";
    const div = document.createElement("div");
    div.className = "chart-empty";
    div.textContent = msg;
    container.appendChild(div);
  }}

  function buildOSChart() {{
    const container = document.getElementById("chart-os");
    if (!data.length) {{ emptyChart(container, "No devices to chart."); return; }}

    // Count one bucket per device using normalizedOS().
    const counts = new Map();
    data.forEach(row => {{
      const b = normalizedOS(row);
      counts.set(b, (counts.get(b) || 0) + 1);
    }});

    // Sort descending by count, then collapse the long tail to "Other".
    let entries = Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
    const MAX_NAMED = 7;
    if (entries.length > MAX_NAMED) {{
      const head = entries.slice(0, MAX_NAMED);
      const tail = entries.slice(MAX_NAMED);
      const otherCount = tail.reduce((s, e) => s + e[1], 0);
      head.push(["__other__", otherCount]);
      entries = head;
    }}

    const total = entries.reduce((s, e) => s + e[1], 0);
    const SIZE = 200;
    const R = 90;
    const CX = SIZE / 2;
    const CY = SIZE / 2;

    container.innerHTML = "";
    const wrap = document.createElement("div");
    wrap.className = "pie-wrap";

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 " + SIZE + " " + SIZE);
    svg.setAttribute("width", SIZE);
    svg.setAttribute("height", SIZE);

    let cumulative = 0;
    const slicePaths = [];
    entries.forEach((entry, i) => {{
      const [bucket, count] = entry;
      const frac = count / total;
      const startAngle = cumulative * 2 * Math.PI - Math.PI / 2;
      cumulative += frac;
      const endAngle = cumulative * 2 * Math.PI - Math.PI / 2;

      const x1 = CX + R * Math.cos(startAngle);
      const y1 = CY + R * Math.sin(startAngle);
      const x2 = CX + R * Math.cos(endAngle);
      const y2 = CY + R * Math.sin(endAngle);
      const largeArc = frac > 0.5 ? 1 : 0;

      let d;
      if (entries.length === 1) {{
        // Single full circle — can't draw a 360° arc with one path command.
        d = "M " + (CX - R) + " " + CY +
            " a " + R + " " + R + " 0 1 0 " + (R * 2) + " 0" +
            " a " + R + " " + R + " 0 1 0 " + (-R * 2) + " 0 Z";
      }} else {{
        d = "M " + CX + " " + CY +
            " L " + x1 + " " + y1 +
            " A " + R + " " + R + " 0 " + largeArc + " 1 " + x2 + " " + y2 +
            " Z";
      }}

      const color = PIE_PALETTE[i % PIE_PALETTE.length];
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", d);
      path.setAttribute("fill", color);
      const label = bucket === "__other__" ? "Other" : osLabel(bucket);
      const pct = ((count / total) * 100).toFixed(1);
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = label + ": " + count + " (" + pct + "%)";
      path.appendChild(title);
      // "Other" is not clickable — it doesn't map to a single bucket.
      if (bucket !== "__other__") {{
        path.addEventListener("click", () => {{
          setOSFilter(bucket);
          switchTab("list");
        }});
      }} else {{
        path.style.cursor = "default";
      }}
      svg.appendChild(path);
      slicePaths.push({{ bucket, count, label, color, pct }});
    }});

    wrap.appendChild(svg);

    // Legend mirrors the slice list — also clickable for non-Other entries.
    const legend = document.createElement("ul");
    legend.className = "legend";
    slicePaths.forEach(s => {{
      const li = document.createElement("li");
      const sw = document.createElement("span");
      sw.className = "swatch";
      sw.style.background = s.color;
      const lbl = document.createElement("span");
      lbl.className = "label";
      lbl.textContent = s.label;
      const cnt = document.createElement("span");
      cnt.className = "count";
      cnt.textContent = s.count + " (" + s.pct + "%)";
      li.appendChild(sw);
      li.appendChild(lbl);
      li.appendChild(cnt);
      if (s.bucket !== "__other__") {{
        li.addEventListener("click", () => {{
          setOSFilter(s.bucket);
          switchTab("list");
        }});
      }} else {{
        li.style.cursor = "default";
      }}
      legend.appendChild(li);
    }});
    wrap.appendChild(legend);
    container.appendChild(wrap);
  }}

  function buildManufacturerChart() {{
    const container = document.getElementById("chart-mfr");
    if (!data.length) {{ emptyChart(container, "No devices to chart."); return; }}

    // First manufacturer:* tag per device. Devices with no manufacturer
    // tag are skipped — they would just add noise to the bar chart.
    const counts = new Map();
    data.forEach(row => {{
      const mfr = splitTags(row[TAGS_COLUMN])
        .find(t => t.startsWith("manufacturer:"));
      if (!mfr) return;
      const name = mfr.slice("manufacturer:".length).trim();
      if (!name) return;
      counts.set(name, (counts.get(name) || 0) + 1);
    }});

    if (counts.size === 0) {{
      emptyChart(container, "No manufacturer tags found.");
      return;
    }}

    const entries = Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10);
    const max = entries[0][1];

    container.innerHTML = "";
    const wrap = document.createElement("div");
    wrap.className = "bar-chart";

    // Widened label column so long brand names ("proxmox server
    // solutions", "raspberry pi foundation") get full room. Names above
    // MAX_CHARS are wrapped onto a second line at a space boundary so
    // the chart is pushed further right without clipping the label.
    const ROW_H = 40;
    const LABEL_W = 200;
    const COUNT_W = 36;
    const PAD_R = 10;
    const totalW = 440;
    const barAreaW = totalW - LABEL_W - COUNT_W - PAD_R;
    const totalH = entries.length * ROW_H + 8;
    const BAR_H = 16;
    const MAX_CHARS = 18;

    function wrapLabel(name) {{
      // 1 line if short enough, else split at the last space before
      // MAX_CHARS (hard-split if no space), truncate line 2 if still long.
      if (name.length <= MAX_CHARS) return [name];
      let splitAt = name.lastIndexOf(" ", MAX_CHARS);
      if (splitAt <= 0) splitAt = MAX_CHARS;
      const line1 = name.slice(0, splitAt).trim();
      let line2 = name.slice(splitAt).trim();
      if (line2.length > MAX_CHARS) {{
        line2 = line2.slice(0, MAX_CHARS - 1) + "\u2026";
      }}
      return [line1, line2];
    }}

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 " + totalW + " " + totalH);
    svg.setAttribute("preserveAspectRatio", "xMinYMin meet");

    entries.forEach((entry, i) => {{
      const [name, count] = entry;
      const rowTop = i * ROW_H + 4;
      const rowMid = rowTop + ROW_H / 2;
      const barW = Math.max(2, (count / max) * barAreaW);

      const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      g.setAttribute("class", "bar");

      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("x", LABEL_W - 10);
      label.setAttribute("text-anchor", "end");
      const lines = wrapLabel(name);
      if (lines.length === 1) {{
        label.setAttribute("y", rowMid + 4);
        label.textContent = lines[0];
      }} else {{
        // Two-line layout: first baseline above the row center, second
        // 14px below. Each tspan gets its own x so right-alignment works.
        label.setAttribute("y", rowMid - 4);
        const t1 = document.createElementNS("http://www.w3.org/2000/svg", "tspan");
        t1.setAttribute("x", LABEL_W - 10);
        t1.textContent = lines[0];
        label.appendChild(t1);
        const t2 = document.createElementNS("http://www.w3.org/2000/svg", "tspan");
        t2.setAttribute("x", LABEL_W - 10);
        t2.setAttribute("dy", "14");
        t2.textContent = lines[1];
        label.appendChild(t2);
      }}
      const titleEl = document.createElementNS("http://www.w3.org/2000/svg", "title");
      titleEl.textContent = name + ": " + count;
      label.appendChild(titleEl);
      g.appendChild(label);

      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("x", LABEL_W);
      rect.setAttribute("y", rowMid - BAR_H / 2);
      rect.setAttribute("width", barW);
      rect.setAttribute("height", BAR_H);
      rect.setAttribute("rx", 3);
      rect.setAttribute("fill", "#2563eb");
      const rectTitle = document.createElementNS("http://www.w3.org/2000/svg", "title");
      rectTitle.textContent = name + ": " + count;
      rect.appendChild(rectTitle);
      g.appendChild(rect);

      const cnt = document.createElementNS("http://www.w3.org/2000/svg", "text");
      cnt.setAttribute("class", "count");
      cnt.setAttribute("x", LABEL_W + barW + 6);
      cnt.setAttribute("y", rowMid + 4);
      cnt.textContent = count;
      g.appendChild(cnt);

      g.addEventListener("click", () => {{
        setManufacturerFilter(name);
        switchTab("list");
      }});

      svg.appendChild(g);
    }});

    wrap.appendChild(svg);
    container.appendChild(wrap);
  }}

  function buildTotalStat() {{
    const el = document.querySelector("#stat-total .value");
    if (el) el.textContent = data.length.toLocaleString();
  }}

  function buildQuarantinedStat() {{
    const el = document.querySelector("#stat-quarantined .value");
    if (!el) return;
    const count = data.filter(r => {{
      const v = r.is_quarantined;
      return v === true || v === "true" || v === 1 || v === "1";
    }}).length;
    el.textContent = count.toLocaleString();
    if (count > 0) el.classList.add("warn");
  }}

  // ---- Synthetic manufacturer filter (driven by the bar chart) ----------

  function setManufacturerFilter(name) {{
    activeManufacturerFilter = (activeManufacturerFilter === name) ? null : name;
    updateManufacturerBanner();
    applyFilters();
  }}

  function clearManufacturerFilter() {{
    activeManufacturerFilter = null;
    updateManufacturerBanner();
    applyFilters();
  }}

  function updateManufacturerBanner() {{
    const banner = document.getElementById("manufacturer-filter-banner");
    if (activeManufacturerFilter === null) {{
      banner.hidden = true;
      banner.textContent = "";
      return;
    }}
    banner.hidden = false;
    banner.innerHTML = "";
    const text = document.createElement("span");
    text.textContent = "Filtered by Manufacturer: " + activeManufacturerFilter;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.setAttribute("aria-label", "Clear manufacturer filter");
    btn.textContent = "\u2715";
    btn.addEventListener("click", clearManufacturerFilter);
    banner.appendChild(text);
    banner.appendChild(btn);
  }}

  // ---- Synthetic protection filter (driven by Protection Status chart) --

  function setProtectionFilter(value) {{
    activeProtectionFilter = (activeProtectionFilter === value) ? null : value;
    updateProtectionBanner();
    applyFilters();
  }}

  function clearProtectionFilter() {{
    activeProtectionFilter = null;
    updateProtectionBanner();
    applyFilters();
  }}

  function updateProtectionBanner() {{
    const banner = document.getElementById("protection-filter-banner");
    if (activeProtectionFilter === null) {{
      banner.hidden = true;
      banner.textContent = "";
      return;
    }}
    banner.hidden = false;
    banner.innerHTML = "";
    const text = document.createElement("span");
    text.textContent = "Filtered by Protection: " + activeProtectionFilter;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.setAttribute("aria-label", "Clear protection filter");
    btn.textContent = "\u2715";
    btn.addEventListener("click", clearProtectionFilter);
    banner.appendChild(text);
    banner.appendChild(btn);
  }}

  // Semantic color maps for security-posture charts.
  const PROTECTION_COLORS = {{
    on: "#10b981",
    off: "#ef4444",
    monitor: "#f59e0b",
    unknown: "#6b7280",
  }};
  // Generic pie builder for simple column-count charts (Protection
  // Status). Renders into `container` with an optional semantic
  // color map. Slices are clickable via the synthetic protection filter.
  function buildColumnPie(container, colName, colorMap) {{
    if (!data.length) {{ emptyChart(container, "No devices to chart."); return; }}
    const hasCol = data.some(r => Object.prototype.hasOwnProperty.call(r, colName));
    if (!hasCol) {{ emptyChart(container, "No " + colName + " data available."); return; }}

    const counts = new Map();
    data.forEach(row => {{
      const raw = row[colName];
      const val = (raw === null || raw === undefined || String(raw).trim() === "")
        ? "unknown"
        : String(raw).trim().toLowerCase();
      counts.set(val, (counts.get(val) || 0) + 1);
    }});

    let entries = Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
    const MAX_NAMED = 7;
    if (entries.length > MAX_NAMED) {{
      const head = entries.slice(0, MAX_NAMED);
      const tail = entries.slice(MAX_NAMED);
      head.push(["__other__", tail.reduce((s, e) => s + e[1], 0)]);
      entries = head;
    }}

    const total = entries.reduce((s, e) => s + e[1], 0);
    const SIZE = 200;
    const R = 90;
    const CX = SIZE / 2;
    const CY = SIZE / 2;

    container.innerHTML = "";
    const wrap = document.createElement("div");
    wrap.className = "pie-wrap";

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 " + SIZE + " " + SIZE);
    svg.setAttribute("width", SIZE);
    svg.setAttribute("height", SIZE);

    let cumulative = 0;
    const sliceMeta = [];
    entries.forEach((entry, i) => {{
      const [bucket, count] = entry;
      const frac = count / total;
      const startAngle = cumulative * 2 * Math.PI - Math.PI / 2;
      cumulative += frac;
      const endAngle = cumulative * 2 * Math.PI - Math.PI / 2;

      const x1 = CX + R * Math.cos(startAngle);
      const y1 = CY + R * Math.sin(startAngle);
      const x2 = CX + R * Math.cos(endAngle);
      const y2 = CY + R * Math.sin(endAngle);
      const largeArc = frac > 0.5 ? 1 : 0;

      let d;
      if (entries.length === 1) {{
        d = "M " + (CX - R) + " " + CY +
            " a " + R + " " + R + " 0 1 0 " + (R * 2) + " 0" +
            " a " + R + " " + R + " 0 1 0 " + (-R * 2) + " 0 Z";
      }} else {{
        d = "M " + CX + " " + CY +
            " L " + x1 + " " + y1 +
            " A " + R + " " + R + " 0 " + largeArc + " 1 " + x2 + " " + y2 +
            " Z";
      }}

      const color = (bucket !== "__other__" && colorMap[bucket])
        ? colorMap[bucket]
        : PIE_PALETTE[i % PIE_PALETTE.length];
      const label = bucket === "__other__" ? "Other" : bucket;
      const pct = ((count / total) * 100).toFixed(1);

      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", d);
      path.setAttribute("fill", color);
      const titleEl = document.createElementNS("http://www.w3.org/2000/svg", "title");
      titleEl.textContent = label + ": " + count + " (" + pct + "%)";
      path.appendChild(titleEl);
      if (bucket !== "__other__") {{
        path.addEventListener("click", () => {{ setProtectionFilter(label); switchTab("list"); }});
      }} else {{
        path.style.cursor = "default";
      }}
      svg.appendChild(path);
      sliceMeta.push({{ bucket, label, color, count, pct }});
    }});

    wrap.appendChild(svg);

    const legend = document.createElement("ul");
    legend.className = "legend";
    sliceMeta.forEach(s => {{
      const li = document.createElement("li");
      const sw = document.createElement("span");
      sw.className = "swatch";
      sw.style.background = s.color;
      const lbl = document.createElement("span");
      lbl.className = "label";
      lbl.textContent = s.label;
      const cnt = document.createElement("span");
      cnt.className = "count";
      cnt.textContent = s.count + " (" + s.pct + "%)";
      li.appendChild(sw);
      li.appendChild(lbl);
      li.appendChild(cnt);
      if (s.bucket !== "__other__") {{
        li.addEventListener("click", () => {{ setProtectionFilter(s.label); switchTab("list"); }});
      }} else {{
        li.style.cursor = "default";
      }}
      legend.appendChild(li);
    }});
    wrap.appendChild(legend);
    container.appendChild(wrap);
  }}

  function buildProtectionChart() {{
    buildColumnPie(
      document.getElementById("chart-protection"),
      "protection",
      PROTECTION_COLORS
    );
  }}

  // Deterministic color for slice i out of `total` total slices. HSL
  // spread is used instead of a fixed palette because the Sites chart
  // can render up to 21 slices (top 20 + Other).
  function hslColor(i, total) {{
    const hue = Math.floor((i * 360) / Math.max(total, 1));
    return "hsl(" + hue + ", 65%, 55%)";
  }}

  function buildSitesChart() {{
    const container = document.getElementById("chart-sites");
    if (!data.length) {{ emptyChart(container, "No devices to chart."); return; }}

    // Defensive: if no row has a location field at all, skip the chart.
    const hasLocationKey = data.some(r => Object.prototype.hasOwnProperty.call(r, "location"));
    if (!hasLocationKey) {{
      emptyChart(container, "No location data available.");
      return;
    }}

    // Count locations. Empty / null / missing → "Unknown".
    const counts = new Map();
    data.forEach(row => {{
      const raw = row.location;
      const name = (raw === null || raw === undefined || String(raw).trim() === "")
        ? "Unknown"
        : String(raw).trim();
      counts.set(name, (counts.get(name) || 0) + 1);
    }});

    // Sort descending, keep top 20, collapse the rest into "Other".
    let entries = Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
    const MAX_NAMED = 20;
    if (entries.length > MAX_NAMED) {{
      const head = entries.slice(0, MAX_NAMED);
      const tail = entries.slice(MAX_NAMED);
      const otherCount = tail.reduce((s, e) => s + e[1], 0);
      head.push(["__other__", otherCount]);
      entries = head;
    }}

    const total = entries.reduce((s, e) => s + e[1], 0);
    const SIZE = 220;
    const R = 100;
    const CX = SIZE / 2;
    const CY = SIZE / 2;

    container.innerHTML = "";
    const wrap = document.createElement("div");
    wrap.className = "pie-wrap split";

    // Left legend populated before the SVG, right legend after.
    const leftLegend = document.createElement("ul");
    leftLegend.className = "legend legend-left";
    const rightLegend = document.createElement("ul");
    rightLegend.className = "legend legend-right";

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 " + SIZE + " " + SIZE);
    svg.setAttribute("width", SIZE);
    svg.setAttribute("height", SIZE);

    let cumulative = 0;
    const sliceMeta = [];
    entries.forEach((entry, i) => {{
      const [bucket, count] = entry;
      const frac = count / total;
      const startAngle = cumulative * 2 * Math.PI - Math.PI / 2;
      cumulative += frac;
      const endAngle = cumulative * 2 * Math.PI - Math.PI / 2;

      const x1 = CX + R * Math.cos(startAngle);
      const y1 = CY + R * Math.sin(startAngle);
      const x2 = CX + R * Math.cos(endAngle);
      const y2 = CY + R * Math.sin(endAngle);
      const largeArc = frac > 0.5 ? 1 : 0;

      let d;
      if (entries.length === 1) {{
        // Single full circle — can't draw a 360° arc with one path command.
        d = "M " + (CX - R) + " " + CY +
            " a " + R + " " + R + " 0 1 0 " + (R * 2) + " 0" +
            " a " + R + " " + R + " 0 1 0 " + (-R * 2) + " 0 Z";
      }} else {{
        d = "M " + CX + " " + CY +
            " L " + x1 + " " + y1 +
            " A " + R + " " + R + " 0 " + largeArc + " 1 " + x2 + " " + y2 +
            " Z";
      }}

      const color = hslColor(i, entries.length);
      const label = bucket === "__other__" ? "Other" : bucket;
      const pct = ((count / total) * 100).toFixed(1);

      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", d);
      path.setAttribute("fill", color);
      const titleEl = document.createElementNS("http://www.w3.org/2000/svg", "title");
      titleEl.textContent = label + ": " + count + " (" + pct + "%)";
      path.appendChild(titleEl);
      if (bucket !== "__other__") {{
        path.addEventListener("click", () => {{
          setLocationFilter(label);
          switchTab("list");
        }});
      }} else {{
        path.style.cursor = "default";
      }}
      svg.appendChild(path);

      sliceMeta.push({{ bucket, label, color, count, pct }});
    }});

    // Split: first half of the sorted slices on the left, rest on the
    // right. "Other", if present, is the last entry of `entries` and
    // therefore lands on the right side naturally.
    const mid = Math.ceil(sliceMeta.length / 2);
    sliceMeta.forEach((s, i) => {{
      const li = document.createElement("li");
      const sw = document.createElement("span");
      sw.className = "swatch";
      sw.style.background = s.color;
      const lbl = document.createElement("span");
      lbl.className = "label truncate";
      lbl.textContent = s.label;
      lbl.title = s.label;
      const cnt = document.createElement("span");
      cnt.className = "count";
      cnt.textContent = s.count;
      li.appendChild(sw);
      li.appendChild(lbl);
      li.appendChild(cnt);
      if (s.bucket !== "__other__") {{
        li.addEventListener("click", () => {{
          setLocationFilter(s.label);
          switchTab("list");
        }});
      }} else {{
        li.style.cursor = "default";
      }}
      (i < mid ? leftLegend : rightLegend).appendChild(li);
    }});

    wrap.appendChild(leftLegend);
    wrap.appendChild(svg);
    wrap.appendChild(rightLegend);
    container.appendChild(wrap);
  }}

  // ---- Boot --------------------------------------------------------------

  resetBtn.addEventListener("click", () => {{
    Object.values(filterInputs).forEach(i => {{ i.value = ""; }});
    activeTags.clear();
    activeOSFilter = null;
    activeLocationFilter = null;
    activeManufacturerFilter = null;
    activeProtectionFilter = null;
    updateOSBanner();
    updateLocationBanner();
    updateManufacturerBanner();
    updateProtectionBanner();
    syncTagChipStates();
    applyFilters();
  }});

  buildHeaders();
  renderRows();
  buildColumnsPanel();
  applyColumnVisibility();
  buildTotalStat();
  buildQuarantinedStat();
  buildOSChart();
  buildManufacturerChart();
  buildSitesChart();
  buildProtectionChart();
  wireTabs();
}})();
</script>
</body>
</html>
"""
