#!/bin/bash
# Install cron job for Utah Board Signal Scout weekly run
# Runs every Sunday at 9pm local time

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Find Python interpreter
if [ -d "$PROJECT_DIR/venv" ]; then
    PYTHON="$PROJECT_DIR/venv/bin/python"
elif [ -d "$PROJECT_DIR/.venv" ]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
else
    PYTHON="python3"
fi

# Create logs directory if needed
mkdir -p "$PROJECT_DIR/data/logs"

# Cron job command
CRON_CMD="0 21 * * 0 cd $PROJECT_DIR && $PYTHON scripts/run_weekly.py >> data/logs/cron.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "run_weekly.py"; then
    echo "Cron job already exists. Updating..."
    # Remove existing job
    crontab -l 2>/dev/null | grep -v "run_weekly.py" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -

echo "Cron job installed successfully!"
echo ""
echo "Schedule: Every Sunday at 9:00 PM"
echo "Command: $CRON_CMD"
echo ""
echo "To view cron jobs: crontab -l"
echo "To remove: ./scripts/uninstall_cron.sh"
