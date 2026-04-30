"""
Tests for limiter/enforcer.py
"""

import sys
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from limiter import enforcer


BLOCK_BEGIN = enforcer.BLOCK_BEGIN
BLOCK_END = enforcer.BLOCK_END


class TestIsDowntime(unittest.TestCase):

    def _check(self, hour, start, end):
        """Helper: patch datetime.now().hour and call is_downtime."""
        mock_dt = MagicMock()
        mock_dt.hour = hour
        with patch("limiter.enforcer.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt
            return enforcer.is_downtime({"start": start, "end": end})

    def test_within_simple_window(self):
        self.assertTrue(self._check(10, 8, 18))

    def test_outside_simple_window(self):
        self.assertFalse(self._check(7, 8, 18))
        self.assertFalse(self._check(19, 8, 18))

    def test_midnight_crossing_before_midnight(self):
        self.assertTrue(self._check(23, 22, 6))

    def test_midnight_crossing_after_midnight(self):
        self.assertTrue(self._check(3, 22, 6))

    def test_midnight_crossing_outside(self):
        self.assertFalse(self._check(10, 22, 6))

    def test_empty_config_returns_false(self):
        self.assertFalse(enforcer.is_downtime({}))

    def test_none_returns_false(self):
        self.assertFalse(enforcer.is_downtime(None))


class TestUpdateHostsFile(unittest.TestCase):

    def setUp(self):
        # Write a minimal hosts file to a temp file
        self.hosts_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".hosts", delete=False
        )
        self.hosts_file.write(
            "127.0.0.1\tlocalhost\n"
            "::1\t\tlocalhost\n"
        )
        self.hosts_file.close()

        # Patch module constants to use temp file
        self._orig_hosts = enforcer.HOSTS_FILE
        self._orig_backup = enforcer.HOSTS_BACKUP
        enforcer.HOSTS_FILE = self.hosts_file.name
        enforcer.HOSTS_BACKUP = self.hosts_file.name + ".backup"

    def tearDown(self):
        enforcer.HOSTS_FILE = self._orig_hosts
        enforcer.HOSTS_BACKUP = self._orig_backup
        os.unlink(self.hosts_file.name)
        backup = self.hosts_file.name + ".backup"
        if os.path.exists(backup):
            os.unlink(backup)

    def _read_hosts(self):
        with open(self.hosts_file.name) as f:
            return f.read()

    @patch("limiter.enforcer._flush_dns")
    def test_adds_block_for_domains(self, _flush):
        enforcer.update_hosts_file(["example.com", "test.com"])
        content = self._read_hosts()
        self.assertIn(BLOCK_BEGIN, content)
        self.assertIn(BLOCK_END, content)
        self.assertIn("127.0.0.1 example.com", content)
        self.assertIn("127.0.0.1 www.example.com", content)

    @patch("limiter.enforcer._flush_dns")
    def test_preserves_non_limiter_entries(self, _flush):
        enforcer.update_hosts_file(["example.com"])
        content = self._read_hosts()
        self.assertIn("127.0.0.1\tlocalhost", content)
        self.assertIn("::1\t\tlocalhost", content)

    @patch("limiter.enforcer._flush_dns")
    def test_clears_block_when_empty_list(self, _flush):
        enforcer.update_hosts_file(["example.com"])
        enforcer.update_hosts_file([])
        content = self._read_hosts()
        self.assertNotIn("example.com", content)
        # Block markers should still be present but empty
        self.assertIn(BLOCK_BEGIN, content)
        self.assertIn(BLOCK_END, content)

    @patch("limiter.enforcer._flush_dns")
    def test_replaces_domains_on_second_run(self, _flush):
        enforcer.update_hosts_file(["old.com"])
        enforcer.update_hosts_file(["new.com"])
        content = self._read_hosts()
        self.assertNotIn("old.com", content)
        self.assertIn("new.com", content)

    @patch("limiter.enforcer._flush_dns")
    def test_creates_backup(self, _flush):
        enforcer.update_hosts_file([])
        self.assertTrue(os.path.exists(self.hosts_file.name + ".backup"))


if __name__ == "__main__":
    unittest.main()
