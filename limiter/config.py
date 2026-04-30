"""
config.py — Parse the raw config dict returned by github_client.

Responsibilities
----------------
* Load the device_id from /etc/limiter/device_id.conf
* Find the matching device block in the YAML
* Return a clean, validated config object for this device
"""

import logging
import os

logger = logging.getLogger(__name__)

DEVICE_ID_FILE = "/etc/limiter/device_id.conf"


def load_device_id() -> str | None:
    """Read the device_id from the local config file."""
    try:
        with open(DEVICE_ID_FILE, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("DEVICE_ID="):
                    value = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if value:
                        return value
        logger.error("DEVICE_ID not found in %s", DEVICE_ID_FILE)
        return None
    except OSError as exc:
        logger.error("Cannot read device ID file %s: %s", DEVICE_ID_FILE, exc)
        return None


def parse_config(raw: dict | None, device_id: str | None) -> dict | None:
    """
    Extract the config for `device_id` from the raw YAML dict.

    Returns a dict with keys:
        device_id, global, downtime_hours, blocked_domains, blocked_urls, notes
    or None if the device is missing / disabled / config is malformed.
    """
    if not raw or not device_id:
        logger.error("Cannot parse config: raw=%r device_id=%r", raw, device_id)
        return None

    global_cfg = raw.get("global", {})
    devices = raw.get("devices", [])

    if not isinstance(devices, list):
        logger.error("Config 'devices' key must be a list")
        return None

    for device in devices:
        if not isinstance(device, dict):
            continue
        if device.get("device_id") == device_id:
            if not device.get("enabled", True):
                logger.info("Device '%s' is disabled in config — skipping", device_id)
                return None

            blocked_domains = device.get("blocked_domains") or []
            blocked_urls = device.get("blocked_urls") or []

            return {
                "device_id": device_id,
                "global": global_cfg,
                "downtime_hours": device.get("downtime_hours") or {},
                "blocked_domains": [str(d).lower().strip() for d in blocked_domains],
                "blocked_urls": [str(u) for u in blocked_urls],
                "notes": device.get("notes", ""),
            }

    logger.warning("Device ID '%s' not found in config", device_id)
    return None
