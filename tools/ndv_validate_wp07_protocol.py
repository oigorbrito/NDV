#!/usr/bin/env python3
"""Validate the frozen WP-07 P1-S2 development comparison protocol.

No treatment, model, Docker, network, or holdout operation is performed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

TREATMENTS = {
    "B0": "STRONG_DIRECT",
    "B1": "CHEAP_DIRECT_VERIFY",
    "B2": "CHEAP_THEN_ESCALATE",
    "B3": "STATIC_FAMILY_POLICY",
    "B4": "LOCAL_OR_FREE_FIRST",
}
PARTITIONS = {
    "routing", "task_shaping", "planning", "context_input", "execution",
    "escalation_handoff", "verification", "retry_replanning",
}
REQUIRED_ESCALATION = {
    "MISSING_CANDIDATE_BEFORE_TIMEOUT", "EXPLICIT_EXECUTOR_BLOCKER",
    "FOCAL_OR_PRESERVATION_FAILURE", "STRUCTURALLY_INVALID_ARTIFACT",
    "DETERMINISTIC_RESOURCE_CEILING",
}
FORBIDDEN_ESCALATION = {
    "SUBJECTIVE_DIFFICULTY", "MANUAL_INTUITION", "HIDDEN_REASONING_CLASSIFICATION",
    "POST_HOC_MODEL_SELECTION",
}


def validate(p: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if p.get("schema_id") != "ndv-p1-wp07-development-comparison-protocol-v1": errors.append("unexpected schema")
    if p.get("status") != "PROSPECTIVE_FROZEN_NOT_RELEASED": errors.append("protocol must remain prospective/not released")
    if p.get("phase") != "P1-S2": errors.append("phase must be P1-S2")
    if p.get("primary_metric") != "TOTAL_SYSTEM_TOKENS / VERIFIED_SOLVED_TASK": errors.append("primary metric drift")
    treatments = p.get("treatments")
    if not isinstance(treatments, dict) or set(treatments) != set(TREATMENTS): errors.append("treatment set must be exactly B0-B4")
    else:
        for tid, name in TREATMENTS.items():
            if treatments[tid].get("name") != name: errors.append(f"{tid} name drift")
            if treatments[tid].get("dynamic_routing") is not False: errors.append(f"{tid} must not introduce dynamic routing")
    shaping = p.get("shaping") or {}
    if set(k for k in shaping if k.startswith("S")) != {"S0_RAW_TASK", "S1_DETERMINISTIC_TASK_SHAPING"}: errors.append("shaping set drift")
    if "no LLM planning" not in str(shaping.get("S1_DETERMINISTIC_TASK_SHAPING", "")): errors.append("S1 must forbid LLM planning")
    if set(p.get("escalation_triggers") or []) != REQUIRED_ESCALATION: errors.append("deterministic escalation triggers drift")
    if set(p.get("forbidden_escalation_triggers") or []) != FORBIDDEN_ESCALATION: errors.append("forbidden escalation trigger set drift")
    accounting = p.get("accounting") or {}
    if set(accounting.get("partitions") or []) != PARTITIONS: errors.append("accounting partition drift")
    for field in ("failure_cost_retained", "inconclusive_cost_retained", "free_local_not_zero_cost", "no_composite_score"):
        if accounting.get(field) is not True: errors.append(f"accounting.{field} must be true")
    if accounting.get("hardware_time_to_token_conversion") != "FORBIDDEN": errors.append("hardware-to-token conversion must be forbidden")
    release = p.get("execution_release") or {}
    if release.get("required_release_schema") != "ndv-p1-wp07-development-comparison-release-v1" or release.get("required_release_status") != "WP07_DEVELOPMENT_COMPARISON_RELEASED": errors.append("release prerequisite drift")
    if release.get("sealed_holdout_access") is not False or release.get("claim_generation") is not False or release.get("architecture_decision") is not False: errors.append("release scope too broad")
    matrix = p.get("matrix_materialization_rules") or {}
    for field in ("materialize_only_after_release", "all_tasks_must_be_admitted_frozen", "all_treatment_bindings_must_be_concrete_and_hash_bound", "no_silent_binding_substitution", "no_unplanned_fallback", "missing_binding_blocks_cell", "blocked_cell_is_not_zero_cost", "holdout_tasks_forbidden"):
        if matrix.get(field) is not True: errors.append(f"matrix rule {field} must be true")
    rollout = p.get("s2_rollout_policy") or {}
    if rollout.get("repetitions_per_cell") != 1: errors.append("P1-S2 must use one rollout per cell")
    if p.get("treatment_execution") != "NOT_EXECUTED" or p.get("holdout_access") != "NONE": errors.append("protocol must remain unexecuted/holdout clean")
    if "HOLDOUT_CONFIRMATION" not in (p.get("claims_forbidden") or []): errors.append("holdout confirmation must be forbidden")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("protocol", type=Path)
    args = ap.parse_args()
    try:
        payload = json.loads(args.protocol.read_text(encoding="utf-8"))
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "errors": [str(exc)]}, indent=2)); return 2
    if not isinstance(payload, dict):
        print(json.dumps({"status": "FAIL", "errors": ["protocol root must be object"]}, indent=2)); return 2
    errors = validate(payload)
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
