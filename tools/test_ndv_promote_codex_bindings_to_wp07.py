import json
import tempfile
import unittest
from pathlib import Path

import ndv_promote_codex_bindings_to_wp07 as mod


class PromotionTests(unittest.TestCase):
    def make_registry(self, root: Path) -> Path:
        p=root/"registry.json"; p.write_text(json.dumps({"schema_id":"ndv-p1-wp07-treatment-bindings-v1","status":"INCOMPLETE_BINDING_COVERAGE","treatment_execution":"NOT_EXECUTED","holdout_access":"NONE","treatments":{
            "B0":{"bindings":{},"status":"UNBOUND"},"B1":{"bindings":{},"status":"UNBOUND"},"B2":{"bindings":{},"status":"UNBOUND"},"B3":{"bindings":{},"family_policy":{},"status":"UNBOUND"},"B4":{"bindings":{},"status":"UNBOUND"}}}),encoding="utf-8"); return p
    def make_candidate(self, root:Path, model:str, cid:str, roles:list[str])->Path:
        d=root/model; d.mkdir(); q={"schema_id":"ndv-p1-wp07-codex-subscription-qualification-v1","status":"S0_READY","candidate_id":cid,"requested_model":model,"observed_models":[model],"exact_model_observed":True,"candidate_roles":roles}; qp=d/"qualification.json"; qp.write_text(json.dumps(q),encoding="utf-8")
        b={"schema_id":"ndv-p1-wp07-executor-binding-v1","status":"QUALIFIED","binding_id":"B-"+model,"candidate_id":cid,"surface_class":"SUBSCRIPTION_EXECUTOR_PINNED","exact_executor_identity":"codex+"+model,"model":{"identity":model},"auth_path":"CHATGPT_SUBSCRIPTION","api_key_routing_forbidden":True,"dynamic_routing":False,"implicit_fallback":False,"retry_limit":0,"escalation_limit":0,"qualification_file_sha256":mod.sha_file(qp),"candidate_roles":roles}; (d/"executor-binding.json").write_text(json.dumps(b),encoding="utf-8"); return d
    def test_sol_luna_fill_expected_roles_b3_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp); reg=self.make_registry(r); sol=self.make_candidate(r,"gpt-5.6-sol","CODEX-PLUS-GPT-5.6-SOL",["PRIMARY_STRONG","ESCALATION_STRONG"]); luna=self.make_candidate(r,"gpt-5.6-luna","CODEX-PLUS-GPT-5.6-LUNA",["PRIMARY_ECONOMIC"])
            out=mod.promote(reg,sol,luna,r)
            self.assertEqual(out["treatments"]["B0"]["status"],"BOUND_READY"); self.assertEqual(out["treatments"]["B1"]["status"],"BOUND_READY"); self.assertEqual(out["treatments"]["B2"]["status"],"BOUND_READY")
            self.assertEqual(out["treatments"]["B3"]["status"],"UNBOUND"); self.assertEqual(out["treatments"]["B4"]["status"],"PARTIALLY_BOUND")
    def test_existing_b4_local_first_hop_makes_b4_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp); reg=self.make_registry(r); payload=json.loads(reg.read_text()); payload["treatments"]["B4"]["bindings"]={"PRIMARY_LOCAL_OR_FREE":{"x":1}}; payload["treatments"]["B4"]["status"]="PARTIALLY_BOUND"; reg.write_text(json.dumps(payload))
            sol=self.make_candidate(r,"gpt-5.6-sol","CODEX-PLUS-GPT-5.6-SOL",["PRIMARY_STRONG","ESCALATION_STRONG"]); luna=self.make_candidate(r,"gpt-5.6-luna","CODEX-PLUS-GPT-5.6-LUNA",["PRIMARY_ECONOMIC"])
            out=mod.promote(reg,sol,luna,r); self.assertEqual(out["treatments"]["B4"]["status"],"BOUND_READY")
    def test_wrong_model_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp); reg=self.make_registry(r); sol=self.make_candidate(r,"gpt-5.6-sol","CODEX-PLUS-GPT-5.6-SOL",["PRIMARY_STRONG","ESCALATION_STRONG"]); luna=self.make_candidate(r,"gpt-5.6-luna","CODEX-PLUS-GPT-5.6-LUNA",["PRIMARY_ECONOMIC"])
            q=json.loads((luna/"qualification.json").read_text()); q["requested_model"]="gpt-5.6-terra"; (luna/"qualification.json").write_text(json.dumps(q))
            with self.assertRaises(ValueError): mod.promote(reg,sol,luna,r)

if __name__=="__main__": unittest.main()
