import json, tempfile, unittest
from pathlib import Path
import ndv_qualify_codex_subscription_executor_v4 as mod


class QualifierV4Tests(unittest.TestCase):
    def amendment(self):
        return {
            "schema_id":"ndv-p1-wp07-codex-qualification-amendment-v4",
            "status":"PROSPECTIVE_AMENDMENT_FROZEN_NOT_EXECUTED",
            "historical_v1_v2_v3_evidence_reinterpretation":"FORBIDDEN",
            "development_task_exposure":False,
            "holdout_access":"NONE",
            "treatment_execution":"NOT_EXECUTED",
            "windows_sandbox_policy":{"config_override":mod.WINDOWS_SANDBOX_OVERRIDE,"danger_full_access":False,"approval_bypass":False},
            "identity_policy":{"required_cli_version_exact":"0.154.0"},
            "environment_failure_markers":["blocked by policy"],
            "upstream_provenance":{"release_commit":"6b9826e3aa83b1a5947db50f4332cb9c65f1b340"},
        }

    def surface(self):
        return {"mode":"exec","fixed_flags":["--json","--sandbox","workspace-write"],"task_delivery":"FINAL_POSITIONAL_PROMPT"}

    def test_invocation_pins_one_root_and_unelevated_before_prompt(self):
        with tempfile.TemporaryDirectory() as td:
            repo=Path(td).resolve()
            argv=mod.invocation_v4(Path("codex.exe"),"gpt-5.6-luna","TASK",self.surface(),repo)
            self.assertEqual(argv[-1],"TASK")
            self.assertEqual(argv.count("--add-dir"),1)
            self.assertEqual(Path(argv[argv.index("--add-dir")+1]),repo)
            self.assertEqual(argv.count("-c"),1)
            self.assertEqual(argv[argv.index("-c")+1],mod.WINDOWS_SANDBOX_OVERRIDE)
            self.assertNotIn("danger-full-access",argv)
            self.assertNotIn("--dangerously-bypass-approvals-and-sandbox",argv)

    def test_amendment_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"a.json"; p.write_text(json.dumps(self.amendment()))
            self.assertEqual(mod.load_amendment(p)["windows_sandbox_policy"]["config_override"],mod.WINDOWS_SANDBOX_OVERRIDE)
            x=json.loads(p.read_text()); x["windows_sandbox_policy"]["danger_full_access"]=True; p.write_text(json.dumps(x))
            with self.assertRaises(ValueError): mod.load_amendment(p)

if __name__=="__main__": unittest.main()
