"""
Sentinel Intelligence — API Authentication

Simple API key middleware. Checks for X-API-Key header on all
protected routes. The health endpoint is excluded.

Usage in routes:
    from backend.api.auth import require_api_key
    @router.get("/findings", dependencies=[Depends(require_api_key)])
"""

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from backend.config import settings

# ---------------------------------------------------------------------------
# API key header extractor
# ---------------------------------------------------------------------------

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(
    api_key: str = Security(_api_key_header),
) -> str:
    """
    FastAPI dependency that validates the X-API-Key header.
    Returns the key if valid, raises 403 otherwise.
    """
    if not api_key or api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key.",
        )
    return api_key
