#!/bin/bash

set -e

# Default cron schedule if not provided
CRON_SCHEDULE=${CRON_SCHEDULE:-"*/30 * * * *"}

echo "Starting ICMS Watcher with cron schedule: $CRON_SCHEDULE"

# Create cron job
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
