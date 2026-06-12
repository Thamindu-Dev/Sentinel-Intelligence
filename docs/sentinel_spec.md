# Project: Sentinel Intelligence (CTI Pipeline)

## Role: Technical Specification for AI Software Engineer

### 1. Objective

Build a lightweight, automated Cyber Threat Intelligence (CTI) pipeline that collects, analyzes, and displays critical cybersecurity findings from high-signal sources in a professional SOC-style dashboard.

### 2. Technical Stack

- **Collector**: Python 3.11+ (Using `web_search`, `web_extract`, and LLM for synthesis).
- **Database**: SQLite (Single file `sentinel.db`).
- **API Layer**: FastAPI (Python) for serving JSON data from SQLite.
- **Frontend**: Vanilla JavaScript + Tailwind CSS (Modern, Dark-themed, Responsive).
- **Hosting**: Ubuntu Linux localhost.
- **Scheduler**: Cron (Hourly updates).
- **LLM**: Gemini API. (via google aistudio.google.com model gemma-4-26b-it)

### 3. Functional Requirements

#### A. Data Collection & Analysis

- **Sources**: Target NIST NVD, CISA KEV, BleepingComputer, The Hacker News, and official vendor security blogs.
- **Analysis**: Raw content must be passed through an LLM to extract:
  - **Severity**: Critical, High, Medium, Low.
  - **Impact**: Vulnerability type (e.g., RCE, LPE, SQLi, Zero-day).
  - **Summary**: A concise 2-sentence a summary of the threat.
  - **Target**: Affected software/hardware and versions.
- **Deduplication**:
  - Use the CVE ID or a normalized title as a unique key.
  - If a finding already exists, append the new URL to a `sources` list rather than creating a new entry.

#### B. Data Management (SQLite)

- **Schema**:
  - `id` (INTEGER PRIMARY KEY)
  - `timestamp` (DATETIME)
  - `title` (TEXT)
  - `severity` (TEXT)
  - `impact` (TEXT)
  - `summary` (TEXT)
  - `target` (TEXT)
  - `sources` (TEXT - JSON array of URLs)
  - `status` (TEXT - 'New' or 'Reviewed')
- **Retention Policy**:
  - Implement a cleanup routine: `DELETE FROM findings WHERE timestamp < datetime('now', '-7 days')`.
  - This must run every time the collector completes a cycle.

#### C. API Layer (FastAPI)

- `GET /api/findings`: Returns all findings sorted by timestamp (descending). Supports query params for filtering (e.g., `?severity=Critical`).
- `PATCH /api/findings/{id}`: Update the status of a finding to 'Reviewed'.

#### D. Frontend Dashboard

- **Theme**: "Security Operations Center" (Deep blacks, charcoal greys, neon accent colors for severity).
- **Components**:
  - **Stat Bar**: Counters for total Critical, High, and Medium threats found in the last 7 days.
  - **Main Feed**: A list of cards or a table containing the findings.
  - **Severity Badges**:
    - Critical $\rightarrow$ Bright Red
    - High $\rightarrow$ Orange
    - Medium $\rightarrow$ Yellow
    - Low $\rightarrow$ Blue
  - **Filtering**: Client-side filter to toggle visibility by severity.

### 4. Non-Functional Requirements

- **Silent Operation**: No external notifications/alerts.
- **Security**: The API should be internal-only or protected by a simple API key/Basic Auth if exposed.
- **Resource Efficiency**: Must run with minimal RAM/CPU overhead.
