import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ndv_probe_wp07_subscription_surfaces as mod


class ProbeTests(unittest.TestCase):
    def program(self, root: Path) -> Path:
        p = root / "program.json"
        p.write_text(json.dumps({
            "schema_id": "ndv-p1-wp07-executor-role-qualification-v1",
            "status": "PROSPECTIVE_FROZEN_NOT_EXECUTED",
            "treatment_execution": "NOT_EXECUTED",
            "holdout_access": "NONE",
        }), encoding="utf-8")
        return p

    def test_missing_clis_are_discovery_not_failure(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(mod.shutil, "which", return_value=None):
            result = mod.build(None, None, self.program(Path(tmp)))
            self.assertEqual(result["surfaces"]["codex"]["status"], "MISSING")
            self.assertEqual(result["surfaces"]["antigravity"]["status"], "MISSING")
            self.assertFalse(result["task_exposure"])

    @mock.patch.object(mod, "run")
    def test_codex_capabilities_detected_from_help(self, run_mock):
        exe = Path(__file__).resolve()
        def fake(argv, timeout=20):
            if "--version" in argv:
                return {"returncode": 0, "stdout": "codex-cli 0.153.0\n", "stderr": "", "timed_out": False}
            if "exec" in argv:
                return {"returncode": 0, "stdout": "--model MODEL --sandbox MODE --json --ephemeral\n", "stderr": "", "timed_out": False}
            return {"returncode": 0, "stdout": "Codex help\n", "stderr": "", "timed_out": False}
        run_mock.side_effect = fake
        result = mod.discover("codex", str(exe))
        self.assertEqual(result["status"], "DISCOVERED")
        self.assertTrue(result["model_flag_discovered"])
        self.assertTrue(result["sandbox_flag_discovered"])
        self.assertTrue(result["json_flag_discovered"])

    @mock.patch.object(mod, "run")
    def test_codex_without_model_flag_is_unresolved(self, run_mock):
        exe = Path(__file__).resolve()
        def fake(argv, timeout=20):
            if "--version" in argv:
                return {"returncode": 0, "stdout": "codex-cli 1\n", "stderr": "", "timed_out": False}
            if "exec" in argv:
                return {"returncode": 0, "stdout": "--sandbox MODE\n", "stderr": "", "timed_out": False}
            return {"returncode": 0, "stdout": "help\n", "stderr": "", "timed_out": False}
        run_mock.side_effect = fake
        self.assertEqual(mod.discover("codex", str(exe))["status"], "INTERFACE_UNRESOLVED")

    @mock.patch.object(mod, "run")
    def test_antigravity_requires_noninteractive_and_model_pinning(self, run_mock):
        exe = Path(__file__).resolve()
        run_mock.side_effect = [
            {"returncode": 0, "stdout": "agy 1.0.1\n", "stderr": "", "timed_out": False},
            {"returncode": 0, "stdout": "interactive terminal only\n", "stderr": "", "timed_out": False},
        ]
        result = mod.discover("agy", str(exe))
        self.assertEqual(result["status"], "INTERFACE_UNRESOLVED")
        self.assertFalse(result["model_pinning_interface_discovered"])

    def test_contaminated_program_blocks_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self.program(Path(tmp))
            payload = json.loads(p.read_text()); payload["treatment_execution"] = "EXECUTED"; p.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "contamination"):
                mod.build(None, None, p)


if __name__ == "__main__":
    unittest.main()
