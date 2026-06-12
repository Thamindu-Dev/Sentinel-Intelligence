"""Tool handlers for the Sentinel Hermes plugin."""

import json
import sys
from pathlib import Path

# Safely inject the Sentinel project root into sys.path
_PLUGIN_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _PLUGIN_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

def get_findings(args: dict, **kwargs) -> str:
    """Fetch recent findings from the database."""
    from backend.db.database import get_all_findings
    
    severity = args.get("severity")
    status = args.get("status")
    limit = args.get("limit", 10)
    
    try:
        findings = get_all_findings(severity=severity, status=status, limit=limit)
        return json.dumps({"status": "success", "count": len(findings), "findings": findings})
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_stats(args: dict, **kwargs) -> str:
    """Fetch statistics from the database."""
    from backend.db.database import get_stats as fetch_stats
    
    try:
        stats = fetch_stats()
        return json.dumps({"status": "success", "stats": stats})
    except Exception as e:
        return json.dumps({"error": str(e)})

def mark_reviewed(args: dict, **kwargs) -> str:
    """Mark a finding as reviewed."""
    from backend.db.database import update_finding_status
    
    finding_id = args.get("finding_id")
    if not finding_id:
        return json.dumps({"error": "finding_id is required"})
        
    try:
        row = update_finding_status(finding_id, "Reviewed")
        if not row:
            return json.dumps({"error": f"Finding #{finding_id} not found."})
        return json.dumps({"status": "success", "message": f"Finding #{finding_id} marked as Reviewed.", "finding": dict(row)})
    except Exception as e:
        return json.dumps({"error": str(e)})
