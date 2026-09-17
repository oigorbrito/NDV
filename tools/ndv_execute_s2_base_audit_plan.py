#!/usr/bin/env python3
"""Execute only byte-bound S2 pre-solution base audits from a frozen plan.

This tool performs Docker base-audit execution only. It never calls a model,
never applies solution/test patches, never exposes executor-visible tasks to a
software executor, and never accesses holdout material.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require_file(path: Path, label: str) -> Path:
    p = path.resolve()
    if not p.is_file():
        raise ValueError(f"{label} not found: {p}")
    return p


def validate_plan(plan_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    plan_path = require_file(plan_path, "base-audit plan")
    plan = load(plan_path)
    if not isinstance(plan, dict) or plan.get("schema_id") != "ndv-p1-s2-base-audit-plan-v2":
        raise ValueError("base-audit plan v2 required")
    if plan.get("status") != "AUDIT_PLAN_READY":
        raise ValueError("plan is not ready")
    if plan.get("docker_execution") is not False or plan.get("model_execution") != "NONE":
        raise ValueError("plan provenance invalid")
    if plan.get("treatment_execution") != "NOT_EXECUTED" or plan.get("holdout_access") != "NONE":
        raise ValueError("plan contamination detected")

    for ref_key, hash_key, label in (
        ("wave_ref", "wave_file_sha256", "wave"),
        ("materialization_receipt_ref", "materialization_receipt_file_sha256", "materialization receipt"),
        ("quarantine_aggregate_ref", "quarantine_aggregate_file_sha256", "quarantine aggregate"),
        ("runner_ref", "runner_file_sha256", "base-audit runner"),
    ):
        ref = plan.get(ref_key)
        if not isinstance(ref, str) or not ref:
            raise ValueError(f"plan missing {ref_key}")
        p = require_file(Path(ref), label)
        if sha256_file(p) != plan.get(hash_key):
            raise ValueError(f"{label} hash mismatch")

    entries = plan.get("entries")
    if not isinstance(entries, list) or len(entries) != plan.get("candidate_count"):
        raise ValueError("plan candidate count mismatch")
    ids = [e.get("candidate_id") for e in entries if isinstance(e, dict)]
    if len(ids) != len(entries) or len(ids) != len(set(ids)):
        raise ValueError("plan candidate identities invalid")

    runner = str(Path(plan["runner_ref"]).resolve())
    for entry in entries:
        cid = entry.get("candidate_id")
        if entry.get("authorized_action") != "PRE_SOLUTION_BASE_AUDIT_ONLY":
            raise ValueError(f"{cid}: unauthorized action")
        if entry.get("treatment_execution") != "NOT_EXECUTED" or entry.get("holdout_access") != "NONE":
            raise ValueError(f"{cid}: entry contamination")
        argv = entry.get("argv")
        if not isinstance(argv, list) or len(argv) < 2 or str(Path(argv[1]).resolve()) != runner:
            raise ValueError(f"{cid}: runner argv mismatch")
        admission = require_file(Path(entry["admission_only_ref"]), f"{cid} admission artifact")
        executor = require_file(Path(entry["executor_visible_ref"]), f"{cid} executor artifact")
        integrity = entry.get("artifact_integrity", {})
        if sha256_file(admission) != integrity.get("admission_only_sha256"):
            raise ValueError(f"{cid}: admission artifact hash mismatch")
        if sha256_file(executor) != integrity.get("executor_visible_sha256"):
            raise ValueError(f"{cid}: executor-visible artifact hash mismatch")
    return plan, entries


def execute_entry(entry: dict[str, Any]) -> dict[str, Any]:
    cid = entry["candidate_id"]
    out = Path(entry["audit_out"])
    if out.exists():
        return {"candidate_id": cid, "status": "BLOCKED", "reason": "AUDIT_OUT_EXISTS", "audit_out": str(out)}
    proc = subprocess.run(entry["argv"], text=True, capture_output=True, check=False)
    report = out / "base-audit-run.json"
    result: dict[str, Any] = {
        "candidate_id": cid,
        "runner_returncode": proc.returncode,
        "audit_out": str(out),
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }
    if report.is_file():
        payload = load(report)
        result.update({
            "status": payload.get("status", payload.get("classification", "RECORDED")),
            "classification": payload.get("classification"),
            "harness_integrity": payload.get("harness_integrity"),
            "image_digest": payload.get("image_digest"),
            "report_ref": str(report),
            "report_sha256": sha256_file(report),
        })
    else:
        result["status"] = "NO_REPORT"
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", required=True, type=Path)
    ap.add_argument("--candidate-id", action="append", dest="candidate_ids", help="Optional exact candidate id; repeatable. Default: all plan entries in frozen order.")
    ap.add_argument("--receipt", type=Path, default=Path(".ndv-corpus/s2-w01/base-audit-execution-receipt.json"))
    args = ap.parse_args()
    try:
        plan, entries = validate_plan(args.plan)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "reason": "BASE_AUDIT_EXECUTION_BLOCKED", "detail": str(exc)}, indent=2))
        return 2

    if args.candidate_ids:
        requested = args.candidate_ids
        if len(requested) != len(set(requested)):
            print(json.dumps({"status": "FAIL", "reason": "DUPLICATE_CANDIDATE_SELECTION"}, indent=2)); return 2
        by_id = {e["candidate_id"]: e for e in entries}
        missing = [cid for cid in requested if cid not in by_id]
        if missing:
            print(json.dumps({"status": "FAIL", "reason": "CANDIDATE_NOT_IN_PLAN", "missing": missing}, indent=2)); return 2
        selected = [e for e in entries if e["candidate_id"] in set(requested)]
    else:
        selected = entries

    results = [execute_entry(entry) for entry in selected]
    receipt = {
        "schema_id": "ndv-p1-s2-base-audit-execution-receipt-v1",
        "status": "BASE_AUDIT_BATCH_RECORDED",
        "plan_ref": str(args.plan.resolve()),
        "plan_file_sha256": sha256_file(args.plan.resolve()),
        "wave_id": plan.get("wave_id"),
        "selected_candidate_ids": [e["candidate_id"] for e in selected],
        "results": results,
        "docker_execution": True,
        "model_execution": "NONE",
        "treatment_execution": "NOT_EXECUTED",
        "holdout_access": "NONE",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    if args.receipt.exists():
        raise SystemExit(f"refusing overwrite: {args.receipt}")
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "receipt": str(args.receipt), "results": [{"candidate_id": r["candidate_id"], "status": r["status"]} for r in results]}, indent=2))
    return 0 if all(r.get("report_ref") for r in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
