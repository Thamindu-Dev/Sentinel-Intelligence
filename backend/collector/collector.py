"""
Sentinel Intelligence — Collector Orchestrator

This is the main entry point run by cron or Hermes.
It orchestrates: scrape → analyse → deduplicate → cleanup.

Usage (cron or manual):
    python -m backend.collector.collector
"""

import asyncio
import glob
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from backend.config import settings
from backend.db.database import init_db, purge_old_findings
from backend.collector.sources import scrape_all_sources
from backend.collector.analyzer import analyse_batch
from backend.collector.deduplicator import deduplicate_finding

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def _cleanup_old_logs(log_dir: Path, max_age_days: int = 2) -> None:
    """Delete log files older than max_age_days."""
    cutoff = datetime.now() - timedelta(days=max_age_days)
    for log_file in log_dir.glob("collector_*.log"):
        try:
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            if mtime < cutoff:
                log_file.unlink()
        except Exception:
            pass


def _setup_logging() -> logging.Logger:
    """Configure per-run timestamped log file + console logging."""
    log_dir = Path(settings.PROJECT_ROOT) / "logs"
    log_dir.mkdir(exist_ok=True)

    # Clean up logs older than 2 days
    _cleanup_old_logs(log_dir, max_age_days=2)

    logger = logging.getLogger("sentinel")
    logger.setLevel(logging.INFO)

    # Clear any existing handlers from previous imports
    if logger.handlers:
        logger.handlers.clear()

    # Per-run log file with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f"collector_{timestamp}.log"

    file_handler = logging.FileHandler(
        log_dir / log_filename,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(name)-22s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    ))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# ---------------------------------------------------------------------------
# Phase 1: Scraper
# ---------------------------------------------------------------------------

async def scrape_to_queue() -> None:
    """Scrape all sources and push instantly into the raw_items queue."""
    from backend.db.database import insert_raw_item, get_all_titles
    
    logger.info("Phase 1: Scraping sources...")
    raw_items = await scrape_all_sources()
    logger.info(f"Scraped {len(raw_items)} raw items from {len(raw_items)} entries")

    if not raw_items:
        return

    existing_titles = [t["title"].lower() for t in get_all_titles()]
    
    inserted = 0
    skipped = 0
    for item in raw_items:
        # Simple pre-filter for title
        item_lower = item.title.lower()
        if any(item_lower in ext or ext in item_lower for ext in existing_titles):
            skipped += 1
            continue
            
        was_inserted = insert_raw_item(
            title=item.title,
            url=item.url,
            raw_text=item.raw_text,
            source_name=item.source_name
        )
        if was_inserted:
            inserted += 1
        else:
            skipped += 1

    logger.info(f"Phase 1 Complete: {inserted} queued for analysis, {skipped} skipped (already known).")


# ---------------------------------------------------------------------------
# Phase 2: Analyzer
# ---------------------------------------------------------------------------

async def process_queue() -> None:
    """Pull pending items from the queue and send them to the LLM analyzer.
    
    Failed chunks are retried up to MAX_RETRIES times within the same run
    with exponential backoff. This prevents data from waiting until the next
    scheduled run while also capping retries to avoid infinite loops.
    """
    from backend.db.database import get_pending_raw_items, update_raw_item_status
    from backend.collector.sources import RawItem

    MAX_RETRIES = 2  # Max retries per failed chunk (so 3 total attempts)
    RETRY_BACKOFF = 90  # Seconds to wait before retrying a failed chunk

    # Fetch up to 1000 pending items per run
    pending = get_pending_raw_items(limit=1000)
    if not pending:
        logger.info("Phase 2: Queue empty. Nothing to analyse.")
        return

    chunk_size = 5
    chunks = [pending[i:i + chunk_size] for i in range(0, len(pending), chunk_size)]
    
    from backend.collector.deduplicator import deduplicate_finding
    from backend.collector.analyzer import analyse_chunk
    import asyncio

    logger.info(f"Phase 2: Processing {len(pending)} pending items in {len(chunks)} chunks.")
    
    total_findings = 0
    errors = 0
    failed_chunks = []  # Collect failed chunks for retry

    for idx, chunk_dicts in enumerate(chunks):
        logger.info(f"Processing chunk {idx + 1}/{len(chunks)}...")
        
        success = await _process_single_chunk(chunk_dicts, idx + 1, len(chunks))
        if success is None:  # CancelledError
            break
        elif success >= 0:
            total_findings += success
        else:
            errors += 1
            failed_chunks.append((idx, chunk_dicts))
            logger.warning(f"Chunk {idx + 1} failed. Waiting 60s before next chunk...")
                
        if idx < len(chunks) - 1:
            await asyncio.sleep(60)

    # --- Retry failed chunks ---
    if failed_chunks:
        for retry_attempt in range(1, MAX_RETRIES + 1):
            if not failed_chunks:
                break
            logger.info(f"Retrying {len(failed_chunks)} failed chunk(s) (attempt {retry_attempt}/{MAX_RETRIES})...")
            await asyncio.sleep(RETRY_BACKOFF)
            
            still_failed = []
            for orig_idx, chunk_dicts in failed_chunks:
                logger.info(f"Retrying chunk {orig_idx + 1} (attempt {retry_attempt}/{MAX_RETRIES})...")
                success = await _process_single_chunk(chunk_dicts, orig_idx + 1, len(chunks))
                if success is None:
                    break
                elif success >= 0:
                    total_findings += success
                    errors -= 1  # Recovered
                else:
                    still_failed.append((orig_idx, chunk_dicts))
            failed_chunks = still_failed
        
        if failed_chunks:
            logger.warning(f"{len(failed_chunks)} chunk(s) still failed after {MAX_RETRIES} retries. Items remain in queue.")

    logger.info(f"Phase 2 Complete: {total_findings} valid new findings added to DB. Errors: {errors}")


