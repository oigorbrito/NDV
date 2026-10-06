import json
import sys
import unittest
from datetime import datetime
from unittest.mock import patch

from tools import ndv_local_surface_probe as probe


class LocalSurfaceProbeTimestampTests(unittest.TestCase):
    def run_probe(self, *args: str) -> dict:
        with patch.object(sys, "argv", ["ndv_local_surface_probe.py", *args]), patch.object(
            probe, "get_total_memory_bytes", return_value=123
        ), patch.object(probe, "probe_nvidia", return_value={"available": False, "gpus": []}), patch.object(
            probe,
            "probe_ollama",
            return_value={
                "cli": {"available": False, "returncode": None, "stdout": "", "stderr": "not found"},
                "api_reachable": False,
                "api_detail": {"error": "fixture"},
                "models": [],
            },
        ), patch("sys.stdout") as stdout:
            stdout.write.side_effect = lambda value: self.output.append(value)
            self.output = []
            self.assertEqual(probe.main(), 0)
            return json.loads("".join(self.output))

    def test_default_timestamp_is_iso8601_and_probe_is_read_only(self):
        report = self.run_probe()

        parsed = datetime.fromisoformat(report["timestamp_utc"])
        self.assertIsNotNone(parsed.tzinfo)
        self.assertTrue(report["read_only"])

    def test_omit_timestamp_is_deterministic_and_probe_is_read_only(self):
        first = self.run_probe("--omit-timestamp")
        second = self.run_probe("--omit-timestamp")

        self.assertEqual(first["timestamp_utc"], "NOT_RECORDED")
        self.assertEqual(second["timestamp_utc"], "NOT_RECORDED")
        self.assertEqual(first["timestamp_utc"], second["timestamp_utc"])
        self.assertTrue(first["read_only"])
        self.assertTrue(second["read_only"])


if __name__ == "__main__":
    unittest.main()
