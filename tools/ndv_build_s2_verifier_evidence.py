#!/usr/bin/env python3
"""Build immutable focal/preservation verifier evidence from quarantined admission metadata.

This tool is admission-side only. It does not execute a model, does not apply a
solution patch, and does not expose grader metadata to executor-visible context.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def normalize_tests(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(x, str) and x for x in value):
        raise ValueError(f"{field} must be an array of non-empty strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{field} contains duplicates")
    return list(value)


def build(admission: dict[str, Any], parser_provenance: dict[str, Any]) -> dict[str, Any]:
    instance_id = admission.get("instance_id")
    repo = admission.get("repo")
    base = admission.get("base_commit")
    if not all(isinstance(x, str) and x for x in (instance_id, repo, base)):
        raise ValueError("admission row requires instance_id, repo, base_commit")

    install = admission.get("install_config")
    if not isinstance(install, dict):
        raise ValueError("admission row requires install_config")
    parser_name = install.get("log_parser")
    if not isinstance(parser_name, str) or not parser_name:
        raise ValueError("install_config.log_parser required")

    if parser_provenance.get("parser_name") != parser_name:
        raise ValueError("parser provenance name mismatch")
    for field in ("repository", "revision", "path", "blob_sha"):
        if not isinstance(parser_provenance.get(field), str) or not parser_provenance[field]:
            raise ValueError(f"parser provenance requires {field}")

    focal = normalize_tests(admission.get("FAIL_TO_PASS"), "FAIL_TO_PASS")
    preservation = normalize_tests(admission.get("PASS_TO_PASS"), "PASS_TO_PASS")
    if not focal:
        raise ValueError("FAIL_TO_PASS must be non-empty for focal verification")

    common = {
        "instance_id": instance_id,
        "repository": repo,
        "base_commit": base,
        "parser": {
            "name": parser_name,
            "repository": parser_provenance["repository"],
            "revision": parser_provenance["revision"],
            "path": parser_provenance["path"],
            "blob_sha": parser_provenance["blob_sha"],
        },
        "source": "QUARANTINED_ADMISSION_ONLY_ROW",
        "treatment_derived": False,
    }
    focal_payload = {
        **common,
        "schema_id": "ndv-p1-s2-focal-verifier-v1",
        "expected_base_statuses": ["FAILED", "ERROR"],
        "expected_solved_status": "PASSED",
        "tests": focal,
    }
    preservation_payload = {
        **common,
        "schema_id": "ndv-p1-s2-preservation-verifier-v1",
        "expected_base_status": "PASSED",
        "expected_solved_status": "PASSED",
        "tests": preservation,
    }
    provenance_payload = {
        "schema_id": "ndv-p1-s2-verifier-provenance-v1",
        "instance_id": instance_id,
        "repository": repo,
        "base_commit": base,
        "parser": common["parser"],
        "focal_tests_source": "FAIL_TO_PASS",
        "preservation_tests_source": "PASS_TO_PASS",
        "focal_sha256": sha256(focal_payload),
        "preservation_sha256": sha256(preservation_payload),
        "independence": {
            "frozen_before_treatment": True,
            "derived_from_treatment_output": False,
            "gold_solution_exposed_to_executor": False,
        },
    }
    return {
        "focal": focal_payload,
        "preservation": preservation_payload,
        "provenance": provenance_payload,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--admission-only", required=True, type=Path)
    ap.add_argument("--parser-provenance", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    admission = load(args.admission_only)
    provenance = load(args.parser_provenance)
    if not isinstance(admission, dict) or not isinstance(provenance, dict):
        raise SystemExit("inputs must be JSON objects")
    result = build(admission, provenance)
    args.out.mkdir(parents=True, exist_ok=True)
    write(args.out / "focal-verifier.json", result["focal"])
    write(args.out / "preservation-verifier.json", result["preservation"])
    write(args.out / "verifier-provenance.json", result["provenance"])
    summary = {
        "schema_id": "ndv-p1-s2-verifier-evidence-bundle-v1",
        "instance_id": admission["instance_id"],
        "focal_ref": "focal-verifier.json",
        "focal_sha256": sha256(result["focal"]),
        "preservation_ref": "preservation-verifier.json",
        "preservation_sha256": sha256(result["preservation"]),
        "provenance_ref": "verifier-provenance.json",
        "provenance_sha256": sha256(result["provenance"]),
    }
    write(args.out / "bundle.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
