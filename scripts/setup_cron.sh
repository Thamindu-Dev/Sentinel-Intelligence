#!/bin/bash
# ============================================================
# Sentinel Intelligence — Cron Installer
# Run this ONCE on the OCI server to register the hourly job.
# ============================================================

set -e

SENTINEL_DIR=$(dirname "$(realpath "$0")")/..
PYTHON="$SENTINEL_DIR/venv/bin/python"
LOG_DIR="$SENTINEL_DIR/logs"

# Verify venv python exists
if [ ! -f "$PYTHON" ]; then
    echo "ERROR: venv python not found at $PYTHON"
    echo "Run: python3 -m venv $SENTINEL_DIR/venv && source $SENTINEL_DIR/venv/bin/activate && pip install -r $SENTINEL_DIR/backend/requirements.txt"
    exit 1
fi

mkdir -p "$LOG_DIR"

# Use absolute paths — cron doesn't inherit your shell $PATH
CRON_JOB="0 0,12 * * * cd $SENTINEL_DIR && $PYTHON -m backend.collector.collector >> $LOG_DIR/cron.log 2>&1"

# Remove any existing sentinel cron job, then add the new one
(crontab -l 2>/dev/null | grep -v 'backend.collector.collector'; echo "$CRON_JOB") | crontab -

echo "✓ Cron job installed. Runs twice a day (00:00 and 12:00)."
echo "  Verify with: crontab -l"
echo "  Logs at:     $LOG_DIR/cron.log"
