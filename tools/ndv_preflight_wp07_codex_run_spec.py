#!/usr/bin/env python3
"""Preflight one NOT_EXECUTED WP-07 run-spec against its frozen Codex surface.

This tool never sends the task to Codex. It revalidates preserved binding,
qualification, evidence-manifest, execution-surface bytes, current Codex version
and CLI flags, then emits only a redacted argv template.
"""
from __future__ import annotations
import argparse, hashlib, json, subprocess
from pathlib import Path
from typing import Any


def sha_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for c in iter(lambda:fh.read(1024*1024),b""):h.update(c)
    return h.hexdigest()
def load(path:Path)->Any:return json.loads(path.read_text(encoding="utf-8"))
def resolve(root:Path,value:Any,label:str)->Path:
    if not isinstance(value,str) or not value:raise ValueError(f"{label} missing")
    p=Path(value);p=p if p.is_absolute() else root/p;p=p.resolve()
    if not p.is_file():raise ValueError(f"{label} not found: {p}")
    return p
def version_tuple(raw:str)->tuple[int,int,int]:
    import re
    m=re.search(r"(\d+)\.(\d+)\.(\d+)",raw)
    if not m:raise ValueError(f"Codex version unparseable: {raw!r}")
    return tuple(map(int,m.groups()))
def selected_binding(spec:dict[str,Any])->dict[str,Any]:
    bindings=((spec.get("treatment") or {}).get("bindings") or {})
    if not isinstance(bindings,dict) or not bindings:raise ValueError("run-spec bindings missing")
    subscription=[b for b in bindings.values() if isinstance(b,dict) and b.get("surface_class")=="SUBSCRIPTION_EXECUTOR_PINNED"]
    if len(subscription)!=1:raise ValueError("preflight requires exactly one selected subscription binding; use per-hop preflight for cascades")
    return subscription[0]
def preflight(spec_path:Path,artifact_root:Path)->dict[str,Any]:
    spec=load(spec_path.resolve())
    if spec.get("schema_id")!="ndv-p1-s2-run-spec-v1" or spec.get("execution_status")!="NOT_EXECUTED":raise ValueError("NOT_EXECUTED P1-S2 run-spec required")
    if spec.get("holdout")!="DEVELOPMENT_ONLY":raise ValueError("development-only run-spec required")
    b=selected_binding(spec)
    bref=resolve(artifact_root,b.get("binding_ref"),"binding_ref");qref=resolve(artifact_root,b.get("qualification_ref"),"qualification_ref");mref=resolve(artifact_root,b.get("evidence_manifest_ref"),"evidence_manifest_ref");sref=resolve(artifact_root,b.get("execution_surface_ref"),"execution_surface_ref")
    for p,key in ((bref,"binding_file_sha256"),(qref,"qualification_file_sha256"),(mref,"evidence_manifest_sha256"),(sref,"execution_surface_file_sha256")):
        if sha_file(p)!=b.get(key):raise ValueError(f"{key} mismatch")
    binding=load(bref);qual=load(qref);surface=load(sref);manifest=load(mref)
    if binding.get("binding_id")!=b.get("binding_id") or binding.get("status")!="QUALIFIED":raise ValueError("binding identity/status mismatch")
    if qual.get("status")!="S0_READY":raise ValueError("qualification is not S0_READY")
    if binding.get("qualification_file_sha256")!=sha_file(qref):raise ValueError("binding->qualification hash mismatch")
    if binding.get("execution_surface_file_sha256")!=sha_file(sref) or qual.get("execution_surface_file_sha256")!=sha_file(sref):raise ValueError("execution-surface chain mismatch")
    if manifest.get("schema_id")!="ndv-p1-wp07-codex-evidence-manifest-v1":raise ValueError("sealed evidence manifest required")
    if surface.get("schema_id")!="ndv-p1-wp07-codex-execution-surface-v1" or surface.get("status")!="PROSPECTIVE_FROZEN_NOT_EXECUTED":raise ValueError("execution surface invalid")
    model=(binding.get("model") or {}).get("identity")
    exe=Path((binding.get("scaffold") or {}).get("executable_path") or "").resolve()
    if not exe.is_file():raise ValueError(f"frozen Codex executable missing: {exe}")
    ver=subprocess.run([str(exe),"--version"],capture_output=True,text=True,check=False,timeout=30)
    raw=(ver.stdout or "")+(ver.stderr or "")
    if ver.returncode!=0:raise ValueError("codex --version failed")
    minimum=tuple(map(int,str(surface["minimum_version"]).split(".")))
    if version_tuple(raw)<minimum:raise ValueError("current Codex version below frozen minimum")
    frozen_version=str((binding.get("scaffold") or {}).get("version") or "")
    if frozen_version and frozen_version not in raw:raise ValueError("current Codex version differs from qualified binding")
    hp=subprocess.run([str(exe),surface["mode"],"--help"],capture_output=True,text=True,check=False,timeout=30)
    help_text=(hp.stdout or "")+(hp.stderr or "")
    if hp.returncode!=0:raise ValueError("codex exec --help failed")
    missing=[f for f in surface["required_flags"] if f not in help_text]
    if missing:raise ValueError(f"current Codex interface missing frozen flags: {missing}")
    argv=[str(exe),surface["mode"],"--model",model,*surface["fixed_flags"],"<FROZEN_TASK_PROMPT>"]
    return {"schema_id":"ndv-p1-wp07-codex-run-preflight-v1","status":"CODEX_RUN_SPEC_PREFLIGHT_PASS","run_id":spec.get("run_id"),"treatment_id":((spec.get("treatment") or {}).get("id")),"binding_id":b.get("binding_id"),"model":model,"execution_surface_ref":b.get("execution_surface_ref"),"execution_surface_file_sha256":b.get("execution_surface_file_sha256"),"codex_version_observed":raw.strip(),"argv_template":argv,"environment_variables_to_remove":surface["environment_variables_removed"],"task_prompt_exposed":False,"treatment_execution":"NOT_EXECUTED","holdout_access":"NONE"}
def main()->int:
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("--run-spec",required=True,type=Path);ap.add_argument("--artifact-root",type=Path,default=Path("."));ap.add_argument("--out",type=Path);args=ap.parse_args()
    try:r=preflight(args.run_spec,args.artifact_root.resolve())
    except (OSError,ValueError,json.JSONDecodeError,subprocess.SubprocessError) as exc:print(json.dumps({"status":"FAIL","reason":"CODEX_RUN_SPEC_PREFLIGHT_BLOCKED","detail":str(exc)},indent=2));return 2
    if args.out:
        if args.out.exists():raise SystemExit(f"refusing overwrite: {args.out}")
        args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(r,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(r,indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
