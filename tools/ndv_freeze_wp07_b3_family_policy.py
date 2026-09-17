#!/usr/bin/env python3
"""Bind qualified Sol/Terra/Luna Codex surfaces into frozen B3 family policy.

No model is executed. This consumes only existing sealed S0_READY synthetic
qualification bundles and the prospective family policy contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from ndv_wp07_codex_bundle import verify_bundle

EXPECTED = {
    "F1": ("gpt-5.6-luna", "CODEX-PLUS-GPT-5.6-LUNA"),
    "F2": ("gpt-5.6-sol", "CODEX-PLUS-GPT-5.6-SOL"),
    "F3": ("gpt-5.6-terra", "CODEX-PLUS-GPT-5.6-TERRA"),
    "F4": ("gpt-5.6-luna", "CODEX-PLUS-GPT-5.6-LUNA"),
    "F5": ("gpt-5.6-terra", "CODEX-PLUS-GPT-5.6-TERRA"),
    "F6": ("gpt-5.6-sol", "CODEX-PLUS-GPT-5.6-SOL"),
}

def sha_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for c in iter(lambda:fh.read(1024*1024),b""): h.update(c)
    return h.hexdigest()
def load(path:Path)->Any: return json.loads(path.read_text(encoding="utf-8"))
def rel(path:Path,root:Path)->str:
    try:return str(path.resolve().relative_to(root.resolve())).replace("\\","/")
    except ValueError:return str(path.resolve())
def verify_candidate(root:Path,model:str,candidate_id:str)->dict[str,Any]:
    sealed=verify_bundle(root,expected_model=model,expected_candidate=candidate_id)
    q,b=sealed["qualification"],sealed["binding"]
    qpath=root.resolve()/"qualification.json"; bpath=root.resolve()/"executor-binding.json"
    if q.get("status")!="S0_READY" or q.get("schema_id")!="ndv-p1-wp07-codex-subscription-qualification-v1": raise ValueError(f"{root}: S0_READY qualification required")
    if b.get("status")!="QUALIFIED" or b.get("schema_id")!="ndv-p1-wp07-executor-binding-v1": raise ValueError(f"{root}: qualified binding required")
    if q.get("candidate_id")!=candidate_id or b.get("candidate_id")!=candidate_id: raise ValueError(f"{root}: candidate mismatch")
    if q.get("requested_model")!=model or q.get("observed_models")!=[model] or q.get("exact_model_observed") is not True or (b.get("model") or {}).get("identity")!=model: raise ValueError(f"{root}: exact model mismatch")
    if b.get("qualification_file_sha256")!=sha_file(qpath): raise ValueError(f"{root}: qualification hash mismatch")
    if b.get("dynamic_routing") is not False or b.get("implicit_fallback") is not False: raise ValueError(f"{root}: dynamic routing/fallback forbidden")
    return {"q":q,"b":b,"qpath":qpath,"bpath":bpath,"manifest_path":sealed["manifest_path"]}
def binding_record(v:dict[str,Any],artifact_root:Path)->dict[str,Any]:
    b=v["b"]
    return {"binding_id":b["binding_id"],"binding_ref":rel(v["bpath"],artifact_root),"binding_file_sha256":sha_file(v["bpath"]),"qualification_ref":rel(v["qpath"],artifact_root),"qualification_file_sha256":sha_file(v["qpath"]),"evidence_manifest_ref":rel(v["manifest_path"],artifact_root),"evidence_manifest_sha256":sha_file(v["manifest_path"]),"exact_executor_identity":b["exact_executor_identity"],"surface_class":"SUBSCRIPTION_EXECUTOR_PINNED"}
def freeze(registry_path:Path,policy_path:Path,sol_dir:Path,terra_dir:Path,luna_dir:Path,artifact_root:Path)->dict[str,Any]:
    reg=load(registry_path.resolve()); policy=load(policy_path.resolve())
    if reg.get("schema_id")!="ndv-p1-wp07-treatment-bindings-v1" or reg.get("treatment_execution")!="NOT_EXECUTED" or reg.get("holdout_access")!="NONE": raise ValueError("registry invalid/contaminated")
    if policy.get("schema_id")!="ndv-p1-wp07-static-family-policy-v1" or policy.get("status")!="PROSPECTIVE_FROZEN_NOT_BOUND" or policy.get("performance_data_used") is not False or policy.get("treatment_results_used") is not False or policy.get("dynamic_routing") is not False or policy.get("post_hoc_remapping") is not False: raise ValueError("family policy invalid/contaminated")
    p=policy.get("policy")
    if not isinstance(p,dict) or set(p)!=set(EXPECTED): raise ValueError("family policy must contain exactly F1-F6")
    for family,(model,cid) in EXPECTED.items():
        if p[family].get("model")!=model or p[family].get("candidate_id")!=cid: raise ValueError(f"{family}: frozen policy drift")
    vals={
        "SOL":verify_candidate(sol_dir,"gpt-5.6-sol","CODEX-PLUS-GPT-5.6-SOL"),
        "TERRA":verify_candidate(terra_dir,"gpt-5.6-terra","CODEX-PLUS-GPT-5.6-TERRA"),
        "LUNA":verify_candidate(luna_dir,"gpt-5.6-luna","CODEX-PLUS-GPT-5.6-LUNA"),
    }
    b3=reg["treatments"]["B3"]
    b3["bindings"]={k:binding_record(v,artifact_root) for k,v in vals.items()}
    b3["family_policy"]={"F1":"LUNA","F2":"SOL","F3":"TERRA","F4":"LUNA","F5":"TERRA","F6":"SOL"}
    b3["status"]="BOUND_READY"
    b3["policy_ref"]=rel(policy_path.resolve(),artifact_root); b3["policy_file_sha256"]=sha_file(policy_path.resolve())
    b3["qualification_bundle_manifest_hashes"]={k:sha_file(v["manifest_path"]) for k,v in vals.items()}
    reg["status"]="ALL_TREATMENTS_BOUND" if all(x.get("status")=="BOUND_READY" for x in reg["treatments"].values()) else "INCOMPLETE_BINDING_COVERAGE"
    return reg
def main()->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument("--registry",type=Path,required=True); ap.add_argument("--policy",type=Path,default=Path("experiments/p1/wp07-static-family-policy-v1.json")); ap.add_argument("--sol-dir",type=Path,required=True); ap.add_argument("--terra-dir",type=Path,required=True); ap.add_argument("--luna-dir",type=Path,required=True); ap.add_argument("--artifact-root",type=Path,default=Path(".")); ap.add_argument("--out",type=Path,required=True); args=ap.parse_args()
    try:r=freeze(args.registry,args.policy,args.sol_dir,args.terra_dir,args.luna_dir,args.artifact_root)
    except (OSError,ValueError,json.JSONDecodeError) as exc: print(json.dumps({"status":"FAIL","reason":"B3_POLICY_FREEZE_BLOCKED","detail":str(exc)},indent=2)); return 2
    if args.out.exists(): raise SystemExit(f"refusing overwrite: {args.out}")
    args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(json.dumps(r,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"status":r["treatments"]["B3"]["status"],"registry_status":r["status"]},indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
