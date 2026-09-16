import copy
import unittest

from ndv_validate_s2_audit import validate


BASE = {
    "schema_id": "ndv-p1-s2-audit-state-v1", "holdout_access": "NONE",
    "audits": [{
        "candidate_id": "c1", "status": "WAITING_QUARANTINE", "quarantine_status": "PENDING",
        "image_ref": "example/image:tag", "image_digest": None,
        "gold_patch_applied_in_base_mode": False, "test_patch_applied_in_base_mode": False,
        "base_run_ref": None, "base_run_sha256": None, "oracle_interpretation_ref": None, "oracle_interpretation_sha256": None,
        "oracle_classification": None, "base_behavior_matches_expected": None, "harness_integrity": None,
        "focal_verifier_ref": None, "focal_verifier_sha256": None, "preservation_ref": None, "preservation_sha256": None,
        "preservation_baseline_pass": None, "verifier_provenance_ref": None, "verifier_provenance_sha256": None,
        "verifier_independent": None, "environment_ref": None, "treatment_execution": "NOT_EXECUTED",
    }],
}


def complete_pass(rec):
    rec.update({
        "status": "AUDIT_PASS", "quarantine_status": "PASS", "image_digest": "sha256:" + "a" * 64,
        "base_run_ref": "runs/base.json", "base_run_sha256": "b" * 64,
        "oracle_interpretation_ref": "oracle/base.json", "oracle_interpretation_sha256": "c" * 64,
        "oracle_classification": "EXPECTED_BASE_BEHAVIOR", "base_behavior_matches_expected": True, "harness_integrity": "PASS",
        "focal_verifier_ref": "verifier/focal.json", "focal_verifier_sha256": "d" * 64,
        "preservation_ref": "verifier/preservation.json", "preservation_sha256": "e" * 64, "preservation_baseline_pass": True,
        "verifier_provenance_ref": "verifier/provenance.json", "verifier_provenance_sha256": "f" * 64,
        "verifier_independent": True, "environment_ref": "environment/image.json",
        "gold_patch_applied_in_base_mode": False, "test_patch_applied_in_base_mode": False,
    })


class AuditValidatorTests(unittest.TestCase):
    def test_waiting_quarantine_is_valid(self):
        self.assertEqual(validate(copy.deepcopy(BASE)), [])

    def test_ready_requires_quarantine_pass(self):
        payload = copy.deepcopy(BASE); payload["audits"][0]["status"] = "READY_FOR_ENVIRONMENT_AUDIT"
        self.assertTrue(any("quarantine_status=PASS" in e for e in validate(payload)))

    def test_patch_application_forbidden_in_base_mode(self):
        for field in ("gold_patch_applied_in_base_mode", "test_patch_applied_in_base_mode"):
            payload = copy.deepcopy(BASE); payload["audits"][0][field] = True
            self.assertTrue(validate(payload))

    def test_audit_pass_requires_complete_evidence(self):
        payload = copy.deepcopy(BASE); payload["audits"][0]["status"] = "AUDIT_PASS"; payload["audits"][0]["quarantine_status"] = "PASS"
        errors = validate(payload)
        self.assertTrue(any("image_digest" in e for e in errors))
        self.assertTrue(any("harness_integrity" in e for e in errors))

    def test_harness_failure_blocks_audit_pass(self):
        payload = copy.deepcopy(BASE); rec = payload["audits"][0]; complete_pass(rec); rec["harness_integrity"] = "FAIL"
        self.assertTrue(any("harness_integrity=PASS" in e for e in validate(payload)))

    def test_oracle_mismatch_blocks_audit_pass(self):
        payload = copy.deepcopy(BASE); rec = payload["audits"][0]; complete_pass(rec); rec["oracle_classification"] = "ORACLE_MISMATCH"
        self.assertTrue(any("EXPECTED_BASE_BEHAVIOR" in e for e in validate(payload)))

    def test_complete_audit_pass_is_valid(self):
        payload = copy.deepcopy(BASE); complete_pass(payload["audits"][0]); self.assertEqual(validate(payload), [])


if __name__ == "__main__":
    unittest.main()
