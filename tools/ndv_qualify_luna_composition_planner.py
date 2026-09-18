#!/usr/bin/env python3
"""Qualify Luna v4 as a non-mutating structured planner on a synthetic task.

This is a synthetic role qualification only. It exposes no development or holdout task
and does not authorize the Luna-only composition comparison.
"""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ndv_qualify_codex_subscription_executor as v1
import ndv_qualify_codex_subscription_executor_v4 as v4
import ndv_compile_luna_composition_prompt as comp
import ndv_parse_codex_jsonl_usage as usage_parser
from ndv_wp07_codex_bundle import verify_bundle

MODEL="gpt-5.6-luna"
CANDIDATE="CODEX-PLUS-GPT-5.6-LUNA"
PROMPTS=Path("experiments/luna-only/luna-composition-prompts-v1.json")
TASK_ID="SYNTHETIC-LUNA-PLANNER-01"
TASK=("Change ALPHA.txt so its complete contents are exactly ALPHA_AFTER followed by one newline, "
      "and change BETA.txt so its complete contents are exactly BETA_AFTER followed by one newline. "
      "Do not create, delete, rename, or modify any other tracked file.")

def sha_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def git(root:Path,*args:str)->subprocess.CompletedProcess[str]:
    return v1.run(["git",*args],root,timeout=30)

def init_repo(root:Path)->None:
    (root/"ALPHA.txt").write_text("ALPHA_BEFORE\n",encoding="utf-8")
    (root/"BETA.txt").write_text("BETA_BEFORE\n",encoding="utf-8")
    for args in (("init",),("config","user.email","ndv@example.invalid"),("config","user.name","NDV Synthetic Planner"),("add","ALPHA.txt","BETA.txt"),("commit","-m","baseline")):
        p=git(root,*args)
        if p.returncode!=0: raise ValueError(f"synthetic git setup failed: {v1.text(p)[-500:]}")

def extract_plan(stdout:str, task_id:str)->dict[str,Any]:
    valid=[]
    for lineno,line in enumerate(stdout.splitlines(),1):
        if not line.strip(): continue
        try:event=json.loads(line)
        except json.JSONDecodeError as exc: raise ValueError(f"malformed Codex JSONL at line {lineno}: {exc.msg}") from exc
        if event.get("type")!="item.completed": continue
        item=event.get("item")
        if not isinstance(item,dict) or item.get("type")!="agent_message": continue
        text=item.get("text")
        if not isinstance(text,str): continue
        try:candidate=json.loads(text.strip())
        except json.JSONDecodeError: continue
        if not isinstance(candidate,dict): continue
        try:comp.validate_plan(candidate,task_id)
        except ValueError: continue
        valid.append(candidate)
    if len(valid)!=1: raise ValueError(f"expected exactly one valid structured plan agent message; observed {len(valid)}")
    return valid[0]

def resolve_surface(q:dict[str,Any], artifact_root:Path)->Path:
    raw=q.get("execution_surface_ref")
    p=Path(raw) if isinstance(raw,str) else Path()
    if not p.is_absolute(): p=artifact_root/p
    p=p.resolve()
    if not p.is_file():
        fallback=(artifact_root/"experiments/p1/wp07-codex-execution-surface-v1.json").resolve()
        if not fallback.is_file(): raise ValueError("execution surface bytes unavailable")
        p=fallback
    if sha_file(p)!=q.get("execution_surface_file_sha256"): raise ValueError("execution surface hash mismatch")
    return p

