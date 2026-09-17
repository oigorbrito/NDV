#!/usr/bin/env python3
"""Seal and verify immutable evidence bundles for WP-07 Codex qualifications."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REQUIRED_ARTIFACTS = (
    "qualification.json",
    "executor-binding.json",
    "evidence/executor.log",
    "evidence/candidate.diff",
    "evidence/git-status.txt",
)


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def artifact_record(root: Path, rel: str) -> dict[str, Any]:
    path = root / rel
    if not path.is_file():
        raise ValueError(f"missing Codex qualification artifact: {rel}")
    return {"path": rel, "sha256": sha_file(path), "size_bytes": path.stat().st_size}


def seal_bundle(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = root / "evidence-manifest.json"
    if manifest_path.exists():
        raise ValueError(f"refusing overwrite: {manifest_path}")
    q = json.loads((root / "qualification.json").read_text(encoding="utf-8"))
    b = json.loads((root / "executor-binding.json").read_text(encoding="utf-8"))
    if q.get("schema_id") != "ndv-p1-wp07-codex-subscription-qualification-v1" or q.get("status") != "S0_READY":
        raise ValueError("only S0_READY Codex qualifications can be sealed")
    if b.get("schema_id") != "ndv-p1-wp07-executor-binding-v1" or b.get("status") != "QUALIFIED":
        raise ValueError("qualified Codex binding required")
    if b.get("qualification_file_sha256") != sha_file(root / "qualification.json"):
        raise ValueError("binding is not hash-bound to qualification.json")
    if b.get("candidate_id") != q.get("candidate_id") or (b.get("model") or {}).get("identity") != q.get("requested_model"):
        raise ValueError("binding/qualification identity mismatch")
    artifacts = [artifact_record(root, rel) for rel in REQUIRED_ARTIFACTS]
    manifest = {
        "schema_id": "ndv-p1-wp07-codex-evidence-manifest-v1",
        "status": "SEALED_SYNTHETIC_QUALIFICATION_EVIDENCE",
        "candidate_id": q.get("candidate_id"),
        "requested_model": q.get("requested_model"),
        "binding_id": b.get("binding_id"),
        "artifacts": artifacts,
        "development_task_exposure": False,
        "treatment_execution": "NOT_EXECUTED",
        "holdout_access": "NONE",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def verify_bundle(root: Path, *, expected_model: str | None = None, expected_candidate: str | None = None) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = root / "evidence-manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"{root}: evidence-manifest.json required")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_id") != "ndv-p1-wp07-codex-evidence-manifest-v1" or manifest.get("status") != "SEALED_SYNTHETIC_QUALIFICATION_EVIDENCE":
        raise ValueError(f"{root}: invalid Codex evidence manifest")
    if manifest.get("development_task_exposure") is not False or manifest.get("treatment_execution") != "NOT_EXECUTED" or manifest.get("holdout_access") != "NONE":
        raise ValueError(f"{root}: contaminated Codex evidence manifest")
    records = manifest.get("artifacts")
    if not isinstance(records, list):
        raise ValueError(f"{root}: artifact inventory must be a list")
    by_path: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str) or record["path"] in by_path:
            raise ValueError(f"{root}: invalid/duplicate artifact inventory")
        by_path[record["path"]] = record
    if set(by_path) != set(REQUIRED_ARTIFACTS):
        raise ValueError(f"{root}: artifact inventory must contain exactly required qualification artifacts")
    for rel in REQUIRED_ARTIFACTS:
        path = root / rel
        rec = by_path[rel]
        if not path.is_file() or sha_file(path) != rec.get("sha256") or path.stat().st_size != rec.get("size_bytes"):
            raise ValueError(f"{root}: artifact hash/size mismatch: {rel}")
    q = json.loads((root / "qualification.json").read_text(encoding="utf-8"))
    b = json.loads((root / "executor-binding.json").read_text(encoding="utf-8"))
    if q.get("status") != "S0_READY" or b.get("status") != "QUALIFIED":
        raise ValueError(f"{root}: qualification/binding no longer ready")
    if b.get("qualification_file_sha256") != sha_file(root / "qualification.json"):
        raise ValueError(f"{root}: binding qualification hash mismatch")
    if manifest.get("candidate_id") != q.get("candidate_id") or manifest.get("binding_id") != b.get("binding_id") or manifest.get("requested_model") != q.get("requested_model"):
        raise ValueError(f"{root}: manifest identity mismatch")
    if expected_model is not None and q.get("requested_model") != expected_model:
        raise ValueError(f"{root}: expected model mismatch")
    if expected_candidate is not None and q.get("candidate_id") != expected_candidate:
        raise ValueError(f"{root}: expected candidate mismatch")
    return {"manifest": manifest, "qualification": q, "binding": b, "manifest_path": manifest_path}
