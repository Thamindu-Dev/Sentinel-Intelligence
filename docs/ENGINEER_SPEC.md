# SENTINEL INTELLIGENCE — Full Engineer Specification
### Cyber Threat Intelligence (CTI) Automated Pipeline & Dashboard
**Version**: 1.1 | **Audience**: AI Software Engineer | **Stack**: Python + FastAPI + SQLite + Vanilla JS
**Deployment Target**: Oracle Cloud Infrastructure (OCI) Ubuntu 22.04 LTS — accessed privately over **Tailscale VPN**

---

## 0. Dashboard Preview

> The target look-and-feel is a premium SOC-style dark dashboard.
> See: `sentinel_preview.html` for an interactive mockup.

---

## 1. Project Overview

Build a **fully automated, zero-noise CTI pipeline** that:

1. Scrapes and analyses live cybersecurity threat data from authoritative sources every hour.
2. Passes raw content through **Gemini API (gemma-4-26b-it)** to extract structured intelligence.
3. Stores deduplicated findings in **SQLite** with a strict 7-day retention policy.
4. Exposes the data via a **FastAPI** REST layer.
5. Displays everything in a **premium dark-themed dashboard** (Vanilla JS, no frameworks).

**Core Constraints:**
- No alerts or push notifications — silent background operation.
- No duplicate findings — one entry per CVE/threat, sources aggregated.
- Data older than 7 days is permanently deleted on every collector run.
- All intelligence is sourced externally — the LLM only **analyses** scraped content, never generates threats from its own knowledge.

---

## 2. Repository Structure

```
sentinel/
├── backend/
│   ├── collector/
│   │   ├── __init__.py
│   │   ├── collector.py        # Main orchestrator — runs hourly via cron
│   │   ├── sources.py          # Source definitions & scraping logic
│   │   ├── analyzer.py         # LLM analysis via Gemini API
│   │   └── deduplicator.py     # CVE/title normalisation + dedup logic
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app entry point
│   │   ├── routes.py           # All API route definitions
│   │   ├── models.py           # Pydantic request/response schemas
│   │   └── auth.py             # Simple API key middleware
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py         # SQLite connection + init
│   │   └── schema.sql          # Table definitions
│   ├── config.py               # Central config (env vars, constants)
│   ├── requirements.txt
│   └── sentinel.db             # Auto-created SQLite database (gitignored)
├── frontend/
│   ├── index.html              # Main dashboard page
│   ├── css/
│   │   └── main.css            # Custom design system (no Tailwind CDN in prod)
│   └── js/
│       ├── app.js              # Main entry point, state management
│       ├── api.js              # All fetch calls to the backend API
│       ├── components.js       # Card & stat-bar renderers
│       └── filters.js          # Client-side filter logic
├── docs/
│   ├── ENGINEER_SPEC.md        # This file
│   ├── sentinel_preview.html   # UI mockup reference
│   └── sentinel_spec.md        # Original brief
├── scripts/
│   └── setup_cron.sh           # Helper to install the hourly cron job
├── .env.example                # Template for environment variables
├── .gitignore
└── README.md
```

---

## 3. Environment & Configuration

### 3.1 `.env.example`
```
# Gemini / Google AI Studio
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemma-4-26b-it

# API Security
API_KEY=change_me_to_a_random_32_char_string

# Server — bind to Tailscale interface IP (find with: ip addr show tailscale0)
# Set to 0.0.0.0 to listen on all interfaces (Tailscale firewall is the perimeter)
API_HOST=0.0.0.0
API_PORT=8000

# Tailscale — your machine's Tailscale IP (100.x.x.x), used for CORS
# Run `tailscale ip -4` on the server to get this value
TAILSCALE_IP=100.x.x.x

# Database — use absolute path for cron reliability
DB_PATH=/home/ubuntu/sentinel/sentinel.db

# Frontend static files directory (served by FastAPI)
FRONTEND_DIR=/home/ubuntu/sentinel/frontend

# Retention
RETENTION_DAYS=7
```

### 3.2 `config.py`
- Load all values from `.env` using `python-dotenv`.
- Expose a single `Settings` object imported everywhere.
- Fail fast with a clear error if `GEMINI_API_KEY` is missing.
- Derive `ALLOWED_ORIGINS` from `TAILSCALE_IP`: build a list `["http://{TAILSCALE_IP}", "http://{TAILSCALE_IP}:8000", "http://localhost:8000", "http://127.0.0.1:8000"]`.

---

