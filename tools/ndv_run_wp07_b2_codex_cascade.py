#!/usr/bin/env python3
"""Execute frozen WP-07 B2 Luna->Sol cascade with deterministic escalation.

The controller is inert without both explicit development execution and
verification tokens. It uses fresh immutable audited-base workspaces per hop,
never transfers transcript/hidden reasoning, verifies a non-empty Luna candidate
before deciding escalation, and permits exactly one Luna->Sol escalation.
"""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ndv_compile_wp07_codex_prompt import compile_prompt
from ndv_materialize_wp07_codex_workspace import materialize
from ndv_parse_codex_jsonl_usage import parse_lines
from ndv_preflight_wp07_codex_run_spec import preflight_hop
from ndv_run_wp07_codex_single_hop import (
    EXECUTE_TOKEN, capture_candidate_diff, run, sha_file, stage_classification,
    verify_workspace_manifest,
)
from ndv_verify_wp07_codex_single_hop import VERIFY_TOKEN, verify

B2_SCHEMA="ndv-p1-wp07-b2-codex-cascade-v1"
B2_CONTRACT_DEFAULT=Path("experiments/p1/wp07-b2-codex-cascade-v1.json")
PRIMARY="PRIMARY_ECONOMIC"; STRONG="ESCALATION_STRONG"

def utc_now()->str:return datetime.now(timezone.utc).isoformat()
def load(path:Path)->Any:return json.loads(path.read_text(encoding="utf-8"))
def canonical(v:Any)->bytes:return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
def sha_value(v:Any)->str:return hashlib.sha256(canonical(v)).hexdigest()

def validate_contract(path:Path)->dict[str,Any]:
    c=load(path.resolve())
    if c.get("schema_id")!=B2_SCHEMA or c.get("status")!="PROSPECTIVE_FROZEN_NOT_EXECUTED" or c.get("treatment_id")!="B2":raise ValueError("valid frozen B2 Codex cascade contract required")
    if c.get("treatment_results_consulted") is not False or c.get("task_exposure") is not False or c.get("treatment_execution")!="NOT_EXECUTED" or c.get("holdout_access")!="NONE":raise ValueError("B2 contract contamination")
    hops=c.get("hops") or []
    if [(x.get("index"),x.get("role"),x.get("model")) for x in hops]!=[(1,PRIMARY,"gpt-5.6-luna"),(2,STRONG,"gpt-5.6-sol")]:raise ValueError("B2 hop identity drift")
    if c.get("retry_limit_per_hop")!=0 or c.get("escalation_limit")!=1 or c.get("dynamic_routing") is not False or c.get("manual_override") is not False:raise ValueError("B2 control-policy drift")
    return c

def escalation_from_primary(stage:dict[str,Any],verification:dict[str,Any]|None)->dict[str,Any]:
    cls=stage.get("classification") or {};trigger=cls.get("escalation_trigger")
    if cls.get("pending_verification") is not True:
        if trigger in {"EXPLICIT_EXECUTOR_BLOCKER","STRUCTURALLY_INVALID_ARTIFACT","DETERMINISTIC_RESOURCE_CEILING"}:
            return {"action":"ESCALATE","trigger":trigger}
        return {"action":"STOP_INCONCLUSIVE","trigger":None}
    candidate=stage.get("candidate") or {}
    if candidate.get("diff_bytes")==0:
        return {"action":"ESCALATE","trigger":"MISSING_CANDIDATE_BEFORE_TIMEOUT"}
    if not isinstance(verification,dict):raise ValueError("non-empty primary candidate requires verification before B2 decision")
    outcome=verification.get("verified_solved_task")
    if outcome=="YES":return {"action":"STOP_YES","trigger":None}
    if outcome=="NO":
        reason=str(verification.get("reason") or "")
        trigger="STRUCTURALLY_INVALID_ARTIFACT" if "did not apply" in reason else "FOCAL_OR_PRESERVATION_FAILURE"
        return {"action":"ESCALATE","trigger":trigger}
    return {"action":"STOP_INCONCLUSIVE","trigger":None}

def compact_failure_observations(verification:dict[str,Any]|None)->dict[str,Any]|None:
    if not isinstance(verification,dict):return None
    ev=verification.get("decision_evidence") or {}
    out={}
    for key in ("focal","preservation","failures","missing"):
        if key in ev:out[key]=ev[key]
    return out or None

