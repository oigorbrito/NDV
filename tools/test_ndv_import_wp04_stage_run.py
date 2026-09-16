import json
import tempfile
import unittest
from pathlib import Path

from ndv_import_wp04_stage_run import parse_aider_tokens, validate_bundle


class WP04ImportTests(unittest.TestCase):
    def test_parses_and_sums_aider_token_lines(self):
        result = parse_aider_tokens("Tokens: 8.3k sent, 81 received.\nTokens: 19k sent, 23 received.\n")
        self.assertEqual(result["input_tokens"], 27300)
        self.assertEqual(result["output_tokens"], 104)
        self.assertEqual(result["total_tokens"], 27404)
        self.assertTrue(result["approximate"])
        self.assertEqual(len(result["samples"]), 2)

    def test_missing_token_lines_stays_missing(self):
        result = parse_aider_tokens("no telemetry")
        self.assertIsNone(result["input_tokens"])
        self.assertIsNone(result["total_tokens"])

    def _bundle(self, schema: str, task: str) -> Path:
        root = Path(self.tmp.name) / task
        evidence = root / "evidence"
        evidence.mkdir(parents=True)
        (evidence / "candidate.diff").write_text("", encoding="utf-8")
        (evidence / "executor.log").write_text("Tokens: 1k sent, 2 received.\n", encoding="utf-8")
        report = {
            "schema_id": schema,
            "task_id": task,
            "binding_id": "binding",
            "retry_count": 0,
            "escalation_count": 0,
            "holdout_access": "NONE",
            "outcome": "SMOKE_VALID_FAILED",
            "failure_attribution": "PRODUCT_FAILURE",
            "candidate": {
                "diff_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "diff_bytes": 0,
            },
            "executor": {"wall_seconds": 1.0},
        }
        (root / "run-report.json").write_text(json.dumps(report), encoding="utf-8")
        return root

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_accepts_stage1_schema(self):
        report, tokens = validate_bundle(self._bundle("ndv-wp04-stage1-run-v1", "D-F5-01"))
        self.assertEqual(report["task_id"], "D-F5-01")
        self.assertEqual(tokens["total_tokens"], 1002)

    def test_accepts_stage2_schema(self):
        report, tokens = validate_bundle(self._bundle("ndv-wp04-stage2-run-v1", "D-F6-01"))
        self.assertEqual(report["task_id"], "D-F6-01")
        self.assertEqual(tokens["total_tokens"], 1002)

    def test_rejects_schema_task_mismatch(self):
        with self.assertRaises(ValueError):
            validate_bundle(self._bundle("ndv-wp04-stage2-run-v1", "D-F5-01"))


if __name__ == "__main__":
    unittest.main()
