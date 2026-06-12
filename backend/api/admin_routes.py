"""
Sentinel Intelligence — Admin API Routes

Settings/admin endpoints: source CRUD, DB management, manual collector trigger.
Separated from the main routes for clean modularity.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.auth import require_api_key
from backend.api.models import (
    ClearDbResponse,
    DbStatsResponse,
    SourceCreate,
    SourceResponse,
    SourceToggle,
)
from backend.db.database import (
    add_source,
    clear_all_findings,
    delete_source,
    get_all_sources,
    get_db_stats,
    toggle_source,
)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

admin_router = APIRouter(
    prefix="/api/admin",
    tags=["Admin / Settings"],
    dependencies=[Depends(require_api_key)],
)


# ---------------------------------------------------------------------------
# Feed Sources
# ---------------------------------------------------------------------------

@admin_router.get("/sources", response_model=list[SourceResponse])
async def list_sources():
    """Return all configured feed sources."""
    return get_all_sources()


@admin_router.post(
    "/sources",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_source(body: SourceCreate):
    """Add a new custom feed source."""
    try:
        return add_source(
            name=body.name,
            url=body.url,
            source_type=body.source_type,
            selector=body.selector,
            max_items=body.max_items,
        )
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A source with this URL already exists.",
            )
        raise


@admin_router.patch("/sources/{source_id}", response_model=SourceResponse)
async def patch_source(source_id: int, body: SourceToggle):
    """Enable or disable a feed source."""
    result = toggle_source(source_id, body.enabled)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source #{source_id} not found.",
        )
    return result


@admin_router.delete("/sources/{source_id}", status_code=status.HTTP_200_OK)
async def remove_source(source_id: int):
    """Delete a feed source."""
    if not delete_source(source_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source #{source_id} not found.",
        )
    return {"message": f"Source #{source_id} deleted."}


# ---------------------------------------------------------------------------
# Database Management
# ---------------------------------------------------------------------------

@admin_router.get("/db-stats", response_model=DbStatsResponse)
async def db_stats():
    """Return detailed database statistics."""
    return get_db_stats()


@admin_router.delete("/clear-db", response_model=ClearDbResponse)
async def clear_database():
    """Delete ALL findings from the database. Cannot be undone."""
    deleted = clear_all_findings()
    return ClearDbResponse(
        deleted=deleted,
        message=f"Deleted {deleted} findings from the database.",
    )


# ---------------------------------------------------------------------------
# Manual Collector Trigger
# ---------------------------------------------------------------------------

@admin_router.post("/run-collector")
async def run_collector_now():
    """
    Trigger a manual collector run in the background.
    Spawns a separate process so it can be managed/killed independently of the API.
    """
    import subprocess
    import sys
    from pathlib import Path
    
    # Spawn a detached subprocess
    subprocess.Popen([sys.executable, "-m", "backend.collector.collector"])
    
    return {"message": "Collector run started. Any existing stalled runs were automatically killed."}
