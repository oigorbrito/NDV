import unittest

from ndv_freeze_s2_admission import freeze


class AdmissionFreezeTests(unittest.TestCase):
    def complete(self):
        candidate = {
            "candidate_id": "c1", "source_instance_id": "i1", "source_row_index": 7, "repository": "org/repo",
            "base_revision": "a" * 40, "language": "python", "proposed_family": "F1",
            "task_statement_sha256": "b" * 64, "ndv_canonical_row_sha256": "c" * 64,
            "admission_only_ref": "admission.json", "executor_visible_ref": "executor.json", "executor_visible_sha256": "d" * 64,
            "quarantine_manifest_ref": "q.json", "quarantine_status": "PASS", "solution_isolation": "PROVEN",
        }
        audit = {
            "candidate_id": "c1", "status": "AUDIT_PASS", "quarantine_status": "PASS", "harness_integrity": "PASS",
            "image_digest": "sha256:" + "e" * 64, "gold_patch_applied_in_base_mode": False, "test_patch_applied_in_base_mode": False,
            "treatment_execution": "NOT_EXECUTED", "oracle_classification": "EXPECTED_BASE_BEHAVIOR", "base_behavior_matches_expected": True,
            "preservation_baseline_pass": True, "verifier_independent": True,
            "base_run_ref": "base.json", "base_run_sha256": "f" * 64,
            "oracle_interpretation_ref": "oracle.json", "oracle_interpretation_sha256": "1" * 64,
            "focal_verifier_ref": "focal.json", "focal_verifier_sha256": "2" * 64,
            "preservation_ref": "pres.json", "preservation_sha256": "3" * 64,
            "verifier_provenance_ref": "prov.json", "verifier_provenance_sha256": "4" * 64,
            "environment_ref": "env.json", "environment_sha256": "5" * 64,
        }
        decision = {
            "candidate_id": "c1", "decision": "ADMIT", "blockers": [],
            "evidence_refs": {
                "quarantine_manifest_ref": "q.json", "admission_only_ref": "admission.json", "executor_visible_ref": "executor.json",
                "base_run_ref": "base.json", "oracle_interpretation_ref": "oracle.json", "focal_verifier_ref": "focal.json",
                "preservation_ref": "pres.json", "verifier_provenance_ref": "prov.json", "environment_ref": "env.json",
            },
            "evidence_hashes": {
                "ndv_canonical_row_sha256": "c" * 64, "executor_visible_sha256": "d" * 64, "task_statement_sha256": "b" * 64,
                "base_run_sha256": "f" * 64, "oracle_interpretation_sha256": "1" * 64, "focal_verifier_sha256": "2" * 64,
                "preservation_sha256": "3" * 64, "verifier_provenance_sha256": "4" * 64, "environment_sha256": "5" * 64,
            },
        }
        integrity = {
            "admission_only_file_sha256": "6" * 64, "executor_visible_file_sha256": "7" * 64,
            "quarantine_manifest_file_sha256": "8" * 64, "base_run_file_sha256": "f" * 64,
            "oracle_interpretation_file_sha256": "1" * 64, "environment_file_sha256": "5" * 64,
        }
        return candidate, audit, decision, integrity

    def test_complete_record_freezes_and_binds_source(self):
        candidate, audit, decision, integrity = self.complete(); record = freeze(candidate, audit, decision, integrity)
        self.assertEqual(record["schema_id"], "ndv-p1-s2-admission-record-v2")
        self.assertEqual(record["status"], "ADMITTED_FROZEN")
        self.assertEqual(record["source_row_index"], 7)
        self.assertEqual(record["source_binding"]["ndv_canonical_row_sha256"], "c" * 64)
        self.assertEqual(record["audit"]["environment_sha256"], "5" * 64)
        self.assertEqual(record["artifact_integrity"]["status"], "VERIFIED")
        self.assertEqual(len(record["record_sha256"]), 64)

    def test_declared_metadata_without_verified_bytes_cannot_freeze(self):
        candidate, audit, decision, _ = self.complete()
        with self.assertRaisesRegex(ValueError, "verified artifact integrity"):
            freeze(candidate, audit, decision)

    def test_stale_decision_ref_is_rejected(self):
        candidate, audit, decision, integrity = self.complete(); decision["evidence_refs"]["base_run_ref"] = "old-base.json"
        with self.assertRaisesRegex(ValueError, "stale decision evidence ref"):
            freeze(candidate, audit, decision, integrity)

    def test_stale_decision_hash_is_rejected(self):
        candidate, audit, decision, integrity = self.complete(); decision["evidence_hashes"]["environment_sha256"] = "9" * 64
        with self.assertRaisesRegex(ValueError, "stale decision evidence hash"):
            freeze(candidate, audit, decision, integrity)

    def test_blocked_decision_cannot_freeze(self):
        candidate, audit, decision, integrity = self.complete(); decision["decision"] = "DO_NOT_ADMIT"; decision["blockers"] = ["X"]
        with self.assertRaisesRegex(ValueError, "unblocked ADMIT"): freeze(candidate, audit, decision, integrity)

    def test_harness_failure_cannot_freeze(self):
        candidate, audit, decision, integrity = self.complete(); audit["harness_integrity"] = "FAIL"
        with self.assertRaisesRegex(ValueError, "stale decision evidence|harness-valid"):
            freeze(candidate, audit, decision, integrity)

    def test_treatment_contamination_cannot_freeze(self):
        candidate, audit, decision, integrity = self.complete(); audit["treatment_execution"] = "EXECUTED"
        with self.assertRaisesRegex(ValueError, "audit contamination"):
            freeze(candidate, audit, decision, integrity)

    def test_missing_environment_hash_is_rejected(self):
        candidate, audit, decision, integrity = self.complete(); audit["environment_sha256"] = None; decision["evidence_hashes"]["environment_sha256"] = None
        with self.assertRaisesRegex(ValueError, "environment_sha256"):
            freeze(candidate, audit, decision, integrity)

    def test_discovery_identity_mismatch_rejected(self):
        candidate, audit, decision, integrity = self.complete(); audit["candidate_id"] = "other"
        with self.assertRaisesRegex(ValueError, "identity mismatch"): freeze(candidate, audit, decision, integrity)


if __name__ == "__main__": unittest.main()
