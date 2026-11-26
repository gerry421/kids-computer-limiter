"""Collect browser visit domains in a private, local SQLite log."""

import logging
import os
import pwd
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

LOG_PATH = Path("/var/log/limiter/website_visits.sqlite3")
CHROME_EPOCH_OFFSET = 11644473600000000
log = logging.getLogger(__name__)


def _profiles():
    """Find history databases in local users' standard browser profiles."""
    homes = {Path(user.pw_dir) for user in pwd.getpwall() if user.pw_dir}
    for home in sorted(homes):
        for pattern in (
            ".config/chromium/*/History",
            ".config/google-chrome/*/History",
            ".mozilla/firefox/*/places.sqlite",
        ):
            for path in home.glob(pattern):
                if path.is_file():
                    yield path, "firefox" if path.name == "places.sqlite" else "chromium"


def _open_log():
    LOG_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(LOG_PATH, os.O_CREAT | os.O_WRONLY, 0o600)
    os.close(fd)
    os.chmod(LOG_PATH, 0o600)
    db = sqlite3.connect(LOG_PATH, timeout=5)
    db.execute(
        """CREATE TABLE IF NOT EXISTS visits (
            profile TEXT NOT NULL,
            visit_id INTEGER NOT NULL,
            visited_us INTEGER NOT NULL,
            domain TEXT NOT NULL,
            PRIMARY KEY (profile, visit_id, visited_us, domain)
        )"""
    )
    return db


def _domain(url):
    try:
        parsed = urlsplit(url)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
            return None
        return parsed.hostname.lower()
    except (TypeError, ValueError):
        return None


def _read_history(path, browser):
    try:
        uri = path.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=5)) as source:
            if browser == "firefox":
                rows = source.execute(
                    "SELECT v.id, v.visit_date, p.url FROM moz_historyvisits v "
                    "JOIN moz_places p ON p.id = v.place_id"
                )
            else:
                rows = source.execute(
                    "SELECT v.id, v.visit_time, u.url FROM visits v "
                    "JOIN urls u ON u.id = v.url"
                )
            while True:
                batch = rows.fetchmany(1000)
                if not batch:
                    break
                yield batch
    except (OSError, sqlite3.Error) as exc:
        log.warning("Could not read browser history %s: %s", path, exc)


def collect():
    """Import stored browser visits; failures never interrupt enforcement."""
    try:
        with closing(_open_log()) as target, target:
            for path, browser in _profiles():
                offset = 0 if browser == "firefox" else CHROME_EPOCH_OFFSET
                for batch in _read_history(path, browser):
                    entries = []
                    for visit_id, timestamp, url in batch:
                        domain = _domain(url)
                        if domain and isinstance(timestamp, int) and timestamp > offset:
                            entries.append((str(path), visit_id, timestamp - offset, domain))
                    target.executemany("INSERT OR IGNORE INTO visits VALUES (?, ?, ?, ?)", entries)
    except (OSError, sqlite3.Error) as exc:
        log.error("Could not update local website log %s: %s", LOG_PATH, exc)


def show():
    """Print the local log without modifying or creating it."""
    try:
        uri = LOG_PATH.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=5)) as db:
            for visited_us, domain, profile in db.execute(
                "SELECT visited_us, domain, profile FROM visits ORDER BY visited_us"
            ):
                visited = datetime.fromtimestamp(visited_us / 1_000_000, timezone.utc)
                print(f"{visited.isoformat()}\t{domain}\t{profile}")
    except (OSError, sqlite3.Error, OverflowError, ValueError) as exc:
        print(f"Could not read website log {LOG_PATH}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(show())
