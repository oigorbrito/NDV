#!/usr/bin/env python3
"""Bind qualified Sol/Terra/Luna Codex surfaces into frozen B3 family policy."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any
from ndv_wp07_codex_bundle import verify_bundle, QUALIFICATION_SCHEMAS, BINDING_SCHEMAS

EXPECTED={"F1":("gpt-5.6-luna","CODEX-PLUS-GPT-5.6-LUNA"),"F2":("gpt-5.6-sol","CODEX-PLUS-GPT-5.6-SOL"),"F3":("gpt-5.6-terra","CODEX-PLUS-GPT-5.6-TERRA"),"F4":("gpt-5.6-luna","CODEX-PLUS-GPT-5.6-LUNA"),"F5":("gpt-5.6-terra","CODEX-PLUS-GPT-5.6-TERRA"),"F6":("gpt-5.6-sol","CODEX-PLUS-GPT-5.6-SOL")}
def sha_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for c in iter(lambda:fh.read(1024*1024),b""): h.update(c)
    return h.hexdigest()
def load(path:Path)->Any:return json.loads(path.read_text(encoding="utf-8"))
def rel(path:Path,root:Path)->str:
    try:return str(path.resolve().relative_to(root.resolve())).replace("\\","/")
    except ValueError:return str(path.resolve())
def resolve_existing(value:str,root:Path)->Path:
    p=Path(value); p=p if p.is_absolute() else root/p; p=p.resolve()
    if not p.is_file(): raise ValueError(f"execution surface not found: {p}")
    return p
def verify_candidate(root:Path,model:str,candidate_id:str,artifact_root:Path)->dict[str,Any]:
    sealed=verify_bundle(root,expected_model=model,expected_candidate=candidate_id); q,b=sealed["qualification"],sealed["binding"]
    qpath=root.resolve()/"qualification.json"; bpath=root.resolve()/"executor-binding.json"
    if q.get("status")!="S0_READY" or q.get("schema_id") not in QUALIFICATION_SCHEMAS: raise ValueError(f"{root}: S0_READY qualification required")
    if b.get("status")!="QUALIFIED" or b.get("schema_id") not in BINDING_SCHEMAS: raise ValueError(f"{root}: qualified binding required")
    if q.get("candidate_id")!=candidate_id or b.get("candidate_id")!=candidate_id: raise ValueError(f"{root}: candidate mismatch")
    if q.get("requested_model")!=model or (b.get("model") or {}).get("identity")!=model: raise ValueError(f"{root}: exact model mismatch")
    if q.get("schema_id")=="ndv-p1-wp07-codex-subscription-qualification-v1":
        if q.get("observed_models")!=[model] or q.get("exact_model_observed") is not True: raise ValueError(f"{root}: exact model observation missing")
    else:
        ia=q.get("identity_assurance") or {}
        if ia.get("status")!="CLI_PINNED_SOURCE_VERIFIED" or ia.get("requested_model")!=model or b.get("identity_assurance")!="CLI_PINNED_SOURCE_VERIFIED": raise ValueError(f"{root}: CLI-pinned identity assurance missing")
    if b.get("qualification_file_sha256")!=sha_file(qpath): raise ValueError(f"{root}: qualification hash mismatch")
    if b.get("dynamic_routing") is not False or b.get("implicit_fallback") is not False: raise ValueError(f"{root}: dynamic routing/fallback forbidden")
    qsurf,qhash=q.get("execution_surface_ref"),q.get("execution_surface_file_sha256"); bsurf,bhash=b.get("execution_surface_ref"),b.get("execution_surface_file_sha256")
    if not all(isinstance(x,str) and x for x in (qsurf,qhash,bsurf,bhash)) or qhash!=bhash: raise ValueError(f"{root}: execution surface provenance invalid")
    qsp=resolve_existing(qsurf,artifact_root); bsp=resolve_existing(bsurf,artifact_root)
    if qsp!=bsp or sha_file(qsp)!=qhash: raise ValueError(f"{root}: execution surface bytes/hash mismatch")
    surf=load(qsp)
    if surf.get("schema_id")!="ndv-p1-wp07-codex-execution-surface-v1" or surf.get("status")!="PROSPECTIVE_FROZEN_NOT_EXECUTED": raise ValueError(f"{root}: execution surface schema/status invalid")
    amendment_path=None
    if q.get("schema_id")!="ndv-p1-wp07-codex-subscription-qualification-v1":
        qaref,qahash=q.get("amendment_ref"),q.get("amendment_file_sha256"); baref,bahash=b.get("amendment_ref"),b.get("amendment_file_sha256")
        if not all(isinstance(x,str) and x for x in (qaref,qahash,baref,bahash)) or qahash!=bahash: raise ValueError(f"{root}: amendment provenance invalid")
        amendment_path=resolve_existing(qaref,artifact_root); bap=resolve_existing(baref,artifact_root)
        if amendment_path!=bap or sha_file(amendment_path)!=qahash: raise ValueError(f"{root}: amendment bytes/hash mismatch")
        amendment=load(amendment_path); cohort=str(q.get("qualification_cohort") or "").upper()
        if amendment.get("schema_id")!=f"ndv-p1-wp07-codex-qualification-amendment-{cohort.lower()}": raise ValueError(f"{root}: amendment/cohort mismatch")
        if cohort=="V4" and (q.get("windows_sandbox_backend_requested")!="unelevated" or b.get("windows_sandbox_backend")!="UNELEVATED"): raise ValueError(f"{root}: v4 Windows sandbox backend mismatch")
    return {"q":q,"b":b,"qpath":qpath,"bpath":bpath,"manifest_path":sealed["manifest_path"],"surface_path":qsp,"amendment_path":amendment_path}
def binding_record(v:dict[str,Any],artifact_root:Path)->dict[str,Any]:
    b=v["b"]; out={"binding_id":b["binding_id"],"binding_ref":rel(v["bpath"],artifact_root),"binding_file_sha256":sha_file(v["bpath"]),"qualification_ref":rel(v["qpath"],artifact_root),"qualification_file_sha256":sha_file(v["qpath"]),"evidence_manifest_ref":rel(v["manifest_path"],artifact_root),"evidence_manifest_sha256":sha_file(v["manifest_path"]),"execution_surface_ref":rel(v["surface_path"],artifact_root),"execution_surface_file_sha256":sha_file(v["surface_path"]),"exact_executor_identity":b["exact_executor_identity"],"surface_class":"SUBSCRIPTION_EXECUTOR_PINNED","qualification_schema":v["q"]["schema_id"]}
    if v.get("amendment_path") is not None:
        out["amendment_ref"]=rel(v["amendment_path"],artifact_root); out["amendment_file_sha256"]=sha_file(v["amendment_path"])
    if b.get("windows_sandbox_backend"): out["windows_sandbox_backend"]=b["windows_sandbox_backend"]
    return out
def freeze(registry_path:Path,policy_path:Path,sol_dir:Path,terra_dir:Path,luna_dir:Path,artifact_root:Path)->dict[str,Any]:
    reg=load(registry_path.resolve()); policy=load(policy_path.resolve())
    if reg.get("schema_id")!="ndv-p1-wp07-treatment-bindings-v1" or reg.get("treatment_execution")!="NOT_EXECUTED" or reg.get("holdout_access")!="NONE": raise ValueError("registry invalid/contaminated")
    if policy.get("schema_id")!="ndv-p1-wp07-static-family-policy-v1" or policy.get("status")!="PROSPECTIVE_FROZEN_NOT_BOUND" or policy.get("performance_data_used") is not False or policy.get("treatment_results_used") is not False or policy.get("dynamic_routing") is not False or policy.get("post_hoc_remapping") is not False: raise ValueError("family policy invalid/contaminated")
    p=policy.get("policy")
    if not isinstance(p,dict) or set(p)!=set(EXPECTED): raise ValueError("family policy must contain exactly F1-F6")
    for family,(model,cid) in EXPECTED.items():
        if p[family].get("model")!=model or p[family].get("candidate_id")!=cid: raise ValueError(f"{family}: frozen policy drift")
    vals={"SOL":verify_candidate(sol_dir,"gpt-5.6-sol","CODEX-PLUS-GPT-5.6-SOL",artifact_root),"TERRA":verify_candidate(terra_dir,"gpt-5.6-terra","CODEX-PLUS-GPT-5.6-TERRA",artifact_root),"LUNA":verify_candidate(luna_dir,"gpt-5.6-luna","CODEX-PLUS-GPT-5.6-LUNA",artifact_root)}
    surface_hashes={sha_file(v["surface_path"]) for v in vals.values()}
    if len(surface_hashes)!=1: raise ValueError("B3 candidates qualified under different execution surfaces")
    schemas={v["q"].get("schema_id") for v in vals.values()}
    if len(schemas)!=1: raise ValueError("B3 candidates qualified under different qualification schemas")
    amendment_hashes={sha_file(v["amendment_path"]) if v.get("amendment_path") is not None else None for v in vals.values()}
    if len(amendment_hashes)!=1: raise ValueError("B3 candidates qualified under different amendments")
    b3=reg["treatments"]["B3"]; b3["bindings"]={k:binding_record(v,artifact_root) for k,v in vals.items()}; b3["family_policy"]={"F1":"LUNA","F2":"SOL","F3":"TERRA","F4":"LUNA","F5":"TERRA","F6":"SOL"}; b3["status"]="BOUND_READY"; b3["policy_ref"]=rel(policy_path.resolve(),artifact_root); b3["policy_file_sha256"]=sha_file(policy_path.resolve()); b3["qualification_bundle_manifest_hashes"]={k:sha_file(v["manifest_path"]) for k,v in vals.items()}; b3["execution_surface_file_sha256"]=next(iter(surface_hashes)); b3["qualification_schema"]=next(iter(schemas)); b3["amendment_file_sha256"]=next(iter(amendment_hashes))
    reg["status"]="ALL_TREATMENTS_BOUND" if all(x.get("status")=="BOUND_READY" for x in reg["treatments"].values()) else "INCOMPLETE_BINDING_COVERAGE"
    return reg
def main()->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument("--registry",type=Path,required=True); ap.add_argument("--policy",type=Path,default=Path("experiments/p1/wp07-static-family-policy-v1.json")); ap.add_argument("--sol-dir",type=Path,required=True); ap.add_argument("--terra-dir",type=Path,required=True); ap.add_argument("--luna-dir",type=Path,required=True); ap.add_argument("--artifact-root",type=Path,default=Path(".")); ap.add_argument("--out",type=Path,required=True); args=ap.parse_args()
    try:r=freeze(args.registry,args.policy,args.sol_dir,args.terra_dir,args.luna_dir,args.artifact_root.resolve())
    except (OSError,ValueError,json.JSONDecodeError) as exc: print(json.dumps({"status":"FAIL","reason":"B3_POLICY_FREEZE_BLOCKED","detail":str(exc)},indent=2)); return 2
    if args.out.exists(): raise SystemExit(f"refusing overwrite: {args.out}")
    args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(json.dumps(r,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"status":r["treatments"]["B3"]["status"],"registry_status":r["status"]},indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
