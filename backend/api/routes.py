"""
Sentinel Intelligence — API Routes

All endpoint definitions. Separated from the app factory for modularity.
Import this router in main.py.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.auth import require_api_key
from backend.api.models import (
    FindingResponse,
    FindingStatusUpdate,
    HealthResponse,
    StatsResponse,
)
from backend.db.database import (
    get_all_findings,
    get_finding_by_id,
    get_stats,
    update_status,
    get_connection,
)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api", tags=["Sentinel API"])


# ---------------------------------------------------------------------------
# Health (no auth required)
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API and database health."""
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        return HealthResponse(status="ok", db_reachable=True)
    except Exception:
        return HealthResponse(status="degraded", db_reachable=False)


# ---------------------------------------------------------------------------
# Findings (auth required)
# ---------------------------------------------------------------------------

@router.get(
    "/findings",
    response_model=list[FindingResponse],
    dependencies=[Depends(require_api_key)],
)
async def list_findings(
    severity: Optional[str] = Query(
        None, description="Filter by severity: Critical, High, Medium, or Low"
    ),
    status_filter: Optional[str] = Query(
        None, alias="status", description="Filter by status: New or Reviewed"
    ),
    limit: int = Query(100, ge=1, le=500, description="Max results to return"),
):
    """Return all findings, sorted by timestamp (newest first)."""
    findings = get_all_findings(
        severity=severity,
        status=status_filter,
        limit=limit,
    )
    return findings


@router.patch(
    "/findings/{finding_id}",
    response_model=FindingResponse,
    dependencies=[Depends(require_api_key)],
)
async def patch_finding(finding_id: int, body: FindingStatusUpdate):
    """Update a finding's status (e.g., mark as Reviewed)."""
    existing = get_finding_by_id(finding_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding #{finding_id} not found.",
        )

    updated = update_status(finding_id, body.status)
    return updated


# ---------------------------------------------------------------------------
# Stats (auth required)
# ---------------------------------------------------------------------------

@router.get(
    "/stats",
    response_model=StatsResponse,
    dependencies=[Depends(require_api_key)],
)
async def get_dashboard_stats():
    """Return severity counts for the stat bar."""
    return get_stats()
