import json
import tempfile
import unittest
from pathlib import Path

import ndv_release_wp07_development_comparison as mod


class WP07ReleaseTests(unittest.TestCase):
    def write_inputs(self, root: Path, *, ready=True):
        wp04 = root / "wp04.json"
        wp04.write_text(json.dumps({
            "schema_id": "ndv-p1-wp04-campaign-closure-v1",
            "status": "WP04_PIPELINE_SMOKE_COMPLETE",
            "integrity": {"raw_evidence_preserved": True, "treatment_reexecuted": False, "retries": 0, "escalations": 0, "holdout_access": "NONE"},
            "authority": {"pipeline_smoke": "COMPLETE", "comparative_p1_release": "NO"},
        }))
        readiness = root / "readiness.json"
        readiness.write_text(json.dumps({
            "schema_id": "ndv-p1-s2-corpus-readiness-assessment-v1",
            "status": "WP06_INTAKE_TARGET_REACHED" if ready else "WP06_INTAKE_TARGET_NOT_REACHED",
            "checks": {"a": ready, "b": ready},
            "combined_task_count": 9,
            "s2": {"admitted_count": 5},
            "comparative_corpus_ready": "NO",
            "wp07_release": "NO",
            "treatment_execution": "NOT_EXECUTED",
            "holdout_access": "NONE",
        }))
        return wp04, readiness

    def test_valid_prerequisites_release_development_comparison_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp04, readiness = self.write_inputs(Path(tmp))
            result = mod.release(wp04, readiness)
            self.assertEqual(result["status"], "WP07_DEVELOPMENT_COMPARISON_RELEASED")
            self.assertTrue(result["authorized_scope"]["development_corpus_comparative_treatment_execution"])
            self.assertFalse(result["authorized_scope"]["sealed_holdout_access"])
            self.assertFalse(result["authorized_scope"]["claim_generation"])
            self.assertEqual(result["holdout_access"], "NONE")

    def test_wp06_not_ready_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp04, readiness = self.write_inputs(Path(tmp), ready=False)
            with self.assertRaisesRegex(ValueError, "intake target"):
                mod.release(wp04, readiness)

    def test_wp04_integrity_drift_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); wp04, readiness = self.write_inputs(root)
            payload = json.loads(wp04.read_text()); payload["integrity"]["retries"] = 1; wp04.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "integrity"):
                mod.release(wp04, readiness)

    def test_wp06_self_authorization_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); wp04, readiness = self.write_inputs(root)
            payload = json.loads(readiness.read_text()); payload["wp07_release"] = "YES"; readiness.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "self-authorize"):
                mod.release(wp04, readiness)

    def test_holdout_contamination_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); wp04, readiness = self.write_inputs(root)
            payload = json.loads(readiness.read_text()); payload["holdout_access"] = "ACCESSED"; readiness.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "contamination"):
                mod.release(wp04, readiness)


if __name__ == "__main__":
    unittest.main()
