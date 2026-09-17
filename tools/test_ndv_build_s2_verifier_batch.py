import hashlib, json, tempfile, unittest
from pathlib import Path
import ndv_build_s2_verifier_batch as mod

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def canonical(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

class VerifierBatchTests(unittest.TestCase):
    def fixture(self, root: Path):
        row={'instance_id':'org__repo-1','repo':'org/repo','base_commit':'a'*40,'FAIL_TO_PASS':['t1'],'PASS_TO_PASS':['t2'],'install_config':{'log_parser':'parse_pytest'}}
        admission=root/'admission.json'; admission.write_text(json.dumps({'schema_id':'ndv-p1-s2-admission-only-row-v1','candidate_id':'c1','source':{'source_row_index':7,'ndv_canonical_row_sha256':canonical(row)},'full_row':row}))
        plan=root/'plan.json'; plan.write_text(json.dumps({'schema_id':'ndv-p1-s2-base-audit-execution-plan-v1','entries':[{'candidate_id':'c1','admission_only_ref':str(admission)}]}))
        oracle_file=root/'oracle.json'; oracle_file.write_text(json.dumps({'schema_id':'ndv-p1-s2-base-oracle-interpretation-v2','candidate_id':'c1','classification':'EXPECTED_BASE_BEHAVIOR','parser_name':'parse_pytest','parser_provenance':{'repository':'SWE-rebench/SWE-rebench-V2','revision':'b'*40,'path':'lib/agent/log_parsers.py','log_parsers_sha256':'c'*64}}))
        oracle=root/'oracle-batch.json'; oracle.write_text(json.dumps({'schema_id':'ndv-p1-s2-oracle-batch-receipt-v1','status':'ORACLE_BATCH_RECORDED','execution_plan_sha256':sha(plan),'results':[{'candidate_id':'c1','status':'RECORDED','oracle_ref':str(oracle_file),'oracle_sha256':sha(oracle_file)}],'model_execution':'NONE','treatment_execution':'NOT_EXECUTED','holdout_access':'NONE'}))
        return oracle,plan
    def test_main_builds_verifier_bundle(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); oracle,plan=self.fixture(root); out=root/'verifier'; receipt=root/'receipt.json'
            argv=['prog','--oracle-receipt',str(oracle),'--execution-plan',str(plan),'--out-root',str(out),'--receipt',str(receipt)]
            with mock.patch('sys.argv',argv): self.assertEqual(mod.main(),0)
            payload=json.loads(receipt.read_text()); self.assertEqual(payload['results'][0]['status'],'RECORDED'); self.assertTrue((out/'c1'/'bundle.json').is_file())
    def test_oracle_hash_mismatch_blocks_candidate(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); oracle,plan=self.fixture(root); p=json.loads(oracle.read_text()); p['results'][0]['oracle_sha256']='0'*64; oracle.write_text(json.dumps(p)); receipt=root/'receipt.json'
            argv=['prog','--oracle-receipt',str(oracle),'--execution-plan',str(plan),'--out-root',str(root/'v'),'--receipt',str(receipt)]
            with mock.patch('sys.argv',argv): self.assertEqual(mod.main(),2)
            self.assertEqual(json.loads(receipt.read_text())['results'][0]['reason'],'ORACLE_HASH_MISMATCH')

if __name__=='__main__': unittest.main()
