#!/usr/bin/env python3
"""Deterministically compile Luna-only composition prompts and validate plan artifacts."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any

PROMPTS=Path("experiments/luna-only/luna-composition-prompts-v1.json")

def load(path:Path)->Any:
    return json.loads(path.read_text(encoding="utf-8"))

def validate_plan(plan:dict[str,Any], task_id:str)->None:
    allowed={"schema_id","task_id","objective","constraints","steps","final_verification"}
    if set(plan)!=allowed: raise ValueError("plan fields must match frozen schema exactly")
    if plan.get("schema_id")!="ndv-luna-decomposition-plan-v1": raise ValueError("plan schema_id invalid")
    if plan.get("task_id")!=task_id: raise ValueError("plan task_id mismatch")
    if not isinstance(plan.get("objective"),str) or not plan["objective"].strip(): raise ValueError("plan objective missing")
    constraints=plan.get("constraints")
    if not isinstance(constraints,list) or len(constraints)>16 or any(not isinstance(x,str) or not x.strip() for x in constraints): raise ValueError("plan constraints invalid")
    steps=plan.get("steps")
    if not isinstance(steps,list) or not (1<=len(steps)<=8): raise ValueError("plan steps invalid")
    seen=[]
    for i,step in enumerate(steps,1):
        if not isinstance(step,dict) or set(step)!={"id","objective","dependencies","expected_artifact","verification"}: raise ValueError(f"step {i}: fields invalid")
        sid=f"S{i}"
        if step.get("id")!=sid: raise ValueError(f"step {i}: ids must be contiguous S1..Sn")
        for field in ("objective","expected_artifact","verification"):
            if not isinstance(step.get(field),str) or not step[field].strip(): raise ValueError(f"{sid}: {field} invalid")
        deps=step.get("dependencies")
        if not isinstance(deps,list) or len(deps)>7 or any(d not in seen for d in deps) or len(set(deps))!=len(deps): raise ValueError(f"{sid}: dependencies must reference unique earlier steps")
        seen.append(sid)
    if not isinstance(plan.get("final_verification"),str) or not plan["final_verification"].strip(): raise ValueError("final_verification invalid")

def render(lines:list[str], values:dict[str,str])->str:
    out="\n".join(lines)+"\n"
    for k,v in values.items(): out=out.replace("{{"+k+"}}",v)
    leftovers=[x for x in ("{{TASK}}","{{TASK_ID}}","{{PLAN_JSON}}","{{STEP_JSON}}") if x in out]
    if leftovers: raise ValueError(f"unresolved placeholders: {leftovers}")
    return out

def compile_prompt(mode:str, task_id:str, task:str, prompts:dict[str,Any], plan:dict[str,Any]|None=None, step_id:str|None=None)->str:
    if mode=="D0":
        return render(prompts["D0_executor"]["template"],{"TASK":task})
    if mode=="PLANNER":
        return render(prompts["planner"]["template"],{"TASK_ID":task_id,"TASK":task})
    if plan is None: raise ValueError(f"{mode}: plan required")
    validate_plan(plan,task_id)
    plan_json=json.dumps(plan,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    if mode=="D1":
        return render(prompts["D1_executor"]["template"],{"TASK":task,"PLAN_JSON":plan_json})
    if mode=="D2":
        if not step_id: raise ValueError("D2: --step-id required")
        matches=[s for s in plan["steps"] if s["id"]==step_id]
        if len(matches)!=1: raise ValueError("D2: step id not in plan")
        step_json=json.dumps(matches[0],sort_keys=True,separators=(",",":"),ensure_ascii=False)
        return render(prompts["D2_step_executor"]["template"],{"TASK":task,"PLAN_JSON":plan_json,"STEP_JSON":step_json})
    raise ValueError(f"unsupported mode: {mode}")

def main()->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode",required=True,choices=["D0","PLANNER","D1","D2"])
    ap.add_argument("--task-id",required=True); ap.add_argument("--task-file",required=True,type=Path)
    ap.add_argument("--plan",type=Path); ap.add_argument("--step-id"); ap.add_argument("--prompts",type=Path,default=PROMPTS); ap.add_argument("--out",required=True,type=Path)
    a=ap.parse_args()
    try:
        if a.out.exists(): raise ValueError(f"refusing overwrite: {a.out}")
        task=a.task_file.read_text(encoding="utf-8")
        prompts=load(a.prompts)
        if prompts.get("schema_id")!="ndv-luna-only-composition-prompts-v1": raise ValueError("prompt contract invalid")
        plan=load(a.plan) if a.plan else None
        rendered=compile_prompt(a.mode,a.task_id,task,prompts,plan,a.step_id)
        a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(rendered,encoding="utf-8")
    except (OSError,ValueError,json.JSONDecodeError) as e:
        print(json.dumps({"status":"FAIL","reason":"LUNA_COMPOSITION_PROMPT_COMPILE_BLOCKED","detail":str(e)},indent=2)); return 2
    print(json.dumps({"status":"PROMPT_COMPILED","mode":a.mode,"out":str(a.out),"task_id":a.task_id},indent=2)); return 0

if __name__=="__main__": raise SystemExit(main())
