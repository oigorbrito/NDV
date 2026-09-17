#!/usr/bin/env python3
"""Prospective Codex subscription qualifier v2 after a v1 harness/interface defect.

V2 never reinterprets historical v1 evidence. It uses a persistent synthetic
workspace under the output directory and a version-matched, source-verified CLI
model pin for Codex 0.154.0 because exec JSONL does not wire-echo model identity.
No P1 development or holdout task is exposed.
"""
from __future__ import annotations

import argparse, hashlib, json, os, shutil, subprocess, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ndv_qualify_codex_subscription_executor as v1
from ndv_wp07_codex_bundle import seal_bundle

AMENDMENT = Path("experiments/p1/wp07-codex-qualification-amendment-v2.json")


def sha_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for c in iter(lambda:fh.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def load(path:Path)->dict[str,Any]:return json.loads(path.read_text(encoding="utf-8"))
def parse_exact_version(raw:str)->str|None:
    parsed=v1.parse_version(raw)
    return ".".join(map(str,parsed)) if parsed else None

def load_amendment(path:Path)->dict[str,Any]:
    x=load(path.resolve())
    if x.get("schema_id")!="ndv-p1-wp07-codex-qualification-amendment-v2" or x.get("status")!="PROSPECTIVE_AMENDMENT_FROZEN_NOT_EXECUTED":raise ValueError("qualification amendment v2 invalid")
    if x.get("historical_v1_evidence_reinterpretation")!="FORBIDDEN" or x.get("development_task_exposure") is not False or x.get("holdout_access")!="NONE" or x.get("treatment_execution")!="NOT_EXECUTED":raise ValueError("qualification amendment v2 contaminated")
    return x

def identity_assurance(version_raw:str,argv:list[str],model:str,amendment:dict[str,Any])->dict[str,Any]:
    exact=parse_exact_version(version_raw);required=(amendment.get("identity_policy") or {}).get("required_cli_version_exact")
    try:i=argv.index("--model");pinned=i+1<len(argv) and argv[i+1]==model
    except ValueError:pinned=False
    accepted=exact==required and pinned
    return {"status":"CLI_PINNED_SOURCE_VERIFIED" if accepted else "IDENTITY_UNRESOLVED","cli_version_exact":exact,"required_cli_version_exact":required,"requested_model":model,"model_argument_exact":pinned,"runtime_model_echo":"UNAVAILABLE_BY_VERSION_MATCHED_UPSTREAM_SCHEMA","upstream_release_commit":((amendment.get("upstream_provenance") or {}).get("release_commit"))}

def qualify(codex:Path,model:str,out_dir:Path,program_path:Path,timeout:int,surface_path:Path=v1.SURFACE,amendment_path:Path=AMENDMENT)->dict[str,Any]:
    if model not in v1.ALLOWED:raise ValueError(f"model not preregistered: {model}")
    out_dir=out_dir.resolve()
    if out_dir.exists():raise ValueError(f"out-dir exists; refusing overwrite: {out_dir}")
    program_path=program_path.resolve();surface_path=surface_path.resolve();amendment_path=amendment_path.resolve()
    v1.load_program(program_path);surface=v1.load_surface(surface_path);amendment=load_amendment(amendment_path)
    version_raw,_=v1.require_interface(codex.resolve(),surface);candidate_id,roles=v1.ALLOWED[model]
    out_dir.mkdir(parents=True);evidence=out_dir/"evidence";evidence.mkdir();repo=out_dir/"synthetic-workspace";repo.mkdir()
    v1.init_repo(repo)
    env=os.environ.copy()
    for key in surface["environment_variables_removed"]:env.pop(key,None)
    argv=v1.invocation(codex,model,v1.TASK,surface)
    identity=identity_assurance(version_raw,argv,model,amendment)
    started=datetime.now(timezone.utc).isoformat();t0=time.monotonic()
    try:proc=v1.run(argv,repo,env,timeout);timed_out=False
    except subprocess.TimeoutExpired as exc:proc=subprocess.CompletedProcess(exc.cmd,124,stdout=exc.stdout or "",stderr=exc.stderr or "");timed_out=True
    wall=time.monotonic()-t0;raw=v1.text(proc);(evidence/"executor.log").write_text(raw,encoding="utf-8")
    exact,status,diff=v1.validate_diff(repo);(evidence/"candidate.diff").write_bytes(diff);(evidence/"git-status.txt").write_text(status+"\n",encoding="utf-8")
    if timed_out:state="S0_RESOURCE_LIMIT"
    elif proc.returncode!=0:state="S0_EXECUTOR_BLOCKED"
    elif identity["status"]!="CLI_PINNED_SOURCE_VERIFIED":state="S0_IDENTITY_UNRESOLVED"
    elif not exact:state="S0_MUTATION_FAILED"
    else:state="S0_READY"
    q={"schema_id":"ndv-p1-wp07-codex-subscription-qualification-v2","status":state,"qualification_cohort":"V2","candidate_id":candidate_id,"requested_model":model,"identity_assurance":identity,"candidate_roles":roles,"surface_class":"SUBSCRIPTION_EXECUTOR_PINNED","codex_executable":str(codex.resolve()),"codex_version_raw":version_raw,"auth_path":"CHATGPT_SUBSCRIPTION_FORCED_BY_REMOVING_API_KEY_ENV","api_key_env_removed":True,"execution_surface_ref":str(surface_path),"execution_surface_file_sha256":sha_file(surface_path),"amendment_ref":str(amendment_path),"amendment_file_sha256":sha_file(amendment_path),"synthetic_workspace_ref":str(repo),"task":"SYNTHETIC_MUTATION_ONLY","task_exposure":False,"development_task_exposure":False,"holdout_access":"NONE","retry_count":0,"escalation_count":0,"executor":{"returncode":proc.returncode,"timed_out":timed_out,"wall_seconds":wall},"mutation":{"exact":exact,"candidate_diff_sha256":hashlib.sha256(diff).hexdigest(),"candidate_diff_bytes":len(diff)},"program_ref":str(program_path),"program_file_sha256":sha_file(program_path),"started_at":started,"completed_at":datetime.now(timezone.utc).isoformat(),"treatment_execution":"NOT_EXECUTED"}
    qpath=out_dir/"qualification.json";qpath.write_text(json.dumps(q,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    binding=None;manifest=None
    if state=="S0_READY":
        seed=json.dumps({"candidate":candidate_id,"model":model,"codex":version_raw,"qualification":sha_file(qpath),"amendment":sha_file(amendment_path),"execution_surface":sha_file(surface_path)},sort_keys=True).encode()
        binding={"schema_id":"ndv-p1-wp07-executor-binding-v2","status":"QUALIFIED","binding_id":"WP07-CODEX-V2-"+hashlib.sha256(seed).hexdigest()[:16],"candidate_id":candidate_id,"provider":"OpenAI","surface_class":"SUBSCRIPTION_EXECUTOR_PINNED","exact_executor_identity":f"codex({version_raw})+{model}","identity_assurance":"CLI_PINNED_SOURCE_VERIFIED","runtime_model_echo":"UNAVAILABLE_BY_VERSION_MATCHED_UPSTREAM_SCHEMA","scaffold":{"name":"codex","version":version_raw,"executable_path":str(codex.resolve()),"invocation_mode":"exec noninteractive frozen-surface-qualified-v2"},"model":{"identity":model,"selection":"EXPLICIT_PINNED"},"auth_path":"CHATGPT_SUBSCRIPTION","api_key_routing_forbidden":True,"dynamic_routing":False,"implicit_fallback":False,"retry_limit":0,"escalation_limit":0,"qualification_ref":"qualification.json","qualification_file_sha256":sha_file(qpath),"program_ref":str(program_path),"program_file_sha256":sha_file(program_path),"execution_surface_ref":str(surface_path),"execution_surface_file_sha256":sha_file(surface_path),"amendment_ref":str(amendment_path),"amendment_file_sha256":sha_file(amendment_path),"candidate_roles":roles,"treatment_execution":"NOT_EXECUTED","holdout_access":"NONE"}
        (out_dir/"executor-binding.json").write_text(json.dumps(binding,indent=2,sort_keys=True)+"\n",encoding="utf-8");manifest=seal_bundle(out_dir)
    return {"qualification":q,"binding":binding,"manifest":manifest}

def main()->int:
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("--codex-exe",required=True,type=Path);ap.add_argument("--model",required=True,choices=sorted(v1.ALLOWED));ap.add_argument("--out-dir",required=True,type=Path);ap.add_argument("--program",type=Path,default=v1.PROGRAM);ap.add_argument("--execution-surface",type=Path,default=v1.SURFACE);ap.add_argument("--amendment",type=Path,default=AMENDMENT);ap.add_argument("--timeout",type=int,default=600);args=ap.parse_args()
    try:r=qualify(args.codex_exe,args.model,args.out_dir,args.program,args.timeout,args.execution_surface,args.amendment)
    except (OSError,ValueError,json.JSONDecodeError) as exc:print(json.dumps({"status":"FAIL","reason":"CODEX_SUBSCRIPTION_QUALIFICATION_V2_BLOCKED","detail":str(exc)},indent=2));return 2
    q=r["qualification"];print(json.dumps({"status":q["status"],"candidate_id":q["candidate_id"],"model":q["requested_model"],"identity_assurance":q["identity_assurance"]["status"],"binding":str(args.out_dir/"executor-binding.json") if r["binding"] else None},indent=2));return 0 if q["status"]=="S0_READY" else 2
if __name__=="__main__":raise SystemExit(main())
