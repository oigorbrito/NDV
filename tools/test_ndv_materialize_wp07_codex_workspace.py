import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ndv_materialize_wp07_codex_workspace as mod
from ndv_compile_wp07_codex_prompt import sha_value


class WorkspaceMaterializerTests(unittest.TestCase):
    def fixture(self, root: Path):
        base = {
            "schema_id":"ndv-p1-s2-base-audit-run-v2",
            "candidate_id":"C1",
            "repository":"org/repo",
            "base_revision":"b"*40,
            "harness_integrity":"PASS",
            "image_digest":"ghcr.io/example/repo@sha256:"+"d"*64,
            "network":"none",
            "gold_patch_applied":False,
            "test_patch_applied":False,
            "workdir":"/repo"
        }
        bp=root/"base-run.json"; bp.write_text(json.dumps(base),encoding="utf-8")
        admission={
            "schema_id":"ndv-p1-s2-admission-record-v2",
            "candidate_id":"C1",
            "repository":"org/repo",
            "base_revision":"b"*40,
            "source_binding":{},
            "audit":{"base_run_ref":str(bp),"base_run_sha256":mod.sha_file(bp),"image_digest":"sha256:"+"d"*64},
            "selection":{"treatment_execution_before_admission":False,"holdout_access":"NONE"},
            "status":"ADMITTED_FROZEN"
        }
        admission["record_sha256"]=sha_value(admission)
        ap=root/"admission.json"; ap.write_text(json.dumps(admission),encoding="utf-8")
        spec={
            "schema_id":"ndv-p1-s2-run-spec-v1",
            "run_id":"R1",
            "task":{"task_id":"C1","base_sha":"b"*40,"admission_record_ref":str(ap),"admission_record_file_sha256":mod.sha_file(ap),"admission_record_sha256":admission["record_sha256"]},
            "treatment":{"id":"B0","bindings":{}},
            "holdout":"DEVELOPMENT_ONLY",
            "execution_status":"NOT_EXECUTED"
        }
        sp=root/"run-spec.json"; sp.write_text(json.dumps(spec),encoding="utf-8")
        return sp,ap,bp

    @mock.patch.object(mod,"run")
    def test_materializes_from_exact_audited_image_and_proves_head_clean(self,run_mock):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); sp,_,_=self.fixture(root); out=root/"out"
            def side(argv,cwd=None,timeout=120):
                if argv[:3]==["docker","image","inspect"]:
                    return mock.Mock(returncode=0,stdout="sha256:imageid\n",stderr="")
                if argv[:2]==["docker","create"]:
                    return mock.Mock(returncode=0,stdout="cid123\n",stderr="")
                if argv[:2]==["docker","cp"]:
                    ws=out/"workspace"; (ws/".git").mkdir(parents=True,exist_ok=True)
                    return mock.Mock(returncode=0,stdout="",stderr="")
                if argv[:2]==["docker","rm"]:
                    return mock.Mock(returncode=0,stdout="",stderr="")
                if argv==["git","rev-parse","HEAD"]:
                    return mock.Mock(returncode=0,stdout="b"*40+"\n",stderr="")
                if argv==["git","status","--porcelain=v1"]:
                    return mock.Mock(returncode=0,stdout="",stderr="")
                raise AssertionError(argv)
            run_mock.side_effect=side
            result=mod.materialize(sp,root,out)
            self.assertEqual(result["status"],"CODEX_WORKSPACE_READY_NOT_EXPOSED")
            self.assertEqual(result["source_image_digest"],"ghcr.io/example/repo@sha256:"+"d"*64)
            self.assertTrue(result["clean"])
            self.assertFalse(result["task_prompt_exposed"])
            calls=[c.args[0] for c in run_mock.call_args_list]
            self.assertIn(["docker","cp","cid123:/repo/.",str((out/"workspace"))],calls)

    @mock.patch.object(mod,"run")
    def test_head_drift_blocks(self,run_mock):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); sp,_,_=self.fixture(root); out=root/"out"
            def side(argv,cwd=None,timeout=120):
                if argv[:3]==["docker","image","inspect"]: return mock.Mock(returncode=0,stdout="id\n",stderr="")
                if argv[:2]==["docker","create"]: return mock.Mock(returncode=0,stdout="cid\n",stderr="")
                if argv[:2]==["docker","cp"]:
                    (out/"workspace"/".git").mkdir(parents=True,exist_ok=True); return mock.Mock(returncode=0,stdout="",stderr="")
                if argv[:2]==["docker","rm"]: return mock.Mock(returncode=0,stdout="",stderr="")
                if argv==["git","rev-parse","HEAD"]: return mock.Mock(returncode=0,stdout="c"*40+"\n",stderr="")
                if argv==["git","status","--porcelain=v1"]: return mock.Mock(returncode=0,stdout="",stderr="")
                raise AssertionError(argv)
            run_mock.side_effect=side
            with self.assertRaisesRegex(ValueError,"HEAD mismatch"):
                mod.materialize(sp,root,out)

    def test_base_run_hash_tamper_blocks_before_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); sp,_,bp=self.fixture(root)
            bp.write_text(bp.read_text()+"\n",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"base-run file hash mismatch"):
                mod.validate_inputs(sp,root)

    def test_image_digest_binding_drift_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); sp,ap,_=self.fixture(root)
            admission=json.loads(ap.read_text()); admission["audit"]["image_digest"]="sha256:"+"e"*64
            admission["record_sha256"]=sha_value({k:v for k,v in admission.items() if k!="record_sha256"})
            ap.write_text(json.dumps(admission),encoding="utf-8")
            spec=json.loads(sp.read_text()); spec["task"]["admission_record_file_sha256"]=mod.sha_file(ap); spec["task"]["admission_record_sha256"]=admission["record_sha256"]; sp.write_text(json.dumps(spec),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"image digest mismatch"):
                mod.validate_inputs(sp,root)


if __name__=="__main__":
    unittest.main()
