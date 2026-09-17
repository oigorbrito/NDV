import json, tempfile, unittest
from pathlib import Path
import ndv_qualify_codex_subscription_executor_v2 as mod

class QualifierV2Tests(unittest.TestCase):
    def amendment(self):
        return {"identity_policy":{"required_cli_version_exact":"0.154.0"},"upstream_provenance":{"release_commit":"6b9826e3aa83b1a5947db50f4332cb9c65f1b340"}}
    def test_identity_accepts_exact_0154_pin(self):
        argv=["codex.exe","exec","--model","gpt-5.6-luna","--json","task"]
        r=mod.identity_assurance("codex-cli 0.154.0",argv,"gpt-5.6-luna",self.amendment())
        self.assertEqual(r["status"],"CLI_PINNED_SOURCE_VERIFIED")
        self.assertEqual(r["runtime_model_echo"],"UNAVAILABLE_BY_VERSION_MATCHED_UPSTREAM_SCHEMA")
    def test_identity_rejects_version_drift(self):
        argv=["codex.exe","exec","--model","gpt-5.6-luna","task"]
        r=mod.identity_assurance("codex-cli 0.155.0",argv,"gpt-5.6-luna",self.amendment())
        self.assertEqual(r["status"],"IDENTITY_UNRESOLVED")
    def test_identity_rejects_wrong_model_argument(self):
        argv=["codex.exe","exec","--model","gpt-5.6-sol","task"]
        r=mod.identity_assurance("codex-cli 0.154.0",argv,"gpt-5.6-luna",self.amendment())
        self.assertEqual(r["status"],"IDENTITY_UNRESOLVED")
    def test_amendment_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"a.json"
            p.write_text(json.dumps({"schema_id":"ndv-p1-wp07-codex-qualification-amendment-v2","status":"PROSPECTIVE_AMENDMENT_FROZEN_NOT_EXECUTED","historical_v1_evidence_reinterpretation":"FORBIDDEN","development_task_exposure":False,"holdout_access":"NONE","treatment_execution":"NOT_EXECUTED"}))
            self.assertEqual(mod.load_amendment(p)["historical_v1_evidence_reinterpretation"],"FORBIDDEN")
            x=json.loads(p.read_text());x["historical_v1_evidence_reinterpretation"]="ALLOWED";p.write_text(json.dumps(x))
            with self.assertRaises(ValueError):mod.load_amendment(p)

if __name__=="__main__":unittest.main()
