#!/usr/bin/env python3
"""Extract selected SWE-rebench V2 rows from a cryptographically pinned parquet.

This tool never calls an executor. It verifies the local parquet SHA-256 against
an expected snapshot, enforces the frozen extraction environment, extracts only
preregistered source row indices, preserves each original parquet row index in
an envelope without mutating the raw row, and optionally invokes quarantine.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")


def validate_indices(indices: list[int]) -> None:
    if not indices:
        raise SystemExit("no row indices requested")
    if not all(isinstance(idx, int) and idx >= 0 for idx in indices):
        raise SystemExit("source_row_index values must be non-negative integers")
    if len(indices) != len(set(indices)):
        raise SystemExit("duplicate source_row_index values are forbidden")


def validate_environment_contract(env_cfg: dict[str, Any]) -> str:
    if env_cfg.get("schema_id") != "ndv-p1-s2-extraction-environment-v1":
        raise SystemExit("unexpected extraction environment schema")
    py = env_cfg.get("python", {})
    wanted = (py.get("required_major"), py.get("required_minor"))
    if sys.version_info[:2] != wanted:
        raise SystemExit(f"extraction requires Python {wanted[0]}.{wanted[1]}.x; observed {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    required = env_cfg.get("pyarrow", {}).get("required_version")
    if not isinstance(required, str) or not required:
        raise SystemExit("extraction environment missing required pyarrow version")
    if env_cfg.get("network_during_extraction") != "FORBIDDEN" or env_cfg.get("model_execution") != "NONE" or env_cfg.get("treatment_execution") != "NOT_EXECUTED" or env_cfg.get("holdout_access") != "NONE":
        raise SystemExit("extraction environment permits forbidden activity")
    return required


def extract_rows(parquet_path: Path, indices: list[int], required_pyarrow: str | None = None) -> list[tuple[int, dict[str, Any]]]:
    validate_indices(indices)
    try:
        import pyarrow
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise SystemExit("pyarrow is required for pinned parquet extraction") from exc
    if required_pyarrow is not None and pyarrow.__version__ != required_pyarrow:
        raise SystemExit(f"pyarrow version mismatch: required {required_pyarrow}, observed {pyarrow.__version__}")

    table = pq.read_table(parquet_path)
    row_count = table.num_rows
    bad = [idx for idx in indices if idx >= row_count]
    if bad:
        raise SystemExit(f"row indices out of range for {row_count} rows: {bad}")
    return [(idx, table.slice(idx, 1).to_pylist()[0]) for idx in indices]


def make_record(source_row_index: int, row: dict[str, Any]) -> dict[str, Any]:
    return {"schema_id": "ndv-p1-s2-extracted-row-envelope-v1", "source_row_index": source_row_index, "full_row": row}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, default=Path("experiments/p1/s2-source-snapshot-01.json"))
    parser.add_argument("--wave", type=Path, default=Path("experiments/p1/s2-candidate-wave-01.json"))
    parser.add_argument("--environment", type=Path, default=Path("experiments/p1/s2-extraction-environment-v1.json"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--quarantine-out", type=Path)
    parser.add_argument("--quarantine-tool", type=Path, default=Path("tools/ndv_quarantine_swe_rebench_rows.py"))
    args = parser.parse_args()

    snapshot = load_json(args.snapshot)
    wave = load_json(args.wave)
    env_cfg = load_json(args.environment)
    if not all(isinstance(x, dict) for x in (snapshot, wave, env_cfg)):
        raise SystemExit("snapshot, wave, and environment must be JSON objects")
    required_pyarrow = validate_environment_contract(env_cfg)
    expected_sha = snapshot.get("parquet_sha256")
    actual_sha = sha256_file(args.parquet)
    if actual_sha != expected_sha:
        print(json.dumps({"status": "FAIL", "reason": "PARQUET_SHA256_MISMATCH", "expected": expected_sha, "actual": actual_sha}, indent=2))
        return 2
    if wave.get("source", {}).get("dataset_revision") != snapshot.get("pinned_revision"):
        print(json.dumps({"status": "FAIL", "reason": "REVISION_MISMATCH_BETWEEN_WAVE_AND_SNAPSHOT"}, indent=2))
        return 2

    candidates = wave.get("candidates", [])
    indices = [candidate["source_row_index"] for candidate in candidates]
    validate_indices(indices)
    extracted = extract_rows(args.parquet, indices, required_pyarrow)
    records: list[dict[str, Any]] = []
    for candidate, (source_index, row) in zip(candidates, extracted):
        if source_index != candidate.get("source_row_index"):
            raise SystemExit("internal source row index alignment failure")
        if row.get("instance_id") != candidate.get("source_instance_id"):
            print(json.dumps({"status": "FAIL", "reason": "ROW_INSTANCE_ID_MISMATCH", "row_index": source_index, "expected": candidate.get("source_instance_id"), "actual": row.get("instance_id")}, indent=2))
            return 2
        if row.get("base_commit") != candidate.get("base_revision"):
            print(json.dumps({"status": "FAIL", "reason": "ROW_BASE_COMMIT_MISMATCH", "instance_id": row.get("instance_id"), "expected": candidate.get("base_revision"), "actual": row.get("base_commit")}, indent=2))
            return 2
        records.append(make_record(source_index, row))

    dump_jsonl(args.out, records)
    result: dict[str, Any] = {
        "status": "PASS", "schema_id": "ndv-p1-s2-pinned-row-extraction-v3",
        "parquet_sha256": actual_sha, "pinned_revision": snapshot.get("pinned_revision"),
        "rows_extracted": len(records), "row_indices": indices, "jsonl": str(args.out), "raw_rows_mutated": False,
        "environment_ref": str(args.environment), "environment_file_sha256": sha256_file(args.environment),
        "python_version": sys.version.split()[0], "pyarrow_version": required_pyarrow,
    }
    if args.quarantine_out:
        proc = subprocess.run([sys.executable, str(args.quarantine_tool), "--rows", str(args.out), "--wave", str(args.wave), "--out", str(args.quarantine_out)], text=True, capture_output=True, check=False)
        result["quarantine_exit_code"], result["quarantine_stdout"], result["quarantine_stderr"] = proc.returncode, proc.stdout.strip(), proc.stderr.strip()
        if proc.returncode != 0:
            result["status"], result["reason"] = "FAIL", "QUARANTINE_FAILED"
            print(json.dumps(result, indent=2, sort_keys=True))
            return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
