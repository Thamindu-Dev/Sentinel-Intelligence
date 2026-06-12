"""Tool schemas for the Sentinel Hermes plugin."""

GET_FINDINGS = {
    "name": "sentinel_get_findings",
    "description": (
        "Fetch recent cyber threat findings from the Sentinel database. "
        "Use this tool to get intelligence about recent vulnerabilities, "
        "ransomware activity, or exploits. Can filter by severity or status."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "severity": {
                "type": "string",
                "description": "Filter by severity (Critical, High, Medium, Low). Omit for all.",
            },
            "status": {
                "type": "string",
                "description": "Filter by status (New, Reviewed). Default is usually New.",
            },
            "limit": {
                "type": "integer",
                "description": "Number of records to fetch. Default 10.",
            }
        },
        "required": [],
    },
}

GET_STATS = {
    "name": "sentinel_get_stats",
    "description": (
        "Get a quick statistical overview of the Sentinel database, "
        "including counts of findings grouped by severity and status."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

MARK_REVIEWED = {
    "name": "sentinel_mark_reviewed",
    "description": (
        "Mark a specific finding as 'Reviewed' in the Sentinel database, "
        "removing it from the active dashboard feed. You must provide the numeric ID of the finding."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "finding_id": {
                "type": "integer",
                "description": "The integer ID of the finding to mark as reviewed.",
            }
        },
        "required": ["finding_id"],
    },
}
