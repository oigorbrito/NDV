import hashlib, json, tempfile, unittest
from pathlib import Path
import ndv_bind_s2_audit_plan_images as mod

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

class BindImagesTests(unittest.TestCase):
    def fixture(self, root: Path):
        wave=root/'wave.json'; wave.write_text('{}')
        runner=root/'runner.py'; runner.write_text('# runner')
        plan=root/'plan.json'
        entry={"candidate_id":"c1","image_ref":"docker.io/org/repo:tag","image_digest":None,"argv":["python",str(runner),"--wave",str(wave),"--candidate-id","c1","--admission-row","a.json","--out","o"],"authorized_action":"PRE_SOLUTION_BASE_AUDIT_ONLY","treatment_execution":"NOT_EXECUTED","holdout_access":"NONE"}
        plan.write_text(json.dumps({"schema_id":"ndv-p1-s2-base-audit-plan-v2","status":"AUDIT_PLAN_READY","wave_id":"w","wave_ref":str(wave),"wave_file_sha256":sha(wave),"runner_ref":str(runner),"runner_file_sha256":sha(runner),"candidate_count":1,"entries":[entry],"docker_execution":False,"model_execution":"NONE","treatment_execution":"NOT_EXECUTED","holdout_access":"NONE"}))
        receipt=root/'images.json'; receipt.write_text(json.dumps({"schema_id":"ndv-p1-s2-image-acquisition-receipt-v1","status":"IMAGES_ACQUIRED_AND_PINNED","wave_id":"w","wave_ref":str(wave),"wave_file_sha256":sha(wave),"images":[{"image_ref":"docker.io/org/repo:tag","repo_digest":"docker.io/org/repo@sha256:"+'a'*64}],"image_count":1,"container_execution":False,"model_execution":"NONE","treatment_execution":"NOT_EXECUTED","holdout_access":"NONE"}))
        return plan,receipt
    def test_bind_adds_digest_to_entry_and_argv(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan,receipt=self.fixture(Path(tmp)); out=mod.bind(plan,receipt); e=out['entries'][0]; self.assertEqual(out['schema_id'],'ndv-p1-s2-base-audit-execution-plan-v1'); self.assertIn('@sha256:',e['image_digest']); self.assertIn('--image-digest',e['argv'])
    def test_wrong_wave_hash_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); plan,receipt=self.fixture(root); p=json.loads(receipt.read_text()); p['wave_file_sha256']='0'*64; receipt.write_text(json.dumps(p))
            with self.assertRaisesRegex(ValueError,'wave binding'): mod.bind(plan,receipt)
    def test_missing_image_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); plan,receipt=self.fixture(root); p=json.loads(receipt.read_text()); p['images']=[]; p['image_count']=0; receipt.write_text(json.dumps(p))
            with self.assertRaisesRegex(ValueError,'exactly cover'): mod.bind(plan,receipt)

if __name__=='__main__': unittest.main()
