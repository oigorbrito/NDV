#!/usr/bin/env python3
"""Validate frozen Luna-only composition contracts without model/task execution."""
from __future__ import annotations
import argparse, json
from pathlib import Path

PROTOCOL=Path("experiments/luna-only/luna-composition-protocol-v1.json")
SCHEMA=Path("experiments/luna-only/luna-decomposition-plan-schema-v1.json")
PROMPTS=Path("experiments/luna-only/luna-composition-prompts-v1.json")

def load(p:Path):
    return json.loads(p.read_text(encoding="utf-8"))

def validate(protocol:Path=PROTOCOL,schema:Path=SCHEMA,prompts:Path=PROMPTS)->dict:
    p,s,pr=load(protocol),load(schema),load(prompts)
    if p.get("schema_id")!="ndv-luna-only-composition-protocol-v1" or p.get("status")!="PROSPECTIVE_FROZEN_NOT_EXECUTED":
        raise ValueError("protocol schema/status invalid")
    fx=p.get("fixed_executor") or {}
    if fx.get("model")!="gpt-5.6-luna" or fx.get("candidate_id")!="CODEX-PLUS-GPT-5.6-LUNA":
        raise ValueError("fixed Luna executor drift")
    if fx.get("required_qualification_schema")!="ndv-p1-wp07-codex-subscription-qualification-v4" or fx.get("required_windows_sandbox_backend")!="UNELEVATED":
        raise ValueError("Luna v4 surface requirement drift")
    if fx.get("substitution_forbidden") is not True or fx.get("other_models_forbidden") is not True:
        raise ValueError("executor substitution must remain forbidden")
    treatments=p.get("treatments") or {}
    if set(treatments)!={"D0","D1","D2"}:
        raise ValueError("treatment set drift")
    for tid in treatments:
        t=treatments[tid]
        if t.get("retry_limit")!=0 or t.get("repair_limit")!=0:
            raise ValueError(f"{tid}: retry/repair drift")
    ctr=p.get("controls") or {}
    for key in ["same_task_across_treatments","same_luna_binding_across_treatments","same_exact_base_across_treatments","same_final_verifier_across_treatments","same_executor_budget_per_invocation","all_planning_cost_counted","all_failed_invocation_cost_counted"]:
        if ctr.get(key) is not True: raise ValueError(f"control drift: {key}")
    for key in ["dynamic_model_routing","model_escalation","parallel_agents"]:
        if ctr.get(key) is not False: raise ValueError(f"forbidden control enabled: {key}")
    if p.get("treatment_execution")!="NOT_EXECUTED" or p.get("holdout_access")!="NONE":
        raise ValueError("protocol contaminated")
    if s.get("$id")!="ndv-luna-decomposition-plan-schema-v1" or s.get("additionalProperties") is not False:
        raise ValueError("plan schema invalid")
    steps=((s.get("properties") or {}).get("steps") or {})
    if steps.get("minItems")!=1 or steps.get("maxItems")!=8:
        raise ValueError("plan step bounds drift")
    if pr.get("schema_id")!="ndv-luna-only-composition-prompts-v1" or pr.get("status")!="PROSPECTIVE_FROZEN_NOT_EXECUTED":
        raise ValueError("prompt contract invalid")
    if (pr.get("planner") or {}).get("mutation_policy")!="ANY_TRACKED_OR_UNTRACKED_WORKSPACE_MUTATION_INVALIDATES_PLAN":
        raise ValueError("planner mutation policy drift")
    if (pr.get("template_substitution") or {}).get("deterministic") is not True or (pr.get("template_substitution") or {}).get("llm_rewriting") is not False:
        raise ValueError("prompt compilation must stay deterministic")
    if pr.get("treatment_execution")!="NOT_EXECUTED" or pr.get("holdout_access")!="NONE":
        raise ValueError("prompt contract contaminated")
    return {"status":"LUNA_ONLY_COMPOSITION_CONTRACTS_VALID","treatment_execution":"NOT_EXECUTED","holdout_access":"NONE"}

def main()->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--protocol",type=Path,default=PROTOCOL); ap.add_argument("--schema",type=Path,default=SCHEMA); ap.add_argument("--prompts",type=Path,default=PROMPTS)
    a=ap.parse_args()
    try:r=validate(a.protocol,a.schema,a.prompts)
    except (OSError,ValueError,json.JSONDecodeError) as e:
        print(json.dumps({"status":"FAIL","reason":"LUNA_ONLY_COMPOSITION_CONTRACT_INVALID","detail":str(e)},indent=2)); return 2
    print(json.dumps(r,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
