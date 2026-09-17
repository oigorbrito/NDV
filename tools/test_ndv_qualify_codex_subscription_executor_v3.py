import json, tempfile, unittest
from pathlib import Path
import ndv_qualify_codex_subscription_executor_v3 as mod


class QualifierV3Tests(unittest.TestCase):
    def amendment(self):
        return {
            "schema_id":"ndv-p1-wp07-codex-qualification-amendment-v3",
            "status":"PROSPECTIVE_AMENDMENT_FROZEN_NOT_EXECUTED",
            "historical_v1_v2_evidence_reinterpretation":"FORBIDDEN",
            "development_task_exposure":False,
            "holdout_access":"NONE",
            "treatment_execution":"NOT_EXECUTED",
            "identity_policy":{"required_cli_version_exact":"0.154.0"},
            "environment_failure_markers":["writing is blocked by read-only sandbox","blocked by policy"],
            "upstream_provenance":{"release_commit":"6b9826e3aa83b1a5947db50f4332cb9c65f1b340"},
        }

    def test_invocation_adds_exact_workspace_root_before_prompt(self):
        with tempfile.TemporaryDirectory() as td:
            repo=Path(td).resolve()
            surface={"mode":"exec","fixed_flags":["--json","--sandbox","workspace-write"],"task_delivery":"FINAL_POSITIONAL_PROMPT"}
            argv=mod.invocation_v3(Path("codex.exe"),"gpt-5.6-luna","TASK",surface,repo)
            self.assertEqual(argv[-1],"TASK")
            i=argv.index("--add-dir")
            self.assertEqual(Path(argv[i+1]),repo)
            self.assertEqual(argv.count("--add-dir"),1)

    def test_environment_block_markers_are_distinct_from_model_failure(self):
        a=self.amendment()
        self.assertTrue(mod.environment_blocked("patch rejected: writing is blocked by read-only sandbox; rejected by user approval settings",a))
        self.assertTrue(mod.environment_blocked("command rejected: blocked by policy",a))
        self.assertFalse(mod.environment_blocked("agent returned without changing TARGET.txt",a))

    def test_amendment_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"a.json"; p.write_text(json.dumps(self.amendment()))
            self.assertEqual(mod.load_amendment(p)["historical_v1_v2_evidence_reinterpretation"],"FORBIDDEN")
            x=json.loads(p.read_text()); x["historical_v1_v2_evidence_reinterpretation"]="ALLOWED"; p.write_text(json.dumps(x))
            with self.assertRaises(ValueError): mod.load_amendment(p)

if __name__=="__main__": unittest.main()
