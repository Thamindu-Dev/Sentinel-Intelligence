"""
Sentinel Intelligence — Database Access Layer

Provides all SQLite CRUD operations for the findings table.
No ORM — uses raw parameterised queries for simplicity and safety.

Usage:
    from backend.db.database import init_db, get_all_findings, upsert_finding
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import settings

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with row-factory enabled."""
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create tables and indexes if they don't exist."""
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_connection()
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a sqlite3.Row into a plain dict, parsing the sources JSON."""
    d = dict(row)
    # Parse sources from JSON string to list
    try:
        d["sources"] = json.loads(d.get("sources", "[]"))
    except (json.JSONDecodeError, TypeError):
        d["sources"] = []
    return d


def get_all_findings(
    severity: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Fetch findings sorted by timestamp DESC.

    Args:
        severity: Optional filter — 'Critical', 'High', 'Medium', or 'Low'.
        status:   Optional filter — 'New' or 'Reviewed'.
        limit:    Max rows to return (default 100, max 500).
    """
    limit = min(max(1, limit), 500)

    query = "SELECT * FROM findings"
    params: list = []
    clauses: list = []

    if severity:
        clauses.append("severity = ?")
        params.append(severity)
    if status:
        clauses.append("status = ?")
        params.append(status)

    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    conn = get_connection()
    try:
        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_finding_by_id(finding_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single finding by its primary key."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM findings WHERE id = ?", (finding_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def get_stats() -> Dict[str, Any]:
    """Return severity counts and the latest update timestamp."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT severity, COUNT(*) as cnt FROM findings GROUP BY severity"
        ).fetchall()

        counts = {r["severity"].lower(): r["cnt"] for r in rows}
        total = sum(counts.values())

        last_row = conn.execute(
            "SELECT MAX(timestamp) as last_ts FROM findings"
        ).fetchone()
        last_updated = last_row["last_ts"] if last_row else None

        queue_row = conn.execute(
            "SELECT COUNT(*) as queue_cnt FROM raw_items"
        ).fetchone()
        queue_count = queue_row["queue_cnt"] if queue_row else 0

        return {
            "critical": counts.get("critical", 0),
            "high": counts.get("high", 0),
            "medium": counts.get("medium", 0),
            "low": counts.get("low", 0),
            "total": total,
            "queue_count": queue_count,
            "last_updated": last_updated,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def insert_finding(data: Dict[str, Any]) -> int:
    """
    Insert a brand-new finding. Returns the new row ID.

    Expected keys: cve_id, title, severity, impact, summary, target, sources.
    `sources` should be a list of {name, url} dicts.
    """
    sources_json = json.dumps(data.get("sources", []))

    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO findings (cve_id, title, severity, impact, summary, target, sources)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.get("cve_id"),
                data["title"],
                data["severity"],
                data["impact"],
                data["summary"],
                data["target"],
                sources_json,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def append_source(finding_id: int, new_source: Dict[str, str]) -> None:
    """
    Append a source {name, url} to an existing finding's sources list.
    Prevents exact URL duplicates. Also bumps the timestamp to now.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT sources FROM findings WHERE id = ?", (finding_id,)
        ).fetchone()
        if not row:
            return

        try:
            existing = json.loads(row["sources"])
        except (json.JSONDecodeError, TypeError):
            existing = []

        # Skip if this exact URL is already present
        if any(s.get("url") == new_source.get("url") for s in existing):
            return

        existing.append(new_source)

        conn.execute(
            """
            UPDATE findings
            SET sources = ?, timestamp = datetime('now')
            WHERE id = ?
            """,
            (json.dumps(existing), finding_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_status(finding_id: int, new_status: str) -> Optional[Dict[str, Any]]:
    """
    Update a finding's status. Returns the updated row or None if not found.
    """
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE findings SET status = ? WHERE id = ?",
            (new_status, finding_id),
        )
        conn.commit()
        return get_finding_by_id(finding_id)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Raw Items Queue (Scraper Phase)
# ---------------------------------------------------------------------------

def insert_raw_item(title: str, url: str, raw_text: str, source_name: str) -> None:
    """Insert a scraped item into the queue. Ignores exact URLs to avoid duplication."""
    conn = get_connection()
    try:
        # Check if URL already exists in raw queue or findings
        exists_raw = conn.execute("SELECT 1 FROM raw_items WHERE url = ?", (url,)).fetchone()
        exists_finding = conn.execute(
            "SELECT 1 FROM findings WHERE sources LIKE ?", (f'%"{url}"%',)
        ).fetchone()

        if not exists_raw and not exists_finding:
            conn.execute(
                """
                INSERT INTO raw_items (title, url, raw_text, source_name, status)
                VALUES (?, ?, ?, ?, 'Pending')
                """,
                (title, url, raw_text, source_name)
            )
            conn.commit()
    finally:
        conn.close()


def get_pending_raw_items(limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch unprocessed items from the queue."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM raw_items WHERE status = 'Pending' ORDER BY id ASC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_raw_item_status(item_id: int, status: str) -> None:
    """Mark an item as Processed or Failed."""
    conn = get_connection()
    try:
        conn.execute("UPDATE raw_items SET status = ? WHERE id = ?", (status, item_id))
        conn.commit()
    finally:
        conn.close()


def delete_raw_item(item_id: int) -> None:
    """Permanently remove an item from the queue."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM raw_items WHERE id = ?", (item_id,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Retention / cleanup
# ---------------------------------------------------------------------------

def purge_old_findings() -> int:
    """
    Delete findings AND raw_items older than RETENTION_DAYS. Returns total count of deleted rows.
    """
    cutoff = datetime.utcnow() - timedelta(days=settings.RETENTION_DAYS)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        cur1 = conn.execute("DELETE FROM findings WHERE timestamp < ?", (cutoff_str,))
        cur2 = conn.execute("DELETE FROM raw_items WHERE fetched_at < ?", (cutoff_str,))
        conn.commit()
        return cur1.rowcount + cur2.rowcount
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Dedup helpers (used by the collector's deduplicator module)
# ---------------------------------------------------------------------------

def find_by_cve_id(cve_id: str) -> Optional[Dict[str, Any]]:
    """Find a finding by its CVE ID."""
    if not cve_id:
        return None
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM findings WHERE cve_id = ?", (cve_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def get_all_titles() -> List[Dict[str, Any]]:
    """Return id + title for all findings (used by fuzzy dedup)."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, title FROM findings").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Source CRUD (for the Settings page)
# ---------------------------------------------------------------------------

# Default built-in sources — seeded once on first init
_BUILTIN_SOURCES = [
    {"name": "BleepingComputer", "url": "https://www.bleepingcomputer.com/feed/", "source_type": "rss", "selector": "article", "max_items": 15},
    {"name": "The Hacker News", "url": "https://feeds.feedburner.com/TheHackersNews", "source_type": "rss", "selector": "article", "max_items": 15},
    {"name": "Krebs on Security", "url": "https://krebsonsecurity.com/feed/", "source_type": "rss", "selector": "article", "max_items": 15},
    {"name": "Google Project Zero", "url": "https://googleprojectzero.blogspot.com/feeds/posts/default", "source_type": "rss", "selector": "article", "max_items": 15},
    {"name": "CISA Advisories", "url": "https://www.cisa.gov/news-events/cybersecurity-advisories?f%5B0%5D=advisory_type%3A94", "source_type": "html", "selector": "article, .c-teaser, .views-row", "max_items": 15},
    {"name": "NIST NVD Recent", "url": "https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=20", "source_type": "json_api", "selector": "article", "max_items": 15},
]


def seed_builtin_sources() -> None:
    """Insert built-in sources if the sources table is empty."""
    conn = get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        if count == 0:
            for src in _BUILTIN_SOURCES:
                conn.execute(
                    """INSERT OR IGNORE INTO sources (name, url, source_type, selector, max_items, enabled, is_builtin)
                       VALUES (?, ?, ?, ?, ?, 1, 1)""",
                    (src["name"], src["url"], src["source_type"], src["selector"], src["max_items"]),
                )
            conn.commit()
    finally:
        conn.close()


def get_all_sources() -> List[Dict[str, Any]]:
    """Return all configured feed sources."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM sources ORDER BY is_builtin DESC, name ASC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_enabled_sources() -> List[Dict[str, Any]]:
    """Return only enabled feed sources (used by the collector)."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM sources WHERE enabled = 1 ORDER BY name").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def add_source(name: str, url: str, source_type: str = "rss", selector: str = "article", max_items: int = 15) -> Dict[str, Any]:
    """Add a new custom feed source. Returns the created row."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO sources (name, url, source_type, selector, max_items, enabled, is_builtin)
               VALUES (?, ?, ?, ?, ?, 1, 0)""",
            (name, url, source_type, selector, max_items),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM sources WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def delete_source(source_id: int) -> bool:
    """Delete a source by ID. Returns True if a row was deleted."""
    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def toggle_source(source_id: int, enabled: bool) -> Optional[Dict[str, Any]]:
    """Enable or disable a source. Returns updated row or None."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE sources SET enabled = ? WHERE id = ?",
            (1 if enabled else 0, source_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Admin: clear DB and stats
# ---------------------------------------------------------------------------

def clear_all_findings() -> int:
    """Delete ALL findings from the database. Returns count of deleted rows."""
    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM findings")
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def get_db_stats() -> Dict[str, Any]:
    """Return detailed database statistics for the admin page."""
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
        reviewed = conn.execute("SELECT COUNT(*) FROM findings WHERE status = 'Reviewed'").fetchone()[0]
        new_count = conn.execute("SELECT COUNT(*) FROM findings WHERE status = 'New'").fetchone()[0]

        severity_rows = conn.execute(
            "SELECT severity, COUNT(*) as cnt FROM findings GROUP BY severity"
        ).fetchall()
        by_severity = {r["severity"]: r["cnt"] for r in severity_rows}

        oldest = conn.execute("SELECT MIN(timestamp) FROM findings").fetchone()[0]
        newest = conn.execute("SELECT MAX(timestamp) FROM findings").fetchone()[0]

        source_count = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        enabled_count = conn.execute("SELECT COUNT(*) FROM sources WHERE enabled = 1").fetchone()[0]

        queue_count = conn.execute("SELECT COUNT(*) FROM raw_items").fetchone()[0]

        # Database file size
        db_size = 0
        try:
            from pathlib import Path
            db_size = Path(settings.DB_PATH).stat().st_size
        except Exception:
            pass

        return {
            "total_findings": total,
            "new_findings": new_count,
            "reviewed_findings": reviewed,
            "by_severity": by_severity,
            "oldest_finding": oldest,
            "newest_finding": newest,
            "queue_count": queue_count,
            "total_sources": source_count,
            "enabled_sources": enabled_count,
            "db_size_bytes": db_size,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI: run directly to initialise the database
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    seed_builtin_sources()
    print(f"[SENTINEL] Database initialised at: {settings.DB_PATH}")
