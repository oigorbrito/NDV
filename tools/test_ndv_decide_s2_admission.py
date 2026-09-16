import unittest

from ndv_decide_s2_admission import decide


class AdmissionDecisionTests(unittest.TestCase):
    def base(self):
        wave = {
            "wave_id": "w1",
            "candidates": [{
                "candidate_id": "c1",
                "quarantine_status": "PASS",
                "quarantine_manifest_ref": "q.json",
                "proposed_family": "F1",
                "solution_isolation": "PROVEN",
            }],
        }
        audit = {
            "audits": [{
                "candidate_id": "c1",
                "status": "AUDIT_PASS",
                "oracle_classification": "EXPECTED_BASE_BEHAVIOR",
                "verifier_independent": True,
                "preservation_baseline_pass": True,
                "treatment_execution": "NOT_EXECUTED",
                "base_run_ref": "base.json",
                "oracle_interpretation_ref": "oracle.json",
                "focal_verifier_ref": "focal.json",
                "preservation_ref": "preserve.json",
                "verifier_provenance_ref": "prov.json",
                "environment_ref": "env.json",
            }]
        }
        return wave, audit

    def test_complete_gates_admit(self):
        wave, audit = self.base()
        result = decide(wave, audit)
        self.assertEqual(result["decisions"][0]["decision"], "ADMIT")
        self.assertEqual(result["summary"]["admit_count"], 1)

    def test_missing_quarantine_blocks(self):
        wave, audit = self.base()
        wave["candidates"][0]["quarantine_status"] = "PENDING"
        d = decide(wave, audit)["decisions"][0]
        self.assertEqual(d["decision"], "DO_NOT_ADMIT")
        self.assertIn("QUARANTINE_NOT_PASS", d["blockers"])

    def test_audit_mismatch_blocks(self):
        wave, audit = self.base()
        audit["audits"][0]["oracle_classification"] = "ORACLE_MISMATCH"
        d = decide(wave, audit)["decisions"][0]
        self.assertIn("BASE_ORACLE_NOT_EXPECTED", d["blockers"])

    def test_unassigned_family_blocks(self):
        wave, audit = self.base()
        wave["candidates"][0]["proposed_family"] = "UNASSIGNED_PENDING_SCREEN"
        d = decide(wave, audit)["decisions"][0]
        self.assertIn("FAMILY_UNASSIGNED", d["blockers"])

    def test_treatment_contamination_blocks(self):
        wave, audit = self.base()
        audit["audits"][0]["treatment_execution"] = "EXECUTED"
        d = decide(wave, audit)["decisions"][0]
        self.assertIn("TREATMENT_EXECUTION_CONTAMINATION", d["blockers"])


if __name__ == "__main__":
    unittest.main()
