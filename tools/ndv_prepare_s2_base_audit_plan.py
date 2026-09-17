#!/usr/bin/env python3
"""Prepare a byte-bound S2 base-audit plan without executing Docker.

Consumes one completed materialization receipt plus quarantine artifacts. It
revalidates wave/quarantine identity and the admission/executor projections for
every candidate, then freezes the exact ndv_run_s2_base_audit.py invocation that
may be executed later. No image pull, Docker run, model call, treatment, or
holdout access occurs here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
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


def canonical_sha(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def task_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require_file(path: Path, label: str) -> Path:
    p = path.resolve()
    if not p.is_file():
        raise ValueError(f"{label} not found: {p}")
    return p


def verify_materialization(receipt_path: Path, wave_path: Path) -> tuple[dict[str, Any], dict[str, Any], Path]:
    receipt_path = require_file(receipt_path, "materialization receipt")
    wave_path = require_file(wave_path, "wave")
    receipt, wave = load(receipt_path), load(wave_path)
    if not isinstance(receipt, dict) or receipt.get("schema_id") != "ndv-p1-s2-wave-materialization-receipt-v2":
        raise ValueError("materialization receipt v2 required")
    if receipt.get("status") != "MATERIALIZED_QUARANTINED":
        raise ValueError("materialization receipt is not terminal/pass")
    if receipt.get("treatment_execution") != "NOT_EXECUTED" or receipt.get("holdout_access") != "NONE":
        raise ValueError("materialization receipt is treatment/holdout contaminated")
    if receipt.get("model_execution") != "NONE" or receipt.get("docker_execution") is not False:
        raise ValueError("materialization phase must not contain model/Docker execution")
    if receipt.get("wave_id") != wave.get("wave_id") or receipt.get("wave_file_sha256") != sha256_file(wave_path):
        raise ValueError("materialization receipt/wave binding mismatch")
    aggregate_ref = receipt.get("quarantine_aggregate_ref")
    if not isinstance(aggregate_ref, str) or not aggregate_ref:
        raise ValueError("materialization receipt missing quarantine aggregate ref")
    aggregate_path = require_file(Path(aggregate_ref), "quarantine aggregate")
    if receipt.get("quarantine_aggregate_file_sha256") != sha256_file(aggregate_path):
        raise ValueError("quarantine aggregate hash mismatch")
    return receipt, wave, aggregate_path


def verify_candidate_artifacts(manifest: dict[str, Any], candidate: dict[str, Any]) -> tuple[Path, Path, dict[str, Any]]:
    cid = candidate.get("candidate_id")
    if manifest.get("candidate_id") != cid or manifest.get("status") != "PASS":
        raise ValueError(f"{cid}: quarantine manifest identity/status mismatch")
    if manifest.get("treatment_execution") != "NOT_EXECUTED" or manifest.get("holdout_access") != "NONE":
        raise ValueError(f"{cid}: quarantine manifest contaminated")
    if manifest.get("source_row_index") != candidate.get("source_row_index") or manifest.get("source_instance_id") != candidate.get("source_instance_id"):
        raise ValueError(f"{cid}: quarantine source identity mismatch")

    admission_ref, executor_ref = manifest.get("admission_only_ref"), manifest.get("executor_visible_ref")
    if not isinstance(admission_ref, str) or not isinstance(executor_ref, str):
        raise ValueError(f"{cid}: quarantine artifact refs missing")
    admission_path = require_file(Path(admission_ref), f"{cid} admission-only artifact")
    executor_path = require_file(Path(executor_ref), f"{cid} executor-visible artifact")
    admission, executor = load(admission_path), load(executor_path)
    if admission.get("schema_id") != "ndv-p1-s2-admission-only-row-v1" or admission.get("candidate_id") != cid:
        raise ValueError(f"{cid}: admission artifact schema/identity mismatch")
    if executor.get("schema_id") != "ndv-p1-s2-executor-visible-row-v1" or executor.get("candidate_id") != cid:
        raise ValueError(f"{cid}: executor artifact schema/identity mismatch")

    row, source = admission.get("full_row"), admission.get("source")
    task, binding = executor.get("task"), executor.get("source_binding")
    if not isinstance(row, dict) or not isinstance(source, dict) or not isinstance(task, dict) or not isinstance(binding, dict):
        raise ValueError(f"{cid}: malformed quarantine artifacts")
    raw_sha = canonical_sha(row)
    if raw_sha != source.get("ndv_canonical_row_sha256") or raw_sha != manifest.get("ndv_canonical_row_sha256") or raw_sha != binding.get("ndv_canonical_row_sha256"):
        raise ValueError(f"{cid}: raw row hash binding mismatch")
    if row.get("instance_id") != candidate.get("source_instance_id") or row.get("repo") != candidate.get("repository") or row.get("base_commit") != candidate.get("base_revision"):
        raise ValueError(f"{cid}: full row identity mismatch")
    statement = task.get("problem_statement")
    if not isinstance(statement, str) or not statement.strip():
        raise ValueError(f"{cid}: executor task missing problem statement")
    if task_sha(statement) != executor.get("task_statement_sha256") or task_sha(statement) != manifest.get("task_statement_sha256"):
        raise ValueError(f"{cid}: task statement hash mismatch")
    if canonical_sha(task) != executor.get("executor_visible_sha256") or canonical_sha(task) != manifest.get("executor_visible_sha256"):
        raise ValueError(f"{cid}: executor projection hash mismatch")
    if binding.get("source_row_index") != candidate.get("source_row_index") or binding.get("dataset_revision") is None:
        raise ValueError(f"{cid}: executor source binding mismatch")

    observed = {
        "admission_only_sha256": sha256_file(admission_path),
        "executor_visible_sha256": sha256_file(executor_path),
        "raw_row_sha256": raw_sha,
        "task_statement_sha256": task_sha(statement),
        "executor_projection_sha256": canonical_sha(task),
    }
    return admission_path, executor_path, observed


def build_plan(receipt_path: Path, wave_path: Path, audit_root: Path, runner: Path) -> dict[str, Any]:
    receipt, wave, aggregate_path = verify_materialization(receipt_path, wave_path)
    aggregate = load(aggregate_path)
    if not isinstance(aggregate, dict) or aggregate.get("schema_id") != "ndv-p1-s2-quarantine-aggregate-v2":
        raise ValueError("unexpected quarantine aggregate schema")
    if aggregate.get("wave_id") != wave.get("wave_id"):
        raise ValueError("quarantine aggregate wave mismatch")
    manifests = aggregate.get("manifests")
    candidates = wave.get("candidates")
    if not isinstance(manifests, list) or not isinstance(candidates, list):
        raise ValueError("wave/quarantine candidate lists missing")
    if aggregate.get("candidate_count") != len(candidates) or aggregate.get("passed_count") != len(candidates):
        raise ValueError("quarantine aggregate does not represent all candidates as PASS")
    manifest_by_id = {m.get("candidate_id"): m for m in manifests if isinstance(m, dict)}
    candidate_ids = [c.get("candidate_id") for c in candidates if isinstance(c, dict)]
    if len(candidate_ids) != len(set(candidate_ids)) or set(manifest_by_id) != set(candidate_ids):
        raise ValueError("wave/quarantine candidate set mismatch")

    runner = runner.resolve()
    entries: list[dict[str, Any]] = []
    for candidate in candidates:
        cid = candidate["candidate_id"]
        admission_path, executor_path, observed = verify_candidate_artifacts(manifest_by_id[cid], candidate)
        out_dir = (audit_root / cid).resolve()
        argv = [
            sys.executable,
            str(runner),
            "--wave", str(wave_path.resolve()),
            "--candidate-id", cid,
            "--admission-row", str(admission_path),
            "--out", str(out_dir),
        ]
        entries.append({
            "candidate_id": cid,
            "source_instance_id": candidate.get("source_instance_id"),
            "repository": candidate.get("repository"),
            "base_revision": candidate.get("base_revision"),
            "language": candidate.get("language"),
            "image_ref": candidate.get("image_ref"),
            "image_digest": None,
            "image_digest_state": "RESOLVE_AT_BASE_AUDIT_THEN_RECORD_IMMUTABLE_REPODIGEST",
            "admission_only_ref": str(admission_path),
            "executor_visible_ref": str(executor_path),
            "artifact_integrity": observed,
            "audit_out": str(out_dir),
            "argv": argv,
            "authorized_action": "PRE_SOLUTION_BASE_AUDIT_ONLY",
            "treatment_execution": "NOT_EXECUTED",
            "holdout_access": "NONE",
        })

    return {
        "schema_id": "ndv-p1-s2-base-audit-plan-v1",
        "status": "AUDIT_PLAN_READY",
        "wave_id": wave.get("wave_id"),
        "wave_ref": str(wave_path.resolve()),
        "wave_file_sha256": sha256_file(wave_path.resolve()),
        "materialization_receipt_ref": str(receipt_path.resolve()),
        "materialization_receipt_file_sha256": sha256_file(receipt_path.resolve()),
        "quarantine_aggregate_ref": str(aggregate_path),
        "quarantine_aggregate_file_sha256": sha256_file(aggregate_path),
        "candidate_count": len(entries),
        "entries": entries,
        "docker_execution": False,
        "model_execution": "NONE",
        "treatment_execution": "NOT_EXECUTED",
        "holdout_access": "NONE",
        "prepared_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--materialization-receipt", required=True, type=Path)
    ap.add_argument("--wave", type=Path, default=Path("experiments/p1/s2-candidate-wave-01.json"))
    ap.add_argument("--audit-root", type=Path, default=Path(".ndv-corpus/s2-w01/base-audits"))
    ap.add_argument("--runner", type=Path, default=Path("tools/ndv_run_s2_base_audit.py"))
    ap.add_argument("--out", type=Path, default=Path(".ndv-corpus/s2-w01/base-audit-plan.json"))
    args = ap.parse_args()
    try:
        plan = build_plan(args.materialization_receipt, args.wave, args.audit_root, args.runner)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "reason": "BASE_AUDIT_PLAN_BLOCKED", "detail": str(exc)}, indent=2))
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists():
        raise SystemExit(f"refusing overwrite: {args.out}")
    args.out.write_text(json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": plan["status"], "out": str(args.out), "candidate_count": plan["candidate_count"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
