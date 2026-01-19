#!/bin/bash

set -e

# Get the path to uv (installed in system Python)
UV_PATH=$(python -m site --user-base)/bin/uv || which uv

# Default cron schedule if not provided
CRON_SCHEDULE=${CRON_SCHEDULE:-"*/30 * * * *"}

# Check if we should run in one-shot mode
if [ "$RUN_ONCE" = "true" ]; then
    echo "Running ICMS Watcher in one-shot mode..."
    cd /app && uv run python /app/main.py
    echo "One-shot run completed, exiting..."
    exit 0
fi

echo "Starting ICMS Watcher with cron schedule: $CRON_SCHEDULE"

# Create cron job with explicit PATH for uv
echo "$CRON_SCHEDULE cd /app && uv run python /app/main.py >> /app/logs/cron.log 2>&1" > /etc/cron.d/icms-watcher

# Give execution rights on the cron job
chmod 0644 /etc/cron.d/icms-watcher

# Apply cron job
crontab /etc/cron.d/icms-watcher

# Create the log file to be able to run tail
touch /app/logs/cron.log

# Run once immediately on startup
echo "Running initial check..."
cd /app && uv run python /app/main.py >> /app/logs/cron.log 2>&1 || true

# Start cron in foreground
echo "Starting cron daemon..."
cron

# Follow the log file
tail -f /app/logs/cron.log
