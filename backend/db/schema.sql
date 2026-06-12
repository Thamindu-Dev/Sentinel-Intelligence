-- ============================================================
-- Sentinel Intelligence — Database Schema
-- ============================================================
-- Run once to initialise. Safe to re-run (IF NOT EXISTS).
-- ============================================================

CREATE TABLE IF NOT EXISTS findings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cve_id      TEXT,
    timestamp   DATETIME NOT NULL DEFAULT (datetime('now')),
    title       TEXT NOT NULL,
    severity    TEXT NOT NULL CHECK(severity IN ('Critical','High','Medium','Low')),
    impact      TEXT NOT NULL,
    summary     TEXT NOT NULL,
    target      TEXT NOT NULL,
    sources     TEXT NOT NULL DEFAULT '[]',
    status      TEXT NOT NULL DEFAULT 'New' CHECK(status IN ('New','Reviewed'))
);

CREATE INDEX IF NOT EXISTS idx_severity  ON findings(severity);
CREATE INDEX IF NOT EXISTS idx_timestamp ON findings(timestamp);
CREATE INDEX IF NOT EXISTS idx_cve_id    ON findings(cve_id);

-- ============================================================
-- Scraper Queue (Fast Phase)
-- ============================================================

CREATE TABLE IF NOT EXISTS raw_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    url         TEXT NOT NULL,
    raw_text    TEXT NOT NULL,
    source_name TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending','Processed','Failed')),
    fetched_at  DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_raw_status ON raw_items(status);

-- ============================================================
-- User-managed feed sources
-- ============================================================

CREATE TABLE IF NOT EXISTS sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    url         TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL DEFAULT 'rss' CHECK(source_type IN ('rss','html','json_api')),
    selector    TEXT NOT NULL DEFAULT 'article',
    max_items   INTEGER NOT NULL DEFAULT 15,
    enabled     INTEGER NOT NULL DEFAULT 1,
    is_builtin  INTEGER NOT NULL DEFAULT 0,
    created_at  DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sources_enabled ON sources(enabled);
