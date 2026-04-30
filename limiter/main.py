"""
main.py — Orchestration entry point.

Execution flow (runs every 5 minutes via cron)
----------------------------------------------
1.  Set up logging
2.  Load device_id from /etc/limiter/device_id.conf
3.  Fetch fresh config from GitHub (falls back to cache on failure)
4.  Parse device-specific restrictions
5.  If currently in downtime → shut down and exit
6.  Update /etc/hosts with current blocked domains
7.  Attempt to commit logs to GitHub (rate-limited to every 2 h)
8.  Exit cleanly
"""

import logging
import sys

from limiter import logger as limiter_logger
from limiter import config, enforcer, github_client


def main() -> int:
    # -----------------------------------------------------------------------
    # 1. Logging
    # -----------------------------------------------------------------------
    limiter_logger.setup_logging()
    log = logging.getLogger("limiter.main")

    log.info("=== Limiter run started ===")

    # -----------------------------------------------------------------------
    # 2. Device ID
    # -----------------------------------------------------------------------
    device_id = config.load_device_id()
    if not device_id:
        log.error("No device ID available — aborting run")
        return 1

    log.info("Device ID: %s", device_id)
    limiter_logger.log_action("INFO", device_id, "STARTUP", "run started")

    # -----------------------------------------------------------------------
    # 3. Fetch config
    # -----------------------------------------------------------------------
    raw_config = github_client.fetch_config()
    if raw_config is None:
        limiter_logger.log_action(
            "WARNING", device_id, "CONFIG_FETCH",
            "GitHub unreachable and no cache — keeping current state",
            success=False,
        )
        log.warning("No config available — keeping current system state")
        limiter_logger.commit_logs_to_github(device_id)
        return 0

    limiter_logger.log_action("INFO", device_id, "CONFIG_FETCH", "success")

    # -----------------------------------------------------------------------
    # 4. Parse device config
    # -----------------------------------------------------------------------
    device_config = config.parse_config(raw_config, device_id)
    if device_config is None:
        limiter_logger.log_action(
            "WARNING", device_id, "CONFIG_PARSE",
            "device not found or disabled — keeping current state",
            success=False,
        )
        log.warning("Device config unavailable — keeping current state")
        limiter_logger.commit_logs_to_github(device_id)
        return 0

    limiter_logger.log_action("INFO", device_id, "CONFIG_PARSE", "success")

    # -----------------------------------------------------------------------
    # 5. Downtime check
    # -----------------------------------------------------------------------
    downtime_hours = device_config.get("downtime_hours", {})
    if enforcer.is_downtime(downtime_hours):
        limiter_logger.log_action(
            "WARNING", device_id, "DOWNTIME",
            f"downtime window {downtime_hours} — shutting down",
        )
        # Attempt to push logs before the machine goes offline
        limiter_logger.commit_logs_to_github(device_id)
        enforcer.trigger_shutdown(device_id)
        return 0

    limiter_logger.log_action("INFO", device_id, "DOWNTIME_CHECK", "outside downtime window")

    # -----------------------------------------------------------------------
    # 6. Apply domain blocks
    # -----------------------------------------------------------------------
    blocked_domains = device_config.get("blocked_domains", [])
    log.info("Applying %d blocked domain(s)", len(blocked_domains))

    success = enforcer.update_hosts_file(blocked_domains)
    limiter_logger.log_action(
        "INFO" if success else "ERROR",
        device_id,
        "HOSTS_UPDATE",
        f"{len(blocked_domains)} domain(s)",
        success=success,
    )

    # -----------------------------------------------------------------------
    # 7. Remote log commit (rate-limited)
    # -----------------------------------------------------------------------
    limiter_logger.commit_logs_to_github(device_id)

    # -----------------------------------------------------------------------
    # 8. Done
    # -----------------------------------------------------------------------
    log.info("=== Limiter run complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
