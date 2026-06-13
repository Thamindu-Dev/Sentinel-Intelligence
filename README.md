# 🛡️ Sentinel Intelligence

**Sentinel Intelligence** is an automated, high-performance Cyber Threat Intelligence (CTI) pipeline and dashboard. It continuously scrapes, analyzes, deduplicates, and surfaces critical security findings from authoritative sources.

## Core Features

- **Automated Collection**: Aggregates threat data from built-in sources (NVD, CISA) and custom RSS/HTML feeds.
- **AI-Powered Analysis**: Utilizes Google Gemini LLMs to parse unstructured threat intelligence into structured, actionable JSON arrays (Severity, Impact, Target, Summary).
- **Intelligent Deduplication**: Prevents noise by merging duplicate findings using fuzzy title matching and CVE cross-referencing.
- **Dynamic Dashboard**: Features a modern, responsive Single Page Application (SPA) with real-time filtering, continuous infinite scroll pagination, and instant visual feedback.
- **Admin Control**: Built-in Admin Panel to manage sources, toggle feeds, and trigger manual collector runs on the fly.
- **Secure Access**: API is secured via `X-API-Key` authentication and designed to run behind a Tailscale (WireGuard) VPN.

## Sources

| Source                   | Type          |
| ------------------------ | ------------- |
| NIST NVD (API)           | JSON          |
| CISA Advisories          | HTML          |
| BleepingComputer         | RSS           |
| The Hacker News          | RSS           |
| Krebs on Security        | RSS           |
| Google Project Zero      | RSS           |
| _Dynamic Custom Sources_ | RSS/HTML/JSON |

## Prerequisites

- Python 3.11+
- Tailscale installed on **both** the OCI server and your device
- Gemini API key from [aistudio.google.com](https://aistudio.google.com)

## Setup (Windows Local Testing)

```powershell
# 1. Clone & setup
git clone <repo>
cd sentinel
python -m venv venv
.\venv\Scripts\activate
pip install -r backend/requirements.txt

# 2. Configure
copy .env.example .env
# Edit .env and fill in: GEMINI_API_KEY, API_KEY

# 3. Initialise database
python -m backend.db.database

# 4. First collector run (manual)
python -m backend.collector.collector

# 5. Run the API Server
uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
```

## Setup (Linux Server)

```bash
# 1. Clone & setup
git clone https://github.com/Thamindu-Dev/Sentinel-Intelligence.git /home/ubuntu/sentinel
cd /home/ubuntu/sentinel
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

# 2. Configure
cp .env.example .env
nano .env
# Fill in: GEMINI_API_KEY, API_KEY, TAILSCALE_IP

# 3. Initialise database
python -m backend.db.database

# 4. Install API as a system service
sudo cp scripts/sentinel-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sentinel-api

# 5. Install cron (Twice a day)
bash scripts/setup_cron.sh

# 6. Firewall — allow Tailscale only
sudo ufw allow in on tailscale0
sudo ufw reload
```

## Hermes AI Agent Integration

Sentinel includes a native plugin for the **Hermes AI Agent**, allowing Hermes to query your threat database, run the collector, and provide security summaries directly in chat.

### Installation

Once Sentinel is deployed to your server (e.g., `/home/ubuntu/sentinel`), symlink the `hermes_plugin` directory into your Hermes configuration:

```bash
mkdir -p ~/.hermes/plugins
ln -s /home/ubuntu/sentinel/hermes_plugin ~/.hermes/plugins/sentinel
```

Restart the Hermes gateway to load the plugin.

### Available Slash Commands

Type these anywhere in the Hermes chat (CLI, Telegram, Discord):

- `/sentinel status` — View a quick breakdown of pending and reviewed threats.
- `/sentinel run` — Trigger the background collector to fetch new threats immediately.
- `/sentinel stop` — Kill the running collector process.

### Available Tools (for the LLM)

Hermes can automatically use these tools when you ask questions:

- `sentinel_get_findings` — E.g., _"What are the latest critical threats?"_
- `sentinel_get_stats` — E.g., _"How many threats are in the database?"_
- `sentinel_mark_reviewed` — E.g., _"Mark finding #69 as reviewed."_

## Access

Open in your browser: `http://<tailscale-ip>:8000/`

## API Endpoints

| Method  | Path                        | Auth | Description                                             |
| ------- | --------------------------- | ---- | ------------------------------------------------------- |
| `GET`   | `/api/health`               | ✗    | Health check                                            |
| `GET`   | `/api/stats`                | ✓    | Severity counts                                         |
| `GET`   | `/api/findings`             | ✓    | List findings (filter: `?severity=Critical&status=New`) |
| `PATCH` | `/api/findings/{id}`        | ✓    | Mark finding as Reviewed                                |
| `GET`   | `/api/admin/sources`        | ✓    | List all feed sources                                   |
| `POST`  | `/api/admin/sources`        | ✓    | Add a new feed source                                   |
| `PATCH` | `/api/admin/sources/{id}`   | ✓    | Enable/disable a feed source                            |
| `DELETE`| `/api/admin/sources/{id}`   | ✓    | Delete a feed source                                    |
| `GET`   | `/api/admin/db-stats`       | ✓    | Detailed database statistics                            |
| `DELETE`| `/api/admin/clear-db`       | ✓    | Delete ALL findings (destructive)                       |
| `POST`  | `/api/admin/run-collector`  | ✓    | Trigger a manual collector run                          |
| `POST`  | `/api/admin/stop-collector` | ✓    | Kill the running collector process                      |

All authenticated endpoints require: `X-API-Key: <your_key>`

## Module Structure

```
backend/
├── config.py                 # Central settings from .env
├── db/
│   ├── schema.sql            # Table definitions
│   └── database.py           # All SQLite CRUD operations
├── collector/
│   ├── sources.py            # Source definitions + scraping
│   ├── analyzer.py           # Gemini LLM analysis
│   ├── deduplicator.py       # CVE/title dedup logic
│   └── collector.py          # Twice-daily orchestrator
└── api/
    ├── auth.py               # X-API-Key middleware
    ├── models.py             # Pydantic schemas
    ├── routes.py             # Public API endpoints
    ├── admin_routes.py       # Admin/settings endpoints
    └── main.py               # FastAPI app + static serving

frontend/
├── index.html                # Dashboard shell
├── css/main.css              # Design system
└── js/
    ├── api.js                # API client
    ├── components.js         # UI renderers
    ├── filters.js            # Filter state
    ├── settings.js           # Settings page logic
    ├── router.js             # SPA router
    └── app.js                # Orchestrator
```

## License

Internal use only.
