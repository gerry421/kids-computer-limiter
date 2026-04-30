"""
Tests for limiter/logger.py
"""

import sys
import os
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import limiter.logger as limiter_logger


class TestLogAction(unittest.TestCase):

    def setUp(self):
        # Redirect logger to a temp file
        self.log_dir = tempfile.mkdtemp()
        self._orig_primary = limiter_logger.LOG_DIR_PRIMARY
        self._orig_fallback = limiter_logger.LOG_DIR_FALLBACK
        limiter_logger.LOG_DIR_PRIMARY = self.log_dir
        limiter_logger.LOG_DIR_FALLBACK = self.log_dir
        limiter_logger._log_path = None  # force re-evaluation

        import logging
        # Clear existing handlers to avoid duplicate output
        logging.getLogger("limiter.action").handlers.clear()
        limiter_logger.setup_logging()

    def tearDown(self):
        limiter_logger.LOG_DIR_PRIMARY = self._orig_primary
        limiter_logger.LOG_DIR_FALLBACK = self._orig_fallback
        limiter_logger._log_path = None
        import logging
        root = logging.getLogger()
        root.handlers.clear()

    def _read_log(self):
        log_path = os.path.join(self.log_dir, limiter_logger.LOG_FILENAME)
        if not os.path.exists(log_path):
            return ""
        with open(log_path) as f:
            return f.read()

    def test_log_action_writes_to_file(self):
        limiter_logger.log_action("INFO", "test-pi", "STARTUP", "test run")
        content = self._read_log()
        self.assertIn("test-pi", content)
        self.assertIn("STARTUP", content)
        self.assertIn("test run", content)

    def test_log_action_records_failure(self):
        limiter_logger.log_action("ERROR", "test-pi", "HOSTS_UPDATE", "failed", success=False)
        content = self._read_log()
        self.assertIn("success=False", content)

    def test_log_action_records_success(self):
        limiter_logger.log_action("INFO", "test-pi", "HOSTS_UPDATE", "ok", success=True)
        content = self._read_log()
        self.assertIn("success=True", content)


class TestHoursSinceLastCommit(unittest.TestCase):

    def test_no_file_returns_inf(self):
        with patch("limiter.logger.LAST_COMMIT_FILE", "/nonexistent/file"):
            result = limiter_logger._hours_since_last_commit()
            self.assertEqual(result, float("inf"))

    def test_fresh_file_returns_low_value(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"dummy")
            name = f.name
        try:
            with patch("limiter.logger.LAST_COMMIT_FILE", name):
                result = limiter_logger._hours_since_last_commit()
                self.assertLess(result, 0.1)
        finally:
            os.unlink(name)


if __name__ == "__main__":
    unittest.main()
