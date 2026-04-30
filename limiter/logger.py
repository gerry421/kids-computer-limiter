"""
logger.py — Local and remote (GitHub) logging.

Design
------
* Every action is written to a local log file immediately.
* A lightweight check at the end of each run decides whether it is time to
  commit the accumulated log lines to the GitHub repository.  The commit
  cadence is controlled by LOG_COMMIT_INTERVAL_HOURS (default 2 h).
* Remote commits use the git CLI, which must be pre-configured on the Pi
  (i.e. the working directory must already be a git checkout of the repo).
"""

import logging
import logging.handlers
import os
import subprocess
from datetime import datetime

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOG_DIR_PRIMARY = "/var/log/limiter"
LOG_DIR_FALLBACK = "/tmp/limiter"
LOG_FILENAME = "limiter.log"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5

LAST_COMMIT_FILE = "/tmp/limiter_last_commit.txt"
LOG_COMMIT_INTERVAL_HOURS = 2

# Path to the git working copy of the repository on the Pi.
# Adjust this if the repo is cloned to a different location.
REPO_PATH = "/opt/kids-computer-limiter"
REMOTE_LOG_FILE = "logs/execution_log.txt"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_log_path: str | None = None


def _get_log_dir() -> str:
    for directory in (LOG_DIR_PRIMARY, LOG_DIR_FALLBACK):
        try:
            os.makedirs(directory, exist_ok=True)
            # Verify we can actually write there
            test = os.path.join(directory, ".write_test")
            with open(test, "w") as fh:
                fh.write("")
            os.remove(test)
            return directory
        except OSError:
            continue
    raise RuntimeError("Cannot create log directory in either primary or fallback path")


def _get_log_path() -> str:
    global _log_path
    if _log_path is None:
        _log_path = os.path.join(_get_log_dir(), LOG_FILENAME)
    return _log_path


def setup_logging() -> None:
    """Configure the root logger to write to a rotating local file + console."""
    log_path = _get_log_path()

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Rotating file handler
    fh = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Console handler (shows up in cron logs / journald)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    root.addHandler(ch)


# ---------------------------------------------------------------------------
# Structured action logging
# ---------------------------------------------------------------------------

_action_logger = logging.getLogger("limiter.action")


def log_action(
    level: str,
    device_id: str,
    action: str,
    details: str = "",
    success: bool = True,
) -> None:
    """
    Write a structured action line immediately to the local log.

    Format:
        [LEVEL] [device_id] [action] [details] success=True/False
    """
    msg = f"[{device_id}] [{action}] {details} success={success}"
    lvl = getattr(logging, level.upper(), logging.INFO)
    _action_logger.log(lvl, msg)


# ---------------------------------------------------------------------------
# Remote (GitHub) commit
# ---------------------------------------------------------------------------

def _hours_since_last_commit() -> float:
    """Return hours elapsed since the last successful remote commit."""
    try:
        mtime = os.path.getmtime(LAST_COMMIT_FILE)
        return (datetime.now().timestamp() - mtime) / 3600
    except OSError:
        return float("inf")  # Never committed yet


def _update_last_commit_timestamp() -> None:
    try:
        with open(LAST_COMMIT_FILE, "w") as fh:
            fh.write(datetime.now().isoformat())
    except OSError as exc:
        logging.getLogger(__name__).warning(
            "Could not write last-commit timestamp: %s", exc
        )


def _run_git(args: list[str], cwd: str) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, (result.stdout + result.stderr).strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return -1, str(exc)


def commit_logs_to_github(device_id: str) -> None:
    """
    If LOG_COMMIT_INTERVAL_HOURS have passed since the last commit, copy the
    local log into the repo's logs/ directory and push it to GitHub.

    Failures are logged locally but never raise — logging must not crash the
    main enforcement loop.
    """
    log = logging.getLogger(__name__)

    if _hours_since_last_commit() < LOG_COMMIT_INTERVAL_HOURS:
        return  # Not time yet

    if not os.path.isdir(REPO_PATH):
        log.debug(
            "Repo path %s not found — skipping remote log commit", REPO_PATH
        )
        return

    try:
        local_log = _get_log_path()
        if not os.path.exists(local_log):
            return

        remote_log_abs = os.path.join(REPO_PATH, REMOTE_LOG_FILE)
        os.makedirs(os.path.dirname(remote_log_abs), exist_ok=True)

        # Append new local log content to the remote log file
        with open(local_log, "r", encoding="utf-8", errors="replace") as src, \
             open(remote_log_abs, "a", encoding="utf-8") as dst:
            dst.write(f"\n# --- {device_id} log sync {datetime.now().isoformat()} ---\n")
            dst.write(src.read())

    except OSError as exc:
        log.warning("Could not copy log to repo: %s", exc)
        return

    # Pull latest to avoid divergence, then add/commit/push
    code, out = _run_git(["pull", "--rebase", "--quiet"], cwd=REPO_PATH)
    if code != 0:
        log.warning("git pull failed (code %d): %s", code, out)

    code, out = _run_git(["add", REMOTE_LOG_FILE], cwd=REPO_PATH)
    if code != 0:
        log.warning("git add failed: %s", out)
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_msg = f"Log update from {device_id} — {timestamp}"
    code, out = _run_git(["commit", "-m", commit_msg], cwd=REPO_PATH)
    if code != 0:
        if "nothing to commit" in out:
            log.debug("No new log data to commit")
        else:
            log.warning("git commit failed: %s", out)
        return

    code, out = _run_git(["push"], cwd=REPO_PATH)
    if code != 0:
        log.warning("git push failed — will retry next cycle: %s", out)
        return

    _update_last_commit_timestamp()
    log.info("[%s] Logs committed and pushed to GitHub", device_id)
