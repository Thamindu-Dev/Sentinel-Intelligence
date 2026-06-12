"""
Sentinel Intelligence — FastAPI Application

App factory + static file serving.
The frontend is served from the same port — no CORS issues.

Run:
    uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.db.database import init_db, seed_builtin_sources
from backend.api.routes import router
from backend.api.admin_routes import admin_router

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Sentinel Intelligence API",
    description="Cyber Threat Intelligence pipeline — REST API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["X-API-Key", "Content-Type"],
)


# ---------------------------------------------------------------------------
# Startup event
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup():
    """Initialise the database and seed built-in sources on API startup."""
    init_db()
    seed_builtin_sources()


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

app.include_router(router)
app.include_router(admin_router)


# ---------------------------------------------------------------------------
# Static frontend serving
# ---------------------------------------------------------------------------

_frontend_dir = Path(settings.FRONTEND_DIR)

if _frontend_dir.exists():
    # Mount CSS, JS, and other assets
    app.mount(
        "/css",
        StaticFiles(directory=str(_frontend_dir / "css")),
        name="css",
    )
    app.mount(
        "/js",
        StaticFiles(directory=str(_frontend_dir / "js")),
        name="js",
    )

    @app.get("/", include_in_schema=False)
    async def serve_dashboard():
        """Serve the main dashboard HTML."""
        return FileResponse(str(_frontend_dir / "index.html"))
else:
    @app.get("/", include_in_schema=False)
    async def no_frontend():
        return {"message": "Frontend not found. Place files in the frontend/ directory."}
