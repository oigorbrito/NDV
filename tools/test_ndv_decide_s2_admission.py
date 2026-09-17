import unittest
from ndv_decide_s2_admission import decide

class AdmissionDecisionTests(unittest.TestCase):
    def base(self):
        state={"schema_id":"ndv-p1-s2-candidate-evidence-state-v2","wave_id":"w1","treatment_execution":"NOT_EXECUTED","holdout_access":"NONE","candidates":[{"candidate_id":"c1","source_row_index":7,"quarantine_status":"PASS","quarantine_manifest_ref":"q.json","admission_only_ref":"admission.json","executor_visible_ref":"executor.json","task_statement_sha256":"a"*64,"ndv_canonical_row_sha256":"b"*64,"executor_visible_sha256":"c"*64,"proposed_family":"F1","solution_isolation":"PROVEN"}]}
        audit={"audits":[{"candidate_id":"c1","status":"AUDIT_PASS","quarantine_status":"PASS","harness_integrity":"PASS","oracle_classification":"EXPECTED_BASE_BEHAVIOR","base_behavior_matches_expected":True,"verifier_independent":True,"preservation_baseline_pass":True,"treatment_execution":"NOT_EXECUTED","gold_patch_applied_in_base_mode":False,"test_patch_applied_in_base_mode":False,"image_digest":"sha256:"+"d"*64,"base_run_ref":"base.json","base_run_sha256":"e"*64,"oracle_interpretation_ref":"oracle.json","oracle_interpretation_sha256":"f"*64,"focal_verifier_ref":"focal.json","focal_verifier_sha256":"1"*64,"preservation_ref":"preserve.json","preservation_sha256":"2"*64,"verifier_provenance_ref":"prov.json","verifier_provenance_sha256":"3"*64,"environment_ref":"env.json","environment_sha256":"4"*64}]}
        return state,audit
    def test_complete_gates_admit(self):
        result=decide(*self.base()); self.assertEqual(result['decisions'][0]['decision'],'ADMIT'); self.assertEqual(result['summary']['admit_count'],1)
    def test_missing_quarantine_blocks(self):
        state,audit=self.base(); state['candidates'][0]['quarantine_status']='PENDING'; self.assertIn('QUARANTINE_NOT_PASS',decide(state,audit)['decisions'][0]['blockers'])
    def test_unassigned_family_blocks(self):
        state,audit=self.base(); state['candidates'][0]['proposed_family']='UNASSIGNED_PENDING_SCREEN'; self.assertIn('FAMILY_UNASSIGNED',decide(state,audit)['decisions'][0]['blockers'])
    def test_audit_mismatch_blocks(self):
        state,audit=self.base(); audit['audits'][0]['oracle_classification']='ORACLE_MISMATCH'; self.assertIn('BASE_ORACLE_NOT_EXPECTED',decide(state,audit)['decisions'][0]['blockers'])
    def test_treatment_contamination_blocks(self):
        state,audit=self.base(); audit['audits'][0]['treatment_execution']='EXECUTED'; self.assertIn('TREATMENT_EXECUTION_CONTAMINATION',decide(state,audit)['decisions'][0]['blockers'])
    def test_wrong_candidate_state_schema_rejected(self):
        state,audit=self.base(); state['schema_id']='ndv-p1-s2-candidate-wave-v1'
        with self.assertRaisesRegex(ValueError,'candidate evidence state v2'): decide(state,audit)
    def test_candidate_state_contamination_rejected(self):
        state,audit=self.base(); state['treatment_execution']='EXECUTED'
        with self.assertRaisesRegex(ValueError,'contaminated'): decide(state,audit)

if __name__=='__main__': unittest.main()
