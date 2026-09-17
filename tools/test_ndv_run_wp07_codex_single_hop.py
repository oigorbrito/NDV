import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ndv_run_wp07_codex_single_hop as mod


class CodexSingleHopRunnerTests(unittest.TestCase):
    def preflight_value(self):
        return {
            "status":"CODEX_RUN_SPEC_PREFLIGHT_PASS",
            "run_id":"R1",
            "treatment_id":"B1",
            "binding_id":"B-LUNA",
            "model":"gpt-5.6-luna",
            "execution_surface_ref":"surface.json",
            "execution_surface_file_sha256":"a"*64,
            "budget_contract_ref":"budgets.json",
            "budget_contract_file_sha256":"b"*64,
            "executor_timeout_ms":1800000,
            "run_timeout_ms":5400000,
            "retry_limit":0,
            "escalation_limit":0,
            "argv_template":["codex.exe","exec","--model","gpt-5.6-luna","--json","<FROZEN_TASK_PROMPT>"],
            "environment_variables_to_remove":["OPENAI_API_KEY"],
        }

    def compiled_value(self):
        prompt="Fix it.\n"
        import hashlib
        return {
            "run_id":"R1","task_id":"C1","shaping":"S0_RAW_TASK",
            "prompt":prompt,"prompt_sha256":hashlib.sha256(prompt.encode()).hexdigest(),
            "executor_visible_sha256":"c"*64,"task_statement_sha256":"d"*64,
        }

    def workspace_value(self, root: Path):
        ws=root/"workspace"; ws.mkdir()
        return {"workspace":ws,"manifest":{"run_id":"R1","base_revision":"e"*40}}

    def source_files(self, root: Path):
        spec=root/"spec.json"; spec.write_text(json.dumps({"schema_id":"ndv-p1-s2-run-spec-v1"}))
        wm=root/"workspace-manifest.json"; wm.write_text(json.dumps({"schema_id":"ndv-p1-wp07-codex-workspace-v1"}))
        return spec,wm

    @mock.patch.object(mod,"compile_prompt")
    @mock.patch.object(mod,"preflight")
    def test_wrong_execute_token_blocks_before_preflight_or_prompt(self,pre_mock,compile_mock):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); spec,wm=self.source_files(root)
            with self.assertRaisesRegex(ValueError,"execution token"):
                mod.execute(spec,wm,root,root/"out","WRONG")
            pre_mock.assert_not_called(); compile_mock.assert_not_called()

    @mock.patch.object(mod,"run")
    @mock.patch.object(mod,"capture_candidate_diff")
    @mock.patch.object(mod,"verify_workspace_manifest")
    @mock.patch.object(mod,"compile_prompt")
    @mock.patch.object(mod,"preflight")
    def test_candidate_is_pending_verification_and_usage_retained(self,pre_mock,compile_mock,ws_mock,diff_mock,run_mock):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); spec,wm=self.source_files(root)
            pre_mock.return_value=self.preflight_value(); compile_mock.return_value=self.compiled_value(); ws_mock.return_value=self.workspace_value(root)
            diff_mock.return_value=(" M file.py\n",b"diff --git a/file.py b/file.py\n")
            run_mock.return_value=subprocess.CompletedProcess([],0,stdout='{"type":"turn.completed","usage":{"input_tokens":10,"cached_input_tokens":2,"cache_write_input_tokens":1,"output_tokens":5,"reasoning_output_tokens":3}}\n',stderr="")
            with mock.patch.dict(mod.os.environ,{"OPENAI_API_KEY":"secret"},clear=False):
                report=mod.execute(spec,wm,root,root/"out",mod.EXECUTE_TOKEN)
            self.assertEqual(report["classification"]["stage_status"],"EXECUTOR_CANDIDATE_PRODUCED_PENDING_VERIFICATION")
            self.assertEqual(report["classification"]["verified_solved_task"],"PENDING_VERIFICATION")
            self.assertEqual(report["verification"]["focal"],"NOT_EXECUTED")
            self.assertEqual(report["accounting"]["total_system_tokens_component"],15)
            self.assertEqual(report["usage"]["usage"]["cached_input_tokens"],2)
            self.assertIn("OPENAI_API_KEY",report["execution"]["environment_variables_present_and_removed"])
            called_env=run_mock.call_args.kwargs["env"]
            self.assertNotIn("OPENAI_API_KEY",called_env)
            self.assertEqual(run_mock.call_args.kwargs["timeout"],1800.0)
            self.assertEqual(report["execution"]["argv_redacted"][-1],"<FROZEN_TASK_PROMPT>")

    @mock.patch.object(mod,"run")
    @mock.patch.object(mod,"capture_candidate_diff",return_value=("",b""))
    @mock.patch.object(mod,"verify_workspace_manifest")
    @mock.patch.object(mod,"compile_prompt")
    @mock.patch.object(mod,"preflight")
    def test_timeout_is_resource_limit_inconclusive(self,pre_mock,compile_mock,ws_mock,diff_mock,run_mock):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); spec,wm=self.source_files(root)
            pre_mock.return_value=self.preflight_value(); compile_mock.return_value=self.compiled_value(); ws_mock.return_value=self.workspace_value(root)
            run_mock.side_effect=subprocess.TimeoutExpired(cmd=["codex"],timeout=1800,output="",stderr="")
            report=mod.execute(spec,wm,root,root/"out",mod.EXECUTE_TOKEN)
            self.assertEqual(report["classification"]["failure_attribution"],"RESOURCE_LIMIT")
            self.assertEqual(report["classification"]["verified_solved_task"],"INCONCLUSIVE")
            self.assertIsNone(report["accounting"]["total_system_tokens_component"])

    @mock.patch.object(mod,"run")
    @mock.patch.object(mod,"capture_candidate_diff",return_value=("",b""))
    @mock.patch.object(mod,"verify_workspace_manifest")
    @mock.patch.object(mod,"compile_prompt")
    @mock.patch.object(mod,"preflight")
    def test_missing_turn_usage_is_inconclusive_not_zero(self,pre_mock,compile_mock,ws_mock,diff_mock,run_mock):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); spec,wm=self.source_files(root)
            pre_mock.return_value=self.preflight_value(); compile_mock.return_value=self.compiled_value(); ws_mock.return_value=self.workspace_value(root)
            run_mock.return_value=subprocess.CompletedProcess([],0,stdout='{"type":"thread.started","thread_id":"t1"}\n',stderr="")
            report=mod.execute(spec,wm,root,root/"out",mod.EXECUTE_TOKEN)
            self.assertEqual(report["classification"]["failure_attribution"],"INCONCLUSIVE_OTHER")
            self.assertIsNone(report["accounting"]["total_system_tokens_component"])
            self.assertFalse(report["accounting"]["missing_telemetry_is_zero"])

    def test_stage_classification_no_candidate_stays_pending_verification(self):
        usage={"status":"AUTHORITATIVE","turn_failed_count":0,"error_event_count":0}
        out=mod.stage_classification(timed_out=False,returncode=0,usage=usage,accounting_error=None,candidate_bytes=0)
        self.assertEqual(out["stage_status"],"EXECUTOR_NO_CANDIDATE_PENDING_VERIFICATION")
        self.assertEqual(out["escalation_trigger"],"MISSING_CANDIDATE_BEFORE_TIMEOUT")
        self.assertEqual(out["verified_solved_task"],"PENDING_VERIFICATION")

    def test_stage_classification_provider_event_is_inconclusive(self):
        usage={"status":"AUTHORITATIVE","turn_failed_count":1,"error_event_count":0}
        out=mod.stage_classification(timed_out=False,returncode=0,usage=usage,accounting_error=None,candidate_bytes=10)
        self.assertEqual(out["failure_attribution"],"PROVIDER_FAILURE")
        self.assertEqual(out["verified_solved_task"],"INCONCLUSIVE")


if __name__=="__main__":
    unittest.main()