## 4. Backend — Collector Pipeline

### 4.1 Sources (`backend/collector/sources.py`)

Define a `SOURCE_LIST` — a list of dicts, each with:
```python
{
    "name": "CISA KEV",
    "url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
    "type": "html",          # or "rss" or "json_api"
    "selector": "article",   # CSS selector for HTML sources
}
```

**Mandatory sources to include:**

| Name | URL | Type |
|---|---|---|
| NIST NVD (Recent CVEs) | `https://nvd.nist.gov/vuln/full-listing` | html |
| CISA KEV | `https://www.cisa.gov/known-exploited-vulnerabilities-catalog` | html |
| BleepingComputer | `https://www.bleepingcomputer.com/feed/` | rss |
| The Hacker News | `https://feeds.feedburner.com/TheHackersNews` | rss |
| Krebs on Security | `https://krebsonsecurity.com/feed/` | rss |
| Google Project Zero | `https://googleprojectzero.blogspot.com/feeds/posts/default` | rss |

**Scraping rules:**
- Use `httpx` (async) with a 10-second timeout and `User-Agent: SentinelBot/1.0`.
- For `html` sources: use `BeautifulSoup` to extract title + body text of each article/listing entry.
- For `rss` sources: use `feedparser` to get entries. Extract `title`, `link`, `summary`, `published`.
- Return a normalised list of `RawItem` dataclasses: `{title, url, raw_text, source_name, fetched_at}`.
- Catch per-source exceptions silently — log to file, do not crash the whole run.

### 4.2 Analyser (`backend/collector/analyzer.py`)

For each `RawItem`, call Gemini to extract structured intelligence.

**Prompt Template:**
```
You are a cybersecurity analyst. Analyse the following threat intelligence content and extract structured data.
Content: {raw_text}
Source URL: {url}

Return ONLY a valid JSON object with these exact fields:
{
  "severity": "<Critical|High|Medium|Low>",
  "impact": "<RCE|LPE|SQLi|XSS|DoS|Zero-day|Phishing|Data Breach|Supply Chain|Other>",
  "summary": "<Exactly 2 sentences. Sentence 1: what the vulnerability is. Sentence 2: what the impact is.>",
  "target": "<Affected software/hardware and version numbers>",
  "cve_id": "<CVE-YYYY-NNNNN if present, else null>",
  "is_critical_field": <true if this is a legitimate, significant security finding, false if it is news, opinion, or not a direct threat>
}
Do not add any explanation outside the JSON block.
```

- Use `google-generativeai` Python SDK.
- If `is_critical_field` is `false`, **discard the item** — do not write to DB.
- Handle JSON parse failures gracefully: log and skip.
- Rate-limit Gemini calls to **max 20 per minute** using `asyncio.Semaphore`.

### 4.3 Deduplicator (`backend/collector/deduplicator.py`)

This is the core dedup logic. A finding is considered a duplicate if:

1. **CVE ID match**: Both have the same non-null `cve_id`. **OR**
2. **Title similarity**: Normalized titles (lowercase, strip punctuation, collapse whitespace) have a **Levenshtein similarity ≥ 85%** using `rapidfuzz`.

**Dedup behaviour:**
- If a match is found in the DB: **append** the new source URL to the existing `sources` JSON array. Update `timestamp` to now. Do NOT create a new row.
- If no match found: create a new row.
- Always prevent exact URL duplicates within the `sources` array of a single finding.

### 4.4 Main Collector (`backend/collector/collector.py`)

This is the script run by cron every hour.

**Execution flow:**
```
1. Log "Collector run started at {timestamp}"
2. For each source in SOURCE_LIST:
   a. Scrape raw items
   b. For each raw item: call analyser
   c. If valid finding: run deduplicator → upsert to DB
3. Run retention cleanup: DELETE WHERE timestamp < now - 7 days
4. Log "Collector run complete. New: {n}. Updated: {n}. Deleted: {n}. Errors: {n}."
```

- All DB writes use transactions. Rollback on error.
- Write a rotating log to `./logs/collector.log` (max 5MB, keep 3 backups).
- The script must be fully self-contained — runnable as `python collector.py` directly.

---

## 5. Backend — Database (`backend/db/`)

### 5.1 Schema (`schema.sql`)

