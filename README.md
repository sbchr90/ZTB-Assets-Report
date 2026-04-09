# 🛡️ ZTB Assets Report

> Export your **Zscaler Zero Trust Branch** discovered devices ("assets") to a clean CSV file — in one command. 📊

A lightweight Python CLI that connects to the Zero Trust Branch API, fetches every device your tenant has discovered, and writes the results to a tidy CSV report. Perfect for periodic inventory snapshots, compliance evidence, or feeding into your own reporting pipeline.

---

## 📖 Contents

- [Why this tool](#-why-this-tool)
- [Requirements](#-requirements)
- [Quick start](#-quick-start)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Output format](#-output-format)
- [Scalability](#-scalability)
- [Security](#-security)
- [Troubleshooting](#-troubleshooting)
- [License](#-license)

---

## 🎯 Why this tool

The Zero Trust Branch console lets you browse discovered devices in the UI, but there's no one-click CSV export for automated workflows. This CLI fills that gap:

- ⚡ **Zero-friction exports** — one command, one CSV file
- 🔁 **Repeatable & scriptable** — ideal for cron jobs, CI pipelines, or ad-hoc reports
- 🔐 **Handles auth for you** — authenticates with your API key, caches the short-lived bearer token, and refreshes it automatically when it expires
- 📋 **Schema-resilient** — if ZTB adds or removes optional device fields, the CSV columns just follow along

---

## 📋 Requirements

| Requirement      | Version / Detail                                   |
|------------------|----------------------------------------------------|
| 🐍 Python         | **3.14 or newer**                                 |
| 📦 uv             | Install from [astral.sh/uv](https://docs.astral.sh/uv/) |
| 🔑 ZTB API key    | Must have permission to list devices              |
| 🌐 Tenant URL     | e.g. `https://<tenant>-api.goairgap.com`          |

> 💡 **How do I get an API key?** In the Zero Trust Branch console, go to **Settings → API Keys** and generate a new key. Copy it immediately — you won't be able to see it again.

---

## 🚀 Quick start

```bash
# 1. Clone and enter the project
git clone <this-repo-url>
cd ZTB-assets-report

# 2. Install dependencies
uv sync

# 3. Configure your credentials
cp .env.example .env
$EDITOR .env       # fill in ZTB_BASE_URL and ZTB_API_KEY

# 4. Run it
uv run ztb-assets
```

You should see:

```
Wrote 42 devices to assets.csv
```

That's it — your report is at `./assets.csv`. 🎉

---

## ⚙️ Configuration

All configuration lives in a local `.env` file. The provided `.env.example` is a ready-to-edit template.

| Variable          | Required | Default         | Description                                                           |
|-------------------|:--------:|-----------------|-----------------------------------------------------------------------|
| `ZTB_BASE_URL`    | ✅        | —               | Your tenant's API base URL. Must begin with `https://`.               |
| `ZTB_API_KEY`     | ✅        | —               | The API key you generated in the ZTB console.                         |
| `ZTB_TOKEN_PATH`  | ❌        | `./.token.json` | Where to cache the short-lived bearer token between runs.             |

> 🔒 **Keep your `.env` private.** It is excluded from git by default. Never commit it, paste it into chat tools, or share it in screenshots.

---

## 🕹️ Usage

### Basic

```bash
uv run ztb-assets
```

Writes `assets.csv` in the current directory.

### All options

```
usage: ztb-assets [-h] [-o OUTPUT] [--page-size PAGE_SIZE] [--html [PATH]]

Fetch discovered devices from Zscaler ZTB and write them to a CSV file.

options:
  -h, --help            show this help message and exit
  -o, --output OUTPUT   Output CSV path (default: assets.csv)
  --page-size PAGE_SIZE Page size for the devices API (default: 100)
  --html [PATH]         Also write an interactive HTML report
                        (default path: assets.html)
```

### 🌐 Interactive HTML report

Pass `--html` to generate a self-contained, browser-friendly report alongside the CSV:

```bash
uv run ztb-assets --html                       # writes assets.csv AND assets.html
uv run ztb-assets --html report.html           # custom HTML path
uv run ztb-assets --html report.html -o report.csv
```

The report has two tabs:

**📊 Assets Report** (default) — visual summary of your fleet:

- 🥧 **OS pie chart** — one slice per operating system, built from `operating_system:*` tags. Linux distributions (debian, ubuntu, fedora, …) are folded into a single `Linux` bucket so the chart isn't fragmented.
- 📊 **Top 10 manufacturers** — horizontal bar chart of the most common `manufacturer:*` tags.
- 👆 **Click-through filtering** — click any pie slice or bar to jump to the **Assets List** tab pre-filtered to just those devices. A banner shows the active OS filter and lets you clear it.

**📋 Assets List** — the full interactive device table:

- 🔍 **Per-column filtering** — type into any column header to live-filter rows (case-insensitive substring match)
- 🏷️ **Smart tag filter** — the `tags` column gets a dropdown listing every unique tag in your dataset. Click tags to filter; multiple selected tags use **AND** semantics ("computers + linux" shows only Linux computers)
- 👆 **Click-to-filter chips** — click any tag chip directly inside a table row to add it to the filter (click again to remove)
- 🔃 **Sortable columns** — click any column header to sort ascending / descending
- 👁️ **Column visibility** — open the **Columns** menu to hide noisy columns. Your selection is remembered across reloads via `localStorage`.
- ♻️ **Reset filters** — one click clears every active filter (per-column, tag, and OS).

**Both tabs share:**

- 📦 **Single-file & offline** — the entire dataset is embedded inside the HTML, so the file works by simple double-click without any web server. Perfect for emailing or archiving.
- 🚫 **No external assets** — no CDNs, fonts, or trackers. Everything is bundled in one HTML file.

### 💡 Examples

**Write to a dated file** — handy for daily snapshots:

```bash
uv run ztb-assets -o "reports/ztb-assets-$(date +%F).csv"
```

**Use a larger page size** — fewer round-trips for big tenants:

```bash
uv run ztb-assets --page-size 500
```

**Run on a schedule** — example cron entry that exports every day at 06:00:

```cron
0 6 * * * cd /opt/ZTB-assets-report && /usr/local/bin/uv run ztb-assets -o "/var/log/ztb/assets-$(date +\%F).csv"
```

### 🚦 Exit codes

The CLI uses distinct exit codes so it behaves well in automation:

| Code | Meaning       | Typical cause                                              |
|-----:|---------------|------------------------------------------------------------|
|  `0` | ✅ Success     | CSV written successfully                                   |
|  `1` | ⚙️ Config      | `.env` missing, blank values, or non-`https://` base URL   |
|  `2` | 🔐 Auth        | API key rejected or login endpoint unreachable             |
|  `3` | 🌐 API         | Non-2xx response after retry, or unexpected payload shape  |

---

## 📄 Output format

The generated CSV contains one row per discovered device. Columns are built from the union of all fields returned by the API and sorted alphabetically, so the file stays consistent even if ZTB changes optional fields in a future release.

Typical columns include:

`id`, `hostname`, `ip_address`, `mac`, `vendor`, `type`, `location`, `network_name`, `network_display_name`, `status`, `protection`, `is_quarantined`, `tags`, `createdAt`, `updatedAt`, …

Nested objects are flattened one level deep using dot notation (e.g. `finger_banks.device_name`). Deeper structures are serialized into a single cell so the CSV stays strictly tabular and opens cleanly in Excel, Numbers, Google Sheets, or `pandas`.

When `--html` is used, the HTML report mirrors the CSV exactly: same columns, same flattening, same values — just rendered as an interactive table.

---

## 📏 Scalability

The **CSV export** scales comfortably into the hundreds of thousands of devices — generation is linear, finishes in seconds, and the resulting file opens cleanly in Excel, Numbers, Google Sheets, or `pandas`. If your tenant is very large, stick with CSV.

The **interactive HTML report** embeds the full dataset inline and renders every row into the DOM, so it's best suited for small-to-mid-size fleets. Rough guidance:

| Devices     | HTML experience                                                        |
|------------:|------------------------------------------------------------------------|
|   ≤ 5,000   | 🟢 Fully responsive — filter, sort, and tab switching feel instant.   |
|   ~10,000   | 🟡 Still usable. Filter typing and sorting show mild lag.             |
|   ~25,000   | 🟠 Soft limit. Filter/sort becomes noticeably sluggish; file ~20 MB.  |
|   ≥ 50,000  | 🔴 Not recommended. File exceeds ~40 MB and the table feels stuck.    |

> 💡 If you only need the HTML report for a specific subset of a very large tenant, generate the CSV first, narrow it down in your tool of choice, and run the HTML report against a smaller export — or simply live with CSV-only for the whole fleet.

---

## 🔒 Security

This tool is built to handle secrets responsibly:

- 🔐 **HTTPS required** — plain `http://` URLs are rejected at startup
- 💾 **Secure token cache** — the bearer token is written atomically to `.token.json` with `chmod 0600` (owner read/write only)
- 🙈 **No secret leakage in logs** — error messages never include response bodies, headers, or request payloads that could contain tokens
- 🗑️ **Sensible `.gitignore`** — `.env`, `.token.json`, and `*.csv` are excluded from version control out of the box
- 🚫 **No secrets on the command line** — your API key is read from the environment only, never passed as a CLI argument

**If you think a token has been compromised:** delete `.token.json` (and rotate the API key in the ZTB console) — the next run will authenticate fresh.

---

## 🧰 Troubleshooting

<details>
<summary><strong>❌ <code>Config error: ZTB_BASE_URL is not set</code></strong></summary>

You haven't created `.env` yet, or the variable is blank. Run `cp .env.example .env` and fill in both values.
</details>

<details>
<summary><strong>❌ <code>Config error: ZTB_BASE_URL must use https://</code></strong></summary>

The base URL validation is strict on purpose. Make sure your URL begins with `https://`, not `http://`.
</details>

<details>
<summary><strong>❌ <code>Auth error: Auth failed with HTTP 401</code></strong></summary>

Your API key is invalid, expired, or revoked. Generate a new one in the ZTB console (**Settings → API Keys**) and update `ZTB_API_KEY` in your `.env` file.
</details>

<details>
<summary><strong>❌ <code>API error: ... failed: HTTP 401</code> (even after retry)</strong></summary>

The client already refreshed the bearer token and still got a `401`. This usually means the API key is valid but lacks the permission to list devices. Ask your ZTB administrator to grant the required role.
</details>

<details>
<summary><strong>🤔 The CSV is empty</strong></summary>

No devices were returned. Double-check that:
1. You're pointed at the correct tenant in `ZTB_BASE_URL`.
2. The same tenant shows devices in the ZTB console.
3. Your API key has permission to read devices.
</details>

<details>
<summary><strong>♻️ How do I force a fresh login?</strong></summary>

Delete the cached token and rerun:

```bash
rm .token.json
uv run ztb-assets
```
</details>

<details>
<summary><strong>🐢 The script feels slow on a large tenant</strong></summary>

Increase the page size to reduce the number of round-trips:

```bash
uv run ztb-assets --page-size 500
```
</details>

---

## 📜 License

This project is distributed as-is, without warranty of any kind. Review your organization's policies before using it in production.

---

Made with 🐍, ☕ and a healthy respect for zero trust.
