#!/usr/bin/env python3
"""Validate NDV P1-S2 verifier/environment audit records without treatment execution."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SHA256 = re.compile(r"^[0-9a-f]{64}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
ALLOWED_STATUS = {
    "WAITING_QUARANTINE",
    "READY_FOR_ENVIRONMENT_AUDIT",
    "ENVIRONMENT_BLOCKED",
    "ORACLE_BLOCKED",
    "AUDIT_PASS",
    "REJECTED",
}
REQUIRED_PASS_FIELDS = {
    "image_digest",
    "base_run_ref",
    "base_run_sha256",
    "oracle_interpretation_ref",
    "oracle_interpretation_sha256",
    "focal_verifier_ref",
    "preservation_ref",
    "verifier_provenance_ref",
    "environment_ref",
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_record(rec: dict[str, Any], idx: int) -> list[str]:
    errors: list[str] = []
    p = f"audit[{idx}]"
    status = rec.get("status")
    if status not in ALLOWED_STATUS:
        errors.append(f"{p} invalid status: {status!r}")
    if rec.get("treatment_execution") != "NOT_EXECUTED":
        errors.append(f"{p} treatment_execution must remain NOT_EXECUTED")
    if rec.get("gold_patch_applied_in_base_mode") is True:
        errors.append(f"{p} gold patch must never be applied in base mode")
    if status in {"READY_FOR_ENVIRONMENT_AUDIT", "AUDIT_PASS"} and rec.get("quarantine_status") != "PASS":
        errors.append(f"{p} {status} requires quarantine_status=PASS")
    if status == "AUDIT_PASS":
        for field in sorted(REQUIRED_PASS_FIELDS):
            if rec.get(field) in (None, "", "UNRESOLVED"):
                errors.append(f"{p} AUDIT_PASS requires {field}")
        digest = rec.get("image_digest")
        if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
            errors.append(f"{p} image_digest must be sha256:<64-hex>")
        for field in ("base_run_sha256", "oracle_interpretation_sha256"):
            value = rec.get(field)
            if not isinstance(value, str) or not SHA256.fullmatch(value):
                errors.append(f"{p} {field} must be 64-hex")
        if rec.get("oracle_classification") != "EXPECTED_BASE_BEHAVIOR":
            errors.append(f"{p} AUDIT_PASS requires oracle_classification=EXPECTED_BASE_BEHAVIOR")
        if rec.get("verifier_independent") is not True:
            errors.append(f"{p} AUDIT_PASS requires verifier_independent=true")
        if rec.get("base_behavior_matches_expected") is not True:
            errors.append(f"{p} AUDIT_PASS requires base_behavior_matches_expected=true")
        if rec.get("preservation_baseline_pass") is not True:
            errors.append(f"{p} AUDIT_PASS requires preservation_baseline_pass=true")
    return errors


def validate(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_id") != "ndv-p1-s2-audit-state-v1":
        errors.append("unexpected schema_id")
    if payload.get("holdout_access") != "NONE":
        errors.append("holdout_access must remain NONE")
    audits = payload.get("audits")
    if not isinstance(audits, list) or not audits:
        errors.append("audits must be a non-empty array")
        return errors
    seen: set[str] = set()
    for idx, rec in enumerate(audits):
        if not isinstance(rec, dict):
            errors.append(f"audit[{idx}] must be an object")
            continue
        cid = rec.get("candidate_id")
        if not isinstance(cid, str) or not cid:
            errors.append(f"audit[{idx}] candidate_id missing")
        elif cid in seen:
            errors.append(f"duplicate candidate_id: {cid}")
        else:
            seen.add(cid)
        errors.extend(validate_record(rec, idx))
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", type=Path)
    args = ap.parse_args()
    payload = load(args.path)
    if not isinstance(payload, dict):
        print(json.dumps({"status": "FAIL", "errors": ["root must be an object"]}, indent=2))
        return 2
    errors = validate(payload)
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
