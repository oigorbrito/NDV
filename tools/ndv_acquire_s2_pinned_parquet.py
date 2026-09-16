#!/usr/bin/env python3
"""Acquire the frozen SWE-rebench V2 Parquet with size/SHA verification.

This command performs network I/O only when explicitly invoked by an operator.
It does not call models, execute treatments, access holdout material, or mutate
candidate metadata. The destination is finalized only after frozen integrity
checks pass.
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


def build_url(snapshot: dict[str, Any], contract: dict[str, Any]) -> str:
    dataset = snapshot.get("dataset")
    revision = snapshot.get("pinned_revision")
    parquet_path = snapshot.get("parquet_path")
    template = contract.get("remote_url_template")
    if not isinstance(dataset, str) or not dataset or "/" not in dataset:
        raise ValueError("snapshot dataset must be owner/name")
    if not isinstance(revision, str) or not SHA40.fullmatch(revision):
        raise ValueError("snapshot pinned_revision must be exact 40-hex")
    if not isinstance(parquet_path, str) or not parquet_path or parquet_path.startswith(("/", "\\")) or ".." in Path(parquet_path).parts:
        raise ValueError("snapshot parquet_path must be a safe relative path")
    if not isinstance(template, str) or "{dataset}" not in template or "{revision}" not in template or "{parquet_path}" not in template:
        raise ValueError("acquisition contract remote_url_template invalid")
    return template.format(dataset=dataset, revision=revision, parquet_path=parquet_path)


def expected_integrity(snapshot: dict[str, Any]) -> tuple[int, str]:
    size = snapshot.get("parquet_remote_size_bytes")
    digest = snapshot.get("parquet_sha256")
    if not isinstance(size, int) or size <= 0:
        raise ValueError("snapshot parquet_remote_size_bytes must be positive integer")
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise ValueError("snapshot parquet_sha256 must be 64-hex")
    return size, digest


def verify_file(path: Path, expected_size: int, expected_sha: str) -> dict[str, Any]:
    size = path.stat().st_size
    digest = sha256_file(path)
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
            out.write(chunk)
            written += len(chunk)
        out.flush()
        os.fsync(out.fileno())
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
    if contract.get("schema_id") != "ndv-p1-s2-parquet-acquisition-v1":
        raise SystemExit("ACQUISITION_BLOCKED: unexpected acquisition contract schema")
    try:
        url = build_url(snapshot, contract)
        expected_size, expected_sha = expected_integrity(snapshot)
    except ValueError as exc:
        raise SystemExit(f"ACQUISITION_BLOCKED: {exc}") from exc

    out = args.out.resolve()
    receipt = (args.receipt or out.with_suffix(out.suffix + ".receipt.json")).resolve()
    partial = out.with_name(out.name + ".part")
    if partial.exists():
        raise SystemExit(f"ACQUISITION_BLOCKED: partial file already exists; inspect/remove explicitly: {partial}")

    if out.exists():
        observed = verify_file(out, expected_size, expected_sha)
        if not observed["size_match"] or not observed["sha256_match"]:
            raise SystemExit("ACQUISITION_BLOCKED: existing destination fails frozen integrity; refusing overwrite")
        status = "REUSED_VERIFIED_EXISTING"
        network_used = False
    else:
        try:
            written = download(url, partial)
        except Exception as exc:
            raise SystemExit(f"ACQUISITION_FAILED: {exc}; partial retained at {partial}") from exc
        observed = verify_file(partial, expected_size, expected_sha)
        observed["stream_written_bytes"] = written
        if not observed["size_match"] or not observed["sha256_match"]:
            raise SystemExit(f"ACQUISITION_INTEGRITY_FAIL: partial retained for inspection at {partial}")
        partial.replace(out)
        status = "DOWNLOADED_VERIFIED"
        network_used = True

    payload = {
        "schema_id": "ndv-p1-s2-parquet-acquisition-receipt-v1",
        "status": status,
        "source_snapshot_ref": str(args.snapshot),
        "acquisition_contract_ref": str(args.contract),
        "dataset": snapshot.get("dataset"),
        "pinned_revision": snapshot.get("pinned_revision"),
        "parquet_path": snapshot.get("parquet_path"),
        "remote_url": url,
        "local_path": str(out),
        "expected_size_bytes": expected_size,
        "expected_sha256": expected_sha,
        "observed": observed,
        "network_used": network_used,
        "credentials_used": False,
        "treatment_execution": "NOT_EXECUTED",
        "holdout_access": "NONE",
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    write_receipt(receipt, payload)
    print(json.dumps({"status": status, "file": str(out), "receipt": str(receipt), "sha256": observed["sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
