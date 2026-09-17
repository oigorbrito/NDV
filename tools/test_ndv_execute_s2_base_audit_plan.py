import hashlib, json, tempfile, unittest
from pathlib import Path
from unittest import mock
import ndv_execute_s2_base_audit_plan as mod

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

class ExecutePlanTests(unittest.TestCase):
    def fixture(self, root: Path):
        wave=root/'wave.json'; wave.write_text('{}')
        base=root/'base-plan.json'; base.write_text('{}')
        images=root/'images.json'; images.write_text('{}')
        runner=root/'runner.py'; runner.write_text('# runner')
        admission=root/'admission.json'; admission.write_text('{}')
        executor=root/'executor.json'; executor.write_text('{}')
        digest='docker.io/org/repo@sha256:'+'a'*64
        entry={"candidate_id":"c1","authorized_action":"PRE_SOLUTION_BASE_AUDIT_ONLY","treatment_execution":"NOT_EXECUTED","holdout_access":"NONE","image_digest":digest,"admission_only_ref":str(admission),"executor_visible_ref":str(executor),"artifact_integrity":{"admission_only_sha256":sha(admission),"executor_visible_sha256":sha(executor)},"audit_out":str(root/'audit'),"argv":["python",str(runner),"--image-digest",digest,"--out",str(root/'audit')]}
        plan=root/'exec-plan.json'; plan.write_text(json.dumps({"schema_id":"ndv-p1-s2-base-audit-execution-plan-v1","status":"AUDIT_EXECUTION_PLAN_READY","wave_id":"w","wave_ref":str(wave),"wave_file_sha256":sha(wave),"base_audit_plan_ref":str(base),"base_audit_plan_file_sha256":sha(base),"image_acquisition_receipt_ref":str(images),"image_acquisition_receipt_file_sha256":sha(images),"runner_ref":str(runner),"runner_file_sha256":sha(runner),"candidate_count":1,"entries":[entry],"docker_execution":False,"model_execution":"NONE","treatment_execution":"NOT_EXECUTED","holdout_access":"NONE"}))
        return plan,entry
    def test_valid_plan_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan,_=self.fixture(Path(tmp)); p,e=mod.validate_plan(plan); self.assertEqual(p['status'],'AUDIT_EXECUTION_PLAN_READY'); self.assertEqual(len(e),1)
    def test_digest_argv_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); plan,_=self.fixture(root); p=json.loads(plan.read_text()); p['entries'][0]['argv'][p['entries'][0]['argv'].index('--image-digest')+1]='docker.io/org/repo@sha256:'+'b'*64; plan.write_text(json.dumps(p))
            with self.assertRaisesRegex(ValueError,'argv/image digest'): mod.validate_plan(plan)
    def test_tampered_admission_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan,entry=self.fixture(Path(tmp)); Path(entry['admission_only_ref']).write_text('{"x":1}')
            with self.assertRaisesRegex(ValueError,'admission artifact hash'): mod.validate_plan(plan)
    @mock.patch.object(mod.subprocess,'run')
    def test_execute_records_report_even_nonzero_runner(self,run_mock):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); _,entry=self.fixture(root)
            class P: returncode=3; stdout='blocked'; stderr=''
            def side_effect(*args,**kwargs):
                out=Path(entry['audit_out']); out.mkdir(); (out/'base-audit-run.json').write_text(json.dumps({'schema_id':'ndv-p1-s2-base-audit-run-v2','status':'ENVIRONMENT_BLOCKED','image_digest':entry['image_digest']})); return P()
            run_mock.side_effect=side_effect
            result=mod.execute_entry(entry); self.assertEqual(result['runner_returncode'],3); self.assertIn('report_ref',result)

if __name__=='__main__': unittest.main()
