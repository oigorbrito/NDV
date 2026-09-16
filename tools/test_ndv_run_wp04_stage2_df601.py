import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from ndv_run_wp04_stage2_df601 import validate_stage1_import


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Stage2GateTests(unittest.TestCase):
    def make_import(self, *, schema="ndv-wp04-import-manifest-v2", binding_id="B1") -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        evidence = root / "evidence"
        evidence.mkdir()
        candidate = b""
        executor = b"Tokens: 1k sent, 2 received.\n"
        report = {
            "schema_id": "ndv-wp04-stage1-run-v1",
            "task_id": "D-F5-01",
            "binding_id": binding_id,
            "outcome": "SMOKE_VALID_FAILED",
        }
        report_bytes = (json.dumps(report, sort_keys=True) + "\n").encode()
        (root / "run-report.json").write_bytes(report_bytes)
        (evidence / "candidate.diff").write_bytes(candidate)
        (evidence / "executor.log").write_bytes(executor)
        manifest = {
            "schema_id": schema,
            "task_id": "D-F5-01",
            "binding_id": binding_id,
            "outcome": "SMOKE_VALID_FAILED",
            "raw_evidence_preserved": True,
            "treatment_reexecuted": False,
            "candidate_diff_sha256": sha(candidate),
            "preserved_artifacts": {
                "run-report.json": {"sha256": sha(report_bytes), "bytes": len(report_bytes)},
                "evidence/candidate.diff": {"sha256": sha(candidate), "bytes": len(candidate)},
                "evidence/executor.log": {"sha256": sha(executor), "bytes": len(executor)},
            },
        }
        (root / "import-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return root

    def test_valid_import_passes(self):
        root = self.make_import()
        manifest = validate_stage1_import(root, "B1")
        self.assertEqual(manifest["task_id"], "D-F5-01")

    def test_old_manifest_is_rejected(self):
        root = self.make_import(schema="ndv-wp04-import-manifest-v1")
        with self.assertRaises(ValueError):
            validate_stage1_import(root, "B1")

    def test_binding_mismatch_is_rejected(self):
        root = self.make_import(binding_id="B1")
        with self.assertRaises(ValueError):
            validate_stage1_import(root, "B2")

    def test_tampered_evidence_is_rejected(self):
        root = self.make_import()
        (root / "evidence" / "executor.log").write_text("tampered", encoding="utf-8")
        with self.assertRaises(ValueError):
            validate_stage1_import(root, "B1")


if __name__ == "__main__":
    unittest.main()
