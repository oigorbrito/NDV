import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ndv_qualify_codex_subscription_executor as mod


class CodexQualifierTests(unittest.TestCase):
    def surface(self):
        return {"schema_id":"ndv-p1-wp07-codex-execution-surface-v1","status":"PROSPECTIVE_FROZEN_NOT_EXECUTED","minimum_version":"0.144.0","mode":"exec","required_flags":["--model","--sandbox","--json","--ephemeral","--ignore-user-config","--ignore-rules","--strict-config","--disable"],"fixed_flags":["--json","--ephemeral","--ignore-user-config","--ignore-rules","--strict-config","--sandbox","workspace-write","--disable","apps","--disable","plugins"],"model_selection":"EXPLICIT_PINNED_PER_BINDING","environment_variables_removed":["OPENAI_API_KEY"],"sandbox":"workspace-write","implicit_fallback":False,"dynamic_routing":False,"holdout_access":"NONE","treatment_execution":"NOT_EXECUTED"}
    def test_parse_version(self):
        self.assertEqual(mod.parse_version("codex-cli 0.153.0"),(0,153,0)); self.assertEqual(mod.parse_version("OpenAI Codex 0.144.1"),(0,144,1)); self.assertIsNone(mod.parse_version("unknown"))
    def test_observed_models_from_text_and_jsonl(self):
        raw='model: gpt-5.6-sol\n{"event":{"model":"gpt-5.6-sol"}}\n'; self.assertEqual(mod.observed_models(raw),{"gpt-5.6-sol"}); self.assertEqual(mod.observed_models(raw+'model: gpt-5.6-luna\n'),{"gpt-5.6-sol","gpt-5.6-luna"})
    @mock.patch.object(mod,"run")
    def test_interface_requires_minimum_version_and_fail_closed_flags(self,run_mock):
        class P:
            def __init__(self,rc,out): self.returncode=rc; self.stdout=out; self.stderr=""
        run_mock.side_effect=[P(0,"codex-cli 0.153.0\n"),P(0,"--model --sandbox --json --ephemeral --ignore-user-config --ignore-rules --strict-config --disable\n")]
        raw,flags=mod.require_interface(Path("codex"),self.surface()); self.assertIn("0.153.0",raw); self.assertIn("--model",flags); self.assertIn("--disable",flags)
    @mock.patch.object(mod,"run")
    def test_old_codex_version_rejected(self,run_mock):
        run_mock.return_value=subprocess.CompletedProcess(["codex","--version"],0,stdout="codex-cli 0.143.9\n",stderr="")
        with self.assertRaisesRegex(ValueError,">=0.144.0"): mod.require_interface(Path("codex"),self.surface())
    @mock.patch.object(mod,"run")
    def test_missing_disable_flag_rejected(self,run_mock):
        run_mock.side_effect=[subprocess.CompletedProcess([],0,stdout="codex-cli 0.153.0\n",stderr=""),subprocess.CompletedProcess([],0,stdout="--model --sandbox --json --ephemeral --ignore-user-config --ignore-rules --strict-config\n",stderr="")]
        with self.assertRaisesRegex(ValueError,"--disable"): mod.require_interface(Path("codex"),self.surface())
    def test_invocation_is_derived_from_surface(self):
        s=self.surface(); argv=mod.invocation(Path("/tmp/codex"),"gpt-5.6-luna","TASK",s); self.assertEqual(argv[1:4],["exec","--model","gpt-5.6-luna"]); self.assertEqual(argv[-1],"TASK"); self.assertIn("workspace-write",argv); self.assertEqual(argv.count("--disable"),2)
    def test_surface_contamination_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"surface.json"; s=self.surface(); s["dynamic_routing"]=True; p.write_text(json.dumps(s))
            with self.assertRaisesRegex(ValueError,"contamination"): mod.load_surface(p)
    def test_role_mapping_is_frozen(self):
        self.assertEqual(mod.ALLOWED["gpt-5.6-sol"][1],["PRIMARY_STRONG","ESCALATION_STRONG"]); self.assertEqual(mod.ALLOWED["gpt-5.6-luna"][1],["PRIMARY_ECONOMIC"]); self.assertIn("FAMILY_POLICY_CANDIDATE",mod.ALLOWED["gpt-5.6-terra"][1])
    def test_exact_diff_requires_only_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); mod.init_repo(root); (root/"TARGET.txt").write_text("AFTER\n",encoding="utf-8"); exact,status,diff=mod.validate_diff(root); self.assertTrue(exact); self.assertIn("TARGET.txt",status); self.assertTrue(diff); (root/"OTHER.txt").write_text("x\n",encoding="utf-8"); exact2,_,_=mod.validate_diff(root); self.assertFalse(exact2)
    def test_program_contamination_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"program.json"; p.write_text(json.dumps({"schema_id":"ndv-p1-wp07-executor-role-qualification-v1","status":"PROSPECTIVE_FROZEN_NOT_EXECUTED","treatment_execution":"EXECUTED","holdout_access":"NONE"}),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"contamination"): mod.load_program(p)

if __name__=="__main__": unittest.main()
