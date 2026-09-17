#!/usr/bin/env python3
"""Promote a preserved WP-04 local binding into WP-07 B4 first-hop registry state.

This is deliberately narrow. The WP-04 Aider+Ollama evidence may populate only
B4.PRIMARY_LOCAL_OR_FREE. It is not evidence for STRONG, ECONOMIC, STATIC_FAMILY,
or escalation roles. No treatment is executed and the input registry is never
modified in place.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require_file(path: Path, label: str) -> Path:
    p = path.resolve()
    if not p.is_file():
        raise ValueError(f"{label} not found: {p}")
    return p


def rel_to_root(path: Path, root: Path, label: str) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError as exc:
        raise ValueError(f"{label} must be inside artifact root {root.resolve()}") from exc


def validate_import(binding_import: Path, artifact_root: Path) -> dict[str, Any]:
    root = binding_import.resolve()
    receipt_path = require_file(root / "binding-import-receipt.json", "binding receipt")
    binding_path = require_file(root / "executor-binding-v2.json", "preserved binding")
    qualification_path = require_file(root / "qualification-evidence.json", "preserved qualification evidence")
    receipt, binding, qualification = load(receipt_path), load(binding_path), load(qualification_path)
    if receipt.get("schema_id") != "ndv-wp04-binding-import-receipt-v2" or receipt.get("status") != "ORIGINAL_BINDING_AND_QUALIFICATION_PRESERVED":
        raise ValueError("WP-04 binding import receipt v2/pass required")
    if receipt.get("binding_reconstructed") is not False or receipt.get("qualification_reconstructed") is not False or receipt.get("treatment_reexecuted") is not False or receipt.get("holdout_access") != "NONE":
        raise ValueError("WP-04 binding import provenance invalid")
    if sha_file(binding_path) != receipt.get("binding_file_sha256") or binding_path.stat().st_size != receipt.get("binding_file_size_bytes"):
        raise ValueError("preserved binding hash/size mismatch")
    if sha_file(qualification_path) != receipt.get("qualification_file_sha256") or qualification_path.stat().st_size != receipt.get("qualification_file_size_bytes"):
        raise ValueError("preserved qualification hash/size mismatch")
    if binding.get("schema_id") != "ndv-p1-wp04-executor-binding-v2" or binding.get("status") != "QUALIFIED":
        raise ValueError("qualified WP-04 binding-v2 required")
    if binding.get("binding_id") != receipt.get("binding_id") or binding.get("exact_executor_identity") != receipt.get("exact_executor_identity"):
        raise ValueError("binding identity differs from preservation receipt")
    if binding.get("qualification_evidence_sha256") != receipt.get("qualification_file_sha256"):
        raise ValueError("binding/qualification SHA-256 mismatch")
    if qualification.get("status") not in {"S0_READY", "QUALIFIED"}:
        raise ValueError("qualification evidence is not ready/qualified")
    surface = binding.get("surface_class")
    if surface not in {"LOCAL_PINNED", "HOSTED_FREE_PINNED"}:
        raise ValueError(f"WP-04 promotion to B4 first hop requires LOCAL_PINNED/HOSTED_FREE_PINNED, got {surface}")
    if binding.get("dynamic_routing") is not False or binding.get("implicit_fallback") is not False or binding.get("automatic_download") is not False:
        raise ValueError("binding permits forbidden dynamic behavior")
    return {
        "binding_id": binding["binding_id"],
        "binding_ref": rel_to_root(binding_path, artifact_root, "binding"),
        "binding_file_sha256": sha_file(binding_path),
        "qualification_ref": rel_to_root(qualification_path, artifact_root, "qualification evidence"),
        "qualification_file_sha256": sha_file(qualification_path),
        "exact_executor_identity": binding["exact_executor_identity"],
        "surface_class": surface,
        "promotion_source": "WP04_ORIGINAL_BINDING_IMPORT_V2",
        "role_scope": "B4.PRIMARY_LOCAL_OR_FREE_ONLY",
    }


def promote(registry_path: Path, binding_import: Path, artifact_root: Path) -> dict[str, Any]:
    registry = load(registry_path)
    if registry.get("schema_id") != "ndv-p1-wp07-treatment-bindings-v1":
        raise ValueError("unexpected WP-07 binding registry schema")
    if registry.get("treatment_execution") != "NOT_EXECUTED" or registry.get("holdout_access") != "NONE":
        raise ValueError("WP-07 registry provenance contaminated")
    treatments = registry.get("treatments")
    if not isinstance(treatments, dict) or "B4" not in treatments:
        raise ValueError("B4 missing from registry")
    b4 = treatments["B4"]
    bindings = b4.get("bindings")
    if not isinstance(bindings, dict):
        raise ValueError("B4 bindings must be object")
    if "PRIMARY_LOCAL_OR_FREE" in bindings:
        raise ValueError("B4.PRIMARY_LOCAL_OR_FREE already populated; refusing overwrite")
    record = validate_import(binding_import, artifact_root)
    bindings["PRIMARY_LOCAL_OR_FREE"] = record
    missing = [role for role in b4.get("required_roles", []) if role not in bindings]
    b4["status"] = "BOUND_READY" if not missing else "PARTIALLY_BOUND"
    registry["status"] = "INCOMPLETE_BINDING_COVERAGE"
    registry["treatment_execution"] = "NOT_EXECUTED"
    registry["holdout_access"] = "NONE"
    return registry


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--registry", type=Path, default=Path("experiments/p1/wp07-treatment-bindings-v1.json"))
    ap.add_argument("--binding-import", required=True, type=Path)
    ap.add_argument("--artifact-root", type=Path, default=Path("."))
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    try:
        result = promote(args.registry.resolve(), args.binding_import.resolve(), args.artifact_root.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status":"FAIL","reason":"WP04_TO_WP07_PROMOTION_BLOCKED","detail":str(exc)}, indent=2)); return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists():
        raise SystemExit(f"refusing overwrite: {args.out}")
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({"status":"WP07_B4_FIRST_HOP_PROMOTED","out":str(args.out),"b4_status":result["treatments"]["B4"]["status"],"treatment_execution":"NOT_EXECUTED"}, indent=2))
    return 0


if __name__ == "__main__": raise SystemExit(main())
