#!/usr/bin/env python3
"""Produce deterministic NDV S2 admission decisions from derived candidate state + audit evidence."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from typing import Any

SHA256=re.compile(r"^[0-9a-f]{64}$"); DIGEST=re.compile(r"^sha256:[0-9a-f]{64}$")
AUDIT_HASH_FIELDS=("base_run_sha256","oracle_interpretation_sha256","focal_verifier_sha256","preservation_sha256","verifier_provenance_sha256","environment_sha256")
AUDIT_REF_FIELDS=("base_run_ref","oracle_interpretation_ref","focal_verifier_ref","preservation_ref","verifier_provenance_ref","environment_ref")

def load(path:Path)->Any: return json.loads(path.read_text(encoding="utf-8"))
def index_by(items:list[dict[str,Any]],key:str)->dict[str,dict[str,Any]]:
    out={}
    for item in items:
        value=item.get(key)
        if not isinstance(value,str) or not value: raise ValueError(f"missing {key}")
        if value in out: raise ValueError(f"duplicate {key}: {value}")
        out[value]=item
    return out

def decide_candidate(candidate:dict[str,Any],audit:dict[str,Any]|None)->dict[str,Any]:
    cid=candidate["candidate_id"]; blockers=[]
    if candidate.get("quarantine_status")!="PASS": blockers.append("QUARANTINE_NOT_PASS")
    if candidate.get("solution_isolation") not in {"PASS","PROVEN"}: blockers.append("SOLUTION_ISOLATION_NOT_PROVEN")
    if candidate.get("proposed_family") in {None,"","UNASSIGNED_PENDING_SCREEN"}: blockers.append("FAMILY_UNASSIGNED")
    for field in ("task_statement_sha256","ndv_canonical_row_sha256","executor_visible_sha256"):
        value=candidate.get(field)
        if not isinstance(value,str) or not SHA256.fullmatch(value): blockers.append(f"CANDIDATE_{field.upper()}_INVALID")
    for field in ("quarantine_manifest_ref","admission_only_ref","executor_visible_ref"):
        if not isinstance(candidate.get(field),str) or not candidate[field]: blockers.append(f"CANDIDATE_{field.upper()}_MISSING")
    if not isinstance(candidate.get("source_row_index"),int) or candidate["source_row_index"]<0: blockers.append("SOURCE_ROW_INDEX_INVALID")
    if audit is None: blockers.append("AUDIT_RECORD_MISSING")
    else:
        if audit.get("status")!="AUDIT_PASS": blockers.append(f"AUDIT_STATUS_{audit.get('status','MISSING')}")
        if audit.get("quarantine_status")!="PASS": blockers.append("AUDIT_QUARANTINE_NOT_PASS")
        if audit.get("harness_integrity")!="PASS": blockers.append("HARNESS_INTEGRITY_NOT_PASS")
        if audit.get("oracle_classification")!="EXPECTED_BASE_BEHAVIOR": blockers.append("BASE_ORACLE_NOT_EXPECTED")
        if audit.get("base_behavior_matches_expected") is not True: blockers.append("BASE_BEHAVIOR_NOT_CONFIRMED")
        if audit.get("verifier_independent") is not True: blockers.append("VERIFIER_INDEPENDENCE_NOT_PROVEN")
        if audit.get("preservation_baseline_pass") is not True: blockers.append("PRESERVATION_NOT_PASS")
        if audit.get("treatment_execution")!="NOT_EXECUTED": blockers.append("TREATMENT_EXECUTION_CONTAMINATION")
        if audit.get("gold_patch_applied_in_base_mode") is not False: blockers.append("GOLD_PATCH_BASE_CONTAMINATION")
        if audit.get("test_patch_applied_in_base_mode") is not False: blockers.append("TEST_PATCH_BASE_CONTAMINATION")
        digest=audit.get("image_digest")
        if not isinstance(digest,str) or not DIGEST.fullmatch(digest): blockers.append("IMAGE_DIGEST_INVALID")
        for field in AUDIT_HASH_FIELDS:
            value=audit.get(field)
            if not isinstance(value,str) or not SHA256.fullmatch(value): blockers.append(f"AUDIT_{field.upper()}_INVALID")
        for field in AUDIT_REF_FIELDS:
            if not isinstance(audit.get(field),str) or not audit[field]: blockers.append(f"AUDIT_{field.upper()}_MISSING")
    return {"candidate_id":cid,"decision":"ADMIT" if not blockers else "DO_NOT_ADMIT","blockers":blockers,"evidence_refs":{"quarantine_manifest_ref":candidate.get("quarantine_manifest_ref"),"admission_only_ref":candidate.get("admission_only_ref"),"executor_visible_ref":candidate.get("executor_visible_ref"),"base_run_ref":None if audit is None else audit.get("base_run_ref"),"oracle_interpretation_ref":None if audit is None else audit.get("oracle_interpretation_ref"),"focal_verifier_ref":None if audit is None else audit.get("focal_verifier_ref"),"preservation_ref":None if audit is None else audit.get("preservation_ref"),"verifier_provenance_ref":None if audit is None else audit.get("verifier_provenance_ref"),"environment_ref":None if audit is None else audit.get("environment_ref")},"evidence_hashes":{"ndv_canonical_row_sha256":candidate.get("ndv_canonical_row_sha256"),"executor_visible_sha256":candidate.get("executor_visible_sha256"),"task_statement_sha256":candidate.get("task_statement_sha256"),**({} if audit is None else {field:audit.get(field) for field in AUDIT_HASH_FIELDS})}}

def decide(candidate_state:dict[str,Any],audit_state:dict[str,Any])->dict[str,Any]:
    if candidate_state.get("schema_id")!="ndv-p1-s2-candidate-evidence-state-v2": raise ValueError("candidate evidence state v2 required")
    if candidate_state.get("treatment_execution")!="NOT_EXECUTED" or candidate_state.get("holdout_access")!="NONE": raise ValueError("candidate state contaminated")
    candidates,audits=candidate_state.get("candidates"),audit_state.get("audits")
    if not isinstance(candidates,list) or not isinstance(audits,list): raise ValueError("candidate_state.candidates and audit_state.audits must be arrays")
    audit_index=index_by(audits,"candidate_id"); decisions=[decide_candidate(c,audit_index.get(c.get("candidate_id"))) for c in candidates]
    return {"schema_id":"ndv-p1-s2-admission-decisions-v2","wave_id":candidate_state.get("wave_id"),"candidate_state_ref":candidate_state.get("source_candidate_state_ref"),"treatment_execution":"NOT_EXECUTED","holdout_access":"NONE","decisions":decisions,"summary":{"candidate_count":len(decisions),"admit_count":sum(d["decision"]=="ADMIT" for d in decisions),"do_not_admit_count":sum(d["decision"]=="DO_NOT_ADMIT" for d in decisions)}}
def main()->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument("--candidates",required=True,type=Path); ap.add_argument("--audit",required=True,type=Path); ap.add_argument("--out",required=True,type=Path); args=ap.parse_args()
    try: result=decide(load(args.candidates),load(args.audit))
    except (ValueError,OSError,json.JSONDecodeError) as exc: print(json.dumps({"status":"FAIL","reason":"ADMISSION_DECISION_BLOCKED","detail":str(exc)},indent=2)); return 2
    args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps(result["summary"],indent=2,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
