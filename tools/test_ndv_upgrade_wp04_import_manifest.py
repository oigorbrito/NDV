import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import ndv_upgrade_wp04_import_manifest as mod


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class UpgradeTests(unittest.TestCase):
    def fixture(self) -> Path:
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root = Path(tmp.name); evidence = root / "evidence"; evidence.mkdir()
        candidate = b""; executor = b"Tokens: 8.3k sent, 81 received.\nTokens: 19k sent, 23 received.\n"
        report = {
            "schema_id": "ndv-wp04-stage1-run-v1", "task_id": "D-F5-01", "binding_id": "B1",
            "outcome": "SMOKE_VALID_FAILED", "failure_attribution": "PRODUCT_FAILURE",
            "retry_count": 0, "escalation_count": 0, "holdout_access": "NONE",
            "candidate": {"diff_sha256": sha(candidate), "diff_bytes": 0},
            "executor": {"wall_seconds": 12.5},
        }
        (root / "run-report.json").write_text(json.dumps(report), encoding="utf-8")
        (evidence / "candidate.diff").write_bytes(candidate); (evidence / "executor.log").write_bytes(executor)
        legacy = {
            "schema_id": "ndv-wp04-import-manifest-v1", "task_id": "D-F5-01", "binding_id": "B1",
            "outcome": "SMOKE_VALID_FAILED", "retry_count": 0, "escalation_count": 0, "holdout_access": "NONE",
            "candidate_diff_sha256": sha(candidate), "candidate_diff_bytes": 0, "treatment_reexecuted": False,
        }
        (root / "import-manifest.json").write_text(json.dumps(legacy), encoding="utf-8")
        return root

    def test_builds_v2_sidecar_without_mutating_legacy(self):
        root = self.fixture(); before = (root / "import-manifest.json").read_bytes()
        sidecar = mod.build_sidecar(root)
        self.assertEqual(sidecar["schema_id"], "ndv-wp04-import-manifest-v2")
        self.assertTrue(sidecar["raw_evidence_preserved"])
        self.assertFalse(sidecar["treatment_reexecuted"])
        self.assertEqual(sidecar["token_reconciliation"]["total_tokens"], 27404)
        self.assertEqual((root / "import-manifest.json").read_bytes(), before)
        paths = {x["path"] for x in sidecar["preserved_artifacts"]}
        self.assertEqual(paths, {"run-report.json", "evidence/candidate.diff", "evidence/executor.log"})

    def test_legacy_mismatch_rejected(self):
        root = self.fixture(); legacy = json.loads((root / "import-manifest.json").read_text()); legacy["binding_id"] = "OTHER"; (root / "import-manifest.json").write_text(json.dumps(legacy))
        with self.assertRaisesRegex(ValueError, "mismatch"):
            mod.build_sidecar(root)

    def test_candidate_tamper_rejected(self):
        root = self.fixture(); (root / "evidence" / "candidate.diff").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "candidate.diff hash"):
            mod.build_sidecar(root)


if __name__ == "__main__": unittest.main()
