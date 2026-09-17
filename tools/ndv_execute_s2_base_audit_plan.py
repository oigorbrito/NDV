#!/usr/bin/env python3
"""Execute only image-bound S2 pre-solution base audits from a frozen plan.

This tool performs Docker base-audit execution only. It never calls a model,
never applies solution/test patches, never exposes tasks to a software executor,
and never accesses holdout material.
"""
from __future__ import annotations
import argparse, hashlib, json, subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def load(path: Path) -> Any: return json.loads(path.read_text(encoding="utf-8"))
def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024*1024), b""): h.update(chunk)
    return h.hexdigest()
def require_file(path: Path, label: str) -> Path:
    p=path.resolve()
    if not p.is_file(): raise ValueError(f"{label} not found: {p}")
    return p

def validate_plan(plan_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    plan_path=require_file(plan_path,"base-audit execution plan"); plan=load(plan_path)
    if not isinstance(plan,dict) or plan.get("schema_id")!="ndv-p1-s2-base-audit-execution-plan-v1": raise ValueError("image-bound execution plan v1 required")
    if plan.get("status")!="AUDIT_EXECUTION_PLAN_READY": raise ValueError("execution plan is not ready")
    if plan.get("docker_execution") is not False or plan.get("model_execution")!="NONE" or plan.get("treatment_execution")!="NOT_EXECUTED" or plan.get("holdout_access")!="NONE": raise ValueError("execution plan provenance invalid")
    for ref_key,hash_key,label in (("wave_ref","wave_file_sha256","wave"),("base_audit_plan_ref","base_audit_plan_file_sha256","base audit plan"),("image_acquisition_receipt_ref","image_acquisition_receipt_file_sha256","image receipt"),("runner_ref","runner_file_sha256","base-audit runner")):
        ref=plan.get(ref_key)
        if not isinstance(ref,str) or not ref: raise ValueError(f"plan missing {ref_key}")
        p=require_file(Path(ref),label)
        if sha256_file(p)!=plan.get(hash_key): raise ValueError(f"{label} hash mismatch")
    entries=plan.get("entries")
    if not isinstance(entries,list) or len(entries)!=plan.get("candidate_count"): raise ValueError("plan candidate count mismatch")
    ids=[e.get("candidate_id") for e in entries if isinstance(e,dict)]
    if len(ids)!=len(entries) or len(ids)!=len(set(ids)): raise ValueError("plan candidate identities invalid")
    runner=str(Path(plan["runner_ref"]).resolve())
    for entry in entries:
        cid=entry.get("candidate_id")
        if entry.get("authorized_action")!="PRE_SOLUTION_BASE_AUDIT_ONLY" or entry.get("treatment_execution")!="NOT_EXECUTED" or entry.get("holdout_access")!="NONE": raise ValueError(f"{cid}: unauthorized/contaminated entry")
        digest=entry.get("image_digest")
        if not isinstance(digest,str) or "@sha256:" not in digest: raise ValueError(f"{cid}: immutable image digest missing")
        argv=entry.get("argv")
        if not isinstance(argv,list) or len(argv)<2 or str(Path(argv[1]).resolve())!=runner: raise ValueError(f"{cid}: runner argv mismatch")
        if "--image-digest" not in argv or argv[argv.index("--image-digest")+1]!=digest: raise ValueError(f"{cid}: argv/image digest mismatch")
        admission=require_file(Path(entry["admission_only_ref"]),f"{cid} admission artifact"); executor=require_file(Path(entry["executor_visible_ref"]),f"{cid} executor artifact"); integrity=entry.get("artifact_integrity",{})
        if sha256_file(admission)!=integrity.get("admission_only_sha256"): raise ValueError(f"{cid}: admission artifact hash mismatch")
        if sha256_file(executor)!=integrity.get("executor_visible_sha256"): raise ValueError(f"{cid}: executor-visible artifact hash mismatch")
    return plan,entries

def execute_entry(entry: dict[str,Any]) -> dict[str,Any]:
    cid=entry["candidate_id"]; out=Path(entry["audit_out"])
    if out.exists(): return {"candidate_id":cid,"status":"BLOCKED","reason":"AUDIT_OUT_EXISTS","audit_out":str(out)}
    proc=subprocess.run(entry["argv"],text=True,capture_output=True,check=False); report=out/"base-audit-run.json"
    result={"candidate_id":cid,"runner_returncode":proc.returncode,"audit_out":str(out),"stdout":proc.stdout.strip(),"stderr":proc.stderr.strip()}
    if report.is_file():
        payload=load(report); result.update({"status":payload.get("status",payload.get("classification","RECORDED")),"classification":payload.get("classification"),"harness_integrity":payload.get("harness_integrity"),"image_digest":payload.get("image_digest"),"report_ref":str(report),"report_sha256":sha256_file(report)})
    else: result["status"]="NO_REPORT"
    return result

def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument("--plan",required=True,type=Path); ap.add_argument("--receipt",type=Path,default=Path(".ndv-corpus/s2-w01/base-audit-execution-receipt.json")); args=ap.parse_args()
    try: plan,entries=validate_plan(args.plan)
    except (OSError,ValueError,json.JSONDecodeError) as exc: print(json.dumps({"status":"FAIL","reason":"BASE_AUDIT_EXECUTION_BLOCKED","detail":str(exc)},indent=2)); return 2
    results=[execute_entry(e) for e in entries]
    receipt={"schema_id":"ndv-p1-s2-base-audit-execution-receipt-v1","status":"BASE_AUDIT_BATCH_RECORDED","plan_ref":str(args.plan.resolve()),"plan_file_sha256":sha256_file(args.plan.resolve()),"wave_id":plan.get("wave_id"),"selected_candidate_ids":[e["candidate_id"] for e in entries],"results":results,"docker_execution":True,"model_execution":"NONE","treatment_execution":"NOT_EXECUTED","holdout_access":"NONE","completed_at":datetime.now(timezone.utc).isoformat()}
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    if args.receipt.exists(): raise SystemExit(f"refusing overwrite: {args.receipt}")
    args.receipt.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"status":receipt["status"],"receipt":str(args.receipt),"results":[{"candidate_id":r["candidate_id"],"status":r["status"]} for r in results]},indent=2)); return 0 if all(r.get("report_ref") for r in results) else 2
if __name__=="__main__": raise SystemExit(main())
