# 🛡️ Sentinel Intelligence

**Automated Cyber Threat Intelligence pipeline that scrapes, analyses, deduplicates, and displays critical security findings from authoritative sources — refreshed every hour.**

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  YOUR DEVICE (browser) → http://100.x.x.x:8000/     │
└─────────────────────┬────────────────────────────────┘
                      │ Tailscale (WireGuard)
┌─────────────────────▼────────────────────────────────┐
│  OCI Ubuntu 22.04                                    │
│                                                      │
│  ┌─────────────────────────────────────────────┐     │
│  │  FastAPI (uvicorn :8000)                    │     │
│  │    /       → Dashboard UI                   │     │
│  │    /api/*  → REST endpoints (X-API-Key)     │     │
│  └──────────────┬──────────────────────────────┘     │
│                 │                                     │
│  ┌──────────────▼──────────────────────────────┐     │
│  │  sentinel.db (SQLite)                       │     │
│  └──────────────▲──────────────────────────────┘     │
│                 │                                     │
│  ┌──────────────┴──────────────────────────────┐     │
│  │  Collector (cron hourly)                    │     │
│  │    sources.py → analyzer.py → dedup → DB    │     │
│  └─────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────┘
```

## Sources

| Source | Type |
|---|---|
| NIST NVD (API) | JSON |
| CISA Advisories | HTML |
| BleepingComputer | RSS |
| The Hacker News | RSS |
| Krebs on Security | RSS |
| Google Project Zero | RSS |

## Prerequisites

- Python 3.11+
- Tailscale installed on **both** the OCI server and your device
- Gemini API key from [aistudio.google.com](https://aistudio.google.com)

## Setup (OCI Server)

```bash
# 1. Clone & setup
git clone <repo> /home/ubuntu/sentinel
cd /home/ubuntu/sentinel
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

# 2. Configure
cp .env.example .env
nano .env
# Fill in: GEMINI_API_KEY, API_KEY, TAILSCALE_IP (run: tailscale ip -4)

# 3. Initialise database
python -m backend.db.database

# 4. First collector run (manual)
python -m backend.collector.collector

# 5. Install API as a system service
sudo cp scripts/sentinel-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sentinel-api

# 6. Install hourly cron
bash scripts/setup_cron.sh

# 7. Firewall — allow Tailscale only
sudo ufw allow in on tailscale0
sudo ufw reload
```

## Access

Open in your browser: `http://<tailscale-ip>:8000/`

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/health` | ✗ | Health check |
| `GET` | `/api/stats` | ✓ | Severity counts |
| `GET` | `/api/findings` | ✓ | List findings (filter: `?severity=Critical&status=New`) |
| `PATCH` | `/api/findings/{id}` | ✓ | Mark finding as Reviewed |

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
│   └── collector.py          # Hourly orchestrator
└── api/
    ├── auth.py               # X-API-Key middleware
    ├── models.py             # Pydantic schemas
    ├── routes.py             # Endpoint definitions
    └── main.py               # FastAPI app + static serving

frontend/
├── index.html                # Dashboard shell
├── css/main.css              # Design system
└── js/
    ├── api.js                # API client
    ├── components.js         # UI renderers
    ├── filters.js            # Filter state
    └── app.js                # Orchestrator
```

## License

Internal use only.