def build_handoff(base_prompt:str,stage:dict[str,Any],verification:dict[str,Any]|None,trigger:str,remaining_ms:int)->dict[str,Any]:
    candidate=stage.get("candidate") or {};diff_ref=candidate.get("diff_ref");diff_text=""
    if isinstance(diff_ref,str) and candidate.get("diff_bytes",0)>0:
        p=Path(diff_ref)
        if not p.is_file():raise ValueError("primary candidate diff missing while building handoff")
        if sha_file(p)!=candidate.get("diff_sha256"):raise ValueError("primary candidate diff hash mismatch while building handoff")
        diff_text=p.read_text(encoding="utf-8",errors="replace")
    cert={
        "task_identity":{"run_id":stage.get("run_id"),"task_id":stage.get("task_id")},
        "escalation_trigger":trigger,
        "first_hop_binding_id":stage.get("binding_id"),
        "first_hop_model":stage.get("model"),
        "first_hop_exit_code":((stage.get("execution") or {}).get("returncode")),
        "first_hop_stage_status":((stage.get("classification") or {}).get("stage_status")),
        "candidate_diff_sha256":candidate.get("diff_sha256"),
        "candidate_diff_bytes":candidate.get("diff_bytes"),
        "failed_verifier_outcome_when_available":verification.get("verified_solved_task") if isinstance(verification,dict) else None,
        "failed_focal_or_preservation_observations_when_available":compact_failure_observations(verification),
        "remaining_run_budget_ms":remaining_ms,
    }
    section=("\n\nNDV DETERMINISTIC ESCALATION HANDOFF\n"
             "The following state is machine-derived from the first frozen hop. Start from the fresh audited base in this workspace. Do not assume the first-hop patch is applied.\n"
             "Failure certificate (canonical JSON):\n"+canonical(cert).decode("utf-8")+"\n"
             "First-hop candidate diff (reference only; not pre-applied):\n"+(diff_text if diff_text else "<EMPTY_DIFF>\n"))
    return {"certificate":cert,"certificate_sha256":sha_value(cert),"diff_text_sha256":hashlib.sha256(diff_text.encode()).hexdigest(),"prompt":base_prompt.rstrip("\n")+section}

def authoritative_tokens(stage:dict[str,Any])->int|None:
    usage=stage.get("usage")
    if not isinstance(usage,dict) or usage.get("status")!="AUTHORITATIVE":return None
    value=usage.get("total_system_tokens_component")
    return value if isinstance(value,int) and value>=0 else None