```sql
CREATE TABLE IF NOT EXISTS findings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cve_id      TEXT,
    timestamp   DATETIME NOT NULL DEFAULT (datetime('now')),
    title       TEXT NOT NULL,
    severity    TEXT NOT NULL CHECK(severity IN ('Critical','High','Medium','Low')),
    impact      TEXT NOT NULL,
    summary     TEXT NOT NULL,
    target      TEXT NOT NULL,
    sources     TEXT NOT NULL DEFAULT '[]',   -- JSON array of {name, url} objects
    status      TEXT NOT NULL DEFAULT 'New' CHECK(status IN ('New','Reviewed'))
);

CREATE INDEX IF NOT EXISTS idx_severity  ON findings(severity);
CREATE INDEX IF NOT EXISTS idx_timestamp ON findings(timestamp);
CREATE INDEX IF NOT EXISTS idx_cve_id    ON findings(cve_id);
```

### 5.2 `database.py`

- Use Python's built-in `sqlite3` module. No ORM.
- Provide functions: `get_connection()`, `init_db()`, `get_all_findings(severity=None)`, `upsert_finding(data)`, `update_status(id, status)`, `purge_old_findings()`.
- `init_db()` must be called on API startup and before every collector run.
- Use `row_factory = sqlite3.Row` so results serialize to dicts easily.

---

## 6. Backend — API Layer (`backend/api/`)

### 6.1 Authentication (`auth.py`)

Simple API key via HTTP header:
```
X-API-Key: <value from API_KEY env var>
```
Use a FastAPI `Security` dependency. Return `403` if missing or incorrect.
Apply to **all routes** globally.

### 6.2 Routes (`routes.py`)

#### `GET /api/findings`
- Query params: `severity` (optional, one of Critical|High|Medium|Low), `status` (optional, New|Reviewed), `limit` (optional, default 100, max 500).
- Returns: JSON array of finding objects, sorted by `timestamp DESC`.
- Response model includes all DB fields. `sources` is returned as a parsed list, not a raw JSON string.

#### `PATCH /api/findings/{id}`
- Body: `{"status": "Reviewed"}` (only `Reviewed` is a valid transition from `New`).
- Returns: the updated finding object.
- Returns `404` if ID not found.

#### `GET /api/stats`
- Returns counts grouped by severity for the last 7 days:
```json
{
  "critical": 2,
  "high": 7,
  "medium": 14,
  "low": 9,
  "total": 32,
  "last_updated": "2026-06-12T10:45:00Z"
}
```

#### `GET /api/health`
- Returns `{"status": "ok", "db_reachable": true}`. No auth required.

### 6.3 CORS
- Allowed origins are derived from `config.py` at startup — includes the Tailscale IP and localhost.
- Allow methods: `GET`, `PATCH`, `OPTIONS`.
- Allow headers: `X-API-Key`, `Content-Type`.

### 6.4 Static Frontend Serving
FastAPI must also serve the `frontend/` directory as static files so the user only needs **one port** open.
```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Serve frontend static assets
app.mount("/static", StaticFiles(directory=settings.FRONTEND_DIR), name="static")

@app.get("/", include_in_schema=False)
async def serve_dashboard():
    return FileResponse(f"{settings.FRONTEND_DIR}/index.html")
```
Frontend `api.js` should use a **relative API base**: `const API_BASE = "/api"` (same origin, no CORS needed from dashboard → API).

### 6.5 Running the API
```bash
# Development
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload

# Production (via systemd — see Section 8.2)
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --workers 1
```
Access the dashboard from your laptop at: `http://<tailscale-ip>:8000/`

---

## 7. Frontend Dashboard (`frontend/`)

### 7.1 Design Specification

| Token | Value |
|---|---|
| Background | `#0a0f1e` |
| Surface (cards) | `#111827` |
| Surface raised | `#1a2035` |
| Border | `#1f2d45` |
| Text primary | `#e2e8f0` |
| Text secondary | `#94a3b8` |
| Accent (cyan) | `#06b6d4` |
| Critical | `#ef4444` |
| High | `#f97316` |
| Medium | `#eab308` |
| Low | `#3b82f6` |
| Font | `'Inter', system-ui, sans-serif` (loaded from Google Fonts) |
| Mono font | `'JetBrains Mono', monospace` |

**Effects:**
- Severity-colored left border on all finding cards (4px solid).
- Subtle box-shadow glow on stat cards matching severity color (`box-shadow: 0 0 20px rgba(color, 0.15)`).
- Card hover: `translateY(-2px)` + brighter border.
- LIVE indicator: pulsing green dot (CSS `@keyframes` pulse animation).
- Smooth fade-in on page load for the finding cards (staggered, 50ms delay per card).

