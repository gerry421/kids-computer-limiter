#!/usr/bin/env bash
# =============================================================================
# limiter_runner.sh — Cron wrapper for the Kids Computer Limiter
#
# Called by cron every 5 minutes as root:
#   */5 * * * * /opt/kids-computer-limiter/install/limiter_runner.sh
# =============================================================================

set -uo pipefail

INSTALL_DIR="/opt/kids-computer-limiter"
MAIN_SCRIPT="$INSTALL_DIR/limiter/main.py"
LOG_FILE="/var/log/limiter/limiter.log"

# Fall back to /tmp if /var/log/limiter isn't writable
if [[ ! -w "$(dirname "$LOG_FILE")" ]]; then
    LOG_FILE="/tmp/limiter/limiter.log"
    mkdir -p "$(dirname "$LOG_FILE")"
fi

# Ensure python3 is on PATH even in a minimal cron environment
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

if [[ ! -f "$MAIN_SCRIPT" ]]; then
    echo "$(date -Iseconds) [ERROR] main.py not found at $MAIN_SCRIPT" >> "$LOG_FILE"
    exit 1
fi

python3 "$MAIN_SCRIPT" >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

if [[ $EXIT_CODE -ne 0 ]]; then
    echo "$(date -Iseconds) [ERROR] limiter exited with code $EXIT_CODE" >> "$LOG_FILE"
fi

exit $EXIT_CODE
