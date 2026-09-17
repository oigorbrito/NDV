import json, tempfile, unittest
from pathlib import Path
from unittest import mock
import subprocess

import ndv_preflight_wp07_codex_run_spec as mod
from ndv_wp07_codex_bundle import seal_bundle

class PreflightTests(unittest.TestCase):
    def make_fixture(self,root:Path):
        surface=root/"surface.json"; surface.write_text(json.dumps({"schema_id":"ndv-p1-wp07-codex-execution-surface-v1","status":"PROSPECTIVE_FROZEN_NOT_EXECUTED","minimum_version":"0.144.0","mode":"exec","required_flags":["--model","--sandbox","--json","--ephemeral","--ignore-user-config","--ignore-rules","--strict-config","--disable"],"fixed_flags":["--json","--ephemeral","--ignore-user-config","--ignore-rules","--strict-config","--sandbox","workspace-write","--disable","apps","--disable","plugins"],"environment_variables_removed":["OPENAI_API_KEY"]}))
        exe=root/"codex.exe"; exe.write_bytes(b"x")
        d=root/"bundle"; (d/"evidence").mkdir(parents=True); sh=mod.sha_file(surface)
        q={"schema_id":"ndv-p1-wp07-codex-subscription-qualification-v1","status":"S0_READY","candidate_id":"CODEX-PLUS-GPT-5.6-LUNA","requested_model":"gpt-5.6-luna","execution_surface_file_sha256":sh}; qp=d/"qualification.json"; qp.write_text(json.dumps(q))
        b={"schema_id":"ndv-p1-wp07-executor-binding-v1","status":"QUALIFIED","binding_id":"B-LUNA","candidate_id":"CODEX-PLUS-GPT-5.6-LUNA","exact_executor_identity":"codex(codex-cli 0.153.0)+gpt-5.6-luna","model":{"identity":"gpt-5.6-luna"},"scaffold":{"executable_path":str(exe),"version":"0.153.0"},"qualification_file_sha256":mod.sha_file(qp),"execution_surface_file_sha256":sh}; bp=d/"executor-binding.json"; bp.write_text(json.dumps(b))
        (d/"evidence"/"executor.log").write_text("model: gpt-5.6-luna\n"); (d/"evidence"/"candidate.diff").write_bytes(b"diff\n"); (d/"evidence"/"git-status.txt").write_text(" M TARGET.txt\n"); seal_bundle(d)
        rec={"binding_id":"B-LUNA","binding_ref":str(bp),"binding_file_sha256":mod.sha_file(bp),"qualification_ref":str(qp),"qualification_file_sha256":mod.sha_file(qp),"evidence_manifest_ref":str(d/"evidence-manifest.json"),"evidence_manifest_sha256":mod.sha_file(d/"evidence-manifest.json"),"execution_surface_ref":str(surface),"execution_surface_file_sha256":sh,"exact_executor_identity":b["exact_executor_identity"],"surface_class":"SUBSCRIPTION_EXECUTOR_PINNED"}
        spec=root/"spec.json"; spec.write_text(json.dumps({"schema_id":"ndv-p1-s2-run-spec-v1","run_id":"R1","execution_status":"NOT_EXECUTED","holdout":"DEVELOPMENT_ONLY","treatment":{"id":"B1","bindings":{"PRIMARY_ECONOMIC":rec}}}))
        return spec,surface
    @mock.patch.object(mod.subprocess,"run")
    def test_preflight_emits_redacted_template_without_task_exposure(self,run_mock):
        run_mock.side_effect=[subprocess.CompletedProcess([],0,stdout="codex-cli 0.153.0\n",stderr=""),subprocess.CompletedProcess([],0,stdout="--model --sandbox --json --ephemeral --ignore-user-config --ignore-rules --strict-config --disable\n",stderr="")]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); spec,_=self.make_fixture(root); out=mod.preflight(spec,root); self.assertEqual(out["status"],"CODEX_RUN_SPEC_PREFLIGHT_PASS"); self.assertFalse(out["task_prompt_exposed"]); self.assertEqual(out["argv_template"][-1],"<FROZEN_TASK_PROMPT>"); self.assertEqual(run_mock.call_count,2)
    @mock.patch.object(mod.subprocess,"run")
    def test_surface_tamper_blocks_before_subprocess(self,run_mock):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); spec,surface=self.make_fixture(root); surface.write_text("{}")
            with self.assertRaisesRegex(ValueError,"execution_surface_file_sha256 mismatch"): mod.preflight(spec,root)
            run_mock.assert_not_called()
    def test_cascade_spec_requires_per_hop_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); spec,_=self.make_fixture(root); payload=json.loads(spec.read_text()); one=payload["treatment"]["bindings"]["PRIMARY_ECONOMIC"]; payload["treatment"]["bindings"]["ESCALATION_STRONG"]=dict(one); spec.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError,"exactly one selected subscription binding"): mod.preflight(spec,root)

if __name__=="__main__":unittest.main()
