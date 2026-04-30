"""
Tests for limiter/config.py
"""

import sys
import os
import tempfile
import unittest

# Allow importing the package from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from limiter.config import load_device_id, parse_config


SAMPLE_RAW = {
    "global": {"update_interval": 300},
    "devices": [
        {
            "device_id": "frankie-pi",
            "enabled": True,
            "downtime_hours": {"start": 22, "end": 6},
            "blocked_domains": ["youtube.com", "tiktok.com"],
            "blocked_urls": [],
            "notes": "Test device",
        },
        {
            "device_id": "disabled-pi",
            "enabled": False,
            "downtime_hours": {},
            "blocked_domains": [],
        },
    ],
}


class TestParseConfig(unittest.TestCase):

    def test_known_device_returns_config(self):
        cfg = parse_config(SAMPLE_RAW, "frankie-pi")
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg["device_id"], "frankie-pi")
        self.assertIn("youtube.com", cfg["blocked_domains"])
        self.assertEqual(cfg["downtime_hours"]["start"], 22)

    def test_unknown_device_returns_none(self):
        cfg = parse_config(SAMPLE_RAW, "unknown-pi")
        self.assertIsNone(cfg)

    def test_disabled_device_returns_none(self):
        cfg = parse_config(SAMPLE_RAW, "disabled-pi")
        self.assertIsNone(cfg)

    def test_none_raw_returns_none(self):
        cfg = parse_config(None, "frankie-pi")
        self.assertIsNone(cfg)

    def test_none_device_id_returns_none(self):
        cfg = parse_config(SAMPLE_RAW, None)
        self.assertIsNone(cfg)

    def test_domains_are_lowercased(self):
        raw = {
            "devices": [
                {
                    "device_id": "test",
                    "enabled": True,
                    "blocked_domains": ["YouTube.COM", "TikTok.com"],
                }
            ]
        }
        cfg = parse_config(raw, "test")
        self.assertIn("youtube.com", cfg["blocked_domains"])
        self.assertIn("tiktok.com", cfg["blocked_domains"])

    def test_missing_blocked_domains_defaults_to_empty_list(self):
        raw = {"devices": [{"device_id": "test", "enabled": True}]}
        cfg = parse_config(raw, "test")
        self.assertEqual(cfg["blocked_domains"], [])


class TestLoadDeviceId(unittest.TestCase):

    def test_reads_device_id(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write('DEVICE_ID="my-test-pi"\n')
            name = f.name

        import limiter.config as config_mod
        original = config_mod.DEVICE_ID_FILE
        config_mod.DEVICE_ID_FILE = name
        try:
            result = load_device_id()
            self.assertEqual(result, "my-test-pi")
        finally:
            config_mod.DEVICE_ID_FILE = original
            os.unlink(name)

    def test_missing_file_returns_none(self):
        import limiter.config as config_mod
        original = config_mod.DEVICE_ID_FILE
        config_mod.DEVICE_ID_FILE = "/nonexistent/path/device_id.conf"
        try:
            result = load_device_id()
            self.assertIsNone(result)
        finally:
            config_mod.DEVICE_ID_FILE = original


if __name__ == "__main__":
    unittest.main()
