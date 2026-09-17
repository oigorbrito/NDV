#!/usr/bin/env python3
"""Verify one WP-07 Codex single-hop candidate in the immutable audited image.

This is deliberately separate from executor invocation. It consumes a pending
executor-stage report, reapplies only candidate.diff to a fresh container from
the exact WP-06 audited image, runs the frozen test commands with network none,
parses results using the frozen SWE-rebench parser, and emits YES/NO/INCONCLUSIVE.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ndv_build_s2_verifier_evidence import sha256 as semantic_sha
from ndv_interpret_s2_base_oracle import import_parser, normalize, verify_upstream

VERIFY_TOKEN = "P1S2_VERIFY_FROZEN_DEVELOPMENT_RUN"
PASS = "PASSED"


def utc_now()->str:return datetime.now(timezone.utc).isoformat()
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
def run(argv:list[str],timeout:float|None=None)->subprocess.CompletedProcess[str]:
    return subprocess.run(argv,capture_output=True,text=True,check=False,timeout=timeout)

def verify_sources(executor_report_path:Path,artifact_root:Path)->dict[str,Any]:
    report=load(executor_report_path.resolve())
    if report.get("schema_id")!="ndv-p1-wp07-codex-single-hop-run-v1":raise ValueError("Codex single-hop executor report required")
    cls=report.get("classification") or {}
    if cls.get("pending_verification") is not True or cls.get("verified_solved_task")!="PENDING_VERIFICATION":raise ValueError("executor stage is not pending verification")
    if report.get("holdout_access")!="NONE":raise ValueError("executor report holdout contamination")
    source=report.get("source_chain") or {}
    run_spec=resolve(artifact_root,source.get("run_spec_ref"),"run_spec_ref")
    if sha_file(run_spec)!=source.get("run_spec_file_sha256"):raise ValueError("run-spec hash mismatch")
    spec=load(run_spec)
    if spec.get("schema_id")!="ndv-p1-s2-run-spec-v1" or spec.get("holdout")!="DEVELOPMENT_ONLY":raise ValueError("development P1-S2 run-spec required")
    if report.get("run_id")!=spec.get("run_id") or report.get("treatment_id")!=((spec.get("treatment") or {}).get("id")):raise ValueError("executor report/run-spec identity mismatch")
    candidate=report.get("candidate") or {}
    diff=resolve(executor_report_path.parent,candidate.get("diff_ref"),"candidate.diff")
    if sha_file(diff)!=candidate.get("diff_sha256") or diff.stat().st_size!=candidate.get("diff_bytes"):raise ValueError("candidate diff hash/size mismatch")
    task=spec.get("task") or {}
    admission=resolve(artifact_root,task.get("admission_record_ref"),"admission_record_ref")
    if sha_file(admission)!=task.get("admission_record_file_sha256"):raise ValueError("admission record file hash mismatch")
    ar=load(admission)
    if ar.get("record_sha256")!=task.get("admission_record_sha256") or ar.get("candidate_id")!=task.get("task_id"):raise ValueError("admission semantic/identity mismatch")
    audit=ar.get("audit") or {}
    base_run=resolve(artifact_root,audit.get("base_run_ref"),"base_run_ref")
    if sha_file(base_run)!=audit.get("base_run_sha256"):raise ValueError("base-run hash mismatch")
    base=load(base_run)
    if base.get("schema_id")!="ndv-p1-s2-base-audit-run-v2" or base.get("harness_integrity")!="PASS":raise ValueError("harness-valid base run required")
    if base.get("base_revision")!=task.get("base_sha") or base.get("repository")!=task.get("repository"):raise ValueError("base-run task identity mismatch")
    if base.get("network")!="none" or base.get("gold_patch_applied") is not False or base.get("test_patch_applied") is not False:raise ValueError("base-run contamination")
    focal=resolve(artifact_root,(spec.get("oracle") or {}).get("focal_verifier_ref"),"focal_verifier_ref")
    preservation=resolve(artifact_root,(spec.get("oracle") or {}).get("preservation_ref"),"preservation_ref")
    fp,pp=load(focal),load(preservation)
    if semantic_sha(fp)!=(spec.get("oracle") or {}).get("focal_verifier_sha256"):raise ValueError("focal verifier semantic hash mismatch")
    if semantic_sha(pp)!=(spec.get("oracle") or {}).get("preservation_sha256"):raise ValueError("preservation verifier semantic hash mismatch")
    if fp.get("schema_id")!="ndv-p1-s2-focal-verifier-v2" or pp.get("schema_id")!="ndv-p1-s2-preservation-verifier-v2":raise ValueError("frozen verifier v2 artifacts required")
    if fp.get("base_commit")!=task.get("base_sha") or pp.get("base_commit")!=task.get("base_sha") or fp.get("repository")!=task.get("repository") or pp.get("repository")!=task.get("repository"):raise ValueError("verifier task identity mismatch")
    if fp.get("parser")!=pp.get("parser"):raise ValueError("focal/preservation parser provenance mismatch")
    return {"report":report,"spec":spec,"run_spec_path":run_spec,"diff":diff,"admission":ar,"admission_path":admission,"base":base,"base_run_path":base_run,"focal":fp,"focal_path":focal,"preservation":pp,"preservation_path":preservation}

def build_script(base_sha:str,commands:list[str])->str:
    lines=[
        "set +e",
        "observed_head=$(git rev-parse HEAD 2>/dev/null)",
        'printf "__NDV_HEAD__=%s\\n" "$observed_head"',
        f"if [ \"$observed_head\" != {shlex.quote(base_sha)} ]; then exit 90; fi",
        'if [ -z "$(git status --porcelain=v1)" ]; then echo __NDV_CLEAN__=YES; else echo __NDV_CLEAN__=NO; exit 91; fi',
        "apply_rc=0",
        "if [ -s /tmp/ndv-candidate.diff ]; then git apply --check /tmp/ndv-candidate.diff; apply_rc=$?; if [ \"$apply_rc\" -eq 0 ]; then git apply --whitespace=nowarn /tmp/ndv-candidate.diff; apply_rc=$?; fi; fi",
        'printf "__NDV_APPLY_RC__=%s\\n" "$apply_rc"',
        'if [ "$apply_rc" -ne 0 ]; then exit 92; fi',
        "overall=0",
    ]
    for idx,command in enumerate(commands,1):
        lines += [f"eval {shlex.quote(command)}","rc=$?",f'printf "__NDV_CMD_{idx}_RC__=%s\\n" "$rc"','if [ "$rc" -ne 0 ]; then overall=1; fi']
    lines.append('exit "$overall"')
    return "\n".join(lines)

def parse_markers(stdout:str,count:int)->dict[str,Any]:
    import re
    hm=re.search(r"^__NDV_HEAD__=([0-9a-f]{40})$",stdout,re.M);cm=re.search(r"^__NDV_CLEAN__=(YES|NO)$",stdout,re.M);am=re.search(r"^__NDV_APPLY_RC__=(\d+)$",stdout,re.M)
    found={int(i):int(rc) for i,rc in re.findall(r"^__NDV_CMD_(\d+)_RC__=(\d+)$",stdout,re.M)}
    return {"head":hm.group(1) if hm else None,"clean":cm.group(1)=="YES" if cm else None,"apply_rc":int(am.group(1)) if am else None,"command_returncodes":[found.get(i) for i in range(1,count+1)],"all_command_markers_present":set(found)==set(range(1,count+1))}
def execute_candidate(image_digest:str,workdir:str,base_sha:str,commands:list[str],diff:Path,timeout_seconds:float)->dict[str,Any]:
    inspect=run(["docker","image","inspect",image_digest,"--format","{{.Id}}"],timeout=30)
    if inspect.returncode!=0 or not inspect.stdout.strip():raise ValueError(f"immutable verifier image unavailable: {image_digest}")
    script=build_script(base_sha,commands)
    create=run(["docker","create","--network","none","-w",workdir,"--entrypoint","/bin/bash",image_digest,"-lc",script],timeout=60)
    if create.returncode!=0 or not create.stdout.strip():raise ValueError("docker create failed")
    cid=create.stdout.strip().splitlines()[-1]
    try:
        cp=run(["docker","cp",str(diff),f"{cid}:/tmp/ndv-candidate.diff"],timeout=120)
        if cp.returncode!=0:raise ValueError("docker cp candidate diff failed")
        t0=time.monotonic()
        try:
            proc=run(["docker","start","-a",cid],timeout=timeout_seconds);timed_out=False;stdout,stderr,rc=proc.stdout or "",proc.stderr or "",proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out=True;stdout=exc.stdout or "";stderr=exc.stderr or "";rc=124
            if isinstance(stdout,bytes):stdout=stdout.decode("utf-8",errors="replace")
            if isinstance(stderr,bytes):stderr=stderr.decode("utf-8",errors="replace")
        duration=time.monotonic()-t0
    finally:
        run(["docker","rm","-f",cid],timeout=30)
    return {"returncode":rc,"timed_out":timed_out,"duration_seconds":duration,"stdout":stdout,"stderr":stderr,"markers":parse_markers(stdout,len(commands)),"script_sha256":hashlib.sha256(script.encode()).hexdigest()}
def evaluate(parsed:dict[str,str],focal:dict[str,Any],preservation:dict[str,Any])->dict[str,Any]:
    normalized={normalize(str(k)):str(v) for k,v in parsed.items()}
    focal_tests=[normalize(str(x)) for x in focal.get("tests",[])];pres_tests=[normalize(str(x)) for x in preservation.get("tests",[])]
    if not focal_tests: return {"outcome":"INCONCLUSIVE","failure_attribution":"ORACLE_DEFECT","reason":"focal verifier has no tests","focal":[],"preservation":[]}
    fobs=[{"test":t,"observed":normalized.get(t)} for t in focal_tests];pobs=[{"test":t,"observed":normalized.get(t)} for t in pres_tests]
    missing=[x["test"] for x in fobs+pobs if x["observed"] is None]
    if not normalized:return {"outcome":"INCONCLUSIVE","failure_attribution":"INCONCLUSIVE_OTHER","reason":"parser produced no test results","focal":fobs,"preservation":pobs,"missing":missing}
    if missing:return {"outcome":"INCONCLUSIVE","failure_attribution":"INCONCLUSIVE_OTHER","reason":"one or more frozen verifier tests absent from parsed candidate evidence","focal":fobs,"preservation":pobs,"missing":missing}
    failures=[x for x in fobs+pobs if x["observed"]!=PASS]
    if failures:return {"outcome":"NO","failure_attribution":"PRODUCT_FAILURE","reason":"one or more frozen focal/preservation tests did not pass","focal":fobs,"preservation":pobs,"failures":failures}
    return {"outcome":"YES","failure_attribution":None,"reason":"all frozen focal and preservation tests passed","focal":fobs,"preservation":pobs,"failures":[]}
def verify(executor_report_path:Path,artifact_root:Path,upstream_root:Path,out_dir:Path,verify_token:str)->dict[str,Any]:
    if verify_token!=VERIFY_TOKEN:raise ValueError("explicit frozen development verification token required")
    if out_dir.exists():raise ValueError(f"out-dir exists; refusing overwrite: {out_dir}")
    src=verify_sources(executor_report_path.resolve(),artifact_root.resolve())
    upstream=verify_upstream(upstream_root.resolve());parser_meta=src["focal"].get("parser") or {}
    if upstream.get("revision")!=parser_meta.get("revision") or upstream.get("log_parsers_sha256")!=parser_meta.get("content_sha256"):raise ValueError("frozen parser provenance mismatch")
    parser=import_parser(upstream_root.resolve(),parser_meta.get("name"))
    base=src["base"];commands=base.get("test_commands")
    if not isinstance(commands,list) or not commands or not all(isinstance(x,str) and x for x in commands):raise ValueError("base run frozen test commands required")
    image=base.get("image_digest");workdir=base.get("workdir")
    budget=src["spec"].get("budgets") or {};remaining=max(1.0,(budget.get("run_timeout_ms",0)-budget.get("executor_timeout_ms",0))/1000.0)
    started=utc_now();result=execute_candidate(image,workdir,src["spec"]["task"]["base_sha"],commands,src["diff"],remaining);completed=utc_now()
    markers=result["markers"]
    harness_ok=markers["head"]==src["spec"]["task"]["base_sha"] and markers["clean"] is True and markers["apply_rc"]==0 and markers["all_command_markers_present"]
    if result["timed_out"]:
        decision={"outcome":"INCONCLUSIVE","failure_attribution":"RESOURCE_LIMIT","reason":"verification run exceeded frozen remaining run budget"}
    elif not harness_ok:
        if markers.get("head")==src["spec"]["task"]["base_sha"] and markers.get("clean") is True and markers.get("apply_rc") not in (None,0):decision={"outcome":"NO","failure_attribution":"PRODUCT_FAILURE","reason":"candidate diff did not apply to exact frozen base"}
        else:decision={"outcome":"INCONCLUSIVE","failure_attribution":"HARNESS_FAILURE","reason":"verification harness integrity markers invalid"}
    else:
        parsed_raw=parser(result["stdout"])
        if not isinstance(parsed_raw,dict):decision={"outcome":"INCONCLUSIVE","failure_attribution":"ORACLE_DEFECT","reason":"frozen parser returned non-object"}
        else:decision=evaluate(parsed_raw,src["focal"],src["preservation"])
    out_dir.mkdir(parents=True);stdout_path=out_dir/"verifier.stdout.log";stderr_path=out_dir/"verifier.stderr.log";stdout_path.write_text(result["stdout"],encoding="utf-8");stderr_path.write_text(result["stderr"],encoding="utf-8")
    report={"schema_id":"ndv-p1-wp07-single-hop-verification-v1","run_id":src["report"]["run_id"],"task_id":src["report"]["task_id"],"treatment_id":src["report"]["treatment_id"],"verified_solved_task":decision["outcome"],"failure_attribution":decision.get("failure_attribution"),"reason":decision["reason"],"decision_evidence":decision,"verification":{"started_at":started,"completed_at":completed,"wall_seconds":result["duration_seconds"],"returncode":result["returncode"],"timed_out":result["timed_out"],"harness_integrity":"PASS" if harness_ok else "FAIL","markers":markers,"image_digest":image,"network":"none","workdir":workdir,"test_commands":commands,"parser":parser_meta},"executor_accounting":src["report"].get("accounting"),"executor_usage":src["report"].get("usage"),"raw_evidence":{"stdout_ref":str(stdout_path),"stdout_sha256":sha_file(stdout_path),"stderr_ref":str(stderr_path),"stderr_sha256":sha_file(stderr_path),"candidate_diff_ref":str(src["diff"]),"candidate_diff_sha256":sha_file(src["diff"])},"source_chain":{"executor_report_ref":str(executor_report_path.resolve()),"executor_report_file_sha256":sha_file(executor_report_path.resolve()),"run_spec_ref":str(src["run_spec_path"]),"run_spec_file_sha256":sha_file(src["run_spec_path"]),"base_run_ref":str(src["base_run_path"]),"base_run_file_sha256":sha_file(src["base_run_path"]),"focal_verifier_ref":str(src["focal_path"]),"preservation_ref":str(src["preservation_path"])},"cost_retained":True,"treatment_execution":"COMPLETE_SINGLE_HOP","holdout_access":"NONE"}
    report_path=out_dir/"verification-report.json";report_path.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return report
def main()->int:
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("--executor-report",required=True,type=Path);ap.add_argument("--artifact-root",type=Path,default=Path("."));ap.add_argument("--upstream-root",required=True,type=Path);ap.add_argument("--out-dir",required=True,type=Path);ap.add_argument("--verify-token",required=True);args=ap.parse_args()
    try:r=verify(args.executor_report,args.artifact_root,args.upstream_root,args.out_dir.resolve(),args.verify_token)
    except (OSError,ValueError,json.JSONDecodeError,subprocess.SubprocessError) as exc:print(json.dumps({"status":"FAIL","reason":"CODEX_SINGLE_HOP_VERIFICATION_BLOCKED","detail":str(exc)},indent=2));return 2
    print(json.dumps({"status":"VERIFICATION_COMPLETE","run_id":r["run_id"],"verified_solved_task":r["verified_solved_task"],"failure_attribution":r["failure_attribution"]},indent=2));return 0 if r["verified_solved_task"] in {"YES","NO"} else 3
if __name__=="__main__":raise SystemExit(main())
