"""
enforcer.py — Apply restrictions to the local system.

Two main responsibilities
-------------------------
1. Downtime — if the current time is inside the configured downtime window,
   trigger an immediate system shutdown.
2. Hosts-file management — maintain a clearly delimited block in /etc/hosts
   so that blocked domains resolve to 127.0.0.1 locally, and the entire
   block can be removed in one sweep to undo all restrictions.
"""

import logging
import os
import subprocess
from datetime import datetime

logger = logging.getLogger(__name__)

HOSTS_FILE = "/etc/hosts"
HOSTS_BACKUP = "/etc/hosts.limiter.backup"
BLOCK_BEGIN = "# === BEGIN LIMITER BLOCK ==="
BLOCK_END = "# === END LIMITER BLOCK ==="


# ---------------------------------------------------------------------------
# Downtime helpers
# ---------------------------------------------------------------------------

def is_downtime(downtime_hours: dict) -> bool:
    """
    Return True if the current local time falls inside the downtime window.

    downtime_hours is expected to have integer keys 'start' and 'end' (24-h).
    Example: start=22, end=6  means 22:00 – 06:00 (crosses midnight).
    """
    if not downtime_hours:
        return False

    start = downtime_hours.get("start")
    end = downtime_hours.get("end")

    if start is None or end is None:
        return False

    try:
        start = int(start)
        end = int(end)
    except (TypeError, ValueError):
        logger.warning("Invalid downtime_hours values: %r", downtime_hours)
        return False

    now = datetime.now().hour

    if start < end:
        # e.g. 08:00 – 18:00 — does not cross midnight
        return start <= now < end
    else:
        # e.g. 22:00 – 06:00 — crosses midnight
        return now >= start or now < end


def trigger_shutdown(device_id: str) -> None:
    """Initiate an immediate system halt."""
    logger.warning(
        "[%s] Downtime in effect — triggering shutdown now", device_id
    )
    try:
        subprocess.run(["sudo", "shutdown", "-h", "now"], check=True)
    except subprocess.CalledProcessError as exc:
        logger.error("shutdown command failed: %s", exc)
    except FileNotFoundError:
        logger.error("'shutdown' binary not found — cannot halt the system")


# ---------------------------------------------------------------------------
# Hosts-file helpers
# ---------------------------------------------------------------------------

def _backup_hosts() -> None:
    """Create a one-time backup of the original /etc/hosts."""
    if os.path.exists(HOSTS_BACKUP):
        return
    try:
        with open(HOSTS_FILE, "r", encoding="utf-8") as src, \
             open(HOSTS_BACKUP, "w", encoding="utf-8") as dst:
            dst.write(src.read())
        logger.info("Created hosts backup at %s", HOSTS_BACKUP)
    except OSError as exc:
        logger.warning("Could not back up hosts file: %s", exc)


def _flush_dns() -> None:
    """Attempt to flush the local DNS resolver cache."""
    for cmd in (
        ["sudo", "systemctl", "restart", "systemd-resolved"],
        ["sudo", "service", "dnsmasq", "restart"],
        ["sudo", "killall", "-HUP", "dnsmasq"],
    ):
        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=10
            )
            if result.returncode == 0:
                logger.debug("DNS flushed via %s", " ".join(cmd))
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    logger.debug("No DNS flush method succeeded (may not be needed)")


def update_hosts_file(blocked_domains: list[str]) -> bool:
    """
    Rewrite the LIMITER BLOCK inside /etc/hosts so that exactly the domains
    in `blocked_domains` are redirected to 127.0.0.1.

    * Lines outside the block are left untouched.
    * An existing block is replaced in-place; if none exists it is appended.
    * Returns True on success, False if the hosts file could not be updated.
    """
    _backup_hosts()

    try:
        with open(HOSTS_FILE, "r", encoding="utf-8") as fh:
            original = fh.read()
    except OSError as exc:
        logger.error("Cannot read %s: %s", HOSTS_FILE, exc)
        return False

    # Split file into: before-block, (ignored old block), after-block
    lines = original.splitlines(keepends=True)
    before_block: list[str] = []
    after_block: list[str] = []
    in_block = False
    found_block = False

    for line in lines:
        stripped = line.rstrip("\n").rstrip()
        if stripped == BLOCK_BEGIN:
            in_block = True
            found_block = True
            continue
        if stripped == BLOCK_END:
            in_block = False
            continue
        if not in_block:
            if not found_block:
                before_block.append(line)
            else:
                after_block.append(line)

    # Build new block lines
    new_block_lines: list[str] = []
    for domain in sorted(set(blocked_domains)):
        new_block_lines.append(f"127.0.0.1 {domain}\n")
        # Also block www. subdomain if not already listed explicitly
        www_domain = f"www.{domain}"
        if www_domain not in blocked_domains:
            new_block_lines.append(f"127.0.0.1 {www_domain}\n")

    # Reassemble
    new_contents = "".join(before_block)
    if not new_contents.endswith("\n") and new_contents:
        new_contents += "\n"
    new_contents += BLOCK_BEGIN + "\n"
    new_contents += "".join(new_block_lines)
    new_contents += BLOCK_END + "\n"
    new_contents += "".join(after_block)

    try:
        with open(HOSTS_FILE, "w", encoding="utf-8") as fh:
            fh.write(new_contents)
    except OSError as exc:
        logger.error("Cannot write %s: %s", HOSTS_FILE, exc)
        return False

    logger.info(
        "Hosts file updated — %d domains blocked", len(blocked_domains)
    )
    _flush_dns()
    return True


def clear_hosts_block() -> bool:
    """
    Remove the entire LIMITER BLOCK from /etc/hosts and flush DNS.
    Useful for emergency override or uninstallation.
    Returns True on success.
    """
    return update_hosts_file([])
