import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ndv_batch_qualify_codex_subscription as mod


class BatchQualificationTests(unittest.TestCase):
    def fake_result(self, model, status="S0_READY", version="codex-cli 0.153.0"):
        cid = {
            "gpt-5.6-luna":"CODEX-PLUS-GPT-5.6-LUNA",
            "gpt-5.6-terra":"CODEX-PLUS-GPT-5.6-TERRA",
            "gpt-5.6-sol":"CODEX-PLUS-GPT-5.6-SOL",
        }[model]
        return {"qualification":{"status":status,"candidate_id":cid,"codex_version_raw":version},"binding":{} if status!="S0_READY" else {"x":1},"manifest":{} if status!="S0_READY" else {"x":1}}

    @mock.patch.object(mod.qualifier, "qualify")
    @mock.patch.object(mod.qualifier, "require_interface")
    def test_all_models_run_once_in_frozen_order(self, req, qual):
        req.return_value=("codex-cli 0.153.0",set())
        qual.side_effect=lambda exe,model,out,program,timeout:self.fake_result(model)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"batch"; receipt=mod.batch(Path("codex.exe"),root,Path("program.json"),600)
            self.assertEqual(receipt["status"],"ALL_SYNTHETIC_QUALIFICATIONS_READY")
            self.assertEqual([c.args[1] for c in qual.call_args_list],list(mod.ORDER))
            self.assertEqual(qual.call_count,3)

    @mock.patch.object(mod.qualifier, "qualify")
    @mock.patch.object(mod.qualifier, "require_interface")
    def test_stops_on_first_non_ready_without_retry(self, req, qual):
        req.return_value=("codex-cli 0.153.0",set())
        def side(exe,model,out,program,timeout):
            return self.fake_result(model,"S0_EXECUTOR_BLOCKED" if model=="gpt-5.6-terra" else "S0_READY")
        qual.side_effect=side
        with tempfile.TemporaryDirectory() as tmp:
            receipt=mod.batch(Path("codex.exe"),Path(tmp)/"batch",Path("program.json"),600)
            self.assertEqual(receipt["status"],"QUALIFICATION_BLOCKED")
            self.assertEqual(receipt["blocked_on_model"],"gpt-5.6-terra")
            self.assertEqual(qual.call_count,2)

    @mock.patch.object(mod.qualifier, "qualify")
    @mock.patch.object(mod.qualifier, "require_interface")
    def test_version_drift_blocks(self, req, qual):
        req.return_value=("codex-cli 0.153.0",set())
        qual.return_value=self.fake_result("gpt-5.6-luna",version="codex-cli 0.154.0")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"version drift"):
                mod.batch(Path("codex.exe"),Path(tmp)/"batch",Path("program.json"),600)

    def probe_fixture(self, root: Path):
        exe=root/"codex.exe"; exe.write_bytes(b"x")
        program=root/"program.json"; program.write_text("{}")
        probe=root/"probe.json"
        probe.write_text(json.dumps({
            "schema_id":mod.PROBE_SCHEMA,"status":"DISCOVERY_COMPLETE","program_file_sha256":mod.sha_file(program),
            "surfaces":{"codex":{"status":"DISCOVERED","executable_path":str(exe),"noninteractive_exec_discovered":True,"model_flag_discovered":True,"sandbox_flag_discovered":True}},
            "task_exposure":False,"treatment_execution":"NOT_EXECUTED","holdout_access":"NONE"
        }))
        return exe,program,probe

    def test_resolves_codex_from_valid_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);exe,program,probe=self.probe_fixture(root)
            observed,binding=mod.resolve_codex_exe(codex_exe=None,probe=probe,program=program)
            self.assertEqual(observed,exe.resolve());self.assertEqual(binding["probe_file_sha256"],mod.sha_file(probe))

    def test_probe_program_hash_mismatch_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,program,probe=self.probe_fixture(root);program.write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError,"program hash mismatch"):
                mod.resolve_codex_exe(codex_exe=None,probe=probe,program=program)

    def test_probe_missing_executable_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);exe,program,probe=self.probe_fixture(root);exe.unlink()
            with self.assertRaisesRegex(ValueError,"no longer present"):
                mod.resolve_codex_exe(codex_exe=None,probe=probe,program=program)


if __name__=="__main__": unittest.main()
