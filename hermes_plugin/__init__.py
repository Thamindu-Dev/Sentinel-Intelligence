"""Sentinel Intelligence plugin for Hermes."""

import subprocess
import threading
from pathlib import Path

from . import schemas, tools

_PLUGIN_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _PLUGIN_DIR.parent
_VENV_PYTHON = _PROJECT_ROOT / "venv" / "bin" / "python"
if not _VENV_PYTHON.exists():
    _VENV_PYTHON = _PROJECT_ROOT / "venv" / "Scripts" / "python.exe" # Windows fallback

def _run_collector_in_background():
    """Run the collector in a background thread."""
    try:
        subprocess.run(
            [str(_VENV_PYTHON), "-m", "backend.collector.collector"],
            cwd=str(_PROJECT_ROOT),
            check=False
        )
    except Exception as e:
        print(f"Error running collector: {e}")

def _handle_sentinel_command(raw_args: str) -> str:
    """Handler for /sentinel command."""
    args = raw_args.strip().lower().split()
    cmd = args[0] if args else "status"
    
    if cmd == "run":
        # Start collector in background
        thread = threading.Thread(target=_run_collector_in_background)
        thread.start()
        return "🚀 Sentinel Collector triggered in the background. Check logs or UI later for results."
        
    elif cmd == "status":
        import sys
        if str(_PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(_PROJECT_ROOT))
        try:
            from backend.db.database import get_stats
            stats = get_stats()
            # Format nicely
            text = "🛡️ **Sentinel Status**\n\n"
            text += "**Severities:**\n"
            for s in stats["severities"]:
                text += f"- {s['severity']}: {s['count']}\n"
            text += "\n**Statuses:**\n"
            for s in stats["statuses"]:
                text += f"- {s['status']}: {s['count']}\n"
            return text
        except Exception as e:
            return f"❌ Error fetching status: {str(e)}"
            
    else:
        return "Usage: `/sentinel status` or `/sentinel run`"

def register(ctx):
    """Wire schemas to handlers and register commands."""
    # Register Tools for LLM
    ctx.register_tool(
        name="sentinel_get_findings",
        toolset="sentinel",
        schema=schemas.GET_FINDINGS,
        handler=tools.get_findings
    )
    ctx.register_tool(
        name="sentinel_get_stats",
        toolset="sentinel",
        schema=schemas.GET_STATS,
        handler=tools.get_stats
    )
    ctx.register_tool(
        name="sentinel_mark_reviewed",
        toolset="sentinel",
        schema=schemas.MARK_REVIEWED,
        handler=tools.mark_reviewed
    )

    # Register Slash Command for User
    ctx.register_command(
        "sentinel",
        handler=_handle_sentinel_command,
        description="Sentinel controls: /sentinel status | /sentinel run"
    )
