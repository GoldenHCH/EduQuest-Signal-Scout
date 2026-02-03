#!/bin/bash
# Uninstall cron job for Utah Board Signal Scout

set -e

# Check if cron job exists
if crontab -l 2>/dev/null | grep -q "run_weekly.py"; then
    # Remove the cron job
    crontab -l 2>/dev/null | grep -v "run_weekly.py" | crontab -
    echo "Cron job removed successfully!"
else
    echo "No cron job found for Utah Board Signal Scout."
fi

echo ""
echo "Current cron jobs:"
crontab -l 2>/dev/null || echo "(none)"
