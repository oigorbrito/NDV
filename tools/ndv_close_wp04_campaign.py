#!/usr/bin/env python3
"""Close WP-04 only from two imported, hash-valid stage evidence bundles.

This tool summarizes pipeline-smoke evidence. It grants no comparative,
routing, economic-superiority, or architecture authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

EXPECTED = {
    "D-F5-01": "ndv-wp04-stage1-run-v1",
    "D-F6-01": "ndv-wp04-stage2-run-v1",
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_import(import_dir: Path, expected_task: str) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = import_dir / "import-manifest.json"
    report_path = import_dir / "run-report.json"
    if not manifest_path.is_file() or not report_path.is_file():
        raise ValueError(f"{expected_task}: import-manifest.json and run-report.json required")
    manifest = load(manifest_path)
    report = load(report_path)
    if manifest.get("schema_id") != "ndv-wp04-import-manifest-v2":
        raise ValueError(f"{expected_task}: import manifest v2 required")
    if manifest.get("task_id") != expected_task or report.get("task_id") != expected_task:
        raise ValueError(f"{expected_task}: task identity mismatch")
    if manifest.get("source_run_schema") != EXPECTED[expected_task] or report.get("schema_id") != EXPECTED[expected_task]:
        raise ValueError(f"{expected_task}: source schema mismatch")
    for key in ("binding_id", "outcome", "retry_count", "escalation_count", "holdout_access"):
        if manifest.get(key) != report.get(key):
            raise ValueError(f"{expected_task}: manifest/report mismatch for {key}")
    if report.get("retry_count") != 0 or report.get("escalation_count") != 0:
        raise ValueError(f"{expected_task}: retry/escalation forbidden")
    if report.get("holdout_access") != "NONE":
        raise ValueError(f"{expected_task}: holdout access forbidden")
    if report.get("outcome") not in {"SMOKE_VALID_SOLVED", "SMOKE_VALID_FAILED", "SMOKE_INCONCLUSIVE"}:
        raise ValueError(f"{expected_task}: invalid outcome")

    records = manifest.get("preserved_artifacts")
    if not isinstance(records, list) or not records:
        raise ValueError(f"{expected_task}: preserved artifact inventory missing")
    for record in records:
        rel = record.get("path")
        if not isinstance(rel, str) or rel == "import-manifest.json":
            raise ValueError(f"{expected_task}: invalid artifact inventory entry")
        path = import_dir / rel
        if not path.is_file():
            raise ValueError(f"{expected_task}: missing preserved artifact {rel}")
        data = path.read_bytes()
        if len(data) != record.get("size_bytes") or sha256_bytes(data) != record.get("sha256"):
            raise ValueError(f"{expected_task}: preserved artifact hash mismatch: {rel}")
    return manifest, report


def token_total(manifest: dict[str, Any]) -> tuple[int | None, bool]:
    reconciliation = manifest.get("token_reconciliation", {})
    total = reconciliation.get("total_tokens")
    approx = reconciliation.get("approximate")
    return (total if isinstance(total, int) else None, bool(approx) if total is not None else False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage1-import", required=True, type=Path)
    ap.add_argument("--stage2-import", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    try:
        m1, r1 = verify_import(args.stage1_import.resolve(), "D-F5-01")
        m2, r2 = verify_import(args.stage2_import.resolve(), "D-F6-01")
    except Exception as exc:
        raise SystemExit(f"WP04_CLOSURE_BLOCKED: {exc}") from exc

    if r1.get("binding_id") != r2.get("binding_id"):
        raise SystemExit("WP04_CLOSURE_BLOCKED: stages used different executor bindings")

    t1, a1 = token_total(m1)
    t2, a2 = token_total(m2)
    token_sum = t1 + t2 if t1 is not None and t2 is not None else None
    wall1 = m1.get("executor_wall_seconds")
    wall2 = m2.get("executor_wall_seconds")
    wall_sum = wall1 + wall2 if isinstance(wall1, (int, float)) and isinstance(wall2, (int, float)) else None

    result = {
        "schema_id": "ndv-p1-wp04-campaign-closure-v1",
        "status": "WP04_PIPELINE_SMOKE_COMPLETE",
        "binding_id": r1.get("binding_id"),
        "stages": [
            {"task_id": "D-F5-01", "outcome": r1.get("outcome"), "failure_attribution": r1.get("failure_attribution")},
            {"task_id": "D-F6-01", "outcome": r2.get("outcome"), "failure_attribution": r2.get("failure_attribution")},
        ],
        "accounting": {
            "stage1_tokens": t1,
            "stage2_tokens": t2,
            "total_tokens": token_sum,
            "token_total_approximate": (a1 or a2) if token_sum is not None else None,
            "stage1_executor_wall_seconds": wall1,
            "stage2_executor_wall_seconds": wall2,
            "total_executor_wall_seconds": wall_sum,
            "missing_telemetry_never_zero": True,
        },
        "integrity": {
            "stage1_import_manifest": str(args.stage1_import / "import-manifest.json"),
            "stage2_import_manifest": str(args.stage2_import / "import-manifest.json"),
            "same_binding_required": True,
            "retries": 0,
            "escalations": 0,
            "holdout_access": "NONE",
        },
        "authority": {
            "pipeline_smoke": "COMPLETE",
            "executor_ranking": "NONE",
            "routing_claim": "NONE",
            "economic_superiority_claim": "NONE",
            "architecture_claim": "NONE",
            "comparative_p1_release": "NO",
        },
        "interpretation": "WP-04 validates the mechanics and evidence chain of one frozen real-executor surface across two smoke tasks. Outcomes are observations of that surface, not comparative evidence.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists():
        raise SystemExit(f"refusing overwrite: {args.out}")
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "out": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
