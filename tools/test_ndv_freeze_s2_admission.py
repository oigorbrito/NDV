import unittest

from ndv_freeze_s2_admission import freeze


class AdmissionFreezeTests(unittest.TestCase):
    def complete(self):
        candidate = {
            "candidate_id": "c1", "source_instance_id": "i1", "repository": "org/repo",
            "base_revision": "a" * 40, "language": "python", "proposed_family": "F1",
            "task_statement_sha256": "b" * 64, "executor_visible_ref": "executor.json",
            "executor_visible_sha256": "c" * 64, "quarantine_manifest_ref": "q.json",
            "quarantine_status": "PASS", "solution_isolation": "PROVEN",
        }
        audit = {
            "candidate_id": "c1", "status": "AUDIT_PASS", "image_digest": "sha256:" + "d" * 64,
            "base_run_ref": "base.json", "base_run_sha256": "e" * 64,
            "oracle_interpretation_ref": "oracle.json", "oracle_interpretation_sha256": "f" * 64,
            "focal_verifier_ref": "focal.json", "focal_verifier_sha256": "1" * 64,
            "preservation_ref": "pres.json", "preservation_sha256": "2" * 64,
            "verifier_provenance_ref": "prov.json", "verifier_provenance_sha256": "3" * 64,
            "environment_ref": "env.json", "oracle_classification": "EXPECTED_BASE_BEHAVIOR",
        }
        decision = {"candidate_id": "c1", "decision": "ADMIT", "blockers": []}
        return candidate, audit, decision

    def test_complete_record_freezes(self):
        candidate, audit, decision = self.complete()
        record = freeze(candidate, audit, decision)
        self.assertEqual(record["status"], "ADMITTED_FROZEN")
        self.assertEqual(len(record["record_sha256"]), 64)
        self.assertFalse(record["selection"]["treatment_performance_consulted"])

    def test_blocked_decision_cannot_freeze(self):
        candidate, audit, decision = self.complete()
        decision["decision"] = "DO_NOT_ADMIT"
        decision["blockers"] = ["X"]
        with self.assertRaisesRegex(ValueError, "unblocked ADMIT"):
            freeze(candidate, audit, decision)

    def test_missing_evidence_cannot_freeze(self):
        candidate, audit, decision = self.complete()
        audit["focal_verifier_sha256"] = None
        with self.assertRaisesRegex(ValueError, "incomplete admission"):
            freeze(candidate, audit, decision)

    def test_discovery_identity_mismatch_rejected(self):
        candidate, audit, decision = self.complete()
        audit["candidate_id"] = "other"
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            freeze(candidate, audit, decision)


if __name__ == "__main__":
    unittest.main()
