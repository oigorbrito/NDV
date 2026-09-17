#!/usr/bin/env python3
"""Report concrete blockers before WP-07 run-matrix materialization.

This is diagnostic only. Missing evidence is reported as a blocker, never as an
experimental failure or zero cost. No model, Docker treatment, holdout, or task
execution occurs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import ndv_assess_wp07_binding_readiness as binding_readiness
import ndv_materialize_wp07_run_matrix as matrix


def load_if_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file(): return None
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else None


def assess(args: argparse.Namespace) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    checks: dict[str, Any] = {}

    protocol = load_if_file(args.protocol.resolve())
    checks["protocol"] = "PASS" if protocol and protocol.get("schema_id") == "ndv-p1-wp07-development-comparison-protocol-v1" else "BLOCKED"
    if checks["protocol"] != "PASS": blockers.append({"gate":"WP07_PROTOCOL","reason":"frozen comparison protocol unavailable/invalid"})

    binding_import = args.wp04_binding_import.resolve()
    receipt = load_if_file(binding_import / "binding-import-receipt.json")
    q = binding_import / "qualification-evidence.json"
    b = binding_import / "executor-binding-v2.json"
    binding_import_ok = bool(receipt and receipt.get("schema_id") == "ndv-wp04-binding-import-receipt-v2" and receipt.get("status") == "ORIGINAL_BINDING_AND_QUALIFICATION_PRESERVED" and q.is_file() and b.is_file())
    checks["wp04_original_binding_import"] = "PASS" if binding_import_ok else "BLOCKED"
    if not binding_import_ok: blockers.append({"gate":"WP04_BINDING_IMPORT","reason":"original binding + qualification evidence not yet preserved with receipt v2"})

    closure = load_if_file(args.wp04_closure.resolve())
    closure_ok = bool(closure and closure.get("schema_id") == "ndv-p1-wp04-campaign-closure-v1" and closure.get("status") == "WP04_PIPELINE_SMOKE_COMPLETE")
    checks["wp04_campaign_closure"] = "PASS" if closure_ok else "BLOCKED"
    if not closure_ok: blockers.append({"gate":"WP04_CLOSURE","reason":"WP-04 Stage 2/import/closure not complete"})

    readiness = load_if_file(args.wp06_readiness.resolve())
    readiness_ok = bool(readiness and readiness.get("schema_id") == "ndv-p1-s2-corpus-readiness-assessment-v1" and readiness.get("status") == "WP06_INTAKE_TARGET_REACHED")
    checks["wp06_intake_readiness"] = "PASS" if readiness_ok else "BLOCKED"
    if not readiness_ok: blockers.append({"gate":"WP06_READINESS","reason":"prospective S2 admissions have not yet reached the intake target"})

    release = load_if_file(args.wp07_release.resolve())
    release_ok = bool(release and release.get("schema_id") == "ndv-p1-wp07-development-comparison-release-v1" and release.get("status") == "WP07_DEVELOPMENT_COMPARISON_RELEASED")
    checks["wp07_development_release"] = "PASS" if release_ok else "BLOCKED"
    if not release_ok: blockers.append({"gate":"WP07_RELEASE","reason":"development comparison release artifact not yet emitted"})

    try:
        binding = binding_readiness.assess(args.bindings.resolve(), args.artifact_root.resolve())
        checks["binding_coverage"] = binding["status"]
        if not binding.get("all_treatments_ready"):
            missing = {k:v.get("missing_roles") for k,v in binding.get("treatments",{}).items() if not v.get("ready")}
            blockers.append({"gate":"WP07_BINDING_COVERAGE","reason":json.dumps(missing, sort_keys=True)})
    except Exception as exc:
        checks["binding_coverage"] = "BLOCKED_INVALID"
        blockers.append({"gate":"WP07_BINDING_COVERAGE","reason":str(exc)})

    admissions=[]
    for p in args.admission_record:
        try: admissions.append(matrix.verify_admission(p.resolve()))
        except Exception as exc: blockers.append({"gate":"WP06_ADMISSION_RECORD","reason":f"{p}: {exc}"})
    checks["admission_records_supplied"] = len(admissions)
    if not admissions: blockers.append({"gate":"WP06_ADMISSION_RECORDS","reason":"no ADMITTED_FROZEN records supplied to preflight"})

    ready = not blockers
    return {
        "schema_id":"ndv-p1-wp07-preflight-v1",
        "status":"READY_TO_MATERIALIZE_RUN_MATRIX" if ready else "BLOCKED_ON_EMPIRICAL_PREREQUISITES",
        "checks":checks,
        "blockers":blockers,
        "blocker_count":len(blockers),
        "treatment_execution":"NOT_EXECUTED",
        "holdout_access":"NONE",
        "blocked_is_not_failure":True,
        "blocked_cost_is_not_zero":True,
    }


def main()->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--protocol",type=Path,default=Path("experiments/p1/wp07-development-comparison-protocol-v1.json"))
    ap.add_argument("--bindings",type=Path,default=Path("experiments/p1/wp07-treatment-bindings-v1.json"))
    ap.add_argument("--artifact-root",type=Path,default=Path("."))
    ap.add_argument("--wp04-binding-import",type=Path,default=Path("pilot-runs/wp04-real-executor-smoke/binding-stage1"))
    ap.add_argument("--wp04-closure",type=Path,default=Path("pilot-runs/wp04-real-executor-smoke/campaign-closure.json"))
    ap.add_argument("--wp06-readiness",type=Path,default=Path(".ndv-corpus/s2-w01/corpus-readiness.json"))
    ap.add_argument("--wp07-release",type=Path,default=Path(".ndv-corpus/s2-w01/wp07-development-release.json"))
    ap.add_argument("--admission-record",action="append",default=[],type=Path)
    ap.add_argument("--out",type=Path)
    args=ap.parse_args()
    try: result=assess(args)
    except (OSError,ValueError,json.JSONDecodeError) as exc:
        print(json.dumps({"status":"FAIL","reason":"WP07_PREFLIGHT_INVALID","detail":str(exc)},indent=2)); return 2
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        if args.out.exists(): raise SystemExit(f"refusing overwrite: {args.out}")
        args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0


if __name__=="__main__": raise SystemExit(main())
