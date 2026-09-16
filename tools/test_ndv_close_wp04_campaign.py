import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from ndv_close_wp04_campaign import verify_import


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class WP04ClosureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def make_import(self, name: str, task: str, schema: str, binding: str = "binding", sidecar: bool = False) -> Path:
        root = self.root / name
        evidence = root / "evidence"
        evidence.mkdir(parents=True)
        (evidence / "candidate.diff").write_text("", encoding="utf-8")
        (evidence / "executor.log").write_text("Tokens: 8 sent, 2 received.\n", encoding="utf-8")
        report = {
            "schema_id": schema,
            "task_id": task,
            "binding_id": binding,
            "outcome": "SMOKE_VALID_FAILED",
            "failure_attribution": "PRODUCT_FAILURE",
            "retry_count": 0,
            "escalation_count": 0,
            "holdout_access": "NONE",
        }
        report_bytes = (json.dumps(report, sort_keys=True) + "\n").encode()
        (root / "run-report.json").write_bytes(report_bytes)
        diff_bytes = (evidence / "candidate.diff").read_bytes()
        log_bytes = (evidence / "executor.log").read_bytes()
        manifest = {
            "schema_id": "ndv-wp04-import-manifest-v2",
            "source_run_schema": schema,
            "task_id": task,
            "binding_id": binding,
            "outcome": "SMOKE_VALID_FAILED",
            "failure_attribution": "PRODUCT_FAILURE",
            "retry_count": 0,
            "escalation_count": 0,
            "holdout_access": "NONE",
            "token_reconciliation": {"total_tokens": 10, "approximate": False},
            "executor_wall_seconds": 1.5,
            "raw_evidence_preserved": True,
            "treatment_reexecuted": False,
            "preserved_artifacts": [
                {"path": "run-report.json", "size_bytes": len(report_bytes), "sha256": sha256(report_bytes)},
                {"path": "evidence/candidate.diff", "size_bytes": len(diff_bytes), "sha256": sha256(diff_bytes)},
                {"path": "evidence/executor.log", "size_bytes": len(log_bytes), "sha256": sha256(log_bytes)},
            ],
        }
        if sidecar:
            (root / "import-manifest.json").write_text(json.dumps({"schema_id": "ndv-wp04-import-manifest-v1"}), encoding="utf-8")
            manifest_path = root / "import-manifest-v2.json"
        else:
            manifest_path = root / "import-manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return root

    def test_stage1_import_verifies(self):
        root = self.make_import("s1", "D-F5-01", "ndv-wp04-stage1-run-v1")
        manifest, report, path = verify_import(root, "D-F5-01")
        self.assertEqual(manifest["binding_id"], report["binding_id"])
        self.assertEqual(path.name, "import-manifest.json")

    def test_sidecar_v2_is_preferred_over_legacy_manifest(self):
        root = self.make_import("s1", "D-F5-01", "ndv-wp04-stage1-run-v1", sidecar=True)
        manifest, _, path = verify_import(root, "D-F5-01")
        self.assertEqual(manifest["schema_id"], "ndv-wp04-import-manifest-v2")
        self.assertEqual(path.name, "import-manifest-v2.json")

    def test_stage2_import_verifies(self):
        root = self.make_import("s2", "D-F6-01", "ndv-wp04-stage2-run-v1")
        _, report, _ = verify_import(root, "D-F6-01")
        self.assertEqual(report["task_id"], "D-F6-01")

    def test_tampered_artifact_is_rejected(self):
        root = self.make_import("s1", "D-F5-01", "ndv-wp04-stage1-run-v1")
        (root / "evidence/candidate.diff").write_text("tampered", encoding="utf-8")
        with self.assertRaises(ValueError):
            verify_import(root, "D-F5-01")

    def test_old_manifest_is_rejected_without_sidecar(self):
        root = self.make_import("s1", "D-F5-01", "ndv-wp04-stage1-run-v1")
        manifest_path = root / "import-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["schema_id"] = "ndv-wp04-import-manifest-v1"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(ValueError):
            verify_import(root, "D-F5-01")

    def test_missing_provenance_flags_are_rejected(self):
        root = self.make_import("s1", "D-F5-01", "ndv-wp04-stage1-run-v1")
        path = root / "import-manifest.json"
        manifest = json.loads(path.read_text())
        manifest.pop("raw_evidence_preserved")
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "provenance"):
            verify_import(root, "D-F5-01")


if __name__ == "__main__":
    unittest.main()
