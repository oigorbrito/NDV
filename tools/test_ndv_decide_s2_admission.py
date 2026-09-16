import unittest

from ndv_decide_s2_admission import decide


class AdmissionDecisionTests(unittest.TestCase):
    def base(self):
        wave = {"wave_id": "w1", "candidates": [{
            "candidate_id": "c1", "source_row_index": 7, "quarantine_status": "PASS",
            "quarantine_manifest_ref": "q.json", "admission_only_ref": "admission.json", "executor_visible_ref": "executor.json",
            "task_statement_sha256": "a" * 64, "ndv_canonical_row_sha256": "b" * 64, "executor_visible_sha256": "c" * 64,
            "proposed_family": "F1", "solution_isolation": "PROVEN",
        }]}
        audit = {"audits": [{
            "candidate_id": "c1", "status": "AUDIT_PASS", "quarantine_status": "PASS", "harness_integrity": "PASS",
            "oracle_classification": "EXPECTED_BASE_BEHAVIOR", "base_behavior_matches_expected": True,
            "verifier_independent": True, "preservation_baseline_pass": True, "treatment_execution": "NOT_EXECUTED",
            "gold_patch_applied_in_base_mode": False, "test_patch_applied_in_base_mode": False,
            "image_digest": "sha256:" + "d" * 64,
            "base_run_ref": "base.json", "base_run_sha256": "e" * 64,
            "oracle_interpretation_ref": "oracle.json", "oracle_interpretation_sha256": "f" * 64,
            "focal_verifier_ref": "focal.json", "focal_verifier_sha256": "1" * 64,
            "preservation_ref": "preserve.json", "preservation_sha256": "2" * 64,
            "verifier_provenance_ref": "prov.json", "verifier_provenance_sha256": "3" * 64,
            "environment_ref": "env.json", "environment_sha256": "4" * 64,
        }]}
        return wave, audit

    def test_complete_gates_admit(self):
        result = decide(*self.base()); decision = result["decisions"][0]
        self.assertEqual(decision["decision"], "ADMIT")
        self.assertEqual(result["summary"]["admit_count"], 1)
        self.assertEqual(decision["evidence_hashes"]["environment_sha256"], "4" * 64)

    def test_missing_quarantine_blocks(self):
        wave, audit = self.base(); wave["candidates"][0]["quarantine_status"] = "PENDING"
        self.assertIn("QUARANTINE_NOT_PASS", decide(wave, audit)["decisions"][0]["blockers"])

    def test_audit_quarantine_must_match(self):
        wave, audit = self.base(); audit["audits"][0]["quarantine_status"] = "PENDING"
        self.assertIn("AUDIT_QUARANTINE_NOT_PASS", decide(wave, audit)["decisions"][0]["blockers"])

    def test_harness_failure_blocks_even_with_audit_pass_label(self):
        wave, audit = self.base(); audit["audits"][0]["harness_integrity"] = "FAIL"
        self.assertIn("HARNESS_INTEGRITY_NOT_PASS", decide(wave, audit)["decisions"][0]["blockers"])

    def test_audit_mismatch_blocks(self):
        wave, audit = self.base(); audit["audits"][0]["oracle_classification"] = "ORACLE_MISMATCH"
        self.assertIn("BASE_ORACLE_NOT_EXPECTED", decide(wave, audit)["decisions"][0]["blockers"])

    def test_unassigned_family_blocks(self):
        wave, audit = self.base(); wave["candidates"][0]["proposed_family"] = "UNASSIGNED_PENDING_SCREEN"
        self.assertIn("FAMILY_UNASSIGNED", decide(wave, audit)["decisions"][0]["blockers"])

    def test_treatment_contamination_blocks(self):
        wave, audit = self.base(); audit["audits"][0]["treatment_execution"] = "EXECUTED"
        self.assertIn("TREATMENT_EXECUTION_CONTAMINATION", decide(wave, audit)["decisions"][0]["blockers"])

    def test_missing_hash_blocks_direct_call(self):
        wave, audit = self.base(); audit["audits"][0]["base_run_sha256"] = None
        self.assertIn("AUDIT_BASE_RUN_SHA256_INVALID", decide(wave, audit)["decisions"][0]["blockers"])

    def test_missing_environment_hash_blocks_direct_call(self):
        wave, audit = self.base(); audit["audits"][0]["environment_sha256"] = None
        self.assertIn("AUDIT_ENVIRONMENT_SHA256_INVALID", decide(wave, audit)["decisions"][0]["blockers"])


if __name__ == "__main__": unittest.main()
