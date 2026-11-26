import contextlib
import io
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from limiter import history, main


class TestHistory(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "home"
        self.chrome = self.home / ".config/chromium/Default/History"
        self.firefox = self.home / ".mozilla/firefox/test.default/places.sqlite"
        self.chrome.parent.mkdir(parents=True)
        self.firefox.parent.mkdir(parents=True)
        self.log_path = Path(self.temp.name) / "log/visits.sqlite3"
        self.patches = [
            patch.object(history, "LOG_PATH", self.log_path),
            patch.object(history.pwd, "getpwall", return_value=[SimpleNamespace(pw_dir=str(self.home))]),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

        with sqlite3.connect(self.chrome) as db:
            db.executescript("""
                CREATE TABLE urls (id INTEGER PRIMARY KEY, url TEXT);
                CREATE TABLE visits (id INTEGER PRIMARY KEY, url INTEGER, visit_time INTEGER);
            """)
            db.executemany("INSERT INTO urls VALUES (?, ?)", [
                (1, "https://Example.COM/private/path?secret=123"),
                (2, "chrome://settings"),
            ])
            db.executemany("INSERT INTO visits VALUES (?, ?, ?)", [
                (1, 1, history.CHROME_EPOCH_OFFSET + 1_700_000_000_000_000),
                (2, 2, history.CHROME_EPOCH_OFFSET + 1_700_000_001_000_000),
            ])
        with sqlite3.connect(self.firefox) as db:
            db.executescript("""
                CREATE TABLE moz_places (id INTEGER PRIMARY KEY, url TEXT);
                CREATE TABLE moz_historyvisits (id INTEGER PRIMARY KEY, place_id INTEGER, visit_date INTEGER);
                INSERT INTO moz_places VALUES (1, 'https://news.example.org/article');
                INSERT INTO moz_historyvisits VALUES (1, 1, 1700000002000000);
            """)

    def test_imports_domains_and_deduplicates_across_runs(self):
        history.collect()
        history.collect()
        with sqlite3.connect(self.chrome) as db:
            db.execute("INSERT INTO visits VALUES (?, ?, ?)",
                       (3, 1, history.CHROME_EPOCH_OFFSET + 1_700_000_003_000_000))
        history.collect()
        with sqlite3.connect(self.log_path) as db:
            rows = db.execute("SELECT visited_us, domain FROM visits ORDER BY visited_us").fetchall()
        self.assertEqual(rows, [
            (1_700_000_000_000_000, "example.com"),
            (1_700_000_002_000_000, "news.example.org"),
            (1_700_000_003_000_000, "example.com"),
        ])
        self.assertEqual(os.stat(self.log_path).st_mode & 0o777, 0o600)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(history.show(), 0)
        self.assertIn("2023-11-14T22:13:20+00:00\texample.com", output.getvalue())
        self.assertNotIn("secret", output.getvalue())
        self.assertNotIn("/private/path", output.getvalue())

    def test_corrupt_profile_does_not_prevent_other_profiles(self):
        self.chrome.write_bytes(b"not a database")
        with self.assertLogs("limiter.history", level="WARNING"):
            history.collect()
        with sqlite3.connect(self.log_path) as db:
            self.assertEqual(db.execute("SELECT domain FROM visits").fetchall(), [("news.example.org",)])

    def test_unavailable_log_is_reported(self):
        with patch.object(history, "LOG_PATH", self.home):
            with self.assertLogs("limiter.history", level="ERROR"):
                history.collect()

    def test_missing_log_reports_error(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(history.show(), 1)


class TestCheckIn(unittest.TestCase):
    @patch("limiter.main.limiter_logger.commit_logs_to_github")
    @patch("limiter.main.github_client.fetch_config", return_value=None)
    @patch("limiter.main.history.collect")
    @patch("limiter.main.config.load_device_id", return_value="test-pi")
    @patch("limiter.main.limiter_logger.log_action")
    @patch("limiter.main.limiter_logger.setup_logging")
    def test_collects_when_config_unavailable(self, setup, action, device, collect, fetch, commit):
        self.assertEqual(main.main(), 0)
        collect.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
