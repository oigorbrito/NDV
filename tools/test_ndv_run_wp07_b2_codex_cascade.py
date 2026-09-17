import json, tempfile, unittest
from pathlib import Path
from unittest import mock

import ndv_run_wp07_b2_codex_cascade as mod


class B2CascadeTests(unittest.TestCase):
    def stage(self, root: Path, *, diff_text="diff --git a/x b/x\n", pending=True, trigger=None, tokens=100, model="gpt-5.6-luna", role=mod.PRIMARY):
        d = root / ("p.diff" if role == mod.PRIMARY else "s.diff")
        d.write_text(diff_text, encoding="utf-8")
        return {
            "schema_id":"ndv-p1-wp07-codex-single-hop-run-v1",
            "run_id":"R1","task_id":"T1","treatment_id":"B2","hop_role":role,
            "binding_id":"B1" if role==mod.PRIMARY else "B2","model":model,
            "execution":{"returncode":0,"wall_seconds":1.0},
            "candidate":{"diff_ref":str(d),"diff_sha256":mod.sha_file(d),"diff_bytes":len(diff_text.encode())},
            "classification":{"stage_status":"EXECUTOR_CANDIDATE_PRODUCED_PENDING_VERIFICATION" if pending else "EXECUTOR_INCONCLUSIVE","pending_verification":pending,"verified_solved_task":"PENDING_VERIFICATION" if pending else "INCONCLUSIVE","failure_attribution":None if pending else "PROVIDER_FAILURE","escalation_trigger":trigger},
            "usage":{"status":"AUTHORITATIVE","total_system_tokens_component":tokens},
        }

    def frozen_contract(self, root: Path) -> Path:
        p=root/"contract.json"
        p.write_text(json.dumps({"schema_id":mod.B2_SCHEMA,"status":"PROSPECTIVE_FROZEN_NOT_EXECUTED","treatment_id":"B2","hops":[{"index":1,"role":mod.PRIMARY,"model":"gpt-5.6-luna"},{"index":2,"role":mod.STRONG,"model":"gpt-5.6-sol"}],"retry_limit_per_hop":0,"escalation_limit":1,"dynamic_routing":False,"manual_override":False,"treatment_results_consulted":False,"task_exposure":False,"treatment_execution":"NOT_EXECUTED","holdout_access":"NONE"}))
        return p

    def budget(self, root: Path) -> Path:
        p=root/"budget.json"
        p.write_text(json.dumps({"schema_id":"ndv-p1-wp07-execution-budgets-v1","status":"PROSPECTIVE_FROZEN_NOT_EXECUTED","executor_timeout_ms_per_hop":1800000,"verification_reserve_ms":1800000,"treatments":{"B2":{"run_timeout_ms":7200000,"retry_limit":0,"escalation_limit":1}},"treatment_results_consulted":False,"task_exposure":False,"treatment_execution":"NOT_EXECUTED","holdout_access":"NONE"}))
        return p

    def preflight_pair(self, budget: Path):
        common={"run_timeout_ms":7200000,"executor_timeout_ms":1800000,"budget_contract_ref":str(budget),"budget_contract_file_sha256":mod.sha_file(budget)}
        return [{**common,"candidate_id":"CODEX-PLUS-GPT-5.6-LUNA"},{**common,"candidate_id":"CODEX-PLUS-GPT-5.6-SOL"}]

    def test_primary_yes_stops_without_escalation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); stage=self.stage(root)
            v={"verified_solved_task":"YES","failure_attribution":None,"reason":"ok"}
            self.assertEqual(mod.escalation_from_primary(stage,v),{"action":"STOP_YES","trigger":None})

    def test_primary_no_escalates_on_focal_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); stage=self.stage(root)
            v={"verified_solved_task":"NO","failure_attribution":"PRODUCT_FAILURE","reason":"one or more frozen focal/preservation tests did not pass"}
            self.assertEqual(mod.escalation_from_primary(stage,v),{"action":"ESCALATE","trigger":"FOCAL_OR_PRESERVATION_FAILURE"})

    def test_inconclusive_verifier_without_trigger_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); stage=self.stage(root)
            v={"verified_solved_task":"INCONCLUSIVE","failure_attribution":"HARNESS_FAILURE","reason":"harness"}
            self.assertEqual(mod.escalation_from_primary(stage,v),{"action":"STOP_INCONCLUSIVE","trigger":None})

    def test_empty_candidate_escalates_directly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); stage=self.stage(root,diff_text="")
            self.assertEqual(mod.escalation_from_primary(stage,None),{"action":"ESCALATE","trigger":"MISSING_CANDIDATE_BEFORE_TIMEOUT"})

    def test_explicit_executor_blocker_escalates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); stage=self.stage(root,pending=False,trigger="EXPLICIT_EXECUTOR_BLOCKER")
            self.assertEqual(mod.escalation_from_primary(stage,None),{"action":"ESCALATE","trigger":"EXPLICIT_EXECUTOR_BLOCKER"})

    def test_handoff_is_compact_and_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); stage=self.stage(root)
            v={"verified_solved_task":"NO","decision_evidence":{"focal":[{"test":"a","observed":"FAILED"}],"preservation":[]}}
            h=mod.build_handoff("TASK\n",stage,v,"FOCAL_OR_PRESERVATION_FAILURE",12345)
            self.assertIn("NDV DETERMINISTIC ESCALATION HANDOFF",h["prompt"])
            self.assertIn("diff --git a/x b/x",h["prompt"])
            encoded=json.dumps(h["certificate"],sort_keys=True)
            for forbidden in ("transcript","chain_of_thought","hidden_reasoning","gold_patch","test_patch"):
                self.assertNotIn(forbidden,encoded)
            self.assertEqual(h["certificate"]["remaining_run_budget_ms"],12345)

    def test_missing_usage_is_not_zero(self):
        self.assertIsNone(mod.authoritative_tokens({"usage":{"status":"MISSING","total_system_tokens_component":0}}))
        self.assertEqual(mod.authoritative_tokens({"usage":{"status":"AUTHORITATIVE","total_system_tokens_component":321}}),321)

    @mock.patch.object(mod,"verify")
    @mock.patch.object(mod,"execute_hop")
    @mock.patch.object(mod,"materialize")
    @mock.patch.object(mod,"compile_prompt")
    @mock.patch.object(mod,"preflight_hop")
    def test_cascade_primary_yes_never_executes_sol(self, preflight, compile_prompt, materialize, execute_hop, verify):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); spec=root/"spec.json"; spec.write_text(json.dumps({"run_id":"R1","task":{"task_id":"T1"},"treatment":{"id":"B2"}}))
            contract=self.frozen_contract(root); budget=self.budget(root); preflight.side_effect=self.preflight_pair(budget)
            compile_prompt.return_value={"prompt":"TASK\n"}
            def mat(_spec,_root,out): out.mkdir(parents=True); (out/"workspace-manifest.json").write_text("{}")
            materialize.side_effect=mat
            primary=self.stage(root); execute_hop.return_value=primary
            verify.return_value={"verified_solved_task":"YES","failure_attribution":None,"verification":{"wall_seconds":1.0}}
            report=mod.cascade(spec,root,root,root/"out",contract,mod.EXECUTE_TOKEN,mod.VERIFY_TOKEN)
            self.assertEqual(report["verified_solved_task"],"YES")
            self.assertEqual(report["escalation_count"],0)
            self.assertEqual(report["accounting"]["verification_reserve_ms"],1800000)
            self.assertEqual(execute_hop.call_count,1)

    @mock.patch.object(mod,"verify")
    @mock.patch.object(mod,"execute_hop")
    @mock.patch.object(mod,"materialize")
    @mock.patch.object(mod,"compile_prompt")
    @mock.patch.object(mod,"preflight_hop")
    def test_cascade_verified_no_escalates_exactly_once_to_sol(self, preflight, compile_prompt, materialize, execute_hop, verify):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); spec=root/"spec.json"; spec.write_text(json.dumps({"run_id":"R1","task":{"task_id":"T1"},"treatment":{"id":"B2"}}))
            contract=self.frozen_contract(root); budget=self.budget(root); preflight.side_effect=self.preflight_pair(budget)
            compile_prompt.return_value={"prompt":"TASK\n"}
            def mat(_spec,_root,out): out.mkdir(parents=True); (out/"workspace-manifest.json").write_text("{}")
            materialize.side_effect=mat
            primary=self.stage(root,tokens=100); strong=self.stage(root,tokens=200,model="gpt-5.6-sol",role=mod.STRONG)
            execute_hop.side_effect=[primary,strong]
            verify.side_effect=[{"verified_solved_task":"NO","failure_attribution":"PRODUCT_FAILURE","reason":"one or more frozen focal/preservation tests did not pass","decision_evidence":{"focal":[],"preservation":[],"failures":[]},"verification":{"wall_seconds":1.0}},{"verified_solved_task":"YES","failure_attribution":None,"reason":"ok","verification":{"wall_seconds":1.0}}]
            report=mod.cascade(spec,root,root,root/"out",contract,mod.EXECUTE_TOKEN,mod.VERIFY_TOKEN)
            self.assertEqual(report["verified_solved_task"],"YES")
            self.assertEqual(report["escalation_count"],1)
            self.assertEqual(report["accounting"]["total_system_tokens"],300)
            self.assertTrue(report["accounting"]["complete_system_wall_accounting"])
            self.assertEqual(execute_hop.call_count,2)
            self.assertEqual(materialize.call_count,2)
            self.assertEqual(execute_hop.call_args_list[1].args[4],mod.STRONG)


if __name__=="__main__":unittest.main()