### 7.2 Layout (`index.html`)

```
┌─────────────────────────────────────────────────┐
│  SENTINEL INTELLIGENCE ●LIVE        [Last Sync] │  ← Header
├─────────────────────────────────────────────────┤
│  [CRITICAL: 02] [HIGH: 07] [MEDIUM: 14] [LOW: 09] │  ← Stat Bar
├─────────────────────────────────────────────────┤
│  [All] [Critical] [High] [Medium] [Low] [New] [Reviewed] │  ← Filters
├─────────────────────────────────────────────────┤
│ ▌ CRITICAL  CVE-2026-4451: RCE in LDAP...       │
│             Summary text...                     │
│             Impact: RCE  |  Target: Win Server  │
│             Sources: [NIST NVD] [CISA KEV]  [✓ Mark Reviewed] │
│─────────────────────────────────────────────────│
│ ▌ HIGH      CVE-2026-3892: Linux Kernel LPE...  │  ← Finding Cards
│─────────────────────────────────────────────────│
│ ▌ MEDIUM    Chrome V8 Heap Buffer Overflow...   │
└─────────────────────────────────────────────────┘
```

### 7.3 JavaScript Architecture (`frontend/js/`)

**`api.js`** — all API communication:
```javascript
const API_BASE = "http://127.0.0.1:8000/api";
const API_KEY  = "your_key_here"; // load from a config or prompt user

async function fetchFindings(filters = {}) { ... }
async function fetchStats() { ... }
async function markReviewed(id) { ... }
```
- All requests include `X-API-Key` header.
- Expose a simple retry: if fetch fails, retry once after 2s.

**`components.js`** — DOM renderers:
- `renderStatBar(stats)` — updates the 4 counter cards.
- `renderFindingCard(finding)` — returns an HTML string/element for one finding.
  - Sources rendered as `<a href="{url}" target="_blank" rel="noopener">{name}</a>`.
  - "Mark Reviewed" button: on click, calls `markReviewed(id)`, then greys out the card and changes badge to "Reviewed".
- `renderFeed(findings)` — clears the feed div and renders all cards with staggered animation.

**`filters.js`** — client-side filtering:
- Maintain `activeFilters = { severity: null, status: null }`.
- Filter pill buttons toggle `activeFilters` and call `renderFeed(applyFilters(allFindings))`.
- `applyFilters()` — pure function, returns filtered copy of `allFindings`.

**`app.js`** — orchestrator:
```javascript
let allFindings = [];

async function init() {
  await refreshStats();
  await refreshFeed();
  setInterval(refreshAll, 60 * 1000); // auto-refresh every 60s
}

async function refreshAll() {
  await refreshStats();
  await refreshFeed();
  updateLastSyncTime();
}

document.addEventListener('DOMContentLoaded', init);
```

### 7.4 Auto-Refresh
- Dashboard polls `GET /api/findings` and `GET /api/stats` every **60 seconds**.
- Show a subtle spinning icon in the header during fetch. On completion, flash "Synced" briefly.
- Do **not** re-render cards that haven't changed (compare by `id` + `timestamp`).

---

## 8. Scheduler & Process Management (OCI Ubuntu)

### 8.1 Cron — Hourly Collector (`scripts/setup_cron.sh`)
```bash
#!/bin/bash
# Run this ONCE on the OCI server to register the hourly collector job.
SENTINEL_DIR=$(dirname "$(realpath "$0")")/..
PYTHON="$SENTINEL_DIR/venv/bin/python"   # use venv python, not system python
LOG_DIR="$SENTINEL_DIR/logs"
mkdir -p "$LOG_DIR"

# Use absolute paths — cron does not inherit your shell $PATH
CRON_JOB="0 * * * * cd $SENTINEL_DIR && $PYTHON -m backend.collector.collector >> $LOG_DIR/cron.log 2>&1"
(crontab -l 2>/dev/null | grep -v 'collector'; echo "$CRON_JOB") | crontab -
echo "Cron job installed. Verify with: crontab -l"
```

