#!/usr/bin/env python3
"""Dispatch one released WP-07 Codex development run by frozen treatment id.

This is plumbing, not a router: B0/B1/B3 use the single-hop Codex path, B2 uses
the frozen Luna->Sol cascade, and B4 is rejected because its first hop is local.
The dispatcher accepts only a hash-bound released run matrix plus run_id; it does
not accept an arbitrary standalone run-spec.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any

from ndv_materialize_wp07_codex_workspace import materialize
from ndv_run_wp07_codex_single_hop import EXECUTE_TOKEN, execute
from ndv_run_wp07_b2_codex_cascade import B2_CONTRACT_DEFAULT, cascade
from ndv_verify_wp07_codex_single_hop import VERIFY_TOKEN, verify

SINGLE={"B0","B1","B3"}

def load(path:Path)->Any:return json.loads(path.read_text(encoding="utf-8"))
def sha_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for c in iter(lambda:fh.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def resolve(root:Path,value:Any,label:str)->Path:
    if not isinstance(value,str) or not value:raise ValueError(f"{label} missing")
    p=Path(value);p=p if p.is_absolute() else root/p;p=p.resolve()
    if not p.is_file():raise ValueError(f"{label} not found: {p}")
    return p

def select_released_spec(matrix_path:Path,artifact_root:Path,run_id:str)->tuple[dict[str,Any],dict[str,Any],Path]:
    matrix=load(matrix_path.resolve())
    if matrix.get("schema_id")!="ndv-p1-wp07-run-matrix-v1" or matrix.get("status")!="RUN_SPECS_MATERIALIZED_NOT_EXECUTED":raise ValueError("released-materialized WP-07 run matrix required")
    if matrix.get("treatment_execution")!="NOT_EXECUTED" or matrix.get("holdout_access")!="NONE":raise ValueError("run matrix contamination")
    release_path=resolve(artifact_root,matrix.get("release_ref"),"release_ref")
    if sha_file(release_path)!=matrix.get("release_file_sha256"):raise ValueError("release file hash mismatch")
    release=load(release_path);scope=release.get("authorized_scope") or {};constraints=release.get("execution_constraints") or {}
    if release.get("schema_id")!="ndv-p1-wp07-development-comparison-release-v1" or release.get("status")!="WP07_DEVELOPMENT_COMPARISON_RELEASED":raise ValueError("valid WP-07 development release required")
    if release.get("holdout_access")!="NONE" or scope.get("development_corpus_comparative_treatment_execution") is not True or scope.get("sealed_holdout_access") is not False:raise ValueError("release authority scope invalid")
    if scope.get("claim_generation") is not False or scope.get("architecture_decision") is not False:raise ValueError("release scope unexpectedly authorizes claims/architecture")
    if constraints.get("preserve_preregistered_treatments") is not True or constraints.get("preserve_zero_unplanned_fallback") is not True or constraints.get("verified_result_required") is not True:raise ValueError("release execution constraints invalid")
    specs=matrix.get("run_specs")
    if not isinstance(specs,list):raise ValueError("run matrix run_specs missing")
    matches=[s for s in specs if isinstance(s,dict) and s.get("run_id")==run_id]
    if len(matches)!=1:raise ValueError(f"run_id must resolve exactly once in released matrix: {run_id}")
    spec=matches[0]
    if spec.get("schema_id")!="ndv-p1-s2-run-spec-v1" or spec.get("execution_status")!="NOT_EXECUTED":raise ValueError("selected NOT_EXECUTED P1-S2 run-spec required")
    if spec.get("holdout")!="DEVELOPMENT_ONLY":raise ValueError("selected run-spec must remain development-only")
    tid=((spec.get("treatment") or {}).get("id"))
    if tid not in {"B0","B1","B2","B3","B4"}:raise ValueError(f"unknown frozen treatment: {tid!r}")
    return matrix,spec,release_path

def dispatch(matrix_path:Path,run_id:str,artifact_root:Path,upstream_root:Path,out_dir:Path,execute_token:str,verify_token:str,b2_contract:Path=B2_CONTRACT_DEFAULT)->dict[str,Any]:
    # Tokens are checked before reading matrix/task-bearing artifacts.
    if execute_token!=EXECUTE_TOKEN:raise ValueError("explicit frozen development execution token required")
    if verify_token!=VERIFY_TOKEN:raise ValueError("explicit frozen development verification token required")
    if out_dir.exists():raise ValueError(f"out-dir exists; refusing overwrite: {out_dir}")
    matrix,spec,release_path=select_released_spec(matrix_path.resolve(),artifact_root.resolve(),run_id)
    tid=((spec.get("treatment") or {}).get("id"))
    if tid=="B4":raise ValueError("B4 is not a Codex-only treatment; local-first controller required")
    if tid not in SINGLE|{"B2"}:raise ValueError(f"unsupported Codex treatment: {tid!r}")
    out_dir.mkdir(parents=True)
    selected=out_dir/"selected-run-spec.json";selected.write_text(json.dumps(spec,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    if tid=="B2":
        result=cascade(selected,artifact_root.resolve(),upstream_root.resolve(),out_dir/"b2",b2_contract.resolve(),execute_token,verify_token)
        route="B2_FROZEN_CASCADE"
        final=result.get("verified_solved_task");failure=result.get("failure_attribution")
        result_ref=out_dir/"b2"/"cascade-report.json"
    else:
        ws_dir=out_dir/"workspace";materialize(selected,artifact_root.resolve(),ws_dir)
        executor_dir=out_dir/"executor";stage=execute(selected,ws_dir/"workspace-manifest.json",artifact_root.resolve(),executor_dir,execute_token)
        if (stage.get("classification") or {}).get("pending_verification") is True:
            verification=verify(executor_dir/"executor-stage-report.json",artifact_root.resolve(),upstream_root.resolve(),out_dir/"verification",verify_token)
            final=verification.get("verified_solved_task");failure=verification.get("failure_attribution");result_ref=out_dir/"verification"/"verification-report.json"
        else:
            final="INCONCLUSIVE";failure=(stage.get("classification") or {}).get("failure_attribution") or "INCONCLUSIVE_OTHER";result_ref=executor_dir/"executor-stage-report.json"
        route="STATIC_SINGLE_HOP"
    report={
        "schema_id":"ndv-p1-wp07-codex-dispatch-report-v1","run_id":run_id,"treatment_id":tid,
        "dispatch_route":route,"verified_solved_task":final,"failure_attribution":failure,
        "dynamic_routing":False,"implicit_fallback":False,"retry_added_by_dispatcher":False,
        "selected_run_spec_ref":str(selected),"selected_run_spec_file_sha256":sha_file(selected),
        "result_ref":str(result_ref),"result_file_sha256":sha_file(result_ref) if result_ref.is_file() else None,
        "source_chain":{"run_matrix_ref":str(matrix_path.resolve()),"run_matrix_file_sha256":sha_file(matrix_path.resolve()),"release_ref":str(release_path),"release_file_sha256":sha_file(release_path)},
        "authority":"DEVELOPMENT_EXECUTION_ONLY_NO_CLAIMS_NO_ARCHITECTURE_DECISION","holdout_access":"NONE"
    }
    (out_dir/"dispatch-report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return report

def main()->int:
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("--run-matrix",required=True,type=Path);ap.add_argument("--run-id",required=True);ap.add_argument("--artifact-root",type=Path,default=Path("."));ap.add_argument("--upstream-root",required=True,type=Path);ap.add_argument("--out-dir",required=True,type=Path);ap.add_argument("--b2-contract",type=Path,default=B2_CONTRACT_DEFAULT);ap.add_argument("--execute-token",required=True);ap.add_argument("--verify-token",required=True);args=ap.parse_args()
    try:r=dispatch(args.run_matrix,args.run_id,args.artifact_root,args.upstream_root,args.out_dir.resolve(),args.execute_token,args.verify_token,args.b2_contract)
    except (OSError,ValueError,json.JSONDecodeError) as exc:print(json.dumps({"status":"FAIL","reason":"WP07_CODEX_DISPATCH_BLOCKED","detail":str(exc)},indent=2));return 2
    print(json.dumps({"status":"WP07_CODEX_DISPATCH_COMPLETE","run_id":r["run_id"],"treatment_id":r["treatment_id"],"dispatch_route":r["dispatch_route"],"verified_solved_task":r["verified_solved_task"],"failure_attribution":r["failure_attribution"]},indent=2));return 0 if r["verified_solved_task"] in {"YES","NO"} else 3
if __name__=="__main__":raise SystemExit(main())
