#!/usr/bin/env python3
"""Acquire the frozen SWE-rebench V2 Parquet with size/SHA verification.

Network I/O occurs only when explicitly invoked by an operator. The tool calls
no models, executes no treatment, accesses no holdout material, and mutates no
candidate metadata. It binds the receipt to the exact source/contract bytes and
finalizes the destination only after frozen integrity checks pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_contract_binding(snapshot: dict[str, Any], contract: dict[str, Any]) -> None:
    if snapshot.get("schema_id") != "ndv-p1-s2-source-snapshot-v1":
        raise ValueError("unexpected source snapshot schema")
    if contract.get("schema_id") != "ndv-p1-s2-parquet-acquisition-v1":
        raise ValueError("unexpected acquisition contract schema")
    source_id = snapshot.get("source_id")
    if not isinstance(source_id, str) or not source_id or source_id != contract.get("source_id"):
        raise ValueError("source_id mismatch between snapshot and acquisition contract")
    if snapshot.get("treatment_execution") != "NOT_EXECUTED" or snapshot.get("holdout_access") != "NONE":
        raise ValueError("source snapshot is treatment/holdout contaminated")
    if contract.get("treatment_execution") != "NOT_EXECUTED" or contract.get("holdout_access") != "NONE" or contract.get("model_execution") != "NONE":
        raise ValueError("acquisition contract permits forbidden execution/access")
    policy = snapshot.get("integrity_policy")
    if not isinstance(policy, dict) or policy.get("admission_requires_strong_path") is not True:
        raise ValueError("source snapshot does not require strong integrity path")


def build_url(snapshot: dict[str, Any], contract: dict[str, Any]) -> str:
    dataset, revision, parquet_path, template = snapshot.get("dataset"), snapshot.get("pinned_revision"), snapshot.get("parquet_path"), contract.get("remote_url_template")
    if not isinstance(dataset, str) or not dataset or "/" not in dataset:
        raise ValueError("snapshot dataset must be owner/name")
    if not isinstance(revision, str) or not SHA40.fullmatch(revision):
        raise ValueError("snapshot pinned_revision must be exact 40-hex")
    if not isinstance(parquet_path, str) or not parquet_path or parquet_path.startswith(("/", "\\")) or ".." in Path(parquet_path).parts:
        raise ValueError("snapshot parquet_path must be a safe relative path")
    if not isinstance(template, str) or any(x not in template for x in ("{dataset}", "{revision}", "{parquet_path}")):
        raise ValueError("acquisition contract remote_url_template invalid")
    return template.format(dataset=dataset, revision=revision, parquet_path=parquet_path)


def expected_integrity(snapshot: dict[str, Any]) -> tuple[int, str]:
    size, digest = snapshot.get("parquet_remote_size_bytes"), snapshot.get("parquet_sha256")
    if not isinstance(size, int) or size <= 0:
        raise ValueError("snapshot parquet_remote_size_bytes must be positive integer")
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise ValueError("snapshot parquet_sha256 must be 64-hex")
    return size, digest


def verify_file(path: Path, expected_size: int, expected_sha: str) -> dict[str, Any]:
    size, digest = path.stat().st_size, sha256_file(path)
    return {"size_bytes": size, "sha256": digest, "size_match": size == expected_size, "sha256_match": digest == expected_sha}


def download(url: str, partial: Path, *, chunk_size: int = 1024 * 1024) -> int:
    partial.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    request = urllib.request.Request(url, headers={"User-Agent": "NDV-P1-S2/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as out:
        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            out.write(chunk); written += len(chunk)
        out.flush(); os.fsync(out.fileno())
    return written


def write_receipt(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--snapshot", type=Path, default=Path("experiments/p1/s2-source-snapshot-01.json"))
    ap.add_argument("--contract", type=Path, default=Path("experiments/p1/s2-parquet-acquisition-v1.json"))
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--receipt", type=Path)
    args = ap.parse_args()

    snapshot, contract = load(args.snapshot), load(args.contract)
    if not isinstance(snapshot, dict) or not isinstance(contract, dict):
        raise SystemExit("ACQUISITION_BLOCKED: snapshot and contract must be JSON objects")
    try:
        validate_contract_binding(snapshot, contract)
        url = build_url(snapshot, contract)
        expected_size, expected_sha = expected_integrity(snapshot)
    except ValueError as exc:
        raise SystemExit(f"ACQUISITION_BLOCKED: {exc}") from exc

    snapshot_file_sha = sha256_file(args.snapshot)
    contract_file_sha = sha256_file(args.contract)
    out = args.out.resolve(); receipt = (args.receipt or out.with_suffix(out.suffix + ".receipt.json")).resolve(); partial = out.with_name(out.name + ".part")
    if partial.exists():
        raise SystemExit(f"ACQUISITION_BLOCKED: partial file already exists; inspect/remove explicitly: {partial}")

    if out.exists():
        observed = verify_file(out, expected_size, expected_sha)
        if not observed["size_match"] or not observed["sha256_match"]:
            raise SystemExit("ACQUISITION_BLOCKED: existing destination fails frozen integrity; refusing overwrite")
        status, network_used = "REUSED_VERIFIED_EXISTING", False
    else:
        try:
            written = download(url, partial)
        except Exception as exc:
            raise SystemExit(f"ACQUISITION_FAILED: {exc}; partial retained at {partial}") from exc
        observed = verify_file(partial, expected_size, expected_sha); observed["stream_written_bytes"] = written
        if not observed["size_match"] or not observed["sha256_match"]:
            raise SystemExit(f"ACQUISITION_INTEGRITY_FAIL: partial retained for inspection at {partial}")
        partial.replace(out); status, network_used = "DOWNLOADED_VERIFIED", True

    payload = {
        "schema_id": "ndv-p1-s2-parquet-acquisition-receipt-v2",
        "status": status,
        "source_id": snapshot.get("source_id"),
        "source_snapshot_ref": str(args.snapshot), "source_snapshot_file_sha256": snapshot_file_sha,
        "acquisition_contract_ref": str(args.contract), "acquisition_contract_file_sha256": contract_file_sha,
        "dataset": snapshot.get("dataset"), "pinned_revision": snapshot.get("pinned_revision"), "parquet_path": snapshot.get("parquet_path"),
        "remote_url": url, "local_path": str(out), "expected_size_bytes": expected_size, "expected_sha256": expected_sha,
        "observed": observed, "network_used": network_used, "credentials_used": False,
        "treatment_execution": "NOT_EXECUTED", "holdout_access": "NONE", "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    write_receipt(receipt, payload)
    print(json.dumps({"status": status, "file": str(out), "receipt": str(receipt), "sha256": observed["sha256"], "source_binding": "VERIFIED"}, indent=2))
    return 0


if __name__ == "__main__": raise SystemExit(main())