def execute_hop(run_spec:Path,workspace_manifest:Path,artifact_root:Path,out_dir:Path,role:str,prompt:str,timeout_seconds:float)->dict[str,Any]:
    if out_dir.exists():raise ValueError(f"hop out-dir exists: {out_dir}")
    pre=preflight_hop(run_spec.resolve(),artifact_root.resolve(),role)
    ws=verify_workspace_manifest(workspace_manifest.resolve(),run_spec.resolve())
    out_dir.mkdir(parents=True);evidence=out_dir/"evidence";evidence.mkdir();prompt_path=evidence/"prompt.txt";prompt_path.write_text(prompt,encoding="utf-8")
    argv_template=list(pre["argv_template"])
    if not argv_template or argv_template[-1]!="<FROZEN_TASK_PROMPT>":raise ValueError("unsafe cascade argv template")
    argv=[*argv_template[:-1],prompt];env=os.environ.copy();removed=[]
    for key in pre.get("environment_variables_to_remove") or []:
        if key in env:removed.append(key);env.pop(key,None)
    started=utc_now();t0=time.monotonic()
    try:
        proc=run(argv,cwd=ws["workspace"],env=env,timeout=timeout_seconds);timed_out=False;stdout=proc.stdout or "";stderr=proc.stderr or "";rc=proc.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out=True;stdout=exc.stdout or "";stderr=exc.stderr or "";rc=124
        if isinstance(stdout,bytes):stdout=stdout.decode("utf-8",errors="replace")
        if isinstance(stderr,bytes):stderr=stderr.decode("utf-8",errors="replace")
        stderr+=f"\nNDV timeout after {timeout_seconds} seconds\n"
    wall=time.monotonic()-t0;completed=utc_now();stdout_path=evidence/"codex.stdout.jsonl";stderr_path=evidence/"codex.stderr.log";stdout_path.write_text(stdout,encoding="utf-8");stderr_path.write_text(stderr,encoding="utf-8")
    usage=None;accounting_error=None
    try:usage=parse_lines(stdout)
    except ValueError as exc:accounting_error=str(exc)
    usage_path=evidence/"usage.json";usage_path.write_text(json.dumps(usage if usage is not None else {"schema_id":"ndv-p1-wp07-codex-usage-v1","status":"INVALID","error":accounting_error,"missing_telemetry_is_zero":False},indent=2,sort_keys=True)+"\n",encoding="utf-8")
    status_text="";diff=b"";candidate_error=None
    try:status_text,diff=capture_candidate_diff(ws["workspace"],ws["manifest"]["base_revision"])
    except ValueError as exc:
        candidate_error=str(exc)
        if accounting_error is None:accounting_error="candidate artifact integrity failure: "+candidate_error
    status_path=evidence/"git-status.txt";diff_path=evidence/"candidate.diff";status_path.write_text(status_text,encoding="utf-8");diff_path.write_bytes(diff)
    classification=stage_classification(timed_out=timed_out,returncode=rc,usage=usage,accounting_error=accounting_error,candidate_bytes=len(diff))
    report={
        "schema_id":"ndv-p1-wp07-codex-single-hop-run-v1","run_id":pre["run_id"],"treatment_id":"B2","task_id":ws["manifest"]["task_id"],"hop_role":role,
        "binding_id":pre["binding_id"],"model":pre["model"],
        "execution":{"started_at":started,"completed_at":completed,"wall_seconds":wall,"returncode":rc,"timed_out":timed_out,"executor_timeout_ms":int(timeout_seconds*1000),"frozen_executor_timeout_ms":pre["executor_timeout_ms"],"run_timeout_ms":pre["run_timeout_ms"],"retry_count":0,"escalation_count":0 if role==PRIMARY else 1,"argv_redacted":[*argv_template[:-1],"<FROZEN_TASK_PROMPT>"],"environment_variables_present_and_removed":sorted(removed)},
        "prompt":{"ref":str(prompt_path),"sha256":sha_file(prompt_path),"bytes":prompt_path.stat().st_size,"exposed_to_executor":True},
        "candidate":{"diff_ref":str(diff_path),"diff_sha256":sha_file(diff_path),"diff_bytes":len(diff),"git_status_ref":str(status_path),"git_status_sha256":sha_file(status_path),"capture_error":candidate_error},
        "usage":usage,"usage_ref":str(usage_path),"usage_file_sha256":sha_file(usage_path),
        "raw_evidence":{"stdout_ref":str(stdout_path),"stdout_sha256":sha_file(stdout_path),"stderr_ref":str(stderr_path),"stderr_sha256":sha_file(stderr_path)},
        "classification":classification,"verification":{"focal":"NOT_EXECUTED","preservation":"NOT_EXECUTED","final_treatment_outcome":"PENDING_VERIFICATION" if classification.get("pending_verification") else "INCONCLUSIVE_AT_EXECUTOR_STAGE"},
        "accounting":{"failure_cost_retained":True,"inconclusive_cost_retained":True,"missing_telemetry_is_zero":False,"total_system_tokens_component":usage.get("total_system_tokens_component") if isinstance(usage,dict) else None},
        "source_chain":{"run_spec_ref":str(run_spec.resolve()),"run_spec_file_sha256":sha_file(run_spec.resolve()),"workspace_manifest_ref":str(workspace_manifest.resolve()),"workspace_manifest_file_sha256":sha_file(workspace_manifest.resolve()),"execution_surface_ref":pre["execution_surface_ref"],"execution_surface_file_sha256":pre["execution_surface_file_sha256"],"budget_contract_ref":pre["budget_contract_ref"],"budget_contract_file_sha256":pre["budget_contract_file_sha256"]},
        "treatment_execution":"EXECUTOR_STAGE_EXECUTED_ONCE","holdout_access":"NONE",
    }
    rp=out_dir/"executor-stage-report.json";rp.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8");return report

