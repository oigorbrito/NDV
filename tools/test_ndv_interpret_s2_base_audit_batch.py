import hashlib, json, tempfile, unittest
from pathlib import Path
from unittest import mock
import ndv_interpret_s2_base_audit_batch as mod

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

class OracleBatchTests(unittest.TestCase):
    def fixture(self, root: Path):
        wave=root/'wave.json'; wave.write_text('{}')
        admission=root/'admission.json'; admission.write_text('{}')
        executor=root/'executor.json'; executor.write_text('{}')
        runner=root/'runner.py'; runner.write_text('# runner')
        base=root/'base.json'; base.write_text(json.dumps({'schema_id':'ndv-p1-s2-base-audit-run-v2','candidate_id':'c1'}))
        plan=root/'plan.json'; plan.write_text(json.dumps({'schema_id':'ndv-p1-s2-base-audit-execution-plan-v1','status':'AUDIT_EXECUTION_PLAN_READY','wave_id':'w','entries':[{'candidate_id':'c1','admission_only_ref':str(admission),'executor_visible_ref':str(executor)}]}))
        receipt=root/'receipt.json'; receipt.write_text(json.dumps({'schema_id':'ndv-p1-s2-base-audit-execution-receipt-v1','status':'BASE_AUDIT_BATCH_RECORDED','plan_file_sha256':sha(plan),'selected_candidate_ids':['c1'],'results':[{'candidate_id':'c1','report_ref':str(base),'report_sha256':sha(base)}],'model_execution':'NONE','treatment_execution':'NOT_EXECUTED','holdout_access':'NONE'}))
        interpreter=root/'interp.py'; interpreter.write_text('# interp')
        upstream=root/'upstream'; upstream.mkdir()
        return receipt,plan,interpreter,upstream
    def test_validate_inputs_accepts_bound_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt,plan,_,_=self.fixture(Path(tmp)); r,p=mod.validate_inputs(receipt,plan); self.assertEqual(r['status'],'BASE_AUDIT_BATCH_RECORDED'); self.assertEqual(p['status'],'AUDIT_EXECUTION_PLAN_READY')
    def test_plan_hash_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); receipt,plan,_,_=self.fixture(root); payload=json.loads(plan.read_text()); payload['note']='changed bytes with valid schema'; plan.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError,'plan hash mismatch'): mod.validate_inputs(receipt,plan)
    @mock.patch.object(mod.subprocess,'run')
    def test_main_records_oracle_output_even_returncode_two(self, run_mock):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); receipt,plan,interp,upstream=self.fixture(root); out_root=root/'oracle'; batch=root/'batch.json'
            class P: returncode=2; stdout=''; stderr=''
            def side_effect(argv,**kwargs):
                out=Path(argv[argv.index('--out')+1]); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps({'schema_id':'ndv-p1-s2-base-oracle-interpretation-v2','candidate_id':'c1','classification':'ORACLE_MISMATCH'})); return P()
            run_mock.side_effect=side_effect
            argv=['prog','--execution-receipt',str(receipt),'--execution-plan',str(plan),'--upstream-root',str(upstream),'--interpreter',str(interp),'--out-root',str(out_root),'--receipt',str(batch)]
            with mock.patch('sys.argv',argv): self.assertEqual(mod.main(),0)
            payload=json.loads(batch.read_text()); self.assertEqual(payload['results'][0]['classification'],'ORACLE_MISMATCH')

if __name__=='__main__': unittest.main()
