#!/usr/bin/env python3
"""Promote qualified Codex Sol/Luna subscription bindings into WP-07 roles."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any
from ndv_wp07_codex_bundle import verify_bundle, QUALIFICATION_SCHEMAS, BINDING_SCHEMAS

def sha_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for c in iter(lambda:fh.read(1024*1024),b""): h.update(c)
    return h.hexdigest()
def load(path:Path)->Any: return json.loads(path.read_text(encoding="utf-8"))
def ref(path:Path,root:Path)->str:
    try:return str(path.resolve().relative_to(root.resolve())).replace("\\","/")
    except ValueError:return str(path.resolve())
def resolve_existing(value:str,root:Path)->Path:
    p=Path(value); p=p if p.is_absolute() else root/p; p=p.resolve()
    if not p.is_file(): raise ValueError(f"execution surface not found: {p}")
    return p

def verify_dir(root:Path,expected_model:str,expected_candidate:str,required_roles:set[str],artifact_root:Path)->dict[str,Any]:
    sealed=verify_bundle(root,expected_model=expected_model,expected_candidate=expected_candidate)
    q,b=sealed["qualification"],sealed["binding"]
    qpath=root.resolve()/"qualification.json"; bpath=root.resolve()/"executor-binding.json"
    if q.get("schema_id") not in QUALIFICATION_SCHEMAS or q.get("status")!="S0_READY": raise ValueError(f"{root}: S0_READY Codex qualification required")
    if b.get("schema_id") not in BINDING_SCHEMAS or b.get("status")!="QUALIFIED": raise ValueError(f"{root}: qualified WP-07 binding required")
    if q.get("candidate_id")!=expected_candidate or b.get("candidate_id")!=expected_candidate: raise ValueError(f"{root}: candidate mismatch")
    if q.get("requested_model")!=expected_model or (b.get("model") or {}).get("identity")!=expected_model: raise ValueError(f"{root}: model mismatch")
    if q.get("schema_id")=="ndv-p1-wp07-codex-subscription-qualification-v1":
        if q.get("observed_models")!=[expected_model] or q.get("exact_model_observed") is not True: raise ValueError(f"{root}: exact model observation missing")
    else:
        ia=q.get("identity_assurance") or {}
        if ia.get("status")!="CLI_PINNED_SOURCE_VERIFIED" or ia.get("requested_model")!=expected_model or b.get("identity_assurance")!="CLI_PINNED_SOURCE_VERIFIED": raise ValueError(f"{root}: CLI-pinned identity assurance missing")
    if not required_roles.issubset(set(q.get("candidate_roles") or [])) or not required_roles.issubset(set(b.get("candidate_roles") or [])): raise ValueError(f"{root}: role evidence mismatch")
    if b.get("auth_path")!="CHATGPT_SUBSCRIPTION" or b.get("api_key_routing_forbidden") is not True: raise ValueError(f"{root}: subscription auth provenance invalid")
    if b.get("dynamic_routing") is not False or b.get("implicit_fallback") is not False or b.get("retry_limit")!=0 or b.get("escalation_limit")!=0: raise ValueError(f"{root}: dynamic/retry policy invalid")
    if b.get("qualification_file_sha256")!=sha_file(qpath): raise ValueError(f"{root}: qualification hash mismatch")
    qsurf,qhash=q.get("execution_surface_ref"),q.get("execution_surface_file_sha256")
    bsurf,bhash=b.get("execution_surface_ref"),b.get("execution_surface_file_sha256")
    if not all(isinstance(x,str) and x for x in (qsurf,qhash,bsurf,bhash)): raise ValueError(f"{root}: execution surface provenance missing")
    if qhash!=bhash: raise ValueError(f"{root}: qualification/binding execution surface hash mismatch")
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
        amendment=load(amendment_path)
        cohort=str(q.get("qualification_cohort") or "").upper()
        if amendment.get("schema_id")!=f"ndv-p1-wp07-codex-qualification-amendment-{cohort.lower()}": raise ValueError(f"{root}: amendment/cohort mismatch")
        if cohort=="V4" and (q.get("windows_sandbox_backend_requested")!="unelevated" or b.get("windows_sandbox_backend")!="UNELEVATED"): raise ValueError(f"{root}: v4 Windows sandbox backend mismatch")
    return {"q":q,"b":b,"qpath":qpath,"bpath":bpath,"manifest_path":sealed["manifest_path"],"surface_path":qsp,"amendment_path":amendment_path}
def record(v:dict[str,Any],artifact_root:Path)->dict[str,Any]:
    b=v["b"]
    out={"binding_id":b["binding_id"],"binding_ref":ref(v["bpath"],artifact_root),"binding_file_sha256":sha_file(v["bpath"]),"qualification_ref":ref(v["qpath"],artifact_root),"qualification_file_sha256":sha_file(v["qpath"]),"evidence_manifest_ref":ref(v["manifest_path"],artifact_root),"evidence_manifest_sha256":sha_file(v["manifest_path"]),"execution_surface_ref":ref(v["surface_path"],artifact_root),"execution_surface_file_sha256":sha_file(v["surface_path"]),"exact_executor_identity":b["exact_executor_identity"],"surface_class":"SUBSCRIPTION_EXECUTOR_PINNED","qualification_schema":v["q"]["schema_id"]}
    if v.get("amendment_path") is not None:
        out["amendment_ref"]=ref(v["amendment_path"],artifact_root); out["amendment_file_sha256"]=sha_file(v["amendment_path"])
    if b.get("windows_sandbox_backend"): out["windows_sandbox_backend"]=b["windows_sandbox_backend"]
    return out
def promote(registry_path:Path,sol_dir:Path,luna_dir:Path,artifact_root:Path)->dict[str,Any]:
    reg=load(registry_path.resolve())
    if reg.get("schema_id")!="ndv-p1-wp07-treatment-bindings-v1" or reg.get("treatment_execution")!="NOT_EXECUTED" or reg.get("holdout_access")!="NONE": raise ValueError("registry invalid/contaminated")
    t=reg.get("treatments")
    if not isinstance(t,dict) or set(t)!={"B0","B1","B2","B3","B4"}: raise ValueError("registry treatment set drift")
    sol=verify_dir(sol_dir,"gpt-5.6-sol","CODEX-PLUS-GPT-5.6-SOL",{"PRIMARY_STRONG","ESCALATION_STRONG"},artifact_root)
    luna=verify_dir(luna_dir,"gpt-5.6-luna","CODEX-PLUS-GPT-5.6-LUNA",{"PRIMARY_ECONOMIC"},artifact_root)
    if sol["q"].get("schema_id")!=luna["q"].get("schema_id"): raise ValueError("Sol/Luna qualification schema mismatch")
    if (sol.get("amendment_path") is None)!=(luna.get("amendment_path") is None): raise ValueError("Sol/Luna amendment provenance mismatch")
    if sol.get("amendment_path") is not None and sha_file(sol["amendment_path"])!=sha_file(luna["amendment_path"]): raise ValueError("Sol/Luna qualified under different amendments")
    srec,lrec=record(sol,artifact_root),record(luna,artifact_root)
    t["B0"]["bindings"]={"PRIMARY_STRONG":srec}; t["B0"]["status"]="BOUND_READY"
    t["B1"]["bindings"]={"PRIMARY_ECONOMIC":lrec}; t["B1"]["status"]="BOUND_READY"
    t["B2"]["bindings"]={"PRIMARY_ECONOMIC":lrec,"ESCALATION_STRONG":srec}; t["B2"]["status"]="BOUND_READY"
    b4=t["B4"].setdefault("bindings",{}); b4["ESCALATION_STRONG"]=srec
    t["B4"]["status"]="BOUND_READY" if "PRIMARY_LOCAL_OR_FREE" in b4 else "PARTIALLY_BOUND"
    reg["status"]="INCOMPLETE_BINDING_COVERAGE" if any(x.get("status")!="BOUND_READY" for x in t.values()) else "ALL_TREATMENTS_BOUND"
    reg["promotion_provenance"]={"codex_sol_binding_sha256":sha_file(sol["bpath"]),"codex_sol_evidence_manifest_sha256":sha_file(sol["manifest_path"]),"codex_luna_binding_sha256":sha_file(luna["bpath"]),"codex_luna_evidence_manifest_sha256":sha_file(luna["manifest_path"]),"execution_surface_file_sha256":sha_file(sol["surface_path"]),"qualification_schema":sol["q"]["schema_id"],"amendment_file_sha256":sha_file(sol["amendment_path"]) if sol.get("amendment_path") is not None else None,"automatic_roles":["B0.PRIMARY_STRONG","B1.PRIMARY_ECONOMIC","B2.PRIMARY_ECONOMIC","B2.ESCALATION_STRONG","B4.ESCALATION_STRONG"],"b3_automatic_promotion":False,"treatment_execution":"NOT_EXECUTED"}
    return reg
def main()->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument("--registry",type=Path,default=Path("experiments/p1/wp07-treatment-bindings-v1.json")); ap.add_argument("--sol-dir",required=True,type=Path); ap.add_argument("--luna-dir",required=True,type=Path); ap.add_argument("--artifact-root",type=Path,default=Path(".")); ap.add_argument("--out",required=True,type=Path); args=ap.parse_args()
    try: result=promote(args.registry,args.sol_dir,args.luna_dir,args.artifact_root.resolve())
    except (OSError,ValueError,json.JSONDecodeError) as exc: print(json.dumps({"status":"FAIL","reason":"CODEX_BINDING_PROMOTION_BLOCKED","detail":str(exc)},indent=2)); return 2
    args.out.parent.mkdir(parents=True,exist_ok=True)
    if args.out.exists(): raise SystemExit(f"refusing overwrite: {args.out}")
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"B0":result["treatments"]["B0"]["status"],"B1":result["treatments"]["B1"]["status"],"B2":result["treatments"]["B2"]["status"],"B3":result["treatments"]["B3"]["status"],"B4":result["treatments"]["B4"]["status"]},indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
