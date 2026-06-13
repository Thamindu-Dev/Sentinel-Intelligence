"""
Sentinel Intelligence — Central Configuration

Loads all settings from the .env file and exposes a single Settings
object that the rest of the application imports.

Usage:
    from backend.config import settings
    print(settings.GEMINI_API_KEY)
"""

import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Locate and load the .env file
# ---------------------------------------------------------------------------
# Walk up from this file to find the project root (where .env lives).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"

if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)
else:
    # Also check CWD (useful when run from cron with cd)
    load_dotenv()


# ---------------------------------------------------------------------------
# Settings dataclass
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Settings:
    """Immutable application settings loaded from environment variables."""

    # --- Gemini ---
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"

    # --- API Security ---
    API_KEY: str = "change_me"

    # --- Server ---
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # --- Tailscale ---
    TAILSCALE_IP: str = "127.0.0.1"

    # --- Database ---
    DB_PATH: str = str(_PROJECT_ROOT / "sentinel.db")

    # --- Frontend ---
    FRONTEND_DIR: str = str(_PROJECT_ROOT / "frontend")

    # --- Retention ---
    RETENTION_DAYS: int = 7

    # --- Collector tunables ---
    GEMINI_RATE_LIMIT: int = 20
    RAW_TEXT_MAX_CHARS: int = 1500
    RAW_TEXT_MIN_CHARS: int = 100

    # --- Derived (computed after init) ---
    ALLOWED_ORIGINS: List[str] = field(default_factory=list)
    PROJECT_ROOT: str = str(_PROJECT_ROOT)

    def __post_init__(self):
        # frozen=True requires object.__setattr__ for post-init mutations
        origins = [
            f"http://{self.TAILSCALE_IP}",
            f"http://{self.TAILSCALE_IP}:{self.API_PORT}",
            f"http://localhost:{self.API_PORT}",
            f"http://127.0.0.1:{self.API_PORT}",
        ]
        object.__setattr__(self, "ALLOWED_ORIGINS", origins)


def _load_settings() -> Settings:
    """Read environment variables and return a populated Settings instance."""

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_key:
        print(
            "[SENTINEL] WARNING: GEMINI_API_KEY is not set. "
            "The collector will not be able to analyse findings.",
            file=sys.stderr,
        )

    return Settings(
        GEMINI_API_KEY=gemini_key,
        GEMINI_MODEL=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
        API_KEY=os.getenv("API_KEY", "change_me"),
        API_HOST=os.getenv("API_HOST", "0.0.0.0"),
        API_PORT=int(os.getenv("API_PORT", "8000")),
        TAILSCALE_IP=os.getenv("TAILSCALE_IP", "127.0.0.1"),
        DB_PATH=os.getenv("DB_PATH", str(_PROJECT_ROOT / "sentinel.db")),
        FRONTEND_DIR=os.getenv("FRONTEND_DIR", str(_PROJECT_ROOT / "frontend")),
        RETENTION_DAYS=int(os.getenv("RETENTION_DAYS", "7")),
        GEMINI_RATE_LIMIT=int(os.getenv("GEMINI_RATE_LIMIT", "20")),
        RAW_TEXT_MAX_CHARS=int(os.getenv("RAW_TEXT_MAX_CHARS", "1500")),
        RAW_TEXT_MIN_CHARS=int(os.getenv("RAW_TEXT_MIN_CHARS", "100")),
    )


# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere
# ---------------------------------------------------------------------------
settings = _load_settings()
