"""Quick script to verify DB contents are real, not mock data."""
import sqlite3
import json

conn = sqlite3.connect("sentinel.db")
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT id, title, severity, sources, target, cve_id, timestamp FROM findings ORDER BY id"
).fetchall()

print(f"Total findings in DB: {len(rows)}\n")
print("=" * 90)

for r in rows:
    sources = json.loads(r["sources"]) if r["sources"] else []
    source_names = [s.get("name", "?") for s in sources]
    source_urls  = [s.get("url", "?") for s in sources]
    print(f"  #{r['id']}  [{r['severity']:>8}]  {r['title'][:75]}")
    print(f"          CVE: {r['cve_id'] or 'N/A'}  |  Target: {r['target']}")
    print(f"          Sources: {', '.join(source_names)}")
    for url in source_urls:
        print(f"            -> {url}")
    print(f"          Timestamp: {r['timestamp']}")
    print("-" * 90)

conn.close()
