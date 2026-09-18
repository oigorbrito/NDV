import json, tempfile, unittest
from pathlib import Path
import ndv_compile_luna_composition_prompt as c
import ndv_validate_luna_only_composition_contracts as v
import ndv_qualify_luna_composition_planner as pq

class LunaCompositionTests(unittest.TestCase):
    def test_contracts_validate(self):
        out=v.validate(Path("../experiments/luna-only/luna-composition-protocol-v1.json"),Path("../experiments/luna-only/luna-decomposition-plan-schema-v1.json"),Path("../experiments/luna-only/luna-composition-prompts-v1.json"))
        self.assertEqual(out["status"],"LUNA_ONLY_COMPOSITION_CONTRACTS_VALID")
    def plan(self):
        return {"schema_id":"ndv-luna-decomposition-plan-v1","task_id":"T1","objective":"Do task","constraints":["preserve behavior"],"steps":[
            {"id":"S1","objective":"Inspect and change target","dependencies":[],"expected_artifact":"candidate change","verification":"inspect diff"},
            {"id":"S2","objective":"Integrate","dependencies":["S1"],"expected_artifact":"integrated candidate","verification":"run focused check"}],
            "final_verification":"run frozen verifier"}
    def prompts(self):
        return json.loads(Path("../experiments/luna-only/luna-composition-prompts-v1.json").read_text())
    def test_plan_and_modes_compile(self):
        p=self.plan(); c.validate_plan(p,"T1")
        for mode in ("D0","PLANNER","D1"):
            text=c.compile_prompt(mode,"T1","fix x",self.prompts(),p if mode=="D1" else None)
            self.assertIn("fix x",text)
        text=c.compile_prompt("D2","T1","fix x",self.prompts(),p,"S2")
        self.assertIn('"id":"S2"',text)
    def test_future_dependency_blocked(self):
        p=self.plan(); p["steps"][0]["dependencies"]=["S2"]
        with self.assertRaisesRegex(ValueError,"earlier steps"): c.validate_plan(p,"T1")
    def test_extra_field_blocked(self):
        p=self.plan(); p["reasoning"]="secret"
        with self.assertRaisesRegex(ValueError,"fields"): c.validate_plan(p,"T1")
    def test_wrong_task_blocked(self):
        with self.assertRaisesRegex(ValueError,"task_id mismatch"): c.validate_plan(self.plan(),"OTHER")
    def test_planner_jsonl_extracts_exactly_one_plan(self):
        p=self.plan()
        events="\n".join([
            json.dumps({"type":"thread.started","thread_id":"t"}),
            json.dumps({"type":"item.completed","item":{"type":"agent_message","text":"inspecting repository"}}),
            json.dumps({"type":"item.completed","item":{"type":"agent_message","text":json.dumps(p)}}),
            json.dumps({"type":"turn.completed","usage":{"input_tokens":1,"cached_input_tokens":0,"cache_write_input_tokens":0,"output_tokens":1,"reasoning_output_tokens":0}})
        ])
        self.assertEqual(pq.extract_plan(events,"T1")["task_id"],"T1")
    def test_planner_multiple_valid_plans_blocked(self):
        p=self.plan(); msg=json.dumps({"type":"item.completed","item":{"type":"agent_message","text":json.dumps(p)}})
        with self.assertRaisesRegex(ValueError,"exactly one"): pq.extract_plan(msg+"\n"+msg,"T1")
    def test_planner_markdown_plan_not_accepted(self):
        p=self.plan(); msg=json.dumps({"type":"item.completed","item":{"type":"agent_message","text":"```json\n"+json.dumps(p)+"\n```"}})
        with self.assertRaisesRegex(ValueError,"observed 0"): pq.extract_plan(msg,"T1")

if __name__=="__main__": unittest.main()
