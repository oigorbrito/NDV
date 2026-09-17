#!/usr/bin/env python3
"""Qualify one pinned Codex/ChatGPT subscription model on a synthetic git mutation.

No development or holdout task is exposed. The qualifier removes API-key routing
from the child environment, pins one model explicitly, permits exactly one
synthetic mutation attempt, captures the diff, and emits a binding only when the
requested model is observed and the repository mutation is exact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROGRAM = Path("experiments/p1/wp07-executor-role-qualification-v1.json")
ALLOWED = {
    "gpt-5.6-sol": ("CODEX-PLUS-GPT-5.6-SOL", ["PRIMARY_STRONG", "ESCALATION_STRONG"]),
    "gpt-5.6-luna": ("CODEX-PLUS-GPT-5.6-LUNA", ["PRIMARY_ECONOMIC"]),
    "gpt-5.6-terra": ("CODEX-PLUS-GPT-5.6-TERRA", ["PRIMARY_ECONOMIC", "FAMILY_POLICY_CANDIDATE"]),
}
TASK = "Change TARGET.txt so its complete contents are exactly AFTER followed by one newline. Do not create or modify any other tracked file."


def sha_bytes(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def sha_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for c in iter(lambda:fh.read(1024*1024),b""): h.update(c)
    return h.hexdigest()
def run(argv:list[str], cwd:Path|None=None, env:dict[str,str]|None=None, timeout:int=120)->subprocess.CompletedProcess[str]:
    return subprocess.run(argv,cwd=cwd,env=env,capture_output=True,text=True,check=False,timeout=timeout)
def text(p:subprocess.CompletedProcess[str])->str: return (p.stdout or "")+("\n[stderr]\n"+(p.stderr or "") if p.stderr else "")

def parse_version(raw:str)->tuple[int,int,int]|None:
    m=re.search(r"(?:codex(?:-cli)?\s+)?(\d+)\.(\d+)\.(\d+)",raw,re.I)
    return tuple(map(int,m.groups())) if m else None

def observed_models(raw:str)->set[str]:
    out=set(re.findall(r"gpt-5\.6-(?:sol|terra|luna)",raw,re.I))
    for line in raw.splitlines():
        try: obj=json.loads(line)
        except Exception: continue
        stack=[obj]
        while stack:
            x=stack.pop()
            if isinstance(x,dict):
                for k,v in x.items():
                    if k.lower()=="model" and isinstance(v,str) and v.lower().startswith("gpt-5.6-"): out.add(v.lower())
                    else: stack.append(v)
            elif isinstance(x,list): stack.extend(x)
    return {x.lower() for x in out}

def load_program(path:Path)->dict[str,Any]:
    p=json.loads(path.read_text(encoding="utf-8"))
    if p.get("schema_id")!="ndv-p1-wp07-executor-role-qualification-v1" or p.get("status")!="PROSPECTIVE_FROZEN_NOT_EXECUTED": raise ValueError("qualification program invalid")
    if p.get("treatment_execution")!="NOT_EXECUTED" or p.get("holdout_access")!="NONE": raise ValueError("qualification program contamination")
    return p

def require_interface(codex:Path)->tuple[str,set[str]]:
    ver=run([str(codex),"--version"],timeout=30); raw=text(ver); parsed=parse_version(raw)
    if ver.returncode!=0 or parsed is None: raise ValueError(f"Codex version unavailable: {raw[-500:]}")
    if parsed < (0,144,0): raise ValueError(f"Codex >=0.144.0 required for GPT-5.6; observed {parsed}")
    help_p=run([str(codex),"exec","--help"],timeout=30); help_text=text(help_p)
    if help_p.returncode!=0: raise ValueError("codex exec --help failed")
    required={"--model","--sandbox","--json","--ephemeral","--ignore-user-config","--ignore-rules","--strict-config","--disable"}
    missing={flag for flag in required if flag not in help_text}
    if missing: raise ValueError(f"Codex exec interface missing required fail-closed flags: {sorted(missing)}")
    return raw.strip(), required

def init_repo(root:Path)->None:
    (root/"TARGET.txt").write_text("BEFORE\n",encoding="utf-8")
    for argv in (["git","init"],["git","config","user.email","ndv@example.invalid"],["git","config","user.name","NDV Synthetic Qualifier"],["git","add","TARGET.txt"],["git","commit","-m","baseline"]):
        p=run(list(argv),root,timeout=30)
        if p.returncode!=0: raise ValueError(f"synthetic git setup failed: {text(p)[-500:]}")
def validate_diff(root:Path)->tuple[bool,str,bytes]:
    target=(root/"TARGET.txt").read_bytes() if (root/"TARGET.txt").is_file() else b""
    diff=run(["git","diff","--binary"],root,timeout=30).stdout.encode("utf-8")
    names=run(["git","status","--porcelain"],root,timeout=30).stdout.splitlines()
    exact=target==b"AFTER\n" and bool(names) and all(line[3:].replace("\\","/")=="TARGET.txt" for line in names)
    return exact,"\n".join(names),diff

def qualify(codex:Path,model:str,out_dir:Path,program_path:Path,timeout:int)->dict[str,Any]:
    if model not in ALLOWED: raise ValueError(f"model not preregistered: {model}")
    program=load_program(program_path.resolve()); version_raw,_=require_interface(codex.resolve())
    candidate_id,roles=ALLOWED[model]
    out_dir=out_dir.resolve()
    if out_dir.exists(): raise ValueError(f"out-dir exists; refusing overwrite: {out_dir}")
    out_dir.mkdir(parents=True); evidence=out_dir/"evidence"; evidence.mkdir()
    with tempfile.TemporaryDirectory(prefix="ndv-codex-qual-") as tmp:
        repo=Path(tmp); init_repo(repo)
        env=os.environ.copy()
        for key in ("OPENAI_API_KEY","OPENAI_ADMIN_KEY","OPENAI_BASE_URL","OPENAI_ORG_ID","OPENAI_PROJECT_ID","OPENAI_CUSTOM_HEADERS"):
            env.pop(key,None)
        argv=[str(codex.resolve()),"exec","--model",model,"--json","--ephemeral","--ignore-user-config","--ignore-rules","--strict-config","--sandbox","workspace-write","--disable","apps","--disable","plugins",TASK]
        started=datetime.now(timezone.utc).isoformat(); t0=time.monotonic()
        try:
            proc=run(argv,repo,env,timeout); timed_out=False
        except subprocess.TimeoutExpired as exc:
            proc=subprocess.CompletedProcess(exc.cmd,124,stdout=exc.stdout or "",stderr=exc.stderr or ""); timed_out=True
        wall=time.monotonic()-t0; raw=text(proc); (evidence/"executor.log").write_text(raw,encoding="utf-8")
        exact,status,diff=validate_diff(repo); (evidence/"candidate.diff").write_bytes(diff); (evidence/"git-status.txt").write_text(status+"\n",encoding="utf-8")
    models=observed_models(raw); observed_exact=models=={model}
    if timed_out: state="S0_RESOURCE_LIMIT"
    elif proc.returncode!=0: state="S0_EXECUTOR_BLOCKED"
    elif not observed_exact: state="S0_IDENTITY_UNRESOLVED"
    elif not exact: state="S0_MUTATION_FAILED"
    else: state="S0_READY"
    qualification={
        "schema_id":"ndv-p1-wp07-codex-subscription-qualification-v1","status":state,"candidate_id":candidate_id,"requested_model":model,"observed_models":sorted(models),"exact_model_observed":observed_exact,"candidate_roles":roles,"surface_class":"SUBSCRIPTION_EXECUTOR_PINNED","codex_executable":str(codex.resolve()),"codex_version_raw":version_raw,"auth_path":"CHATGPT_SUBSCRIPTION_FORCED_BY_REMOVING_API_KEY_ENV","api_key_env_removed":True,"task":"SYNTHETIC_MUTATION_ONLY","task_exposure":False,"development_task_exposure":False,"holdout_access":"NONE","retry_count":0,"escalation_count":0,"executor":{"returncode":proc.returncode,"timed_out":timed_out,"wall_seconds":wall},"mutation":{"exact":exact,"candidate_diff_sha256":sha_bytes(diff),"candidate_diff_bytes":len(diff)},"program_ref":str(program_path.resolve()),"program_file_sha256":sha_file(program_path.resolve()),"started_at":started,"completed_at":datetime.now(timezone.utc).isoformat(),"treatment_execution":"NOT_EXECUTED"
    }
    qpath=out_dir/"qualification.json"; qpath.write_text(json.dumps(qualification,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    binding=None
    if state=="S0_READY":
        seed=json.dumps({"candidate":candidate_id,"model":model,"codex":version_raw,"qualification":sha_file(qpath)},sort_keys=True).encode()
        binding={"schema_id":"ndv-p1-wp07-executor-binding-v1","status":"QUALIFIED","binding_id":"WP07-CODEX-"+hashlib.sha256(seed).hexdigest()[:16],"candidate_id":candidate_id,"provider":"OpenAI","surface_class":"SUBSCRIPTION_EXECUTOR_PINNED","exact_executor_identity":f"codex({version_raw})+{model}","scaffold":{"name":"codex","version":version_raw,"executable_path":str(codex.resolve()),"invocation_mode":"exec noninteractive synthetic-qualified"},"model":{"identity":model,"selection":"EXPLICIT_PINNED"},"auth_path":"CHATGPT_SUBSCRIPTION","api_key_routing_forbidden":True,"dynamic_routing":False,"implicit_fallback":False,"retry_limit":0,"escalation_limit":0,"qualification_ref":"qualification.json","qualification_file_sha256":sha_file(qpath),"program_ref":str(program_path.resolve()),"program_file_sha256":sha_file(program_path.resolve()),"candidate_roles":roles,"treatment_execution":"NOT_EXECUTED","holdout_access":"NONE"}
        (out_dir/"executor-binding.json").write_text(json.dumps(binding,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return {"qualification":qualification,"binding":binding}

def main()->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument("--codex-exe",required=True,type=Path); ap.add_argument("--model",required=True,choices=sorted(ALLOWED)); ap.add_argument("--out-dir",required=True,type=Path); ap.add_argument("--program",type=Path,default=PROGRAM); ap.add_argument("--timeout",type=int,default=600); args=ap.parse_args()
    try: result=qualify(args.codex_exe,args.model,args.out_dir,args.program,args.timeout)
    except (OSError,ValueError,json.JSONDecodeError) as exc: print(json.dumps({"status":"FAIL","reason":"CODEX_SUBSCRIPTION_QUALIFICATION_BLOCKED","detail":str(exc)},indent=2)); return 2
    q=result["qualification"]; print(json.dumps({"status":q["status"],"candidate_id":q["candidate_id"],"model":q["requested_model"],"binding":str(args.out_dir/"executor-binding.json") if result["binding"] else None},indent=2)); return 0 if q["status"]=="S0_READY" else 2
if __name__=="__main__": raise SystemExit(main())
