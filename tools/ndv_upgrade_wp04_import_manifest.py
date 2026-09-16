#!/usr/bin/env python3
"""Upgrade a preserved WP-04 import manifest v1 to a hash-indexed v2 sidecar.

The historical v1 manifest is never modified. The tool independently revalidates
run-report.json and evidence/ using the current importer contract, recomputes the
artifact inventory and token telemetry, and writes import-manifest-v2.json.
It never re-executes a treatment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from ndv_import_wp04_stage_run import parse_aider_tokens, validate_bundle


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def preserved_artifacts(run_dir: Path) -> list[dict[str, Any]]:
    paths = [run_dir / "run-report.json"]
    evidence = run_dir / "evidence"
    paths.extend(sorted(p for p in evidence.rglob("*") if p.is_file()))
    records = []
    for path in paths:
        data = path.read_bytes()
        records.append({"path": path.relative_to(run_dir).as_posix(), "size_bytes": len(data), "sha256": sha256_bytes(data)})
    return records


def validate_legacy(legacy: dict[str, Any], report: dict[str, Any]) -> None:
    if legacy.get("schema_id") != "ndv-wp04-import-manifest-v1":
        raise ValueError("historical import-manifest.json must be v1")
    for key in ("task_id", "binding_id", "outcome", "retry_count", "escalation_count", "holdout_access"):
        if legacy.get(key) != report.get(key):
            raise ValueError(f"legacy manifest/report mismatch for {key}")
    candidate = report.get("candidate", {})
    if legacy.get("candidate_diff_sha256") != candidate.get("diff_sha256") or legacy.get("candidate_diff_bytes") != candidate.get("diff_bytes"):
        raise ValueError("legacy candidate binding mismatch")
    if legacy.get("treatment_reexecuted") is not False:
        raise ValueError("legacy manifest does not prove treatment_reexecuted=false")


def build_sidecar(run_dir: Path) -> dict[str, Any]:
    legacy_path = run_dir / "import-manifest.json"
    if not legacy_path.is_file():
        raise ValueError("historical import-manifest.json missing")
    legacy = load(legacy_path)
    report, tokens = validate_bundle(run_dir)
    validate_legacy(legacy, report)
    executor_log = run_dir / "evidence" / "executor.log"
    tokens = parse_aider_tokens(executor_log.read_text(encoding="utf-8", errors="replace"))
    return {
        "schema_id": "ndv-wp04-import-manifest-v2",
        "source_run_schema": report["schema_id"],
        "task_id": report.get("task_id"),
        "binding_id": report.get("binding_id"),
        "outcome": report.get("outcome"),
        "failure_attribution": report.get("failure_attribution"),
        "retry_count": report.get("retry_count"),
        "escalation_count": report.get("escalation_count"),
        "holdout_access": report.get("holdout_access"),
        "candidate_diff_sha256": report.get("candidate", {}).get("diff_sha256"),
        "candidate_diff_bytes": report.get("candidate", {}).get("diff_bytes"),
        "executor_wall_seconds": report.get("accounting", {}).get("executor_wall_seconds", report.get("executor", {}).get("wall_seconds")),
        "token_reconciliation": tokens,
        "preserved_artifacts": preserved_artifacts(run_dir),
        "excluded_from_import": ["workspace/", "verifier-venv/"],
        "raw_evidence_preserved": True,
        "treatment_reexecuted": False,
        "upgrade_provenance": {
            "mode": "NON_DESTRUCTIVE_SIDECAR",
            "legacy_manifest_ref": "import-manifest.json",
            "legacy_manifest_sha256": sha256_bytes(legacy_path.read_bytes()),
            "treatment_reexecution": "NONE",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", required=True, type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    run_dir = args.run_dir.resolve()
    out = (args.out or run_dir / "import-manifest-v2.json").resolve()
    if out.exists():
        raise SystemExit(f"refusing overwrite: {out}")
    try:
        sidecar = build_sidecar(run_dir)
    except Exception as exc:
        raise SystemExit(f"UPGRADE_REJECTED: {exc}") from exc
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "UPGRADED_SIDECAR_ONLY", "out": str(out), "task_id": sidecar["task_id"], "treatment_reexecuted": False}, indent=2))
    return 0


if __name__ == "__main__": raise SystemExit(main())
