import json
import tempfile
import unittest
from pathlib import Path

import ndv_materialize_wp07_run_matrix as mod


class MatrixMaterializerTests(unittest.TestCase):
    def protocol(self, root: Path):
        p=root/"protocol.json"; p.write_text(json.dumps({"schema_id":"ndv-p1-wp07-development-comparison-protocol-v1","status":"PROSPECTIVE_FROZEN_NOT_RELEASED","primary_metric":"TOTAL_SYSTEM_TOKENS / VERIFIED_SOLVED_TASK","treatment_execution":"NOT_EXECUTED","holdout_access":"NONE"})); return p
    def release(self, root: Path):
        p=root/"release.json"; p.write_text(json.dumps({"schema_id":"ndv-p1-wp07-development-comparison-release-v1","status":"WP07_DEVELOPMENT_COMPARISON_RELEASED","authorized_scope":{"development_corpus_comparative_treatment_execution":True,"sealed_holdout_access":False,"claim_generation":False,"architecture_decision":False},"holdout_access":"NONE"})); return p
    def binding(self, root: Path, name: str):
        bf=root/f"{name}-binding.json"; qf=root/f"{name}-qual.json"; bf.write_text(json.dumps({"binding_id":name})); qf.write_text(json.dumps({"status":"PASS"}))
        return {"binding_id":name,"binding_ref":str(bf),"binding_file_sha256":mod.sha_file(bf),"qualification_ref":str(qf),"qualification_file_sha256":mod.sha_file(qf),"exact_executor_identity":name+"-exec","surface_class":"LOCAL_PINNED"}
    def registry(self, root: Path, ready=True):
        b0=self.binding(root,"strong"); b1=self.binding(root,"cheap"); b4=self.binding(root,"local")
        data={"schema_id":"ndv-p1-wp07-treatment-bindings-v1","treatments":{
            "B0":{"status":"BOUND_READY" if ready else "UNBOUND","bindings":{"PRIMARY_STRONG":b0} if ready else {}},
            "B1":{"status":"BOUND_READY","bindings":{"PRIMARY_ECONOMIC":b1}},
            "B2":{"status":"BOUND_READY","bindings":{"PRIMARY_ECONOMIC":b1,"ESCALATION_STRONG":b0}},
            "B3":{"status":"BOUND_READY","bindings":{"f1":b0},"family_policy":{"F1":"f1"}},
            "B4":{"status":"BOUND_READY","bindings":{"PRIMARY_LOCAL_OR_FREE":b4,"ESCALATION_STRONG":b0}},
        },"treatment_execution":"NOT_EXECUTED","holdout_access":"NONE"}
        p=root/"registry.json"; p.write_text(json.dumps(data)); return p
    def admission(self, root: Path):
        body={"schema_id":"ndv-p1-s2-admission-record-v2","status":"ADMITTED_FROZEN","candidate_id":"C1","repository":"org/repo","base_revision":"a"*40,"family":"F1","source_binding":{"task_statement_sha256":"b"*64},"audit":{"focal_verifier_ref":"focal.json","focal_verifier_sha256":"c"*64,"preservation_ref":"pres.json","preservation_sha256":"d"*64,"environment_ref":"env.json","environment_sha256":"e"*64},"selection":{"treatment_execution_before_admission":False,"holdout_access":"NONE"}}
        body["record_sha256"]=mod.sha(body); p=root/"admission.json"; p.write_text(json.dumps(body)); return p

    def test_incomplete_binding_registry_blocks_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaisesRegex(ValueError,"B0: binding coverage incomplete"):
                mod.materialize(self.release(root),self.protocol(root),self.registry(root,ready=False),[self.admission(root)],root,"S0_ONLY")

    def test_s0_one_task_materializes_exactly_five_specs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); result=mod.materialize(self.release(root),self.protocol(root),self.registry(root),[self.admission(root)],root,"S0_ONLY")
            self.assertEqual(result["run_spec_count"],5)
            self.assertEqual({x["treatment"]["id"] for x in result["run_specs"]},{"B0","B1","B2","B3","B4"})
            self.assertTrue(all(x["execution_status"]=="NOT_EXECUTED" for x in result["run_specs"]))
            self.assertEqual(result["holdout_access"],"NONE")

    def test_paired_shaping_materializes_ten_specs_per_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); result=mod.materialize(self.release(root),self.protocol(root),self.registry(root),[self.admission(root)],root,"PAIRED_S0_S1")
            self.assertEqual(result["run_spec_count"],10)
            for tid in {"B0","B1","B2","B3","B4"}:
                self.assertEqual({x["treatment"]["shaping"] for x in result["run_specs"] if x["treatment"]["id"]==tid},{"S0_RAW_TASK","S1_DETERMINISTIC_TASK_SHAPING"})

    def test_tampered_admission_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); admission=self.admission(root); payload=json.loads(admission.read_text()); payload["repository"]="tampered/repo"; admission.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError,"record_sha256 mismatch"):
                mod.materialize(self.release(root),self.protocol(root),self.registry(root),[admission],root,"S0_ONLY")

    def test_b3_missing_family_binding_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); reg=self.registry(root); payload=json.loads(reg.read_text()); payload["treatments"]["B3"]["family_policy"]={"F2":"f1"}; reg.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError,"no frozen binding for family F1"):
                mod.materialize(self.release(root),self.protocol(root),reg,[self.admission(root)],root,"S0_ONLY")


if __name__=="__main__": unittest.main()