async def _process_single_chunk(chunk_dicts, chunk_num, total_chunks):
    """Process a single chunk. Returns: findings_count (>=0) on success, -1 on failure, None on cancel."""
    from backend.db.database import update_raw_item_status
    from backend.collector.sources import RawItem
    from backend.collector.deduplicator import deduplicate_finding
    from backend.collector.analyzer import analyse_chunk

    try:
        raw_objects = [
            RawItem(
                title=r["title"],
                url=r["url"],
                raw_text=r["raw_text"],
                source_name=r["source_name"],
                fetched_at=r["fetched_at"]
            ) for r in chunk_dicts
        ]
        
        findings, success = await analyse_chunk(raw_objects)
        
        if success:
            count = 0
            for finding in findings:
                try:
                    action, _ = deduplicate_finding(finding)
                    if action == "inserted":
                        count += 1
                except Exception as e:
                    logger.error(f"Error storing finding '{finding.title[:50]}': {e}")
            
            for r in chunk_dicts:
                update_raw_item_status(r["id"], "Processed")
            return count
        else:
            logger.error(f"Chunk {chunk_num} failed.")
            return -1
            
    except asyncio.CancelledError:
        logger.info("Collector interrupted! Gracefully exiting phase 2...")
        return None
    except Exception as e:
        logger.error(f"Analysis task error on chunk {chunk_num}: {e}")
        return -1


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

async def run_collector() -> None:
    """Execute one full collection cycle."""
    global logger
    logger = _setup_logging()

    start_time = datetime.now(timezone.utc)
    logger.info("=" * 60)
    logger.info(f"Collector run started at {start_time.isoformat()}")
    logger.info("=" * 60)

    # --- Step 0: Initialise DB ---
    init_db()

    # --- Step 1: Scrape directly to Queue ---
    await scrape_to_queue()

    # --- Step 2: Process Queue to Findings ---
    await process_queue()

    # --- Step 3: Retention cleanup ---
    logger.info("Phase 3: Running retention cleanup...")
    deleted = purge_old_findings()
    logger.info(f"Retention: deleted {deleted} findings/raw_items older than {settings.RETENTION_DAYS} days")

    # --- Done ---
    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(f"Collector run complete in {elapsed:.1f}s")
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _kill_old_instance():
    """Ensure only one collector runs. Catch and kill older processes."""
    import os
    import sys
    import subprocess
    
    lock_file = "collector.pid"
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "r") as f:
                old_pid = int(f.read().strip())
                
            if old_pid != os.getpid():
                # Attempt to kill old process cross-platform
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/PID", str(old_pid)], capture_output=True)
                else:
                    import signal
                    os.kill(old_pid, signal.SIGTERM)
        except Exception:
            pass # Ignore if old process didn't exist or couldn't be killed

    # Write our own PID to the lock file
    try:
        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass


def main():
    """Synchronous entry point for cron / CLI."""
    _kill_old_instance()
    try:
        asyncio.run(run_collector())
    except KeyboardInterrupt:
        # Expected manual cancellation
        pass
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
