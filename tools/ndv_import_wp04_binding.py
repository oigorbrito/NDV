#!/usr/bin/env python3
"""Preserve the exact original WP-04 binding-v2 and its qualification evidence.

This tool never reconstructs either artifact. It accepts the operator-supplied
original binding file and the exact qualification evidence referenced by that
binding, validates both against the frozen WP-04 contract and preserved Stage-1
report, copies the exact bytes into an immutable evidence directory, and writes
a SHA-256 receipt. No treatment is executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from ndv_validate_wp04_smoke import validate_binding


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_original(binding: dict[str, Any], stage1_report: dict[str, Any]) -> None:
    errors = validate_binding(binding)
    if errors:
        raise ValueError("binding contract invalid: " + "; ".join(errors))
    if stage1_report.get("schema_id") != "ndv-wp04-stage1-run-v1" or stage1_report.get("task_id") != "D-F5-01":
        raise ValueError("Stage-1 report identity/schema invalid")
    if binding.get("binding_id") != stage1_report.get("binding_id"):
        raise ValueError("binding_id does not match preserved Stage-1 report")
    if binding.get("exact_executor_identity") != stage1_report.get("executor_identity"):
        raise ValueError("exact executor identity does not match preserved Stage-1 report")
    if stage1_report.get("retry_count") != 0 or stage1_report.get("escalation_count") != 0 or stage1_report.get("holdout_access") != "NONE":
        raise ValueError("Stage-1 report is not compatible with WP-04 frozen execution policy")
    if binding.get("retry_limit") != 0 or binding.get("escalation_limit") != 0:
        raise ValueError("binding retry/escalation policy mismatch")
    if any(binding.get(field) is not False for field in ("automatic_download", "implicit_fallback", "dynamic_routing")):
        raise ValueError("binding permits forbidden dynamic behavior")


def validate_qualification_bytes(binding: dict[str, Any], qualification_path: Path) -> None:
    expected = binding.get("qualification_evidence_sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError("binding qualification_evidence_sha256 missing/invalid")
    observed = sha256_file(qualification_path)
    if observed != expected:
        raise ValueError("qualification evidence SHA-256 does not match binding")
    payload = load(qualification_path)
    if not isinstance(payload, dict):
        raise ValueError("qualification evidence must be a JSON object")
    status = payload.get("status")
    if status not in {"S0_READY", "QUALIFIED"}:
        raise ValueError(f"qualification evidence is not a ready/qualified result: {status}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--binding", required=True, type=Path, help="Exact original binding-v2 file used by Stage 1")
    ap.add_argument("--qualification-evidence", required=True, type=Path, help="Exact qualification evidence referenced by the binding")
    ap.add_argument("--stage1-report", type=Path, default=Path("pilot-runs/wp04-real-executor-smoke/stage1-d-f5-01-r1/run-report.json"))
    ap.add_argument("--dest-dir", type=Path, default=Path("pilot-runs/wp04-real-executor-smoke/binding-stage1"))
    args = ap.parse_args()

    source = args.binding.resolve()
    qualification_source = args.qualification_evidence.resolve()
    report_path = args.stage1_report.resolve()
    for path, label in ((source, "original binding"), (qualification_source, "qualification evidence"), (report_path, "Stage-1 report")):
        if not path.is_file():
            raise SystemExit(f"BINDING_IMPORT_BLOCKED: {label} not found: {path}")
    try:
        binding = load(source)
        report = load(report_path)
        if not isinstance(binding, dict) or not isinstance(report, dict):
            raise ValueError("binding and Stage-1 report must be JSON objects")
        validate_original(binding, report)
        validate_qualification_bytes(binding, qualification_source)
    except Exception as exc:
        raise SystemExit(f"BINDING_IMPORT_REJECTED: {exc}") from exc

    dest = args.dest_dir.resolve()
    if dest.exists():
        raise SystemExit(f"BINDING_IMPORT_BLOCKED: destination exists; refusing overwrite: {dest}")
    dest.mkdir(parents=True)
    binding_dest = dest / "executor-binding-v2.json"
    qualification_dest = dest / "qualification-evidence.json"
    shutil.copyfile(source, binding_dest)
    shutil.copyfile(qualification_source, qualification_dest)
    source_sha = sha256_file(source)
    qualification_sha = sha256_file(qualification_source)
    if sha256_file(binding_dest) != source_sha or sha256_file(qualification_dest) != qualification_sha:
        raise SystemExit("BINDING_IMPORT_REJECTED: copied evidence bytes differ from originals")

    receipt = {
        "schema_id": "ndv-wp04-binding-import-receipt-v2",
        "status": "ORIGINAL_BINDING_AND_QUALIFICATION_PRESERVED",
        "binding_id": binding.get("binding_id"),
        "exact_executor_identity": binding.get("exact_executor_identity"),
        "surface_class": binding.get("surface_class"),
        "source_binding_path_observed": str(source),
        "source_qualification_path_observed": str(qualification_source),
        "preserved_binding_ref": "executor-binding-v2.json",
        "binding_file_sha256": source_sha,
        "binding_file_size_bytes": binding_dest.stat().st_size,
        "preserved_qualification_ref": "qualification-evidence.json",
        "qualification_file_sha256": qualification_sha,
        "qualification_file_size_bytes": qualification_dest.stat().st_size,
        "stage1_report_ref": str(args.stage1_report),
        "stage1_report_sha256": sha256_file(report_path),
        "binding_declared_qualification_ref": binding.get("qualification_evidence_ref"),
        "binding_declared_qualification_sha256": binding.get("qualification_evidence_sha256"),
        "treatment_reexecuted": False,
        "binding_reconstructed": False,
        "qualification_reconstructed": False,
        "holdout_access": "NONE",
    }
    (dest / "binding-import-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "binding_id": receipt["binding_id"], "binding_sha256": source_sha, "qualification_sha256": qualification_sha, "dest": str(dest)}, indent=2))
    return 0


if __name__ == "__main__": raise SystemExit(main())
