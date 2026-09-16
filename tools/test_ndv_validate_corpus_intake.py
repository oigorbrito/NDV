import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "ndv_validate_corpus_intake.py"
spec = importlib.util.spec_from_file_location("ndv_validate", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class CorpusIntakeValidatorTests(unittest.TestCase):
    def payload(self):
        candidate = {
            "candidate_id": "S2W01-fixture",
            "source_instance_id": "owner__repo-1",
            "source_row_index": 0,
            "source_record_sha256": "a" * 64,
            "repository": "owner/repo",
            "base_revision": "b" * 40,
            "language": "python",
            "task_statement_sha256": None,
            "proposed_family": "UNASSIGNED_PENDING_SCREEN",
            "focal_verifier_ref": None,
            "verifier_independent": "UNRESOLVED",
            "preservation_ref": None,
            "environment_ref": "fixture-image",
            "solution_isolation": "PENDING_QUARANTINED_ROW_EXPORT",
            "quarantine_status": "PENDING",
            "disposition": "SCREENING",
        }
        return {
            "schema_id": "ndv-p1-s2-candidate-wave-v1",
            "source": {"dataset_revision": "c" * 40},
            "source_field_quarantine": {
                "agent_forbidden_fields": sorted(module.FORBIDDEN_AGENT_FIELDS),
                "projection_mode": "STRICT_ALLOWLIST",
            },
            "candidates": [candidate],
            "wave_summary": {
                "candidate_count": 1,
                "repository_count": 1,
                "language_count": 1,
                "treatment_execution": "NOT_EXECUTED",
                "holdout_access": "NONE",
            },
        }

    def test_screening_does_not_require_completed_quarantine(self):
        self.assertEqual(module.validate(self.payload()), [])

    def test_admitted_without_quarantine_is_rejected(self):
        payload = self.payload()
        payload["candidates"][0]["disposition"] = "ADMITTED"
        errors = module.validate(payload)
        self.assertTrue(any("quarantine_status=PASS" in error for error in errors))
        self.assertTrue(any("executor_visible_sha256" in error for error in errors))

    def test_admitted_with_complete_gate_is_accepted(self):
        payload = self.payload()
        candidate = payload["candidates"][0]
        candidate.update({
            "disposition": "ADMITTED",
            "task_statement_sha256": "d" * 64,
            "proposed_family": "F1",
            "focal_verifier_ref": "fixture:focal",
            "verifier_independent": True,
            "preservation_ref": "fixture:preservation",
            "solution_isolation": "PROVEN",
            "quarantine_status": "PASS",
            "quarantine_manifest_ref": ".ndv-corpus/fixture/quarantine-manifest.json",
            "admission_only_ref": ".ndv-corpus/fixture/admission-only.json",
            "executor_visible_ref": ".ndv-corpus/fixture/executor-visible.json",
            "ndv_canonical_row_sha256": "e" * 64,
            "executor_visible_sha256": "f" * 64,
        })
        self.assertEqual(module.validate(payload), [])


if __name__ == "__main__":
    unittest.main()
