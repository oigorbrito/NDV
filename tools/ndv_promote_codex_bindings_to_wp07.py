#!/usr/bin/env python3
"""Promote qualified Codex Sol/Luna subscription bindings into WP-07 roles.

This tool never executes a model. It only verifies already-qualified synthetic
artifacts and fills the preregistered roles: Sol -> strong roles, Luna -> economic
roles. B3 is intentionally untouched. B4 becomes ready only if a local/free
first-hop binding is already present.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for c in iter(lambda:fh.read(1024*1024),b""): h.update(c)
    return h.hexdigest()
def load(path:Path)->Any: return json.loads(path.read_text(encoding="utf-8"))
def ref(path:Path,root:Path)->str:
    try: return str(path.resolve().relative_to(root.resolve())).replace("\\","/")
    except ValueError: return str(path.resolve())

def verify_dir(root:Path,expected_model:str,expected_candidate:str,required_roles:set[str])->dict[str,Any]:
    qpath=root.resolve()/"qualification.json"; bpath=root.resolve()/"executor-binding.json"
    if not qpath.is_file() or not bpath.is_file(): raise ValueError(f"{root}: qualification.json and executor-binding.json required")
    q,b=load(qpath),load(bpath)
    if q.get("schema_id")!="ndv-p1-wp07-codex-subscription-qualification-v1" or q.get("status")!="S0_READY": raise ValueError(f"{root}: S0_READY Codex qualification required")
    if b.get("schema_id")!="ndv-p1-wp07-executor-binding-v1" or b.get("status")!="QUALIFIED": raise ValueError(f"{root}: qualified WP-07 binding required")
    if q.get("candidate_id")!=expected_candidate or b.get("candidate_id")!=expected_candidate: raise ValueError(f"{root}: candidate mismatch")
    if q.get("requested_model")!=expected_model or (b.get("model") or {}).get("identity")!=expected_model: raise ValueError(f"{root}: model mismatch")
    if q.get("observed_models")!=[expected_model] or q.get("exact_model_observed") is not True: raise ValueError(f"{root}: exact model observation missing")
    if not required_roles.issubset(set(q.get("candidate_roles") or [])) or not required_roles.issubset(set(b.get("candidate_roles") or [])): raise ValueError(f"{root}: role evidence mismatch")
    if b.get("auth_path")!="CHATGPT_SUBSCRIPTION" or b.get("api_key_routing_forbidden") is not True: raise ValueError(f"{root}: subscription auth provenance invalid")
    if b.get("dynamic_routing") is not False or b.get("implicit_fallback") is not False or b.get("retry_limit")!=0 or b.get("escalation_limit")!=0: raise ValueError(f"{root}: dynamic/retry policy invalid")
    if b.get("qualification_file_sha256")!=sha_file(qpath): raise ValueError(f"{root}: qualification hash mismatch")
    return {"q":q,"b":b,"qpath":qpath,"bpath":bpath}
def record(v:dict[str,Any],artifact_root:Path)->dict[str,Any]:
    b,q=v["b"],v["q"]
    return {"binding_id":b["binding_id"],"binding_ref":ref(v["bpath"],artifact_root),"binding_file_sha256":sha_file(v["bpath"]),"qualification_ref":ref(v["qpath"],artifact_root),"qualification_file_sha256":sha_file(v["qpath"]),"exact_executor_identity":b["exact_executor_identity"],"surface_class":"SUBSCRIPTION_EXECUTOR_PINNED"}
def promote(registry_path:Path,sol_dir:Path,luna_dir:Path,artifact_root:Path)->dict[str,Any]:
    reg=load(registry_path.resolve())
    if reg.get("schema_id")!="ndv-p1-wp07-treatment-bindings-v1" or reg.get("treatment_execution")!="NOT_EXECUTED" or reg.get("holdout_access")!="NONE": raise ValueError("registry invalid/contaminated")
    t=reg.get("treatments")
    if not isinstance(t,dict) or set(t)!={"B0","B1","B2","B3","B4"}: raise ValueError("registry treatment set drift")
    sol=verify_dir(sol_dir,"gpt-5.6-sol","CODEX-PLUS-GPT-5.6-SOL",{"PRIMARY_STRONG","ESCALATION_STRONG"})
    luna=verify_dir(luna_dir,"gpt-5.6-luna","CODEX-PLUS-GPT-5.6-LUNA",{"PRIMARY_ECONOMIC"})
    srec,lrec=record(sol,artifact_root),record(luna,artifact_root)
    t["B0"]["bindings"]={"PRIMARY_STRONG":srec}; t["B0"]["status"]="BOUND_READY"
    t["B1"]["bindings"]={"PRIMARY_ECONOMIC":lrec}; t["B1"]["status"]="BOUND_READY"
    t["B2"]["bindings"]={"PRIMARY_ECONOMIC":lrec,"ESCALATION_STRONG":srec}; t["B2"]["status"]="BOUND_READY"
    b4=t["B4"].setdefault("bindings",{})
    b4["ESCALATION_STRONG"]=srec
    t["B4"]["status"]="BOUND_READY" if "PRIMARY_LOCAL_OR_FREE" in b4 else "PARTIALLY_BOUND"
    # B3 is intentionally unchanged; static family policy must be frozen separately.
    reg["status"]="INCOMPLETE_BINDING_COVERAGE" if any(x.get("status")!="BOUND_READY" for x in t.values()) else "ALL_TREATMENTS_BOUND"
    reg["promotion_provenance"]={"codex_sol_binding_sha256":sha_file(sol["bpath"]),"codex_luna_binding_sha256":sha_file(luna["bpath"]),"automatic_roles":["B0.PRIMARY_STRONG","B1.PRIMARY_ECONOMIC","B2.PRIMARY_ECONOMIC","B2.ESCALATION_STRONG","B4.ESCALATION_STRONG"],"b3_automatic_promotion":False,"treatment_execution":"NOT_EXECUTED"}
    return reg
def main()->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument("--registry",type=Path,default=Path("experiments/p1/wp07-treatment-bindings-v1.json")); ap.add_argument("--sol-dir",required=True,type=Path); ap.add_argument("--luna-dir",required=True,type=Path); ap.add_argument("--artifact-root",type=Path,default=Path(".")); ap.add_argument("--out",required=True,type=Path); args=ap.parse_args()
    try: result=promote(args.registry,args.sol_dir,args.luna_dir,args.artifact_root)
    except (OSError,ValueError,json.JSONDecodeError) as exc: print(json.dumps({"status":"FAIL","reason":"CODEX_BINDING_PROMOTION_BLOCKED","detail":str(exc)},indent=2)); return 2
    args.out.parent.mkdir(parents=True,exist_ok=True)
    if args.out.exists(): raise SystemExit(f"refusing overwrite: {args.out}")
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"B0":result["treatments"]["B0"]["status"],"B1":result["treatments"]["B1"]["status"],"B2":result["treatments"]["B2"]["status"],"B3":result["treatments"]["B3"]["status"],"B4":result["treatments"]["B4"]["status"]},indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