def cascade(run_spec:Path,artifact_root:Path,upstream_root:Path,out_dir:Path,contract_path:Path,execute_token:str,verify_token:str)->dict[str,Any]:
    if execute_token!=EXECUTE_TOKEN:raise ValueError("explicit frozen development execution token required")
    if verify_token!=VERIFY_TOKEN:raise ValueError("explicit frozen development verification token required")
    if out_dir.exists():raise ValueError(f"out-dir exists; refusing overwrite: {out_dir}")
    contract=validate_contract(contract_path);spec=load(run_spec.resolve())
    if ((spec.get("treatment") or {}).get("id"))!="B2":raise ValueError("B2 run-spec required")
    primary_pre=preflight_hop(run_spec.resolve(),artifact_root.resolve(),PRIMARY);strong_pre=preflight_hop(run_spec.resolve(),artifact_root.resolve(),STRONG)
    if primary_pre.get("candidate_id")!="CODEX-PLUS-GPT-5.6-LUNA" or strong_pre.get("candidate_id")!="CODEX-PLUS-GPT-5.6-SOL":raise ValueError("B2 binding identities differ from frozen cascade contract")
    compiled=compile_prompt(run_spec.resolve(),artifact_root.resolve());base_prompt=compiled["prompt"]
    run_budget_ms=primary_pre["run_timeout_ms"];reserve_ms=(primary_pre["executor_timeout_ms"]);consumed_ms=0
    out_dir.mkdir(parents=True);started=utc_now()
    pws_dir=out_dir/"hop1-workspace";materialize(run_spec.resolve(),artifact_root.resolve(),pws_dir);pws=pws_dir/"workspace-manifest.json"
    p_timeout=min(primary_pre["executor_timeout_ms"],run_budget_ms-consumed_ms)/1000.0
    primary=execute_hop(run_spec,pws,artifact_root,out_dir/"hop1-executor",PRIMARY,base_prompt,p_timeout);consumed_ms+=int((primary.get("execution") or {}).get("wall_seconds",0)*1000)
    primary_ver=None
    if (primary.get("classification") or {}).get("pending_verification") is True and (primary.get("candidate") or {}).get("diff_bytes",0)>0:
        if run_budget_ms-consumed_ms<reserve_ms:
            decision={"action":"STOP_INCONCLUSIVE","trigger":None};primary_ver={"verified_solved_task":"INCONCLUSIVE","failure_attribution":"RESOURCE_LIMIT","reason":"insufficient frozen run budget for first-hop verification"}
        else:
            primary_ver=verify((out_dir/"hop1-executor"/"executor-stage-report.json"),artifact_root,upstream_root,out_dir/"hop1-verification",verify_token);consumed_ms+=int((primary_ver.get("verification") or {}).get("wall_seconds",0)*1000);decision=escalation_from_primary(primary,primary_ver)
    else:decision=escalation_from_primary(primary,None)
    if decision["action"]=="STOP_YES":
        final="YES";failure=None;strong=None;strong_ver=None;handoff=None
    elif decision["action"]=="STOP_INCONCLUSIVE":
        final="INCONCLUSIVE";failure=(primary_ver or {}).get("failure_attribution") or (primary.get("classification") or {}).get("failure_attribution") or "INCONCLUSIVE_OTHER";strong=None;strong_ver=None;handoff=None
    else:
        remaining=run_budget_ms-consumed_ms
        if remaining<=reserve_ms:
            final="INCONCLUSIVE";failure="RESOURCE_LIMIT";strong=None;strong_ver=None;handoff=None
        else:
            handoff=build_handoff(base_prompt,primary,primary_ver,decision["trigger"],remaining);handoff_path=out_dir/"handoff.json";handoff_path.write_text(json.dumps({k:v for k,v in handoff.items() if k!="prompt"},indent=2,sort_keys=True)+"\n",encoding="utf-8")
            sws_dir=out_dir/"hop2-workspace";materialize(run_spec.resolve(),artifact_root.resolve(),sws_dir);sws=sws_dir/"workspace-manifest.json"
            strong_timeout=min(strong_pre["executor_timeout_ms"],max(0,remaining-reserve_ms))/1000.0
            if strong_timeout<=0:
                final="INCONCLUSIVE";failure="RESOURCE_LIMIT";strong=None;strong_ver=None
            else:
                strong=execute_hop(run_spec,sws,artifact_root,out_dir/"hop2-executor",STRONG,handoff["prompt"],strong_timeout);consumed_ms+=int((strong.get("execution") or {}).get("wall_seconds",0)*1000);remaining2=run_budget_ms-consumed_ms
                if (strong.get("classification") or {}).get("pending_verification") is not True:
                    final="INCONCLUSIVE";failure=(strong.get("classification") or {}).get("failure_attribution") or "INCONCLUSIVE_OTHER";strong_ver=None
                elif remaining2<=0:
                    final="INCONCLUSIVE";failure="RESOURCE_LIMIT";strong_ver=None
                else:
                    strong_ver=verify((out_dir/"hop2-executor"/"executor-stage-report.json"),artifact_root,upstream_root,out_dir/"hop2-verification",verify_token);consumed_ms+=int((strong_ver.get("verification") or {}).get("wall_seconds",0)*1000);final=strong_ver.get("verified_solved_task");failure=strong_ver.get("failure_attribution")
    tokens=[authoritative_tokens(x) for x in (primary,strong) if isinstance(x,dict)];all_authoritative=all(x is not None for x in tokens);total_tokens=sum(tokens) if all_authoritative else None
    if not all_authoritative:final="INCONCLUSIVE";failure=failure or "INCONCLUSIVE_OTHER"
    report={"schema_id":"ndv-p1-wp07-b2-cascade-run-v1","run_id":spec.get("run_id"),"task_id":((spec.get("task") or {}).get("task_id")),"treatment_id":"B2","started_at":started,"completed_at":utc_now(),"verified_solved_task":final,"failure_attribution":failure,"escalation_count":1 if isinstance(strong,dict) else 0,"retry_count":0,"decision_after_primary":decision,"primary_executor_ref":str(out_dir/"hop1-executor"/"executor-stage-report.json"),"primary_verification_ref":str(out_dir/"hop1-verification"/"verification-report.json") if primary_ver else None,"strong_executor_ref":str(out_dir/"hop2-executor"/"executor-stage-report.json") if isinstance(strong,dict) else None,"strong_verification_ref":str(out_dir/"hop2-verification"/"verification-report.json") if strong_ver else None,"handoff":{"certificate":handoff["certificate"],"certificate_sha256":handoff["certificate_sha256"],"diff_text_sha256":handoff["diff_text_sha256"]} if isinstance(handoff,dict) else None,"accounting":{"consumed_wall_ms":consumed_ms,"run_timeout_ms":run_budget_ms,"total_system_tokens":total_tokens,"all_consumed_hop_usage_authoritative":all_authoritative,"missing_telemetry_is_zero":False,"failure_cost_retained":True,"inconclusive_cost_retained":True},"source_chain":{"run_spec_ref":str(run_spec.resolve()),"run_spec_file_sha256":sha_file(run_spec.resolve()),"b2_contract_ref":str(contract_path.resolve()),"b2_contract_file_sha256":sha_file(contract_path.resolve())},"treatment_execution":"COMPLETE_B2_CASCADE","holdout_access":"NONE"}
    (out_dir/"cascade-report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8");return report

