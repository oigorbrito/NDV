#!/usr/bin/env python3
"""Assess WP-07 concrete treatment binding coverage without executing treatments."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from ndv_wp07_codex_bundle import verify_bundle

EXPECTED = {
    "B0": ("STRONG_DIRECT", {"PRIMARY_STRONG"}),
    "B1": ("CHEAP_DIRECT_VERIFY", {"PRIMARY_ECONOMIC"}),
    "B2": ("CHEAP_THEN_ESCALATE", {"PRIMARY_ECONOMIC", "ESCALATION_STRONG"}),
    "B3": ("STATIC_FAMILY_POLICY", {"FAMILY_POLICY_MAP"}),
    "B4": ("LOCAL_OR_FREE_FIRST", {"PRIMARY_LOCAL_OR_FREE", "ESCALATION_STRONG"}),
}
REQUIRED_BINDING_FIELDS = {
    "binding_id", "binding_ref", "binding_file_sha256", "qualification_ref",
    "qualification_file_sha256", "exact_executor_identity", "surface_class",
}
ALLOWED_SURFACES = {
    "STRONG_REMOTE_PINNED", "ECONOMIC_REMOTE_PINNED", "LOCAL_PINNED",
    "HOSTED_FREE_PINNED", "SUBSCRIPTION_EXECUTOR_PINNED",
}


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve(root: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} missing")
    p = Path(value)
    if not p.is_absolute(): p = root / p
    p = p.resolve()
    if not p.is_file(): raise ValueError(f"{label} not found: {p}")
    return p


def verify_binding(root: Path, role: str, b: dict[str, Any]) -> None:
    missing = REQUIRED_BINDING_FIELDS - set(b)
    if missing: raise ValueError(f"{role}: binding fields missing: {sorted(missing)}")
    surface = b.get("surface_class")
    if surface not in ALLOWED_SURFACES: raise ValueError(f"{role}: invalid surface_class")
    bref = resolve(root, b.get("binding_ref"), f"{role}.binding_ref")
    qref = resolve(root, b.get("qualification_ref"), f"{role}.qualification_ref")
    if sha_file(bref) != b.get("binding_file_sha256"): raise ValueError(f"{role}: binding hash mismatch")
    if sha_file(qref) != b.get("qualification_file_sha256"): raise ValueError(f"{role}: qualification hash mismatch")
    payload = json.loads(bref.read_text(encoding="utf-8"))
    if payload.get("binding_id") != b.get("binding_id"): raise ValueError(f"{role}: binding_id mismatch")
    if payload.get("exact_executor_identity") != b.get("exact_executor_identity"): raise ValueError(f"{role}: executor identity mismatch")
    if payload.get("status") != "QUALIFIED": raise ValueError(f"{role}: binding is not QUALIFIED")
    if surface == "SUBSCRIPTION_EXECUTOR_PINNED":
        mref = resolve(root, b.get("evidence_manifest_ref"), f"{role}.evidence_manifest_ref")
        if sha_file(mref) != b.get("evidence_manifest_sha256"): raise ValueError(f"{role}: evidence manifest hash mismatch")
        sealed = verify_bundle(mref.parent)
        if (mref.parent / "executor-binding.json").resolve() != bref or (mref.parent / "qualification.json").resolve() != qref:
            raise ValueError(f"{role}: evidence manifest does not bind referenced binding/qualification files")
        if sealed["binding"].get("binding_id") != b.get("binding_id"):
            raise ValueError(f"{role}: sealed bundle binding_id mismatch")


def assess(registry_path: Path, artifact_root: Path) -> dict[str, Any]:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if registry.get("schema_id") != "ndv-p1-wp07-treatment-bindings-v1": raise ValueError("unexpected registry schema")
    rules = registry.get("binding_rules") or {}
    for field in ("concrete_binding_required", "binding_bytes_must_be_preserved", "binding_file_sha256_required", "qualification_evidence_required", "silent_substitution_forbidden", "dynamic_provider_routing_forbidden", "missing_binding_blocks_cell", "blocked_cell_is_not_a_run", "blocked_cell_cost_is_not_zero"):
        if rules.get(field) is not True: raise ValueError(f"binding rule drift: {field}")
    if registry.get("treatment_execution") != "NOT_EXECUTED" or registry.get("holdout_access") != "NONE": raise ValueError("binding registry contamination")
    treatments = registry.get("treatments")
    if not isinstance(treatments, dict) or set(treatments) != set(EXPECTED): raise ValueError("treatment registry must contain exactly B0-B4")

    status: dict[str, Any] = {}
    all_ready = True
    for tid, (name, required_roles) in EXPECTED.items():
        t = treatments[tid]
        if t.get("name") != name or set(t.get("required_roles") or []) != required_roles: raise ValueError(f"{tid}: treatment definition drift")
        bindings = t.get("bindings")
        if not isinstance(bindings, dict): raise ValueError(f"{tid}: bindings must be object")
        if tid == "B3":
            policy = t.get("family_policy")
            if policy:
                if not isinstance(policy, dict): raise ValueError("B3: family_policy must be object")
                bad = [f for f in policy if f not in {"F1","F2","F3","F4","F5","F6"}]
                if bad: raise ValueError(f"B3: invalid family keys: {bad}")
                for family, alias in policy.items():
                    if alias not in bindings: raise ValueError(f"B3: {family} points to unknown binding alias {alias}")
                for alias, b in bindings.items(): verify_binding(artifact_root, f"B3.{alias}", b)
                ready = bool(policy)
                missing = [] if ready else ["FAMILY_POLICY_MAP"]
            else:
                ready, missing = False, ["FAMILY_POLICY_MAP"]
        else:
            missing = sorted(role for role in required_roles if role not in bindings)
            for role, b in bindings.items():
                if role not in required_roles: raise ValueError(f"{tid}: unexpected role {role}")
                verify_binding(artifact_root, f"{tid}.{role}", b)
            ready = not missing
        declared = t.get("status")
        if ready and declared != "BOUND_READY": raise ValueError(f"{tid}: ready bindings require status BOUND_READY")
        if not ready and declared not in {"UNBOUND", "PARTIALLY_BOUND"}: raise ValueError(f"{tid}: incomplete bindings require UNBOUND/PARTIALLY_BOUND")
        status[tid] = {"ready": ready, "missing_roles": missing, "declared_status": declared}
        all_ready = all_ready and ready

    return {
        "schema_id": "ndv-p1-wp07-binding-readiness-v1",
        "status": "ALL_TREATMENTS_BOUND" if all_ready else "BINDING_COVERAGE_INCOMPLETE",
        "registry_ref": str(registry_path.resolve()),
        "registry_file_sha256": sha_file(registry_path.resolve()),
        "treatments": status,
        "all_treatments_ready": all_ready,
        "matrix_materialization_release": "YES" if all_ready else "NO",
        "treatment_execution": "NOT_EXECUTED",
        "holdout_access": "NONE",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--registry", type=Path, default=Path("experiments/p1/wp07-treatment-bindings-v1.json"))
    ap.add_argument("--artifact-root", type=Path, default=Path("."))
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    try: result = assess(args.registry.resolve(), args.artifact_root.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status":"FAIL","reason":"WP07_BINDING_READINESS_BLOCKED","detail":str(exc)}, indent=2)); return 2
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        if args.out.exists(): raise SystemExit(f"refusing overwrite: {args.out}")
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__": raise SystemExit(main())
