#!/usr/bin/env python3
"""Release WP-07 development comparison only from completed prerequisite gates.

This gate authorizes development-corpus comparative treatment execution only. It
does not authorize holdout access, executor ranking claims, economic superiority,
or architecture conclusions. Those remain downstream evidence decisions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def release(wp04_path: Path, readiness_path: Path) -> dict[str, Any]:
    wp04_path, readiness_path = wp04_path.resolve(), readiness_path.resolve()
    wp04, readiness = load(wp04_path), load(readiness_path)
    if wp04.get("schema_id") != "ndv-p1-wp04-campaign-closure-v1" or wp04.get("status") != "WP04_PIPELINE_SMOKE_COMPLETE":
        raise ValueError("completed WP-04 campaign closure required")
    integrity = wp04.get("integrity")
    authority = wp04.get("authority")
    if not isinstance(integrity, dict) or integrity.get("raw_evidence_preserved") is not True or integrity.get("treatment_reexecuted") is not False or integrity.get("retries") != 0 or integrity.get("escalations") != 0 or integrity.get("holdout_access") != "NONE":
        raise ValueError("WP-04 closure integrity invalid")
    if not isinstance(authority, dict) or authority.get("pipeline_smoke") != "COMPLETE" or authority.get("comparative_p1_release") != "NO":
        raise ValueError("WP-04 authority state invalid")

    if readiness.get("schema_id") != "ndv-p1-s2-corpus-readiness-assessment-v1" or readiness.get("status") != "WP06_INTAKE_TARGET_REACHED":
        raise ValueError("WP-06 intake target must be reached")
    if readiness.get("comparative_corpus_ready") != "NO" or readiness.get("wp07_release") != "NO":
        raise ValueError("WP-06 readiness input must not self-authorize comparative execution")
    if readiness.get("treatment_execution") != "NOT_EXECUTED" or readiness.get("holdout_access") != "NONE":
        raise ValueError("WP-06 readiness contamination detected")
    checks = readiness.get("checks")
    if not isinstance(checks, dict) or not checks or not all(value is True for value in checks.values()):
        raise ValueError("WP-06 readiness checks are not all satisfied")

    return {
        "schema_id": "ndv-p1-wp07-development-comparison-release-v1",
        "status": "WP07_DEVELOPMENT_COMPARISON_RELEASED",
        "prerequisites": {
            "wp04_closure_ref": str(wp04_path),
            "wp04_closure_sha256": sha_file(wp04_path),
            "wp04_status": wp04.get("status"),
            "wp06_readiness_ref": str(readiness_path),
            "wp06_readiness_sha256": sha_file(readiness_path),
            "wp06_status": readiness.get("status"),
            "combined_task_count": readiness.get("combined_task_count"),
            "s2_admitted_count": readiness.get("s2", {}).get("admitted_count"),
        },
        "authorized_scope": {
            "development_corpus_comparative_treatment_execution": True,
            "sealed_holdout_access": False,
            "holdout_release": False,
            "claim_generation": False,
            "architecture_decision": False,
        },
        "execution_constraints": {
            "use_only_frozen_admission_records": True,
            "preserve_preregistered_treatments": True,
            "preserve_zero_unplanned_fallback": True,
            "record_total_system_cost": True,
            "verified_result_required": True,
        },
        "holdout_access": "NONE",
        "interpretation": "This release permits WP-07 development comparison execution only. Comparative findings and architecture decisions require downstream analysis gates; sealed holdout remains inaccessible.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wp04-closure", required=True, type=Path)
    ap.add_argument("--wp06-readiness", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    try:
        result = release(args.wp04_closure, args.wp06_readiness)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "reason": "WP07_RELEASE_BLOCKED", "detail": str(exc)}, indent=2))
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists():
        raise SystemExit(f"refusing overwrite: {args.out}")
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "out": str(args.out), "holdout_access": "NONE"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