### 8.2 systemd Service — API Server (`scripts/sentinel-api.service`)
Create this file at `/etc/systemd/system/sentinel-api.service` so the API auto-starts after OCI reboots:
```ini
[Unit]
Description=Sentinel Intelligence API
After=network.target tailscaled.service
Wants=tailscaled.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/sentinel
EnvironmentFile=/home/ubuntu/sentinel/.env
ExecStart=/home/ubuntu/sentinel/venv/bin/uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```
**Enable:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable sentinel-api
sudo systemctl start sentinel-api
sudo systemctl status sentinel-api
```

### 8.3 OCI Security List (Firewall)
OCI has two layers of firewall. Since access is **only via Tailscale**, you do NOT need to open port 8000 in OCI Security Lists to the public internet.

```
OCI Security List rule needed: NONE (keep port 8000 closed to 0.0.0.0/0)
Tailscale handles the private network — only devices on your Tailnet can reach the server.
```

However, you must allow Tailscale traffic through the Ubuntu UFW firewall:
```bash
sudo ufw allow in on tailscale0
sudo ufw reload
```

### 8.4 Manual trigger
```bash
cd /home/ubuntu/sentinel/
source venv/bin/activate
python -m backend.collector.collector
```

---

## 9. Dependencies (`backend/requirements.txt`)

```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
httpx>=0.27.0
beautifulsoup4>=4.12.3
feedparser>=6.0.11
google-generativeai>=0.7.0
rapidfuzz>=3.9.0
python-dotenv>=1.0.1
pydantic>=2.7.0
lxml>=5.2.2
```

---

## 10. Security Considerations

| Concern | Mitigation |
|---|---|
| Public internet exposure | Port 8000 is **NOT** opened in OCI Security Lists. Tailscale is the only network path in. |
| API unauthorised access | `X-API-Key` header required on all `/api/*` routes — second layer after Tailscale. |
| OCI instance compromise | UFW blocks all non-Tailscale inbound traffic. Only SSH (via Tailscale) and Tailscale itself allowed. |
| LLM hallucination | Discard items where `is_critical_field=false`. Validate JSON schema strictly. |
| Prompt injection via scraped content | Wrap raw content in triple-backtick block in the prompt. Limit `raw_text` to 3000 chars. |
| SQLite injection | Use parameterised queries (`?` placeholders) exclusively. |
| Excessive Gemini API cost | Semaphore limits concurrent calls. Skip items with `raw_text < 100 chars`. |
| Cron env issues on OCI | Use venv's absolute Python path in crontab. Load `.env` explicitly in collector.py. |

---

## 11. Implementation Order (Recommended)

```
Phase 1 — Foundation
  [ ] Set up repo structure and venv
  [ ] Write schema.sql and database.py
  [ ] Write config.py and .env.example

Phase 2 — Collector
  [ ] Implement sources.py (start with 2 RSS feeds to test)
  [ ] Implement analyzer.py with Gemini integration
  [ ] Implement deduplicator.py
  [ ] Implement collector.py orchestrator
  [ ] Test full run, verify DB writes

Phase 3 — API
  [ ] Implement FastAPI main.py + routes.py
  [ ] Implement auth.py middleware
  [ ] Test all endpoints with curl/Postman

Phase 4 — Frontend
  [ ] Build index.html structure
  [ ] Write main.css with design tokens
  [ ] Implement api.js
  [ ] Implement components.js
  [ ] Implement filters.js + app.js
  [ ] Test full end-to-end flow

Phase 5 — Hardening
  [ ] Set up cron via setup_cron.sh
  [ ] Add logging + error handling
  [ ] Write README.md with setup instructions
  [ ] Verify 7-day retention works
```

---

## 12. README Sections (for final README.md)

The README should include:
1. One-sentence description.
2. Architecture diagram (ASCII or Mermaid).
3. Prerequisites (Python 3.11+, pip, Tailscale installed on both server and your laptop).
4. OCI-specific setup steps:
   ```
   git clone <repo> /home/ubuntu/sentinel
   cd /home/ubuntu/sentinel
   python3 -m venv venv
   source venv/bin/activate
   pip install -r backend/requirements.txt
   cp .env.example .env
   # Edit .env: add GEMINI_API_KEY, API_KEY, set TAILSCALE_IP to output of `tailscale ip -4`
   python -m backend.db.database          # initialise DB
   python -m backend.collector.collector  # first manual run
   bash scripts/setup_cron.sh             # install hourly cron
   sudo cp scripts/sentinel-api.service /etc/systemd/system/
   sudo systemctl enable --now sentinel-api
   ```
5. Access: open `http://<tailscale-ip>:8000/` from any device on your Tailnet.
6. API documentation (endpoint table with X-API-Key header example).
7. Troubleshooting: common OCI/cron/Tailscale errors + fixes.

---

*End of specification — Sentinel Intelligence v1.1 (OCI + Tailscale deployment)*
