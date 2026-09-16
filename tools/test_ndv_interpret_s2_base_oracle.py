import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "ndv_interpret_s2_base_oracle.py"
spec = importlib.util.spec_from_file_location("ndv_oracle", TARGET)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


class OracleInterpreterTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "instance_id": "repo__task-1",
            "base_commit": "a" * 40,
            "FAIL_TO_PASS": ["test_bug"],
            "PASS_TO_PASS": ["test_regression"],
            "install_config": {"log_parser": "fixture"},
        }
        self.run = {
            "candidate_id": "S2W01-repo__task-1",
            "source_instance_id": "repo__task-1",
            "base_revision": "a" * 40,
            "gold_patch_applied": False,
            "test_patch_applied": False,
        }

    def parser(self, _log):
        return {"test_bug": "FAILED", "test_regression": "PASSED"}

    def test_expected_base_behavior(self):
        result = mod.interpret(self.row, self.run, "ignored", self.parser)
        self.assertEqual(result["classification"], "EXPECTED_BASE_BEHAVIOR")

    def test_missing_expected_test_is_oracle_mismatch(self):
        result = mod.interpret(self.row, self.run, "ignored", lambda _: {"test_bug": "FAILED"})
        self.assertEqual(result["classification"], "ORACLE_MISMATCH")
        self.assertIn("test_regression", result["missing_expected_tests"])

    def test_empty_parser_result_is_environment_inconclusive(self):
        result = mod.interpret(self.row, self.run, "ignored", lambda _: {})
        self.assertEqual(result["classification"], "ENVIRONMENT_INCONCLUSIVE")

    def test_patch_application_is_rejected(self):
        run = dict(self.run)
        run["gold_patch_applied"] = True
        with self.assertRaises(RuntimeError):
            mod.interpret(self.row, run, "ignored", self.parser)

    def test_identity_mismatch_is_rejected(self):
        run = dict(self.run)
        run["base_revision"] = "b" * 40
        with self.assertRaises(RuntimeError):
            mod.interpret(self.row, run, "ignored", self.parser)

    def test_no_fail_to_pass_is_not_silently_accepted(self):
        row = dict(self.row)
        row["FAIL_TO_PASS"] = []
        result = mod.interpret(row, self.run, "ignored", self.parser)
        self.assertEqual(result["classification"], "ORACLE_MISMATCH")


if __name__ == "__main__":
    unittest.main()
