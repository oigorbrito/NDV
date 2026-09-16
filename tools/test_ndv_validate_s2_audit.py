import copy
import unittest

from ndv_validate_s2_audit import validate


BASE = {
    "schema_id": "ndv-p1-s2-audit-state-v1",
    "holdout_access": "NONE",
    "audits": [
        {
            "candidate_id": "c1",
            "status": "WAITING_QUARANTINE",
            "quarantine_status": "PENDING",
            "image_ref": "example/image:tag",
            "image_digest": None,
            "gold_patch_applied_in_base_mode": False,
            "base_run_ref": None,
            "base_run_sha256": None,
            "base_behavior_matches_expected": None,
            "focal_verifier_ref": None,
            "preservation_ref": None,
            "preservation_baseline_pass": None,
            "verifier_provenance_ref": None,
            "verifier_independent": None,
            "environment_ref": None,
            "treatment_execution": "NOT_EXECUTED",
        }
    ],
}


class AuditValidatorTests(unittest.TestCase):
    def test_waiting_quarantine_is_valid(self):
        self.assertEqual(validate(copy.deepcopy(BASE)), [])

    def test_ready_requires_quarantine_pass(self):
        payload = copy.deepcopy(BASE)
        payload["audits"][0]["status"] = "READY_FOR_ENVIRONMENT_AUDIT"
        errors = validate(payload)
        self.assertTrue(any("quarantine_status=PASS" in e for e in errors))

    def test_gold_patch_forbidden_in_base_mode(self):
        payload = copy.deepcopy(BASE)
        payload["audits"][0]["gold_patch_applied_in_base_mode"] = True
        errors = validate(payload)
        self.assertTrue(any("gold patch" in e for e in errors))

    def test_audit_pass_requires_complete_evidence(self):
        payload = copy.deepcopy(BASE)
        rec = payload["audits"][0]
        rec["status"] = "AUDIT_PASS"
        rec["quarantine_status"] = "PASS"
        errors = validate(payload)
        self.assertTrue(any("AUDIT_PASS requires image_digest" in e for e in errors))

    def test_complete_audit_pass_is_valid(self):
        payload = copy.deepcopy(BASE)
        rec = payload["audits"][0]
        rec.update({
            "status": "AUDIT_PASS",
            "quarantine_status": "PASS",
            "image_digest": "sha256:" + "a" * 64,
            "base_run_ref": "runs/base.json",
            "base_run_sha256": "b" * 64,
            "base_behavior_matches_expected": True,
            "focal_verifier_ref": "verifier/focal.json",
            "preservation_ref": "verifier/preservation.json",
            "preservation_baseline_pass": True,
            "verifier_provenance_ref": "verifier/provenance.json",
            "verifier_independent": True,
            "environment_ref": "environment/image.json",
        })
        self.assertEqual(validate(payload), [])


if __name__ == "__main__":
    unittest.main()
