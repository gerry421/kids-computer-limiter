"""
github_client.py — Fetches the master config YAML from GitHub and caches it locally.

On a successful fetch the raw config dict is returned and a local cache file is
written so the next run can fall back to it when the network is unavailable.
"""

import logging
import time
import urllib.error
import urllib.request

import yaml

logger = logging.getLogger(__name__)

CONFIG_URL = (
    "https://raw.githubusercontent.com/gerry421/kids-computer-limiter"
    "/main/configs/devices.yaml"
)
CACHE_PATH = "/tmp/limiter_config_cache.yaml"
REQUEST_TIMEOUT = 15  # seconds
MAX_RETRIES = 3


def _fetch_raw(url: str) -> str | None:
    """Attempt a single HTTP GET, returning the response body as a string."""
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        logger.warning("HTTP fetch failed: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unexpected fetch error: %s", exc)
        return None


def _save_cache(raw_yaml: str) -> None:
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as fh:
            fh.write(raw_yaml)
    except OSError as exc:
        logger.warning("Could not write config cache: %s", exc)


def _load_cache() -> dict | None:
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        age = time.time() - __import__("os").path.getmtime(CACHE_PATH)
        logger.info("Loaded cached config (age: %ds)", int(age))
        return data
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("Could not read config cache: %s", exc)
        return None


def fetch_config() -> dict | None:
    """
    Fetch the config from GitHub.  On failure, fall back to the local cache.
    Returns a parsed dict or None if both sources are unavailable.
    """
    backoff = 2
    for attempt in range(1, MAX_RETRIES + 1):
        raw = _fetch_raw(CONFIG_URL)
        if raw is not None:
            try:
                data = yaml.safe_load(raw)
                _save_cache(raw)
                logger.info("Config fetched from GitHub (attempt %d)", attempt)
                return data
            except yaml.YAMLError as exc:
                logger.error("GitHub config YAML is invalid: %s", exc)
                return _load_cache()

        if attempt < MAX_RETRIES:
            logger.debug("Retrying in %ds…", backoff)
            time.sleep(backoff)
            backoff *= 2

    logger.warning("All %d fetch attempts failed — using cached config", MAX_RETRIES)
    return _load_cache()
