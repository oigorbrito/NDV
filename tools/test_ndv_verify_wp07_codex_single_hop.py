import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ndv_verify_wp07_codex_single_hop as mod


class CodexSingleHopVerificationTests(unittest.TestCase):
    def test_evaluate_yes_requires_all_focal_and_preservation_pass(self):
        focal={"tests":["t::focal"]}; preservation={"tests":["t::keep"]}
        out=mod.evaluate({"t::focal":"PASSED","t::keep":"PASSED"},focal,preservation)
        self.assertEqual(out["outcome"],"YES")
        self.assertIsNone(out["failure_attribution"])

    def test_evaluate_executable_failure_is_product_no(self):
        focal={"tests":["t::focal"]}; preservation={"tests":["t::keep"]}
        out=mod.evaluate({"t::focal":"FAILED","t::keep":"PASSED"},focal,preservation)
        self.assertEqual(out["outcome"],"NO")
        self.assertEqual(out["failure_attribution"],"PRODUCT_FAILURE")

    def test_evaluate_missing_frozen_test_is_inconclusive(self):
        focal={"tests":["t::focal"]}; preservation={"tests":["t::keep"]}
        out=mod.evaluate({"t::focal":"PASSED"},focal,preservation)
        self.assertEqual(out["outcome"],"INCONCLUSIVE")
        self.assertEqual(out["failure_attribution"],"INCONCLUSIVE_OTHER")

    def test_evaluate_empty_parser_is_inconclusive(self):
        out=mod.evaluate({}, {"tests":["t::focal"]}, {"tests":[]})
        self.assertEqual(out["outcome"],"INCONCLUSIVE")

    def test_parse_markers_requires_all_commands(self):
        raw="__NDV_HEAD__="+"b"*40+"\n__NDV_CLEAN__=YES\n__NDV_APPLY_RC__=0\n__NDV_CMD_1_RC__=0\n"
        m=mod.parse_markers(raw,2)
        self.assertFalse(m["all_command_markers_present"])
        self.assertEqual(m["command_returncodes"],[0,None])

    def test_build_script_is_network_agnostic_and_records_apply_and_each_rc(self):
        script=mod.build_script("b"*40,["pytest -q","python -m unittest"])
        self.assertIn("git apply --check",script)
        self.assertIn("__NDV_APPLY_RC__",script)
        self.assertIn("__NDV_CMD_1_RC__",script)
        self.assertIn("__NDV_CMD_2_RC__",script)

    def test_verifier_timeout_uses_frozen_reserve_not_full_remaining_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            contract=root/"budgets.json"
            contract.write_text(json.dumps({
                "schema_id":"ndv-p1-wp07-execution-budgets-v1",
                "status":"PROSPECTIVE_FROZEN_NOT_EXECUTED",
                "executor_timeout_ms_per_hop":1800000,
                "verification_reserve_ms":1800000,
                "treatments":{"B1":{"run_timeout_ms":5400000,"retry_limit":0,"escalation_limit":0}}
            }))
            spec={"treatment":{"id":"B1"},"budgets":{"executor_timeout_ms":1800000,"run_timeout_ms":5400000,"retry_limit":0,"escalation_limit":0,"budget_contract_ref":str(contract),"budget_contract_file_sha256":mod.sha_file(contract)}}
            self.assertEqual(mod.verifier_timeout_seconds(spec,root),1800.0)

    def test_budget_hash_tamper_blocks_verifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); contract=root/"budgets.json"; contract.write_text("{}")
            spec={"treatment":{"id":"B1"},"budgets":{"executor_timeout_ms":1,"run_timeout_ms":2,"retry_limit":0,"escalation_limit":0,"budget_contract_ref":str(contract),"budget_contract_file_sha256":"0"*64}}
            with self.assertRaisesRegex(ValueError,"budget contract hash mismatch"):
                mod.verifier_timeout_seconds(spec,root)

    @mock.patch.object(mod,"verify_sources")
    def test_wrong_verify_token_blocks_before_source_access(self,source_mock):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaisesRegex(ValueError,"verification token"):
                mod.verify(root/"executor.json",root,root,root/"out","WRONG")
            source_mock.assert_not_called()

    @mock.patch.object(mod,"execute_candidate")
    @mock.patch.object(mod,"import_parser")
    @mock.patch.object(mod,"verify_upstream")
    @mock.patch.object(mod,"verifier_timeout_seconds",return_value=1800.0)
    @mock.patch.object(mod,"verify_sources")
    def test_verify_harness_failure_is_inconclusive(self,source_mock,timeout_mock,upstream_mock,parser_mock,exec_mock):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); diff=root/"candidate.diff"; diff.write_bytes(b"diff\n"); er=root/"executor.json"; er.write_text("{}")
            run_spec=root/"spec.json"; run_spec.write_text("{}")
            base_run=root/"base.json"; base_run.write_text("{}")
            focal=root/"focal.json"; focal.write_text("{}")
            preservation=root/"pres.json"; preservation.write_text("{}")
            src={
                "report":{"run_id":"R1","task_id":"C1","treatment_id":"B1","accounting":{},"usage":{}},
                "spec":{"task":{"base_sha":"b"*40},"budgets":{}},"run_spec_path":run_spec,"diff":diff,
                "base":{"test_commands":["pytest"],"image_digest":"repo@sha256:"+"d"*64,"workdir":"/repo"},"base_run_path":base_run,
                "focal":{"parser":{"revision":"rev","content_sha256":"hash","name":"pytest"},"tests":["t"]},"focal_path":focal,
                "preservation":{"parser":{"revision":"rev","content_sha256":"hash","name":"pytest"},"tests":[]},"preservation_path":preservation,
            }
            source_mock.return_value=src; upstream_mock.return_value={"revision":"rev","log_parsers_sha256":"hash"}; parser_mock.return_value=lambda s:{"t":"PASSED"}
            exec_mock.return_value={"returncode":90,"timed_out":False,"duration_seconds":1.0,"stdout":"","stderr":"","markers":{"head":None,"clean":None,"apply_rc":None,"all_command_markers_present":False,"command_returncodes":[None]},"script_sha256":"x"}
            report=mod.verify(er,root,root,root/"out",mod.VERIFY_TOKEN)
            self.assertEqual(report["verified_solved_task"],"INCONCLUSIVE")
            self.assertEqual(report["failure_attribution"],"HARNESS_FAILURE")

    @mock.patch.object(mod,"execute_candidate")
    @mock.patch.object(mod,"import_parser")
    @mock.patch.object(mod,"verify_upstream")
    @mock.patch.object(mod,"verifier_timeout_seconds",return_value=1800.0)
    @mock.patch.object(mod,"verify_sources")
    def test_apply_failure_on_exact_clean_base_is_product_no(self,source_mock,timeout_mock,upstream_mock,parser_mock,exec_mock):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); diff=root/"candidate.diff"; diff.write_bytes(b"bad\n"); er=root/"executor.json"; er.write_text("{}")
            run_spec=root/"spec.json"; run_spec.write_text("{}")
            base_run=root/"base.json"; base_run.write_text("{}")
            focal=root/"focal.json"; focal.write_text("{}")
            preservation=root/"pres.json"; preservation.write_text("{}")
            parser_meta={"revision":"rev","content_sha256":"hash","name":"pytest"}
            source_mock.return_value={"report":{"run_id":"R1","task_id":"C1","treatment_id":"B1","accounting":{},"usage":{}},"spec":{"task":{"base_sha":"b"*40},"budgets":{}},"run_spec_path":run_spec,"diff":diff,"base":{"test_commands":["pytest"],"image_digest":"repo@sha256:"+"d"*64,"workdir":"/repo"},"base_run_path":base_run,"focal":{"parser":parser_meta,"tests":["t"]},"focal_path":focal,"preservation":{"parser":parser_meta,"tests":[]},"preservation_path":preservation}
            upstream_mock.return_value={"revision":"rev","log_parsers_sha256":"hash"}; parser_mock.return_value=lambda s:{}
            exec_mock.return_value={"returncode":92,"timed_out":False,"duration_seconds":1.0,"stdout":"","stderr":"","markers":{"head":"b"*40,"clean":True,"apply_rc":1,"all_command_markers_present":False,"command_returncodes":[None]},"script_sha256":"x"}
            report=mod.verify(er,root,root,root/"out",mod.VERIFY_TOKEN)
            self.assertEqual(report["verified_solved_task"],"NO")
            self.assertEqual(report["failure_attribution"],"PRODUCT_FAILURE")

if __name__=="__main__":
    unittest.main()
