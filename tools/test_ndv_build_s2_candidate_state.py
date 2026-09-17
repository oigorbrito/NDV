import hashlib, json, tempfile, unittest
from pathlib import Path
import ndv_build_s2_candidate_state as mod

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

class CandidateStateTests(unittest.TestCase):
    def fixture(self, root: Path):
        cid='c1'; row={'instance_id':'i1','repo':'org/repo','base_commit':'a'*40,'problem_statement':'fix'}
        raw=hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':')).encode()).hexdigest(); task=hashlib.sha256(b'fix').hexdigest(); projection={'instance_id':'i1','repo':'org/repo','base_commit':'a'*40,'problem_statement':'fix','language':'python'}; proj=hashlib.sha256(json.dumps(projection,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        wave=root/'wave.json'; wave.write_text(json.dumps({'schema_id':'ndv-p1-s2-candidate-wave-v1','wave_id':'w','source':{'source_id':'src'},'candidates':[{'candidate_id':cid,'source_instance_id':'i1','source_row_index':7,'repository':'org/repo','base_revision':'a'*40,'language':'python','image_ref':'docker.io/org/repo:1','task_statement_ref':'src:row7'}]}))
        qdir=root/'q'/cid; qdir.mkdir(parents=True)
        admission=qdir/'admission-only.json'; admission.write_text(json.dumps({'schema_id':'ndv-p1-s2-admission-only-row-v1','candidate_id':cid,'source':{'source_row_index':7,'source_instance_id':'i1','ndv_canonical_row_sha256':raw},'full_row':row}))
        executor=qdir/'executor-visible.json'; executor.write_text(json.dumps({'schema_id':'ndv-p1-s2-executor-visible-row-v1','candidate_id':cid,'source_binding':{'source_row_index':7,'ndv_canonical_row_sha256':raw},'task_statement_sha256':task,'executor_visible_sha256':proj,'task':projection}))
        manifest={'schema_id':'ndv-p1-s2-quarantine-manifest-v2','candidate_id':cid,'status':'PASS','source_row_index':7,'source_instance_id':'i1','ndv_canonical_row_sha256':raw,'task_statement_sha256':task,'executor_visible_sha256':proj,'admission_only_ref':str(admission),'executor_visible_ref':str(executor),'treatment_execution':'NOT_EXECUTED','holdout_access':'NONE'}
        (qdir/'quarantine-manifest.json').write_text(json.dumps(manifest))
        aggregate=root/'q'/'quarantine-aggregate.json'; aggregate.write_text(json.dumps({'schema_id':'ndv-p1-s2-quarantine-aggregate-v2','wave_id':'w','manifests':[manifest]}))
        receipt=root/'material.json'; receipt.write_text(json.dumps({'schema_id':'ndv-p1-s2-wave-materialization-receipt-v2','status':'MATERIALIZED_QUARANTINED','wave_id':'w','wave_file_sha256':sha(wave),'quarantine_aggregate_ref':str(aggregate),'quarantine_aggregate_file_sha256':sha(aggregate),'model_execution':'NONE','treatment_execution':'NOT_EXECUTED','holdout_access':'NONE'}))
        return wave,receipt,qdir
    def test_build_promotes_quarantine_facts_without_family(self):
        with tempfile.TemporaryDirectory() as tmp:
            wave,receipt,_=self.fixture(Path(tmp)); state=mod.build(wave,receipt); c=state['candidates'][0]; self.assertEqual(c['quarantine_status'],'PASS'); self.assertEqual(c['solution_isolation'],'PROVEN'); self.assertEqual(c['proposed_family'],'UNASSIGNED_PENDING_SCREEN'); self.assertTrue(Path(c['quarantine_manifest_ref']).is_file())
    def test_preserved_manifest_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            wave,receipt,qdir=self.fixture(Path(tmp)); p=json.loads((qdir/'quarantine-manifest.json').read_text()); p['status']='FAIL'; (qdir/'quarantine-manifest.json').write_text(json.dumps(p))
            with self.assertRaisesRegex(ValueError,'aggregate manifest differs'): mod.build(wave,receipt)

if __name__=='__main__': unittest.main()