def qualify(luna_dir:Path,out_dir:Path,artifact_root:Path,timeout:int)->dict[str,Any]:
    luna_dir=luna_dir.resolve(); out_dir=out_dir.resolve(); artifact_root=artifact_root.resolve()
    if out_dir.exists(): raise ValueError(f"out-dir exists; refusing overwrite: {out_dir}")
    sealed=verify_bundle(luna_dir,expected_model=MODEL,expected_candidate=CANDIDATE)
    q,b=sealed["qualification"],sealed["binding"]
    if q.get("schema_id")!="ndv-p1-wp07-codex-subscription-qualification-v4" or q.get("status")!="S0_READY": raise ValueError("Luna v4 S0_READY bundle required")
    if (q.get("identity_assurance") or {}).get("status")!="CLI_PINNED_SOURCE_VERIFIED" or b.get("identity_assurance")!="CLI_PINNED_SOURCE_VERIFIED": raise ValueError("Luna identity assurance invalid")
    if q.get("windows_sandbox_backend_requested")!="unelevated" or b.get("windows_sandbox_backend")!="UNELEVATED": raise ValueError("Luna v4 Windows sandbox backend invalid")
    surface_path=resolve_surface(q,artifact_root); surface=v1.load_surface(surface_path)
    codex=Path((b.get("scaffold") or {}).get("executable_path","")).resolve()
    if not codex.is_file(): raise ValueError(f"Codex executable unavailable: {codex}")
    version_raw,_=v1.require_interface(codex,surface)
    if "0.154.0" not in version_raw: raise ValueError(f"planner qualification requires Codex 0.154.0; observed {version_raw}")

    prompts_path=(artifact_root/PROMPTS).resolve()
    prompts=json.loads(prompts_path.read_text(encoding="utf-8"))
    prompt=comp.compile_prompt("PLANNER",TASK_ID,TASK,prompts)
    out_dir.mkdir(parents=True); evidence=out_dir/"evidence"; evidence.mkdir(); workspace=out_dir/"synthetic-workspace"; workspace.mkdir()
    init_repo(workspace)
    env=os.environ.copy()
    for key in surface["environment_variables_removed"]: env.pop(key,None)
    argv=v4.invocation_v4(codex,MODEL,prompt,surface,workspace)
    started=datetime.now(timezone.utc).isoformat(); t0=time.monotonic()
    try:
        proc=v1.run(argv,workspace,env,timeout); timed_out=False
    except subprocess.TimeoutExpired as exc:
        proc=subprocess.CompletedProcess(exc.cmd,124,stdout=exc.stdout or "",stderr=exc.stderr or ""); timed_out=True
    wall=time.monotonic()-t0
    stdout=proc.stdout or ""; stderr=proc.stderr or ""
    (evidence/"executor.jsonl").write_text(stdout,encoding="utf-8"); (evidence/"stderr.txt").write_text(stderr,encoding="utf-8")
    status=git(workspace,"status","--porcelain").stdout
    diff=git(workspace,"diff","--binary").stdout
    (evidence/"git-status.txt").write_text(status,encoding="utf-8"); (evidence/"candidate.diff").write_text(diff,encoding="utf-8")
    usage=None
    try: usage=usage_parser.parse_lines(stdout)
    except ValueError: usage={"status":"INVALID"}
    (evidence/"usage.json").write_text(json.dumps(usage,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    plan=None; plan_error=None
    try: plan=extract_plan(stdout,TASK_ID)
    except ValueError as exc: plan_error=str(exc)
    if plan is not None: (out_dir/"plan.json").write_text(json.dumps(plan,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
    workspace_clean=(status.strip()=="")
    if timed_out: state="S0_RESOURCE_LIMIT"
    elif proc.returncode!=0: state="S0_EXECUTOR_BLOCKED"
    elif not workspace_clean: state="S0_PLANNER_MUTATED_WORKSPACE"
    elif plan is None: state="S0_PLAN_INVALID"
    elif usage.get("status")!="AUTHORITATIVE": state="S0_USAGE_INVALID"
    else: state="S0_READY"
    result={
      "schema_id":"ndv-luna-only-planner-qualification-v1","status":state,"candidate_id":CANDIDATE,"model":MODEL,
      "source_binding_id":b.get("binding_id"),"source_binding_file_sha256":sha_file(luna_dir/"executor-binding.json"),
      "source_evidence_manifest_sha256":sha_file(luna_dir/"evidence-manifest.json"),
      "execution_surface_file_sha256":sha_file(surface_path),"prompt_contract_file_sha256":sha_file(prompts_path),
      "task":"SYNTHETIC_PLANNING_ONLY","task_id":TASK_ID,"development_task_exposure":False,"holdout_access":"NONE",
      "treatment_execution":"NOT_EXECUTED","retry_count":0,"escalation_count":0,
      "executor":{"returncode":proc.returncode,"timed_out":timed_out,"wall_seconds":wall},
      "workspace_clean":workspace_clean,"plan_valid":plan is not None,"plan_error":plan_error,
      "plan_file_sha256":sha_file(out_dir/"plan.json") if plan is not None else None,
      "usage":usage,"started_at":started,"completed_at":datetime.now(timezone.utc).isoformat()
    }
    (out_dir/"qualification.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return result

def main()->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument("--luna-dir",required=True,type=Path); ap.add_argument("--out-dir",required=True,type=Path); ap.add_argument("--artifact-root",type=Path,default=Path(".")); ap.add_argument("--timeout",type=int,default=600); a=ap.parse_args()
    try:r=qualify(a.luna_dir,a.out_dir,a.artifact_root,a.timeout)
    except (OSError,ValueError,json.JSONDecodeError) as exc:
        print(json.dumps({"status":"FAIL","reason":"LUNA_PLANNER_QUALIFICATION_BLOCKED","detail":str(exc)},indent=2)); return 2
    print(json.dumps({"status":r["status"],"model":r["model"],"workspace_clean":r["workspace_clean"],"plan_valid":r["plan_valid"],"usage_status":(r.get("usage") or {}).get("status"),"out_dir":str(a.out_dir)},indent=2))
    return 0 if r["status"]=="S0_READY" else 2

if __name__=="__main__": raise SystemExit(main())
