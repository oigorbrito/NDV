#!/usr/bin/env python3
"""Validate NDV P1-S2 candidate intake without executing treatments.

This validator intentionally checks only acquisition/governance invariants. It must
not run models, apply gold patches, or access sealed holdout material.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

FORBIDDEN_AGENT_FIELDS = {
    "patch",
    "test_patch",
    "FAIL_TO_PASS",
    "PASS_TO_PASS",
    "interface",
    "meta",
    "install_config",
    "pr_description",
}
ALLOWED_DISPOSITIONS = {
    "DISCOVERED",
    "SCREENING",
    "ADMITTED",
    "REJECTED_INVALID_ORACLE",
    "REJECTED_VERIFIER_ARTIFACT_UNAVAILABLE",
    "REJECTED_ENVIRONMENT_NOT_REPRODUCIBLE",
    "REJECTED_BASE_UNUSABLE",
    "REJECTED_SOLUTION_LEAKAGE_REQUIRED",
    "REJECTED_OTHER_EXPLICIT_REASON",
}
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_id") != "ndv-p1-s2-candidate-wave-v1":
        errors.append("unexpected schema_id")

    quarantine = payload.get("source_field_quarantine", {})
    actual_forbidden = set(quarantine.get("agent_forbidden_fields", []))
    missing = FORBIDDEN_AGENT_FIELDS - actual_forbidden
    if missing:
        errors.append(f"quarantine is missing forbidden fields: {sorted(missing)}")
    if quarantine.get("projection_mode") not in {None, "STRICT_ALLOWLIST"}:
        errors.append("source_field_quarantine.projection_mode must be STRICT_ALLOWLIST when declared")

    source = payload.get("source", {})
    rev = source.get("dataset_revision")
    if not isinstance(rev, str) or not SHA40.fullmatch(rev):
        errors.append("dataset_revision must be a pinned 40-hex SHA")

    seen_ids: set[str] = set()
    repos: set[str] = set()
    languages: set[str] = set()
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        errors.append("candidates must be a non-empty array")
        return errors

    for idx, candidate in enumerate(candidates):
        prefix = f"candidate[{idx}]"
        if not isinstance(candidate, dict):
            errors.append(f"{prefix} must be an object")
            continue

        leaked = FORBIDDEN_AGENT_FIELDS & set(candidate)
        if leaked:
            errors.append(f"{prefix} contains quarantined source fields: {sorted(leaked)}")

        cid = candidate.get("candidate_id")
        if not isinstance(cid, str) or not cid:
            errors.append(f"{prefix} candidate_id missing")
        elif cid in seen_ids:
            errors.append(f"duplicate candidate_id: {cid}")
        else:
            seen_ids.add(cid)

        base = candidate.get("base_revision")
        if not isinstance(base, str) or not SHA40.fullmatch(base):
            errors.append(f"{prefix} base_revision must be 40-hex")

        record_hash = candidate.get("source_record_sha256")
        if not isinstance(record_hash, str) or not SHA256.fullmatch(record_hash):
            errors.append(f"{prefix} source_record_sha256 must be 64-hex")

        disposition = candidate.get("disposition")
        if disposition not in ALLOWED_DISPOSITIONS:
            errors.append(f"{prefix} invalid disposition: {disposition!r}")

        qstatus = candidate.get("quarantine_status")
        if qstatus not in {None, "PENDING", "PASS", "FAIL"}:
            errors.append(f"{prefix} invalid quarantine_status: {qstatus!r}")
        for field in ("ndv_canonical_row_sha256", "executor_visible_sha256"):
            value = candidate.get(field)
            if value is not None and (not isinstance(value, str) or not SHA256.fullmatch(value)):
                errors.append(f"{prefix} {field} must be 64-hex when present")

        if disposition == "ADMITTED":
            required_admission = {
                "task_statement_sha256",
                "focal_verifier_ref",
                "preservation_ref",
                "environment_ref",
                "quarantine_manifest_ref",
                "admission_only_ref",
                "executor_visible_ref",
                "ndv_canonical_row_sha256",
                "executor_visible_sha256",
            }
            for field in sorted(required_admission):
                value = candidate.get(field)
                if value in (None, "", "UNRESOLVED"):
                    errors.append(f"{prefix} ADMITTED requires {field}")
            if candidate.get("quarantine_status") != "PASS":
                errors.append(f"{prefix} ADMITTED requires quarantine_status=PASS")
            if candidate.get("verifier_independent") is not True:
                errors.append(f"{prefix} ADMITTED requires verifier_independent=true")
            if candidate.get("solution_isolation") not in {"PASS", "PROVEN"}:
                errors.append(f"{prefix} ADMITTED requires proven solution isolation")
            if candidate.get("proposed_family") in {None, "", "UNASSIGNED_PENDING_SCREEN"}:
                errors.append(f"{prefix} ADMITTED requires exactly one assigned family")

        repo = candidate.get("repository")
        language = candidate.get("language")
        if isinstance(repo, str) and repo:
            repos.add(repo)
        if isinstance(language, str) and language:
            languages.add(language)

    summary = payload.get("wave_summary", {})
    if summary.get("candidate_count") != len(candidates):
        errors.append("wave_summary.candidate_count does not match candidates")
    if summary.get("repository_count") != len(repos):
        errors.append("wave_summary.repository_count does not match observed repositories")
    if summary.get("language_count") != len(languages):
        errors.append("wave_summary.language_count does not match observed languages")
    if summary.get("treatment_execution") != "NOT_EXECUTED":
        errors.append("treatment execution must remain NOT_EXECUTED during intake")
    if summary.get("holdout_access") != "NONE":
        errors.append("holdout access must remain NONE during development intake")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, nargs="?", default=Path("experiments/p1/s2-candidate-wave-01.json"))
    args = parser.parse_args()
    payload = load(args.path)
    if not isinstance(payload, dict):
        print(json.dumps({"status": "FAIL", "errors": ["root must be a JSON object"]}, indent=2))
        return 2
    errors = validate(payload)
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
