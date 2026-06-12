"""
Sentinel Intelligence — Pydantic Models

Request/response schemas for the FastAPI endpoints.
Keeps validation logic separate from route handlers.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Source sub-model
# ---------------------------------------------------------------------------

class SourceEntry(BaseModel):
    """A single source reference for a finding."""
    name: str
    url: str


# ---------------------------------------------------------------------------
# Finding models
# ---------------------------------------------------------------------------

class FindingResponse(BaseModel):
    """Full finding as returned by the API."""
    id: int
    cve_id: Optional[str] = None
    timestamp: str
    title: str
    severity: str
    impact: str
    summary: str
    target: str
    sources: List[SourceEntry] = []
    status: str = "New"

    class Config:
        from_attributes = True


class FindingStatusUpdate(BaseModel):
    """Request body for PATCH /api/findings/{id}."""
    status: str = Field(
        ...,
        pattern="^(Reviewed)$",
        description="Only 'Reviewed' is accepted as a status transition.",
    )


# ---------------------------------------------------------------------------
# Stats model
# ---------------------------------------------------------------------------

class StatsResponse(BaseModel):
    """Response for GET /api/stats."""
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    total: int = 0
    queue_count: int = 0
    last_updated: Optional[str] = None


# ---------------------------------------------------------------------------
# Health model
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Response for GET /api/health."""
    status: str = "ok"
    db_reachable: bool = True


# ---------------------------------------------------------------------------
# Source models (Settings page)
# ---------------------------------------------------------------------------

class SourceResponse(BaseModel):
    """A feed source as returned by the API."""
    id: int
    name: str
    url: str
    source_type: str
    selector: str = "article"
    max_items: int = 15
    enabled: int = 1
    is_builtin: int = 0
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class SourceCreate(BaseModel):
    """Request body for POST /api/admin/sources."""
    name: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., min_length=10)
    source_type: str = Field("rss", pattern="^(rss|html|json_api)$")
    selector: str = Field("article", max_length=200)
    max_items: int = Field(15, ge=1, le=50)


class SourceToggle(BaseModel):
    """Request body for PATCH /api/admin/sources/{id}."""
    enabled: bool


class DbStatsResponse(BaseModel):
    """Response for GET /api/admin/db-stats."""
    total_findings: int = 0
    new_findings: int = 0
    reviewed_findings: int = 0
    by_severity: Dict[str, Any] = {}
    oldest_finding: Optional[str] = None
    newest_finding: Optional[str] = None
    queue_count: int = 0
    total_sources: int = 0
    enabled_sources: int = 0
    db_size_bytes: int = 0


class ClearDbResponse(BaseModel):
    """Response for DELETE /api/admin/clear-db."""
    deleted: int = 0
    message: str = ""
