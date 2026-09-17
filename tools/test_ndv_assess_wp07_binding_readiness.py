import json
import tempfile
import unittest
from pathlib import Path

import ndv_assess_wp07_binding_readiness as mod


class BindingReadinessTests(unittest.TestCase):
    def base_registry(self):
        return {
            "schema_id":"ndv-p1-wp07-treatment-bindings-v1",
            "binding_rules":{k:True for k in (
                "concrete_binding_required","binding_bytes_must_be_preserved","binding_file_sha256_required",
                "qualification_evidence_required","silent_substitution_forbidden","dynamic_provider_routing_forbidden",
                "missing_binding_blocks_cell","blocked_cell_is_not_a_run","blocked_cell_cost_is_not_zero")},
            "treatments":{
                "B0":{"name":"STRONG_DIRECT","required_roles":["PRIMARY_STRONG"],"bindings":{},"status":"UNBOUND"},
                "B1":{"name":"CHEAP_DIRECT_VERIFY","required_roles":["PRIMARY_ECONOMIC"],"bindings":{},"status":"UNBOUND"},
                "B2":{"name":"CHEAP_THEN_ESCALATE","required_roles":["PRIMARY_ECONOMIC","ESCALATION_STRONG"],"bindings":{},"status":"UNBOUND"},
                "B3":{"name":"STATIC_FAMILY_POLICY","required_roles":["FAMILY_POLICY_MAP"],"bindings":{},"family_policy":{},"status":"UNBOUND"},
                "B4":{"name":"LOCAL_OR_FREE_FIRST","required_roles":["PRIMARY_LOCAL_OR_FREE","ESCALATION_STRONG"],"bindings":{},"status":"UNBOUND"},
            },
            "treatment_execution":"NOT_EXECUTED","holdout_access":"NONE"
        }

    def make_binding(self, root: Path, name: str):
        bfile=root/f"{name}-binding.json"; qfile=root/f"{name}-qualification.json"
        payload={"binding_id":name,"exact_executor_identity":name+"-executor","status":"QUALIFIED"}
        bfile.write_text(json.dumps(payload)); qfile.write_text(json.dumps({"status":"PASS"}))
        return {"binding_id":name,"binding_ref":str(bfile),"binding_file_sha256":mod.sha_file(bfile),"qualification_ref":str(qfile),"qualification_file_sha256":mod.sha_file(qfile),"exact_executor_identity":payload["exact_executor_identity"],"surface_class":"LOCAL_PINNED"}

    def write_registry(self, root: Path, registry):
        p=root/"registry.json"; p.write_text(json.dumps(registry)); return p

    def test_empty_registry_is_valid_but_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); result=mod.assess(self.write_registry(root,self.base_registry()),root)
            self.assertEqual(result["status"],"BINDING_COVERAGE_INCOMPLETE")
            self.assertFalse(result["all_treatments_ready"])
            self.assertEqual(result["matrix_materialization_release"],"NO")

    def test_one_local_binding_does_not_make_b4_ready_without_strong_escalation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); reg=self.base_registry(); reg["treatments"]["B4"]["bindings"]["PRIMARY_LOCAL_OR_FREE"]=self.make_binding(root,"local"); reg["treatments"]["B4"]["status"]="PARTIALLY_BOUND"
            result=mod.assess(self.write_registry(root,reg),root)
            self.assertFalse(result["treatments"]["B4"]["ready"])
            self.assertEqual(result["treatments"]["B4"]["missing_roles"],["ESCALATION_STRONG"])

    def test_tampered_binding_bytes_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); reg=self.base_registry(); b=self.make_binding(root,"strong"); reg["treatments"]["B0"]["bindings"]["PRIMARY_STRONG"]=b; reg["treatments"]["B0"]["status"]="BOUND_READY"
            Path(b["binding_ref"]).write_text("{}")
            with self.assertRaisesRegex(ValueError,"binding hash mismatch"): mod.assess(self.write_registry(root,reg),root)

    def test_ready_binding_requires_declared_ready_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); reg=self.base_registry(); reg["treatments"]["B0"]["bindings"]["PRIMARY_STRONG"]=self.make_binding(root,"strong")
            with self.assertRaisesRegex(ValueError,"BOUND_READY"): mod.assess(self.write_registry(root,reg),root)

    def test_b3_policy_cannot_reference_unknown_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); reg=self.base_registry(); reg["treatments"]["B3"]["family_policy"]={"F1":"missing"}; reg["treatments"]["B3"]["status"]="BOUND_READY"
            with self.assertRaisesRegex(ValueError,"unknown binding alias"): mod.assess(self.write_registry(root,reg),root)


if __name__=="__main__": unittest.main()
