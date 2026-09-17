import json, tempfile, unittest
from pathlib import Path
import ndv_promote_codex_bindings_to_wp07 as promote
from ndv_wp07_codex_bundle import seal_bundle

class V4PromotionTests(unittest.TestCase):
    def mk_surface(self, root):
        p=root/"surface.json"; p.write_text(json.dumps({"schema_id":"ndv-p1-wp07-codex-execution-surface-v1","status":"PROSPECTIVE_FROZEN_NOT_EXECUTED"})); return p
    def mk_amendment(self, root, cohort="v4"):
        p=root/f"amendment-{cohort}.json"; p.write_text(json.dumps({"schema_id":f"ndv-p1-wp07-codex-qualification-amendment-{cohort}","status":"PROSPECTIVE_AMENDMENT_FROZEN_NOT_EXECUTED"})); return p
    def mk_registry(self, root):
        p=root/"registry.json"; p.write_text(json.dumps({"schema_id":"ndv-p1-wp07-treatment-bindings-v1","status":"INCOMPLETE_BINDING_COVERAGE","treatment_execution":"NOT_EXECUTED","holdout_access":"NONE","treatments":{"B0":{"bindings":{},"status":"UNBOUND"},"B1":{"bindings":{},"status":"UNBOUND"},"B2":{"bindings":{},"status":"UNBOUND"},"B3":{"bindings":{},"family_policy":{},"status":"UNBOUND"},"B4":{"bindings":{},"status":"UNBOUND"}}})); return p
    def mk(self, root, surface, amendment, model, cid, roles, cohort="V4"):
        d=root/model; (d/"evidence").mkdir(parents=True)
        sh=promote.sha_file(surface); ah=promote.sha_file(amendment)
        q={"schema_id":f"ndv-p1-wp07-codex-subscription-qualification-{cohort.lower()}","status":"S0_READY","qualification_cohort":cohort,"candidate_id":cid,"requested_model":model,"identity_assurance":{"status":"CLI_PINNED_SOURCE_VERIFIED","requested_model":model},"candidate_roles":roles,"execution_surface_ref":str(surface),"execution_surface_file_sha256":sh,"amendment_ref":str(amendment),"amendment_file_sha256":ah,"windows_sandbox_backend_requested":"unelevated"}
        qp=d/"qualification.json"; qp.write_text(json.dumps(q))
        b={"schema_id":f"ndv-p1-wp07-executor-binding-{cohort.lower()}","status":"QUALIFIED","binding_id":"B-"+model,"candidate_id":cid,"surface_class":"SUBSCRIPTION_EXECUTOR_PINNED","exact_executor_identity":"codex+"+model,"identity_assurance":"CLI_PINNED_SOURCE_VERIFIED","model":{"identity":model},"auth_path":"CHATGPT_SUBSCRIPTION","api_key_routing_forbidden":True,"dynamic_routing":False,"implicit_fallback":False,"retry_limit":0,"escalation_limit":0,"qualification_file_sha256":promote.sha_file(qp),"candidate_roles":roles,"execution_surface_ref":str(surface),"execution_surface_file_sha256":sh,"amendment_ref":str(amendment),"amendment_file_sha256":ah,"windows_sandbox_backend":"UNELEVATED"}
        (d/"executor-binding.json").write_text(json.dumps(b))
        (d/"evidence"/"executor.log").write_text("ok\n"); (d/"evidence"/"candidate.diff").write_bytes(b"diff\n"); (d/"evidence"/"git-status.txt").write_text(" M TARGET.txt\n")
        seal_bundle(d); return d
    def test_v4_sol_luna_promote(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp); s=self.mk_surface(r); a=self.mk_amendment(r); reg=self.mk_registry(r)
            sol=self.mk(r,s,a,"gpt-5.6-sol","CODEX-PLUS-GPT-5.6-SOL",["PRIMARY_STRONG","ESCALATION_STRONG"])
            luna=self.mk(r,s,a,"gpt-5.6-luna","CODEX-PLUS-GPT-5.6-LUNA",["PRIMARY_ECONOMIC"])
            out=promote.promote(reg,sol,luna,r)
            self.assertEqual(out["treatments"]["B1"]["status"],"BOUND_READY")
            rec=out["treatments"]["B1"]["bindings"]["PRIMARY_ECONOMIC"]
            self.assertEqual(rec["qualification_schema"],"ndv-p1-wp07-codex-subscription-qualification-v4")
            self.assertEqual(rec["windows_sandbox_backend"],"UNELEVATED")
            self.assertEqual(rec["amendment_file_sha256"],promote.sha_file(a))
    def test_mixed_amendment_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp); s=self.mk_surface(r); a1=self.mk_amendment(r,"v4"); a2=r/"amendment-v4b.json"; a2.write_text(json.dumps({"schema_id":"ndv-p1-wp07-codex-qualification-amendment-v4","status":"PROSPECTIVE_AMENDMENT_FROZEN_NOT_EXECUTED","variant":"b"})); reg=self.mk_registry(r)
            sol=self.mk(r,s,a1,"gpt-5.6-sol","CODEX-PLUS-GPT-5.6-SOL",["PRIMARY_STRONG","ESCALATION_STRONG"])
            luna=self.mk(r,s,a2,"gpt-5.6-luna","CODEX-PLUS-GPT-5.6-LUNA",["PRIMARY_ECONOMIC"])
            with self.assertRaisesRegex(ValueError,"different amendments"): promote.promote(reg,sol,luna,r)

if __name__=="__main__": unittest.main()
