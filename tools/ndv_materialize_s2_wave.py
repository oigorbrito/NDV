#!/usr/bin/env python3
"""Materialize one frozen S2 wave from already-acquired Parquet bytes.

This command performs no network access, Docker execution, model call, treatment,
or holdout access. It verifies the acquisition receipt against the exact snapshot,
contract, and Parquet bytes, then invokes the pinned extractor with quarantine and
writes a byte-bound materialization receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require_file(path: Path, name: str) -> Path:
    path = path.resolve()
    if not path.is_file():
        raise ValueError(f"{name} not found: {path}")
    return path


def verify_acquisition(parquet: Path, receipt_path: Path, snapshot_path: Path, contract_path: Path) -> dict[str, Any]:
    parquet = require_file(parquet, "parquet")
    receipt_path = require_file(receipt_path, "acquisition receipt")
    snapshot_path = require_file(snapshot_path, "source snapshot")
    contract_path = require_file(contract_path, "acquisition contract")
    receipt, snapshot, contract = load(receipt_path), load(snapshot_path), load(contract_path)
    if not all(isinstance(x, dict) for x in (receipt, snapshot, contract)):
        raise ValueError("receipt, snapshot, and contract must be JSON objects")
    if receipt.get("schema_id") != "ndv-p1-s2-parquet-acquisition-receipt-v2":
        raise ValueError("unexpected acquisition receipt schema")
    if receipt.get("status") not in {"DOWNLOADED_VERIFIED", "REUSED_VERIFIED_EXISTING"}:
        raise ValueError("acquisition receipt is not a verified terminal state")
    if receipt.get("treatment_execution") != "NOT_EXECUTED" or receipt.get("holdout_access") != "NONE":
        raise ValueError("acquisition receipt contamination detected")
    if snapshot.get("source_id") != contract.get("source_id") or receipt.get("source_id") != snapshot.get("source_id"):
        raise ValueError("source_id binding mismatch")
    if receipt.get("source_snapshot_file_sha256") != sha256_file(snapshot_path):
        raise ValueError("source snapshot file SHA-256 mismatch")
    if receipt.get("acquisition_contract_file_sha256") != sha256_file(contract_path):
        raise ValueError("acquisition contract file SHA-256 mismatch")
    observed = receipt.get("observed")
    expected_sha, expected_size = snapshot.get("parquet_sha256"), snapshot.get("parquet_remote_size_bytes")
    actual_sha, actual_size = sha256_file(parquet), parquet.stat().st_size
    if actual_sha != expected_sha or actual_size != expected_size:
        raise ValueError("local Parquet bytes do not match frozen snapshot")
    if not isinstance(observed, dict) or observed.get("sha256") != actual_sha or observed.get("size_bytes") != actual_size or observed.get("sha256_match") is not True or observed.get("size_match") is not True:
        raise ValueError("acquisition receipt observed-byte binding mismatch")
    if receipt.get("expected_sha256") != expected_sha or receipt.get("expected_size_bytes") != expected_size:
        raise ValueError("acquisition receipt expected-byte binding mismatch")
    if receipt.get("pinned_revision") != snapshot.get("pinned_revision") or receipt.get("dataset") != snapshot.get("dataset") or receipt.get("parquet_path") != snapshot.get("parquet_path"):
        raise ValueError("acquisition receipt source identity mismatch")
    return {"parquet_sha256": actual_sha, "parquet_size_bytes": actual_size, "receipt_file_sha256": sha256_file(receipt_path), "snapshot_file_sha256": sha256_file(snapshot_path), "contract_file_sha256": sha256_file(contract_path)}


def run_extraction(extractor: Path, parquet: Path, snapshot: Path, wave: Path, rows_out: Path, quarantine_out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([
        sys.executable, str(extractor), "--parquet", str(parquet), "--snapshot", str(snapshot),
        "--wave", str(wave), "--out", str(rows_out), "--quarantine-out", str(quarantine_out),
    ], text=True, capture_output=True, check=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parquet", required=True, type=Path)
    ap.add_argument("--acquisition-receipt", required=True, type=Path)
    ap.add_argument("--snapshot", type=Path, default=Path("experiments/p1/s2-source-snapshot-01.json"))
    ap.add_argument("--contract", type=Path, default=Path("experiments/p1/s2-parquet-acquisition-v1.json"))
    ap.add_argument("--wave", type=Path, default=Path("experiments/p1/s2-candidate-wave-01.json"))
    ap.add_argument("--out-root", type=Path, default=Path(".ndv-corpus/s2-w01"))
    ap.add_argument("--extractor", type=Path, default=Path("tools/ndv_extract_pinned_swe_rebench_rows.py"))
    args = ap.parse_args()
    try:
        integrity = verify_acquisition(args.parquet, args.acquisition_receipt, args.snapshot, args.contract)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "reason": "ACQUISITION_BINDING_INVALID", "detail": str(exc)}, indent=2)); return 2

    root = args.out_root.resolve(); rows_out = root / "pinned-rows.jsonl"; quarantine_out = root / "quarantine"
    proc = run_extraction(args.extractor, args.parquet, args.snapshot, args.wave, rows_out, quarantine_out)
    if proc.returncode != 0:
        print(json.dumps({"status": "FAIL", "reason": "EXTRACTION_OR_QUARANTINE_FAILED", "exit_code": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}, indent=2)); return 2
    aggregate = quarantine_out / "quarantine-aggregate.json"
    if not rows_out.is_file() or not aggregate.is_file():
        print(json.dumps({"status": "FAIL", "reason": "EXPECTED_MATERIALIZATION_ARTIFACT_MISSING"}, indent=2)); return 2
    q = load(aggregate)
    wave = load(args.wave)
    if not isinstance(q, dict) or q.get("schema_id") != "ndv-p1-s2-quarantine-aggregate-v2" or q.get("wave_id") != wave.get("wave_id") or q.get("passed_count") != q.get("candidate_count") or q.get("candidate_count") != len(wave.get("candidates", [])):
        print(json.dumps({"status": "FAIL", "reason": "QUARANTINE_AGGREGATE_INVALID"}, indent=2)); return 2

    receipt = {
        "schema_id": "ndv-p1-s2-wave-materialization-receipt-v1", "status": "MATERIALIZED_QUARANTINED",
        "wave_id": wave.get("wave_id"), "wave_file_sha256": sha256_file(args.wave),
        "acquisition": integrity, "rows_ref": str(rows_out), "rows_file_sha256": sha256_file(rows_out),
        "quarantine_aggregate_ref": str(aggregate), "quarantine_aggregate_file_sha256": sha256_file(aggregate),
        "candidate_count": q.get("candidate_count"), "passed_count": q.get("passed_count"),
        "network_used": False, "docker_execution": False, "model_execution": "NONE",
        "treatment_execution": "NOT_EXECUTED", "holdout_access": "NONE", "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    root.mkdir(parents=True, exist_ok=True); out = root / "materialization-receipt.json"
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "receipt": str(out), "candidate_count": receipt["candidate_count"], "passed_count": receipt["passed_count"]}, indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
