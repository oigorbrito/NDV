import hashlib, json, tempfile, unittest
from pathlib import Path
import ndv_apply_s2_family_assignments as mod

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

class FamilyAssignmentTests(unittest.TestCase):
    def fixture(self, root: Path):
        state=root/'state.json'; state.write_text(json.dumps({'schema_id':'ndv-p1-s2-candidate-evidence-state-v1','wave_id':'w','wave_ref':'wave.json','wave_file_sha256':'a'*64,'candidates':[{'candidate_id':'c1','task_statement_sha256':'b'*64,'proposed_family':'UNASSIGNED_PENDING_SCREEN'}],'treatment_execution':'NOT_EXECUTED','holdout_access':'NONE'}))
        taxonomy=root/'taxonomy.json'; taxonomy.write_text(json.dumps({'schema_id':'ndv-p1-s2-family-taxonomy-v1','families':{'F1':{},'F2':{},'F3':{},'F4':{},'F5':{},'F6':{}},'treatment_execution':'NOT_EXECUTED','holdout_access':'NONE'}))
        assignments=root/'assignments.json'; assignments.write_text(json.dumps({'schema_id':'ndv-p1-s2-family-assignments-v1','wave_id':'w','candidate_state_sha256':sha(state),'taxonomy_sha256':sha(taxonomy),'assignments':[{'candidate_id':'c1','family':'F2','task_statement_sha256':'b'*64,'rationale':'Cross-file interface mismatch.'}],'treatment_execution':'NOT_EXECUTED','holdout_access':'NONE'}))
        return state,assignments,taxonomy
    def test_apply_sets_family_with_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            state,assignments,taxonomy=self.fixture(Path(tmp)); result=mod.apply(state,assignments,taxonomy); c=result['candidates'][0]; self.assertEqual(result['schema_id'],'ndv-p1-s2-candidate-evidence-state-v2'); self.assertEqual(c['proposed_family'],'F2'); self.assertFalse(c['family_assignment']['performance_based'])
    def test_invalid_family_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); state,assignments,taxonomy=self.fixture(root); p=json.loads(assignments.read_text()); p['assignments'][0]['family']='F9'; assignments.write_text(json.dumps(p))
            with self.assertRaisesRegex(ValueError,'invalid family'): mod.apply(state,assignments,taxonomy)
    def test_state_hash_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); state,assignments,taxonomy=self.fixture(root); state.write_text('{}')
            with self.assertRaisesRegex(ValueError,'candidate-state hash mismatch'): mod.apply(state,assignments,taxonomy)

if __name__=='__main__': unittest.main()
