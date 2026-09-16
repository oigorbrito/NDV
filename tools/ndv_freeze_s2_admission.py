#!/usr/bin/env python3
"""Freeze one NDV S2 admission decision into an immutable admission record.

Discovery history is not rewritten. A candidate is considered admitted only when
this tool receives an explicit ADMIT decision and the referenced audit is AUDIT_PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def find(items: list[dict[str, Any]], cid: str, key: str = "candidate_id") -> dict[str, Any]:
    matches = [x for x in items if x.get(key) == cid]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {key}={cid}, found {len(matches)}")
    return matches[0]


def freeze(candidate: dict[str, Any], audit: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    cid = candidate.get("candidate_id")
    if not isinstance(cid, str) or not cid:
        raise ValueError("candidate_id missing")
    if decision.get("candidate_id") != cid or audit.get("candidate_id") != cid:
        raise ValueError("candidate/audit/decision identity mismatch")
    if decision.get("decision") != "ADMIT" or decision.get("blockers"):
        raise ValueError("only an unblocked ADMIT decision can be frozen")
    if audit.get("status") != "AUDIT_PASS":
        raise ValueError("AUDIT_PASS required")
    if candidate.get("quarantine_status") != "PASS":
        raise ValueError("quarantine PASS required")
    if candidate.get("solution_isolation") not in {"PASS", "PROVEN"}:
        raise ValueError("solution isolation required")
    family = candidate.get("proposed_family")
    if family in {None, "", "UNASSIGNED_PENDING_SCREEN"}:
        raise ValueError("assigned family required")

    record = {
        "schema_id": "ndv-p1-s2-admission-record-v1",
        "candidate_id": cid,
        "source_instance_id": candidate.get("source_instance_id"),
        "repository": candidate.get("repository"),
        "base_revision": candidate.get("base_revision"),
        "language": candidate.get("language"),
        "family": family,
        "task_statement_sha256": candidate.get("task_statement_sha256"),
        "executor_visible_ref": candidate.get("executor_visible_ref"),
        "executor_visible_sha256": candidate.get("executor_visible_sha256"),
        "quarantine_manifest_ref": candidate.get("quarantine_manifest_ref"),
        "audit": {
            "image_digest": audit.get("image_digest"),
            "base_run_ref": audit.get("base_run_ref"),
            "base_run_sha256": audit.get("base_run_sha256"),
            "oracle_interpretation_ref": audit.get("oracle_interpretation_ref"),
            "oracle_interpretation_sha256": audit.get("oracle_interpretation_sha256"),
            "focal_verifier_ref": audit.get("focal_verifier_ref"),
            "focal_verifier_sha256": audit.get("focal_verifier_sha256"),
            "preservation_ref": audit.get("preservation_ref"),
            "preservation_sha256": audit.get("preservation_sha256"),
            "verifier_provenance_ref": audit.get("verifier_provenance_ref"),
            "verifier_provenance_sha256": audit.get("verifier_provenance_sha256"),
            "environment_ref": audit.get("environment_ref"),
            "oracle_classification": audit.get("oracle_classification"),
        },
        "selection": {
            "treatment_performance_consulted": False,
            "treatment_execution_before_admission": False,
            "holdout_access": "NONE",
        },
        "status": "ADMITTED_FROZEN",
    }
    required = [
        "repository", "base_revision", "family", "task_statement_sha256",
        "executor_visible_ref", "executor_visible_sha256", "quarantine_manifest_ref",
    ]
    missing = [x for x in required if record.get(x) in (None, "")]
    missing += [f"audit.{k}" for k, v in record["audit"].items() if v in (None, "")]
    if missing:
        raise ValueError(f"cannot freeze incomplete admission record: {missing}")
    record["record_sha256"] = sha256(record)
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wave", required=True, type=Path)
    ap.add_argument("--audit", required=True, type=Path)
    ap.add_argument("--decisions", required=True, type=Path)
    ap.add_argument("--candidate-id", required=True)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    wave, audit_state, decisions = load(args.wave), load(args.audit), load(args.decisions)
    candidate = find(wave["candidates"], args.candidate_id)
    audit = find(audit_state["audits"], args.candidate_id)
    decision = find(decisions["decisions"], args.candidate_id)
    record = freeze(candidate, audit, decision)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"candidate_id": args.candidate_id, "status": record["status"], "record_sha256": record["record_sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
