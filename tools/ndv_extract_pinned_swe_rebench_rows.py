#!/usr/bin/env python3
"""Extract selected SWE-rebench V2 rows from a cryptographically pinned parquet.

This tool never calls an executor. It verifies the local parquet SHA-256 against
an expected snapshot, extracts only preregistered row indices, writes complete
rows to a temporary JSONL artifact, and optionally invokes the NDV quarantine
tool to create admission-only and executor-visible projections.
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


def dump_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def extract_rows(parquet_path: Path, indices: list[int]) -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise SystemExit("pyarrow is required for pinned parquet extraction") from exc

    table = pq.read_table(parquet_path)
    if not indices:
        raise SystemExit("no row indices requested")
    row_count = table.num_rows
    bad = [idx for idx in indices if idx < 0 or idx >= row_count]
    if bad:
        raise SystemExit(f"row indices out of range for {row_count} rows: {bad}")
    return [table.slice(idx, 1).to_pylist()[0] for idx in indices]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, default=Path("experiments/p1/s2-source-snapshot-01.json"))
    parser.add_argument("--wave", type=Path, default=Path("experiments/p1/s2-candidate-wave-01.json"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--quarantine-out", type=Path)
    parser.add_argument("--quarantine-tool", type=Path, default=Path("tools/ndv_quarantine_swe_rebench_rows.py"))
    args = parser.parse_args()

    snapshot = load_json(args.snapshot)
    wave = load_json(args.wave)
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
    rows = extract_rows(args.parquet, indices)

    for candidate, row in zip(candidates, rows):
        if row.get("instance_id") != candidate.get("source_instance_id"):
            print(json.dumps({
                "status": "FAIL",
                "reason": "ROW_INSTANCE_ID_MISMATCH",
                "row_index": candidate.get("source_row_index"),
                "expected": candidate.get("source_instance_id"),
                "actual": row.get("instance_id"),
            }, indent=2))
            return 2
        if row.get("base_commit") != candidate.get("base_revision"):
            print(json.dumps({
                "status": "FAIL",
                "reason": "ROW_BASE_COMMIT_MISMATCH",
                "instance_id": row.get("instance_id"),
                "expected": candidate.get("base_revision"),
                "actual": row.get("base_commit"),
            }, indent=2))
            return 2

    dump_jsonl(args.out, rows)
    result: dict[str, Any] = {
        "status": "PASS",
        "parquet_sha256": actual_sha,
        "pinned_revision": snapshot.get("pinned_revision"),
        "rows_extracted": len(rows),
        "row_indices": indices,
        "jsonl": str(args.out),
    }

    if args.quarantine_out:
        proc = subprocess.run(
            [
                sys.executable,
                str(args.quarantine_tool),
                "--rows",
                str(args.out),
                "--wave",
                str(args.wave),
                "--out",
                str(args.quarantine_out),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        result["quarantine_exit_code"] = proc.returncode
        result["quarantine_stdout"] = proc.stdout.strip()
        result["quarantine_stderr"] = proc.stderr.strip()
        if proc.returncode != 0:
            result["status"] = "FAIL"
            result["reason"] = "QUARANTINE_FAILED"
            print(json.dumps(result, indent=2, sort_keys=True))
            return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