def main()->int:
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("--run-spec",required=True,type=Path);ap.add_argument("--artifact-root",type=Path,default=Path("."));ap.add_argument("--upstream-root",required=True,type=Path);ap.add_argument("--b2-contract",type=Path,default=B2_CONTRACT_DEFAULT);ap.add_argument("--out-dir",required=True,type=Path);ap.add_argument("--execute-token",required=True);ap.add_argument("--verify-token",required=True);args=ap.parse_args()
    try:r=cascade(args.run_spec,args.artifact_root,args.upstream_root,args.out_dir.resolve(),args.b2_contract,args.execute_token,args.verify_token)
    except (OSError,ValueError,json.JSONDecodeError,subprocess.SubprocessError) as exc:print(json.dumps({"status":"FAIL","reason":"B2_CODEX_CASCADE_BLOCKED","detail":str(exc)},indent=2));return 2
    print(json.dumps({"status":"B2_COMPLETE","run_id":r["run_id"],"verified_solved_task":r["verified_solved_task"],"failure_attribution":r["failure_attribution"],"escalation_count":r["escalation_count"],"total_system_tokens":r["accounting"]["total_system_tokens"]},indent=2));return 0 if r["verified_solved_task"] in {"YES","NO"} else 3
if __name__=="__main__":raise SystemExit(main())
