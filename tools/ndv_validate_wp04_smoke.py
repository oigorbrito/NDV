#!/usr/bin/env python3
"""Validate the NDV WP-04 real-executor smoke contract and one frozen executor binding."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ALLOWED_SURFACES = {"LOCAL_PINNED", "HOSTED_FREE_PINNED", "SUBSCRIPTION_EXECUTOR_PINNED"}
ALLOWED_EXECUTOR_KINDS = {"STANDALONE_AGENT", "MODEL_PLUS_FROZEN_SCAFFOLD"}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_campaign(c: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if c.get("schema_id") != "ndv-p1-wp04-real-executor-smoke-v1":
        errors.append("unexpected campaign schema_id")
    scope = c.get("scope", {})
    if scope.get("classification") != "PIPELINE_SMOKE_ONLY":
        errors.append("WP-04 must remain PIPELINE_SMOKE_ONLY")
    for field in ("executor_ranking", "economic_superiority_claim", "routing_claim", "architecture_claim", "holdout_access"):
        if scope.get(field) != "FORBIDDEN":
            errors.append(f"scope.{field} must be FORBIDDEN")
    if scope.get("retries") != 0 or scope.get("escalations") != 0:
        errors.append("WP-04 retries and escalations must be zero")
    if scope.get("shaping") != "S0_RAW_TASK":
        errors.append("WP-04 must start with S0_RAW_TASK")

    tasks = c.get("task_sequence")
    if not isinstance(tasks, list) or len(tasks) != 2:
        errors.append("task_sequence must contain exactly two staged smoke tasks")
    else:
        expected = [(1, "D-F5-01"), (2, "D-F6-01")]
        actual = [(t.get("stage"), t.get("task_id")) for t in tasks if isinstance(t, dict)]
        if actual != expected:
            errors.append(f"unexpected staged task order: {actual!r}")

    policy = c.get("executor_binding_policy", {})
    if policy.get("provider_neutral") is not True:
        errors.append("campaign design must remain provider-neutral")
    if policy.get("dynamic_or_random_routing") != "FORBIDDEN":
        errors.append("dynamic/random routing must be forbidden")
    if policy.get("automatic_download") != "FORBIDDEN":
        errors.append("automatic download must be forbidden")
    if policy.get("implicit_fallback") != "FORBIDDEN":
        errors.append("implicit fallback must be forbidden")
    return errors


def validate_binding(b: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if b.get("schema_id") != "ndv-p1-wp04-executor-binding-v2":
        errors.append("execution requires binding schema ndv-p1-wp04-executor-binding-v2")
    if b.get("surface_class") not in ALLOWED_SURFACES:
        errors.append("binding.surface_class is not allowed")
    if b.get("executor_kind") not in ALLOWED_EXECUTOR_KINDS:
        errors.append("binding.executor_kind must identify a standalone agent or model+frozen scaffold")

    required = [
        "binding_id",
        "provider_or_runtime",
        "exact_executor_identity",
        "version_or_model_hash",
        "invocation_command_or_surface",
        "qualification_evidence_ref",
        "candidate_capture_mode",
        "network_policy",
        "frozen_at",
        "status",
    ]
    for field in required:
        if b.get(field) in (None, "", "REQUIRED", "REQUIRED_UNIQUE", "REQUIRED_ISO8601"):
            errors.append(f"binding requires concrete {field}")

    scaffold = b.get("scaffold")
    if not isinstance(scaffold, dict):
        errors.append("binding.scaffold must be an object")
    else:
        for field in ("name", "source_repository", "version_or_commit", "invocation_mode"):
            if scaffold.get(field) in (None, "", "REQUIRED"):
                errors.append(f"binding.scaffold requires {field}")
        if scaffold.get("repository_tool_access") is not True:
            errors.append("binding.scaffold.repository_tool_access must be true")
        if scaffold.get("implicit_model_fallback") is not False:
            errors.append("binding.scaffold.implicit_model_fallback must be false")
        if scaffold.get("dynamic_routing") is not False:
            errors.append("binding.scaffold.dynamic_routing must be false")

    model = b.get("model")
    if not isinstance(model, dict):
        errors.append("binding.model must be an object")
    else:
        for field in ("identity", "digest_or_exact_version", "endpoint"):
            if model.get(field) in (None, "", "REQUIRED"):
                errors.append(f"binding.model requires {field}")

    timeout = b.get("timeout_seconds")
    if not isinstance(timeout, int) or timeout <= 0:
        errors.append("binding.timeout_seconds must be a positive integer")
    if b.get("retry_limit") != 0:
        errors.append("binding.retry_limit must be zero")
    if b.get("escalation_limit") != 0:
        errors.append("binding.escalation_limit must be zero")
    for field in ("automatic_download", "implicit_fallback", "dynamic_routing"):
        if b.get(field) is not False:
            errors.append(f"binding.{field} must be false")
    if b.get("task_context_mode") != "RAW_TASK_PLUS_REPOSITORY_TOOL_ACCESS":
        errors.append("binding.task_context_mode must be RAW_TASK_PLUS_REPOSITORY_TOOL_ACCESS")
    if b.get("status") != "QUALIFIED":
        errors.append("execution requires status=QUALIFIED")

    telemetry = b.get("telemetry_mode")
    if not isinstance(telemetry, dict):
        errors.append("binding.telemetry_mode must be an object")
    else:
        for field in ("identity", "usage", "timestamps", "raw_response_or_local_trace"):
            if telemetry.get(field) in (None, "", "REQUIRED"):
                errors.append(f"binding.telemetry_mode requires {field}")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--campaign", type=Path, default=Path("experiments/p1/wp04-real-executor-smoke-v1.json"))
    ap.add_argument("--binding", type=Path)
    args = ap.parse_args()

    campaign = load(args.campaign)
    errors = validate_campaign(campaign if isinstance(campaign, dict) else {})
    if args.binding is not None:
        binding = load(args.binding)
        errors.extend(validate_binding(binding if isinstance(binding, dict) else {}))

    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
