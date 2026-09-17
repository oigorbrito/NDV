import json, tempfile, unittest
from pathlib import Path
import ndv_freeze_wp07_b3_family_policy as mod
from ndv_wp07_codex_bundle import seal_bundle

class B3PolicyTests(unittest.TestCase):
    def mk_candidate(self,root,model,cid):
        d=root/model; (d/"evidence").mkdir(parents=True); q={"schema_id":"ndv-p1-wp07-codex-subscription-qualification-v1","status":"S0_READY","candidate_id":cid,"requested_model":model,"observed_models":[model],"exact_model_observed":True}; qp=d/"qualification.json"; qp.write_text(json.dumps(q)); b={"schema_id":"ndv-p1-wp07-executor-binding-v1","status":"QUALIFIED","binding_id":"B-"+model,"candidate_id":cid,"model":{"identity":model},"qualification_file_sha256":mod.sha_file(qp),"dynamic_routing":False,"implicit_fallback":False,"exact_executor_identity":"codex+"+model}; (d/"executor-binding.json").write_text(json.dumps(b)); (d/"evidence"/"executor.log").write_text("model: "+model+"\n"); (d/"evidence"/"candidate.diff").write_bytes(b"diff\n"); (d/"evidence"/"git-status.txt").write_text(" M TARGET.txt\n"); seal_bundle(d); return d
    def mk_registry(self,root):
        p=root/"reg.json"; p.write_text(json.dumps({"schema_id":"ndv-p1-wp07-treatment-bindings-v1","treatment_execution":"NOT_EXECUTED","holdout_access":"NONE","treatments":{x:{"bindings":{},"status":"UNBOUND"} for x in ["B0","B1","B2","B3","B4"]}})); return p
    def mk_policy(self,root):
        p=root/"policy.json"; p.write_text(json.dumps({"schema_id":"ndv-p1-wp07-static-family-policy-v1","status":"PROSPECTIVE_FROZEN_NOT_BOUND","performance_data_used":False,"treatment_results_used":False,"dynamic_routing":False,"post_hoc_remapping":False,"policy":{f:{"model":m,"candidate_id":c} for f,(m,c) in mod.EXPECTED.items()}})); return p
    def test_freezes_exact_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp); reg=self.mk_registry(r); pol=self.mk_policy(r); sol=self.mk_candidate(r,"gpt-5.6-sol","CODEX-PLUS-GPT-5.6-SOL"); terra=self.mk_candidate(r,"gpt-5.6-terra","CODEX-PLUS-GPT-5.6-TERRA"); luna=self.mk_candidate(r,"gpt-5.6-luna","CODEX-PLUS-GPT-5.6-LUNA")
            out=mod.freeze(reg,pol,sol,terra,luna,r); b3=out["treatments"]["B3"]; self.assertEqual(b3["status"],"BOUND_READY"); self.assertEqual(b3["family_policy"]["F2"],"SOL"); self.assertEqual(b3["family_policy"]["F4"],"LUNA")
    def test_policy_drift_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp); reg=self.mk_registry(r); pol=self.mk_policy(r); payload=json.loads(pol.read_text()); payload["policy"]["F1"]["model"]="gpt-5.6-sol"; pol.write_text(json.dumps(payload)); sol=self.mk_candidate(r,"gpt-5.6-sol","CODEX-PLUS-GPT-5.6-SOL"); terra=self.mk_candidate(r,"gpt-5.6-terra","CODEX-PLUS-GPT-5.6-TERRA"); luna=self.mk_candidate(r,"gpt-5.6-luna","CODEX-PLUS-GPT-5.6-LUNA")
            with self.assertRaisesRegex(ValueError,"policy drift"): mod.freeze(reg,pol,sol,terra,luna,r)
    def test_tampered_bundle_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp); reg=self.mk_registry(r); pol=self.mk_policy(r); sol=self.mk_candidate(r,"gpt-5.6-sol","CODEX-PLUS-GPT-5.6-SOL"); terra=self.mk_candidate(r,"gpt-5.6-terra","CODEX-PLUS-GPT-5.6-TERRA"); luna=self.mk_candidate(r,"gpt-5.6-luna","CODEX-PLUS-GPT-5.6-LUNA"); (terra/"evidence"/"executor.log").write_text("tampered")
            with self.assertRaisesRegex(ValueError,"hash/size mismatch"): mod.freeze(reg,pol,sol,terra,luna,r)
if __name__=="__main__": unittest.main()
