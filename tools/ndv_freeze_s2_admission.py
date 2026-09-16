#!/usr/bin/env python3
"""Freeze one NDV S2 admission decision into an immutable admission record.

Admission is allowed only when global schemas are valid, the decision is still
bound to the exact candidate/audit evidence, and every referenced artifact is
re-read and re-hashed successfully. Metadata declarations alone are insufficient.
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
AUDIT_HASH_FIELDS = ("base_run_sha256", "oracle_interpretation_sha256", "focal_verifier_sha256", "preservation_sha256", "verifier_provenance_sha256", "environment_sha256")
DECISION_REF_FIELDS = ("quarantine_manifest_ref", "admission_only_ref", "executor_visible_ref", "base_run_ref", "oracle_interpretation_ref", "focal_verifier_ref", "preservation_ref", "verifier_provenance_ref", "environment_ref")


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


def require_sha(name: str, value: Any) -> str:
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        raise ValueError(f"{name} must be 64-hex")
    return value


def find(items: Any, cid: str) -> dict[str, Any]:
    if not isinstance(items, list):
        raise ValueError("expected array of candidate records")
    matches = [item for item in items if isinstance(item, dict) and item.get("candidate_id") == cid]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one candidate_id={cid}, found {len(matches)}")
    return matches[0]


def validate_global_inputs(wave: dict[str, Any], audit_state: dict[str, Any], decisions: dict[str, Any]) -> None:
    if wave.get("schema_id") != "ndv-p1-s2-candidate-wave-v1":
        raise ValueError("unexpected candidate wave schema")
    summary = wave.get("wave_summary")
    if not isinstance(summary, dict) or summary.get("treatment_execution") != "NOT_EXECUTED" or summary.get("holdout_access") != "NONE":
        raise ValueError("candidate wave is treatment/holdout contaminated")
    if audit_state.get("schema_id") != "ndv-p1-s2-audit-state-v1" or audit_state.get("holdout_access") != "NONE":
        raise ValueError("unexpected or holdout-contaminated audit state")
    if decisions.get("schema_id") != "ndv-p1-s2-admission-decisions-v2":
        raise ValueError("unexpected admission decisions schema")
    if decisions.get("treatment_execution") != "NOT_EXECUTED" or decisions.get("holdout_access") != "NONE":
        raise ValueError("admission decisions are treatment/holdout contaminated")
    if decisions.get("wave_id") != wave.get("wave_id"):
        raise ValueError("admission decisions wave_id mismatch")


def validate_decision_snapshot(candidate: dict[str, Any], audit: dict[str, Any], decision: dict[str, Any]) -> None:
    refs = decision.get("evidence_refs")
    hashes = decision.get("evidence_hashes")
    if not isinstance(refs, dict) or not isinstance(hashes, dict):
        raise ValueError("decision must freeze evidence_refs and evidence_hashes")
    expected_refs = {
        "quarantine_manifest_ref": candidate.get("quarantine_manifest_ref"),
        "admission_only_ref": candidate.get("admission_only_ref"),
        "executor_visible_ref": candidate.get("executor_visible_ref"),
        "base_run_ref": audit.get("base_run_ref"),
        "oracle_interpretation_ref": audit.get("oracle_interpretation_ref"),
        "focal_verifier_ref": audit.get("focal_verifier_ref"),
        "preservation_ref": audit.get("preservation_ref"),
        "verifier_provenance_ref": audit.get("verifier_provenance_ref"),
        "environment_ref": audit.get("environment_ref"),
    }
    for field in DECISION_REF_FIELDS:
        if refs.get(field) != expected_refs[field]:
            raise ValueError(f"stale decision evidence ref: {field}")
    expected_hashes = {
        "ndv_canonical_row_sha256": candidate.get("ndv_canonical_row_sha256"),
        "executor_visible_sha256": candidate.get("executor_visible_sha256"),
        "task_statement_sha256": candidate.get("task_statement_sha256"),
        **{field: audit.get(field) for field in AUDIT_HASH_FIELDS},
    }
    for field, expected in expected_hashes.items():
        if hashes.get(field) != expected:
            raise ValueError(f"stale decision evidence hash: {field}")


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


def verify_file_hash(root: Path, ref: Any, expected: Any, name: str) -> tuple[Path, dict[str, Any]]:
    path = resolve_ref(root, ref, f"{name}_ref")
    if sha256_file(path) != require_sha(f"{name}_sha256", expected):
        raise ValueError(f"{name} file SHA-256 mismatch")
    payload = load(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must be a JSON object")
    return path, payload


def verify_canonical_json_hash(root: Path, ref: Any, expected: Any, name: str) -> tuple[Path, dict[str, Any]]:
    path = resolve_ref(root, ref, f"{name}_ref")
    payload = load(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must be a JSON object")
    if sha256(payload) != require_sha(f"{name}_sha256", expected):
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
    expected = {"source_row_index": row_index, "source_instance_id": candidate.get("source_instance_id"), "ndv_canonical_row_sha256": raw_sha, "task_statement_sha256": task_sha, "executor_visible_sha256": executor_sha, "treatment_execution": "NOT_EXECUTED", "holdout_access": "NONE"}
    for field, value in expected.items():
        if manifest.get(field) != value:
            raise ValueError(f"quarantine manifest {field} mismatch")
    return {"admission_only_file_sha256": sha256_file(admission_path), "executor_visible_file_sha256": sha256_file(executor_path), "quarantine_manifest_file_sha256": sha256_file(manifest_path)}


def verify_audit_artifacts(candidate: dict[str, Any], audit: dict[str, Any], root: Path) -> dict[str, str]:
    cid = candidate["candidate_id"]
    base_path, base = verify_file_hash(root, audit.get("base_run_ref"), audit.get("base_run_sha256"), "base_run")
    if base.get("schema_id") != "ndv-p1-s2-base-audit-run-v2" or base.get("candidate_id") != cid or base.get("base_revision") != candidate.get("base_revision") or base.get("harness_integrity") != "PASS":
        raise ValueError("base run identity/base/harness mismatch")
    if base.get("gold_patch_applied") is not False or base.get("test_patch_applied") is not False or base.get("treatment_execution") != "NOT_EXECUTED" or base.get("holdout_access") != "NONE":
        raise ValueError("base run contamination detected")

    oracle_path, oracle = verify_file_hash(root, audit.get("oracle_interpretation_ref"), audit.get("oracle_interpretation_sha256"), "oracle_interpretation")
    if oracle.get("schema_id") != "ndv-p1-s2-base-oracle-interpretation-v2" or oracle.get("candidate_id") != cid or oracle.get("classification") != "EXPECTED_BASE_BEHAVIOR":
        raise ValueError("oracle interpretation identity/schema/classification mismatch")
    if oracle.get("treatment_execution") != "NOT_EXECUTED" or oracle.get("holdout_access") != "NONE":
        raise ValueError("oracle interpretation contamination detected")

    _, focal = verify_canonical_json_hash(root, audit.get("focal_verifier_ref"), audit.get("focal_verifier_sha256"), "focal_verifier")
    _, preservation = verify_canonical_json_hash(root, audit.get("preservation_ref"), audit.get("preservation_sha256"), "preservation")
    _, provenance = verify_canonical_json_hash(root, audit.get("verifier_provenance_ref"), audit.get("verifier_provenance_sha256"), "verifier_provenance")
    for name, payload in (("focal", focal), ("preservation", preservation), ("provenance", provenance)):
        if payload.get("instance_id") != candidate.get("source_instance_id") or payload.get("base_commit") != candidate.get("base_revision") or payload.get("source_row_index") != candidate.get("source_row_index"):
            raise ValueError(f"{name} verifier source binding mismatch")

    environment_path, _ = verify_file_hash(root, audit.get("environment_ref"), audit.get("environment_sha256"), "environment")
    return {"base_run_file_sha256": sha256_file(base_path), "oracle_interpretation_file_sha256": sha256_file(oracle_path), "environment_file_sha256": sha256_file(environment_path)}


def freeze(candidate: dict[str, Any], audit: dict[str, Any], decision: dict[str, Any], artifact_integrity: dict[str, str] | None = None) -> dict[str, Any]:
    cid = candidate.get("candidate_id")
    if not isinstance(cid, str) or not cid or audit.get("candidate_id") != cid or decision.get("candidate_id") != cid:
        raise ValueError("candidate/audit/decision identity mismatch")
    if decision.get("decision") != "ADMIT" or decision.get("blockers"):
        raise ValueError("only an unblocked ADMIT decision can be frozen")
    validate_decision_snapshot(candidate, audit, decision)
    if audit.get("status") != "AUDIT_PASS" or audit.get("quarantine_status") != "PASS":
        raise ValueError("AUDIT_PASS with quarantine PASS required")
    if audit.get("harness_integrity") != "PASS" or audit.get("oracle_classification") != "EXPECTED_BASE_BEHAVIOR" or audit.get("base_behavior_matches_expected") is not True:
        raise ValueError("expected harness-valid base behavior required")
    if audit.get("preservation_baseline_pass") is not True or audit.get("verifier_independent") is not True:
        raise ValueError("preservation/verifier independence required")
    if audit.get("treatment_execution") != "NOT_EXECUTED" or audit.get("gold_patch_applied_in_base_mode") is not False or audit.get("test_patch_applied_in_base_mode") is not False:
        raise ValueError("audit contamination forbids admission")
    digest = audit.get("image_digest")
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
        raise ValueError("immutable image digest required")
    if candidate.get("quarantine_status") != "PASS" or candidate.get("solution_isolation") not in {"PASS", "PROVEN"}:
        raise ValueError("quarantine and solution isolation required")
    family = candidate.get("proposed_family")
    if family in {None, "", "UNASSIGNED_PENDING_SCREEN"}:
        raise ValueError("assigned family required")
    row_index = candidate.get("source_row_index")
    if not isinstance(row_index, int) or row_index < 0:
        raise ValueError("valid source_row_index required")
    if artifact_integrity is None:
        raise ValueError("verified artifact integrity evidence required")

    task_sha = require_sha("task_statement_sha256", candidate.get("task_statement_sha256")); raw_sha = require_sha("ndv_canonical_row_sha256", candidate.get("ndv_canonical_row_sha256")); executor_sha = require_sha("executor_visible_sha256", candidate.get("executor_visible_sha256"))
    audit_hashes = {field: require_sha(field, audit.get(field)) for field in AUDIT_HASH_FIELDS}
    record = {
        "schema_id": "ndv-p1-s2-admission-record-v2", "candidate_id": cid,
        "source_instance_id": candidate.get("source_instance_id"), "source_row_index": row_index, "repository": candidate.get("repository"), "base_revision": candidate.get("base_revision"), "language": candidate.get("language"), "family": family,
        "source_binding": {"task_statement_sha256": task_sha, "ndv_canonical_row_sha256": raw_sha, "admission_only_ref": candidate.get("admission_only_ref"), "executor_visible_ref": candidate.get("executor_visible_ref"), "executor_visible_sha256": executor_sha, "quarantine_manifest_ref": candidate.get("quarantine_manifest_ref")},
        "audit": {"image_digest": digest, "harness_integrity": "PASS", "base_run_ref": audit.get("base_run_ref"), "base_run_sha256": audit_hashes["base_run_sha256"], "oracle_interpretation_ref": audit.get("oracle_interpretation_ref"), "oracle_interpretation_sha256": audit_hashes["oracle_interpretation_sha256"], "focal_verifier_ref": audit.get("focal_verifier_ref"), "focal_verifier_sha256": audit_hashes["focal_verifier_sha256"], "preservation_ref": audit.get("preservation_ref"), "preservation_sha256": audit_hashes["preservation_sha256"], "verifier_provenance_ref": audit.get("verifier_provenance_ref"), "verifier_provenance_sha256": audit_hashes["verifier_provenance_sha256"], "environment_ref": audit.get("environment_ref"), "environment_sha256": audit_hashes["environment_sha256"], "oracle_classification": "EXPECTED_BASE_BEHAVIOR"},
        "artifact_integrity": {"status": "VERIFIED", **artifact_integrity},
        "selection": {"treatment_performance_consulted": False, "treatment_execution_before_admission": False, "holdout_access": "NONE"},
        "status": "ADMITTED_FROZEN",
    }
    for field in ("source_instance_id", "repository", "base_revision", "language"):
        if record.get(field) in (None, ""):
            raise ValueError(f"cannot freeze incomplete admission record: {field}")
    record["record_sha256"] = sha256(record)
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wave", required=True, type=Path); ap.add_argument("--audit", required=True, type=Path); ap.add_argument("--decisions", required=True, type=Path); ap.add_argument("--candidate-id", required=True); ap.add_argument("--out", required=True, type=Path); ap.add_argument("--artifact-root", type=Path, default=Path(".")); args = ap.parse_args()
    wave, audit_state, decisions = load(args.wave), load(args.audit), load(args.decisions)
    if not all(isinstance(x, dict) for x in (wave, audit_state, decisions)):
        raise SystemExit("ADMISSION_FREEZE_BLOCKED: all inputs must be JSON objects")
    try:
        validate_global_inputs(wave, audit_state, decisions)
        candidate = find(wave.get("candidates"), args.candidate_id); audit = find(audit_state.get("audits"), args.candidate_id); decision = find(decisions.get("decisions"), args.candidate_id)
        root = args.artifact_root.resolve()
        integrity = {**verify_candidate_artifacts(candidate, root), **verify_audit_artifacts(candidate, audit, root)}
        record = freeze(candidate, audit, decision, integrity)
    except ValueError as exc:
        raise SystemExit(f"ADMISSION_FREEZE_BLOCKED: {exc}") from exc
    args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"candidate_id": args.candidate_id, "status": record["status"], "record_sha256": record["record_sha256"], "artifact_integrity": "VERIFIED"}, indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
