#!/usr/bin/env python3
"""Freeze one NDV S2 admission decision into an immutable admission record.

The CLI fails closed unless every referenced artifact exists and matches its
frozen hash/binding. Declared metadata alone is insufficient for admission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SHA256 = re.compile(r"^[0-9a-f]{64}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find(items: list[dict[str, Any]], cid: str, key: str = "candidate_id") -> dict[str, Any]:
    matches = [x for x in items if x.get(key) == cid]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {key}={cid}, found {len(matches)}")
    return matches[0]


def require_sha(name: str, value: Any) -> str:
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        raise ValueError(f"{name} must be 64-hex")
    return value


def resolve_ref(root: Path, value: Any, name: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} missing")
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if not path.is_file():
        raise ValueError(f"{name} not found: {path}")
    return path


def verify_file_hash(root: Path, ref: Any, expected: Any, name: str) -> Path:
    path = resolve_ref(root, ref, f"{name}_ref")
    expected_sha = require_sha(f"{name}_sha256", expected)
    observed = sha256_file(path)
    if observed != expected_sha:
        raise ValueError(f"{name} file SHA-256 mismatch")
    return path


def verify_canonical_json_hash(root: Path, ref: Any, expected: Any, name: str) -> tuple[Path, dict[str, Any]]:
    path = resolve_ref(root, ref, f"{name}_ref")
    payload = load(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must be a JSON object")
    expected_sha = require_sha(f"{name}_sha256", expected)
    if sha256(payload) != expected_sha:
        raise ValueError(f"{name} canonical JSON SHA-256 mismatch")
    return path, payload


def verify_candidate_artifacts(candidate: dict[str, Any], root: Path) -> dict[str, str]:
    cid = candidate["candidate_id"]
    raw_sha = require_sha("ndv_canonical_row_sha256", candidate.get("ndv_canonical_row_sha256"))
    executor_sha = require_sha("executor_visible_sha256", candidate.get("executor_visible_sha256"))
    task_sha = require_sha("task_statement_sha256", candidate.get("task_statement_sha256"))
    row_index = candidate.get("source_row_index")

    admission_path = resolve_ref(root, candidate.get("admission_only_ref"), "admission_only_ref")
    admission = load(admission_path)
    if not isinstance(admission, dict) or admission.get("schema_id") != "ndv-p1-s2-admission-only-row-v1" or admission.get("candidate_id") != cid:
        raise ValueError("admission-only artifact identity/schema mismatch")
    source, row = admission.get("source"), admission.get("full_row")
    if not isinstance(source, dict) or not isinstance(row, dict):
        raise ValueError("admission-only artifact missing source/full_row")
    if source.get("source_row_index") != row_index or source.get("source_instance_id") != candidate.get("source_instance_id"):
        raise ValueError("admission-only source binding mismatch")
    if source.get("ndv_canonical_row_sha256") != raw_sha or sha256(row) != raw_sha:
        raise ValueError("admission-only raw row SHA-256 mismatch")
    problem = row.get("problem_statement")
    if not isinstance(problem, str) or hashlib.sha256(problem.encode("utf-8")).hexdigest() != task_sha:
        raise ValueError("admission-only task statement hash mismatch")

    executor_path = resolve_ref(root, candidate.get("executor_visible_ref"), "executor_visible_ref")
    executor = load(executor_path)
    if not isinstance(executor, dict) or executor.get("schema_id") != "ndv-p1-s2-executor-visible-row-v1" or executor.get("candidate_id") != cid:
        raise ValueError("executor-visible artifact identity/schema mismatch")
    binding, task = executor.get("source_binding"), executor.get("task")
    if not isinstance(binding, dict) or not isinstance(task, dict):
        raise ValueError("executor-visible artifact missing binding/task")
    if binding.get("source_row_index") != row_index or binding.get("ndv_canonical_row_sha256") != raw_sha:
        raise ValueError("executor-visible source binding mismatch")
    if executor.get("executor_visible_sha256") != executor_sha or sha256(task) != executor_sha:
        raise ValueError("executor-visible projection SHA-256 mismatch")
    if executor.get("task_statement_sha256") != task_sha:
        raise ValueError("executor-visible task statement hash mismatch")

    manifest_path = resolve_ref(root, candidate.get("quarantine_manifest_ref"), "quarantine_manifest_ref")
    manifest = load(manifest_path)
    if not isinstance(manifest, dict) or manifest.get("schema_id") != "ndv-p1-s2-quarantine-manifest-v2" or manifest.get("candidate_id") != cid or manifest.get("status") != "PASS":
        raise ValueError("quarantine manifest identity/schema/status mismatch")
    expected = {
        "source_row_index": row_index,
        "source_instance_id": candidate.get("source_instance_id"),
        "ndv_canonical_row_sha256": raw_sha,
        "task_statement_sha256": task_sha,
        "executor_visible_sha256": executor_sha,
        "treatment_execution": "NOT_EXECUTED",
        "holdout_access": "NONE",
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(f"quarantine manifest {key} mismatch")

    return {
        "admission_only_file_sha256": sha256_file(admission_path),
        "executor_visible_file_sha256": sha256_file(executor_path),
        "quarantine_manifest_file_sha256": sha256_file(manifest_path),
    }


def verify_audit_artifacts(candidate: dict[str, Any], audit: dict[str, Any], root: Path) -> dict[str, str]:
    cid = candidate["candidate_id"]
    base_path = verify_file_hash(root, audit.get("base_run_ref"), audit.get("base_run_sha256"), "base_run")
    base = load(base_path)
    if not isinstance(base, dict) or base.get("schema_id") != "ndv-p1-s2-base-audit-run-v2" or base.get("candidate_id") != cid:
        raise ValueError("base run identity/schema mismatch")
    if base.get("base_revision") != candidate.get("base_revision") or base.get("harness_integrity") != "PASS":
        raise ValueError("base run base revision/harness integrity mismatch")
    if base.get("gold_patch_applied") is not False or base.get("test_patch_applied") is not False or base.get("treatment_execution") != "NOT_EXECUTED" or base.get("holdout_access") != "NONE":
        raise ValueError("base run contamination detected")

    oracle_path = verify_file_hash(root, audit.get("oracle_interpretation_ref"), audit.get("oracle_interpretation_sha256"), "oracle_interpretation")
    oracle = load(oracle_path)
    if not isinstance(oracle, dict) or oracle.get("schema_id") != "ndv-p1-s2-base-oracle-interpretation-v2" or oracle.get("candidate_id") != cid:
        raise ValueError("oracle interpretation identity/schema mismatch")
    if oracle.get("classification") != "EXPECTED_BASE_BEHAVIOR" or oracle.get("treatment_execution") != "NOT_EXECUTED" or oracle.get("holdout_access") != "NONE":
        raise ValueError("oracle interpretation classification/contamination mismatch")

    _, focal = verify_canonical_json_hash(root, audit.get("focal_verifier_ref"), audit.get("focal_verifier_sha256"), "focal_verifier")
    _, preservation = verify_canonical_json_hash(root, audit.get("preservation_ref"), audit.get("preservation_sha256"), "preservation")
    _, provenance = verify_canonical_json_hash(root, audit.get("verifier_provenance_ref"), audit.get("verifier_provenance_sha256"), "verifier_provenance")
    for name, payload in (("focal", focal), ("preservation", preservation), ("provenance", provenance)):
        if payload.get("instance_id") != candidate.get("source_instance_id") or payload.get("base_commit") != candidate.get("base_revision"):
            raise ValueError(f"{name} verifier source binding mismatch")
        if payload.get("source_row_index") != candidate.get("source_row_index"):
            raise ValueError(f"{name} verifier source row index mismatch")

    environment_path = verify_file_hash(root, audit.get("environment_ref"), audit.get("environment_sha256"), "environment")
    return {
        "base_run_file_sha256": sha256_file(base_path),
        "oracle_interpretation_file_sha256": sha256_file(oracle_path),
        "environment_file_sha256": sha256_file(environment_path),
    }


def freeze(candidate: dict[str, Any], audit: dict[str, Any], decision: dict[str, Any], artifact_integrity: dict[str, str] | None = None) -> dict[str, Any]:
    cid = candidate.get("candidate_id")
    if not isinstance(cid, str) or not cid: raise ValueError("candidate_id missing")
    if decision.get("candidate_id") != cid or audit.get("candidate_id") != cid: raise ValueError("candidate/audit/decision identity mismatch")
    if decision.get("decision") != "ADMIT" or decision.get("blockers"): raise ValueError("only an unblocked ADMIT decision can be frozen")
    if audit.get("status") != "AUDIT_PASS": raise ValueError("AUDIT_PASS required")
    if audit.get("harness_integrity") != "PASS": raise ValueError("harness_integrity=PASS required")
    if audit.get("oracle_classification") != "EXPECTED_BASE_BEHAVIOR" or audit.get("base_behavior_matches_expected") is not True: raise ValueError("expected base behavior required")
    if audit.get("preservation_baseline_pass") is not True: raise ValueError("preservation baseline PASS required")
    if audit.get("verifier_independent") is not True: raise ValueError("verifier independence required")
    if audit.get("treatment_execution") != "NOT_EXECUTED": raise ValueError("treatment contamination forbids admission")
    if audit.get("gold_patch_applied_in_base_mode") is not False or audit.get("test_patch_applied_in_base_mode") is not False: raise ValueError("base audit patch contamination forbids admission")
    digest = audit.get("image_digest")
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest): raise ValueError("immutable image digest required")
    require_sha("environment_sha256", audit.get("environment_sha256"))

    if candidate.get("quarantine_status") != "PASS": raise ValueError("quarantine PASS required")
    if candidate.get("solution_isolation") not in {"PASS", "PROVEN"}: raise ValueError("solution isolation required")
    family = candidate.get("proposed_family")
    if family in {None, "", "UNASSIGNED_PENDING_SCREEN"}: raise ValueError("assigned family required")
    source_row_index = candidate.get("source_row_index")
    if not isinstance(source_row_index, int) or source_row_index < 0: raise ValueError("valid source_row_index required")

    task_sha = require_sha("task_statement_sha256", candidate.get("task_statement_sha256")); raw_sha = require_sha("ndv_canonical_row_sha256", candidate.get("ndv_canonical_row_sha256")); executor_sha = require_sha("executor_visible_sha256", candidate.get("executor_visible_sha256"))
    audit_hashes = {name: require_sha(name, audit.get(name)) for name in ("base_run_sha256", "oracle_interpretation_sha256", "focal_verifier_sha256", "preservation_sha256", "verifier_provenance_sha256", "environment_sha256")}
    if artifact_integrity is None:
        raise ValueError("verified artifact integrity evidence required")

    record = {
        "schema_id": "ndv-p1-s2-admission-record-v2", "candidate_id": cid,
        "source_instance_id": candidate.get("source_instance_id"), "source_row_index": source_row_index,
        "repository": candidate.get("repository"), "base_revision": candidate.get("base_revision"), "language": candidate.get("language"), "family": family,
        "source_binding": {"task_statement_sha256": task_sha, "ndv_canonical_row_sha256": raw_sha, "admission_only_ref": candidate.get("admission_only_ref"), "executor_visible_ref": candidate.get("executor_visible_ref"), "executor_visible_sha256": executor_sha, "quarantine_manifest_ref": candidate.get("quarantine_manifest_ref")},
        "audit": {"image_digest": digest, "harness_integrity": "PASS", "base_run_ref": audit.get("base_run_ref"), "base_run_sha256": audit_hashes["base_run_sha256"], "oracle_interpretation_ref": audit.get("oracle_interpretation_ref"), "oracle_interpretation_sha256": audit_hashes["oracle_interpretation_sha256"], "focal_verifier_ref": audit.get("focal_verifier_ref"), "focal_verifier_sha256": audit_hashes["focal_verifier_sha256"], "preservation_ref": audit.get("preservation_ref"), "preservation_sha256": audit_hashes["preservation_sha256"], "verifier_provenance_ref": audit.get("verifier_provenance_ref"), "verifier_provenance_sha256": audit_hashes["verifier_provenance_sha256"], "environment_ref": audit.get("environment_ref"), "environment_sha256": audit_hashes["environment_sha256"], "oracle_classification": "EXPECTED_BASE_BEHAVIOR"},
        "artifact_integrity": {"status": "VERIFIED", **artifact_integrity},
        "selection": {"treatment_performance_consulted": False, "treatment_execution_before_admission": False, "holdout_access": "NONE"},
        "status": "ADMITTED_FROZEN",
    }
    required_top = ("source_instance_id", "repository", "base_revision", "language")
    missing = [x for x in required_top if record.get(x) in (None, "")]
    missing += [f"source_binding.{k}" for k, v in record["source_binding"].items() if v in (None, "")]
    missing += [f"audit.{k}" for k, v in record["audit"].items() if v in (None, "")]
    if missing: raise ValueError(f"cannot freeze incomplete admission record: {missing}")
    record["record_sha256"] = sha256(record)
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wave", required=True, type=Path); ap.add_argument("--audit", required=True, type=Path); ap.add_argument("--decisions", required=True, type=Path); ap.add_argument("--candidate-id", required=True); ap.add_argument("--out", required=True, type=Path); ap.add_argument("--artifact-root", type=Path, default=Path(".")); args = ap.parse_args()
    wave, audit_state, decisions = load(args.wave), load(args.audit), load(args.decisions)
    candidate = find(wave["candidates"], args.candidate_id); audit = find(audit_state["audits"], args.candidate_id); decision = find(decisions["decisions"], args.candidate_id)
    root = args.artifact_root.resolve()
    try:
        integrity = {**verify_candidate_artifacts(candidate, root), **verify_audit_artifacts(candidate, audit, root)}
        record = freeze(candidate, audit, decision, integrity)
    except ValueError as exc:
        raise SystemExit(f"ADMISSION_FREEZE_BLOCKED: {exc}") from exc
    args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps({"candidate_id": args.candidate_id, "status": record["status"], "record_sha256": record["record_sha256"], "artifact_integrity": "VERIFIED"}, indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
