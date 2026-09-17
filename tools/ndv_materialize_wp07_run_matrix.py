#!/usr/bin/env python3
"""Materialize frozen P1-S2 development run specs; never executes treatments."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from ndv_wp07_codex_bundle import verify_bundle

TREATMENTS={"B0","B1","B2","B3","B4"}
SHAPING_MODES={"S0_ONLY","PAIRED_S0_S1"}
DEFAULT_BUDGETS=Path(__file__).resolve().parents[1]/"experiments/p1/wp07-execution-budgets-v1.json"


def canonical(v:Any)->bytes:return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
def sha(v:Any)->str:return hashlib.sha256(canonical(v)).hexdigest()
def sha_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for c in iter(lambda:fh.read(1024*1024),b""):h.update(c)
    return h.hexdigest()
def load(path:Path)->Any:return json.loads(path.read_text(encoding="utf-8"))
def require(path:Path,label:str)->Path:
    p=path.resolve()
    if not p.is_file():raise ValueError(f"{label} not found: {p}")
    return p
def resolve(root:Path,value:Any,label:str)->Path:
    if not isinstance(value,str) or not value:raise ValueError(f"{label} missing")
    p=Path(value);p=p if p.is_absolute() else root/p;return require(p,label)

def verify_admission(path:Path)->dict[str,Any]:
    path=require(path,"admission record");r=load(path)
    if r.get("schema_id")!="ndv-p1-s2-admission-record-v2" or r.get("status")!="ADMITTED_FROZEN":raise ValueError(f"{path}: ADMITTED_FROZEN v2 required")
    expected=r.get("record_sha256");body={k:v for k,v in r.items() if k!="record_sha256"}
    if not isinstance(expected,str) or sha(body)!=expected:raise ValueError(f"{path}: record_sha256 mismatch")
    sel=r.get("selection") or {}
    if sel.get("treatment_execution_before_admission") is not False or sel.get("holdout_access")!="NONE":raise ValueError(f"{path}: contaminated admission")
    return r

def verify_release(path:Path)->dict[str,Any]:
    path=require(path,"WP-07 release");r=load(path)
    if r.get("schema_id")!="ndv-p1-wp07-development-comparison-release-v1" or r.get("status")!="WP07_DEVELOPMENT_COMPARISON_RELEASED":raise ValueError("valid WP-07 development release required")
    scope=r.get("authorized_scope") or {}
    if scope.get("development_corpus_comparative_treatment_execution") is not True or scope.get("sealed_holdout_access") is not False or scope.get("claim_generation") is not False or scope.get("architecture_decision") is not False:raise ValueError("release scope invalid")
    if r.get("holdout_access")!="NONE":raise ValueError("release holdout contamination")
    return r

def verify_protocol(path:Path)->dict[str,Any]:
    path=require(path,"WP-07 protocol");p=load(path)
    if p.get("schema_id")!="ndv-p1-wp07-development-comparison-protocol-v1" or p.get("status")!="PROSPECTIVE_FROZEN_NOT_RELEASED":raise ValueError("frozen WP-07 protocol required")
    if p.get("treatment_execution")!="NOT_EXECUTED" or p.get("holdout_access")!="NONE":raise ValueError("protocol contamination")
    return p

def verify_budgets(path:Path)->dict[str,Any]:
    path=require(path,"WP-07 budget contract");b=load(path)
    if b.get("schema_id")!="ndv-p1-wp07-execution-budgets-v1" or b.get("status")!="PROSPECTIVE_FROZEN_NOT_EXECUTED":raise ValueError("frozen WP-07 execution budgets required")
    if b.get("treatment_results_consulted") is not False or b.get("task_exposure") is not False or b.get("treatment_execution")!="NOT_EXECUTED" or b.get("holdout_access")!="NONE":raise ValueError("budget contract contamination")
    timeout=b.get("executor_timeout_ms_per_hop")
    if not isinstance(timeout,int) or timeout<=0:raise ValueError("positive executor_timeout_ms_per_hop required")
    treatments=b.get("treatments")
    if not isinstance(treatments,dict) or set(treatments)!=TREATMENTS:raise ValueError("budget treatment set drift")
    for tid,x in treatments.items():
        if not isinstance(x,dict) or not isinstance(x.get("run_timeout_ms"),int) or x["run_timeout_ms"]<=0:raise ValueError(f"{tid}: positive run_timeout_ms required")
        if x.get("retry_limit")!=0:raise ValueError(f"{tid}: retry_limit must remain zero")
        expected_escalation=1 if tid in {"B2","B4"} else 0
        if x.get("escalation_limit")!=expected_escalation:raise ValueError(f"{tid}: escalation_limit drift")
    return b

def verify_registry(path:Path,root:Path)->dict[str,Any]:
    path=require(path,"binding registry");reg=load(path)
    if reg.get("schema_id")!="ndv-p1-wp07-treatment-bindings-v1":raise ValueError("binding registry v1 required")
    treatments=reg.get("treatments")
    if not isinstance(treatments,dict) or set(treatments)!=TREATMENTS:raise ValueError("binding registry treatment set drift")
    if reg.get("treatment_execution")!="NOT_EXECUTED" or reg.get("holdout_access")!="NONE":raise ValueError("binding registry contamination")
    for tid,t in treatments.items():
        if t.get("status")!="BOUND_READY":raise ValueError(f"{tid}: binding coverage incomplete")
        bindings=t.get("bindings")
        if not isinstance(bindings,dict) or not bindings:raise ValueError(f"{tid}: concrete bindings required")
        for alias,b in bindings.items():
            resolved={}
            for rk,hk in (("binding_ref","binding_file_sha256"),("qualification_ref","qualification_file_sha256")):
                p=resolve(root,b.get(rk),f"{tid}.{alias} {rk}")
                if sha_file(p)!=b.get(hk):raise ValueError(f"{tid}.{alias}: {rk} hash mismatch")
                resolved[rk]=p
            if b.get("surface_class")=="SUBSCRIPTION_EXECUTOR_PINNED":
                mp=resolve(root,b.get("evidence_manifest_ref"),f"{tid}.{alias} evidence_manifest_ref")
                if sha_file(mp)!=b.get("evidence_manifest_sha256"):raise ValueError(f"{tid}.{alias}: evidence manifest hash mismatch")
                verify_bundle(mp.parent)
                if (mp.parent/"executor-binding.json").resolve()!=resolved["binding_ref"] or (mp.parent/"qualification.json").resolve()!=resolved["qualification_ref"]:raise ValueError(f"{tid}.{alias}: evidence manifest does not bind registry refs")
                sp=resolve(root,b.get("execution_surface_ref"),f"{tid}.{alias} execution_surface_ref")
                if sha_file(sp)!=b.get("execution_surface_file_sha256"):raise ValueError(f"{tid}.{alias}: execution surface hash mismatch")
                bp=load(resolved["binding_ref"]);qp=load(resolved["qualification_ref"]);surf=load(sp)
                if bp.get("execution_surface_file_sha256")!=b.get("execution_surface_file_sha256") or qp.get("execution_surface_file_sha256")!=b.get("execution_surface_file_sha256"):raise ValueError(f"{tid}.{alias}: execution surface chain mismatch")
                if surf.get("schema_id")!="ndv-p1-wp07-codex-execution-surface-v1" or surf.get("status")!="PROSPECTIVE_FROZEN_NOT_EXECUTED":raise ValueError(f"{tid}.{alias}: execution surface invalid")
    return reg

def treatment_binding_snapshot(tid:str,family:str,reg:dict[str,Any])->dict[str,Any]:
    t=reg["treatments"][tid];bindings=t["bindings"]
    if tid=="B3":
        alias=(t.get("family_policy") or {}).get(family)
        if alias not in bindings:raise ValueError(f"B3: no frozen binding for family {family}")
        selected={"FAMILY_SELECTED":bindings[alias]}
    else:selected=bindings
    keys=("binding_id","binding_ref","binding_file_sha256","qualification_ref","qualification_file_sha256","evidence_manifest_ref","evidence_manifest_sha256","execution_surface_ref","execution_surface_file_sha256","exact_executor_identity","surface_class")
    return {role:{k:b.get(k) for k in keys if k in b} for role,b in selected.items()}
def run_id(task_id:str,tid:str,shaping:str)->str:return "P1S2-"+hashlib.sha256(f"P1-S2|{task_id}|{tid}|{shaping}|rollout=1|repetition=1".encode()).hexdigest()[:20]
def budget_snapshot(tid:str,budget:dict[str,Any],budget_path:Path)->dict[str,Any]:
    per=budget["treatments"][tid]
    return {
        "executor_timeout_ms":budget["executor_timeout_ms_per_hop"],
        "run_timeout_ms":per["run_timeout_ms"],
        "retry_limit":per["retry_limit"],
        "escalation_limit":per["escalation_limit"],
        "budget_contract_ref":str(budget_path.resolve()),
        "budget_contract_file_sha256":sha_file(budget_path.resolve()),
    }
def materialize(release_path:Path,protocol_path:Path,registry_path:Path,admission_paths:list[Path],artifact_root:Path,shaping_mode:str,budget_path:Path|None=None)->dict[str,Any]:
    if shaping_mode not in SHAPING_MODES:raise ValueError("invalid shaping mode")
    budget_path=(budget_path or DEFAULT_BUDGETS).resolve()
    verify_release(release_path);protocol=verify_protocol(protocol_path);budget=verify_budgets(budget_path);reg=verify_registry(registry_path,artifact_root);records=[verify_admission(p) for p in admission_paths]
    ids=[r["candidate_id"] for r in records]
    if len(ids)!=len(set(ids)) or not records:raise ValueError("unique non-empty admission set required")
    shapings=["S0_RAW_TASK"] if shaping_mode=="S0_ONLY" else ["S0_RAW_TASK","S1_DETERMINISTIC_TASK_SHAPING"];specs=[]
    for r,p in zip(records,admission_paths):
        family=r.get("family")
        if family not in {"F1","F2","F3","F4","F5","F6"}:raise ValueError(f"{r.get('candidate_id')}: invalid family")
        source=r.get("source_binding") or {};audit=r.get("audit") or {}
        for tid in sorted(TREATMENTS):
            binding=treatment_binding_snapshot(tid,family,reg)
            for shaping in shapings:
                specs.append({
                    "schema_id":"ndv-p1-s2-run-spec-v1",
                    "run_id":run_id(r["candidate_id"],tid,shaping),
                    "phase":"P1-S2",
                    "task":{"task_id":r["candidate_id"],"family":family,"repository":r["repository"],"base_sha":r["base_revision"],"task_statement_sha256":source.get("task_statement_sha256"),"admission_record_ref":str(p.resolve()),"admission_record_file_sha256":sha_file(p.resolve()),"admission_record_sha256":r["record_sha256"],"solution_isolation":"SOLUTION_NOT_AVAILABLE_TO_EXECUTOR"},
                    "treatment":{"id":tid,"bindings":binding,"shaping":shaping,"rollout":1,"repetition":1},
                    "environment":{"source":"WP06_AUDITED_IMMUTABLE_DOCKER_IMAGE","environment_ref":audit.get("environment_ref"),"environment_sha256":audit.get("environment_sha256"),"network_policy":"EXECUTOR_HOST_NETWORK_AS_REQUIRED_BY_SUBSCRIPTION; VERIFIER_NETWORK_NONE","cache_state":"RECORDED_AT_EXECUTION","warm_cold_state":"RECORDED_AT_EXECUTION","environment_variables":"NO_SECRETS_EXCEPT_SUBSCRIPTION_SESSION_STATE"},
                    "budgets":budget_snapshot(tid,budget,budget_path),
                    "telemetry_requirements":["identity","timestamps","candidate_artifact","usage or explicit missingness","retry/escalation events","authoritative usage reference"],
                    "oracle":{"focal_verifier_ref":audit.get("focal_verifier_ref"),"focal_verifier_sha256":audit.get("focal_verifier_sha256"),"preservation_ref":audit.get("preservation_ref"),"preservation_sha256":audit.get("preservation_sha256"),"environment_ref":audit.get("environment_ref"),"environment_sha256":audit.get("environment_sha256"),"failure_attribution_ref":"experiments/p1/failure-attribution-v1.json"},
                    "accounting":{"ref":"experiments/p1/run-accounting-contract-v1.json","primary":protocol["primary_metric"],"failure_cost_retained":True,"inconclusive_cost_retained":True,"missing_telemetry_is_zero":False},
                    "holdout":"DEVELOPMENT_ONLY",
                    "execution_status":"NOT_EXECUTED"
                })
    run_ids=[s["run_id"] for s in specs]
    if len(run_ids)!=len(set(run_ids)):raise ValueError("run_id collision")
    return {"schema_id":"ndv-p1-wp07-run-matrix-v1","status":"RUN_SPECS_MATERIALIZED_NOT_EXECUTED","shaping_mode":shaping_mode,"task_count":len(records),"treatment_count":5,"run_spec_count":len(specs),"release_ref":str(release_path.resolve()),"release_file_sha256":sha_file(release_path.resolve()),"protocol_ref":str(protocol_path.resolve()),"protocol_file_sha256":sha_file(protocol_path.resolve()),"budget_contract_ref":str(budget_path),"budget_contract_file_sha256":sha_file(budget_path),"binding_registry_ref":str(registry_path.resolve()),"binding_registry_file_sha256":sha_file(registry_path.resolve()),"run_specs":specs,"treatment_execution":"NOT_EXECUTED","holdout_access":"NONE"}
def main()->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--release",required=True,type=Path)
    ap.add_argument("--protocol",type=Path,default=Path("experiments/p1/wp07-development-comparison-protocol-v1.json"))
    ap.add_argument("--bindings",type=Path,default=Path("experiments/p1/wp07-treatment-bindings-v1.json"))
    ap.add_argument("--budgets",type=Path,default=DEFAULT_BUDGETS)
    ap.add_argument("--admission-record",action="append",default=[],type=Path)
    ap.add_argument("--artifact-root",type=Path,default=Path("."))
    ap.add_argument("--shaping-mode",choices=sorted(SHAPING_MODES),default="S0_ONLY")
    ap.add_argument("--out",required=True,type=Path)
    args=ap.parse_args()
    try:result=materialize(args.release.resolve(),args.protocol.resolve(),args.bindings.resolve(),args.admission_record,args.artifact_root.resolve(),args.shaping_mode,args.budgets.resolve())
    except (OSError,ValueError,json.JSONDecodeError) as exc:print(json.dumps({"status":"FAIL","reason":"WP07_MATRIX_MATERIALIZATION_BLOCKED","detail":str(exc)},indent=2));return 2
    args.out.parent.mkdir(parents=True,exist_ok=True)
    if args.out.exists():raise SystemExit(f"refusing overwrite: {args.out}")
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"task_count":result["task_count"],"run_spec_count":result["run_spec_count"],"shaping_mode":result["shaping_mode"]},indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
