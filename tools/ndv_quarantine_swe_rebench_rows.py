#!/usr/bin/env python3
"""Quarantine SWE-rebench V2 rows into admission-only and executor-visible artifacts.

Consumes either a full ordered dataset export or NDV extracted-row envelopes. The
raw upstream row is never modified before hashing/preservation. Original parquet
row indices are preserved explicitly so selected-row exports cannot be confused
with compacted 0..N positions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

EXECUTOR_ALLOWLIST = ("instance_id", "repo", "base_commit", "problem_statement", "language")
FORBIDDEN_EXECUTOR_FIELDS = {"patch", "test_patch", "FAIL_TO_PASS", "PASS_TO_PASS", "interface", "meta", "install_config", "pr_description"}
ENVELOPE_SCHEMA = "ndv-p1-s2-extracted-row-envelope-v1"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def load_records(path: Path) -> list[tuple[int, dict[str, Any]]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        values = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        value = json.loads(text)
        values = value.get("rows") if isinstance(value, dict) and isinstance(value.get("rows"), list) else value
    if not isinstance(values, list) or not all(isinstance(v, dict) for v in values):
        raise ValueError("input must contain JSON objects")

    records: list[tuple[int, dict[str, Any]]] = []
    envelope_mode = any(v.get("schema_id") == ENVELOPE_SCHEMA for v in values)
    if envelope_mode and not all(v.get("schema_id") == ENVELOPE_SCHEMA for v in values):
        raise ValueError("mixed raw-row and extracted-envelope input is forbidden")

    if envelope_mode:
        seen: set[int] = set()
        for value in values:
            idx = value.get("source_row_index")
            row = value.get("full_row")
            if not isinstance(idx, int) or idx < 0 or not isinstance(row, dict):
                raise ValueError("invalid extracted-row envelope")
            if idx in seen:
                raise ValueError(f"duplicate source_row_index in extracted input: {idx}")
            seen.add(idx)
            records.append((idx, row))
        return records

    return [(idx, row) for idx, row in enumerate(values)]


def source_instance_id(row: dict[str, Any]) -> str | None:
    for key in ("instance_id", "id"):
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def project_executor_view(row: dict[str, Any]) -> dict[str, Any]:
    projection = {key: row[key] for key in EXECUTOR_ALLOWLIST if key in row}
    leaked = FORBIDDEN_EXECUTOR_FIELDS & set(projection)
    if leaked:
        raise AssertionError(f"internal error: forbidden fields leaked: {sorted(leaked)}")
    return projection


def find_row(records: list[tuple[int, dict[str, Any]]], candidate: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    wanted_id = candidate["source_instance_id"]
    declared_index = candidate.get("source_row_index")
    matches = [(idx, row) for idx, row in records if source_instance_id(row) == wanted_id]
    if len(matches) != 1:
        raise ValueError(f"{wanted_id}: expected exactly one matching source row, found {len(matches)}")
    idx, row = matches[0]
    if not isinstance(declared_index, int) or declared_index != idx:
        raise ValueError(f"{wanted_id}: source_row_index mismatch: wave={declared_index}, export={idx}")
    return idx, row


def validate_identity(row: dict[str, Any], candidate: dict[str, Any]) -> None:
    for row_key, candidate_key in (("repo", "repository"), ("base_commit", "base_revision")):
        observed = row.get(row_key)
        expected = candidate.get(candidate_key)
        if observed is not None and observed != expected:
            raise ValueError(f"{candidate['candidate_id']}: {row_key} mismatch: {observed!r} != {expected!r}")


def quarantine_one(row: dict[str, Any], row_index: int, candidate: dict[str, Any], wave: dict[str, Any], out_root: Path, input_ref: str) -> dict[str, Any]:
    validate_identity(row, candidate)
    cid = candidate["candidate_id"]
    raw_sha = sha256_value(row)
    projection = project_executor_view(row)
    if not isinstance(projection.get("problem_statement"), str) or not projection["problem_statement"].strip():
        raise ValueError(f"{cid}: executor projection requires a non-empty problem_statement")
    task_sha = hashlib.sha256(projection["problem_statement"].encode("utf-8")).hexdigest()
    executor_sha = sha256_value(projection)

    admission = {
        "schema_id": "ndv-p1-s2-admission-only-row-v1",
        "candidate_id": cid,
        "source": {
            "dataset": wave["source"]["dataset"], "split": wave["source"]["split"],
            "dataset_revision": wave["source"]["dataset_revision"], "source_row_index": row_index,
            "source_instance_id": candidate["source_instance_id"], "operator_input_ref": input_ref,
            "ndv_canonical_row_sha256": raw_sha, "external_discovery_record_sha256": candidate.get("source_record_sha256"),
            "external_hash_role": "DISCOVERY_DONOR_ONLY_NOT_ASSUMED_SAME_CANONICALIZATION",
        },
        "full_row": row,
    }
    executor = {
        "schema_id": "ndv-p1-s2-executor-visible-row-v1", "candidate_id": cid,
        "source_binding": {"dataset_revision": wave["source"]["dataset_revision"], "source_row_index": row_index, "ndv_canonical_row_sha256": raw_sha},
        "projection_policy": {"mode": "STRICT_ALLOWLIST", "allowed_fields": list(EXECUTOR_ALLOWLIST), "forbidden_fields": sorted(FORBIDDEN_EXECUTOR_FIELDS), "unknown_upstream_fields_default": "ADMISSION_ONLY"},
        "task_statement_sha256": task_sha, "executor_visible_sha256": executor_sha, "task": projection,
    }

    candidate_dir = out_root / cid
    admission_path = candidate_dir / "admission-only.json"
    executor_path = candidate_dir / "executor-visible.json"
    manifest_path = candidate_dir / "quarantine-manifest.json"
    write_json(admission_path, admission)
    write_json(executor_path, executor)
    manifest = {
        "schema_id": "ndv-p1-s2-quarantine-manifest-v2", "candidate_id": cid, "status": "PASS",
        "dataset_revision": wave["source"]["dataset_revision"], "source_row_index": row_index,
        "source_instance_id": candidate["source_instance_id"], "ndv_canonical_row_sha256": raw_sha,
        "task_statement_sha256": task_sha, "executor_visible_sha256": executor_sha,
        "admission_only_ref": str(admission_path), "executor_visible_ref": str(executor_path),
        "forbidden_field_intersection": sorted(FORBIDDEN_EXECUTOR_FIELDS & set(projection)),
        "raw_row_mutated": False, "treatment_execution": "NOT_EXECUTED", "holdout_access": "NONE",
    }
    write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wave", type=Path, default=Path("experiments/p1/s2-candidate-wave-01.json"))
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path(".ndv-corpus/s2-w01"))
    args = parser.parse_args()

    wave = json.loads(args.wave.read_text(encoding="utf-8"))
    records = load_records(args.rows)
    manifests = []
    for candidate in wave["candidates"]:
        row_index, row = find_row(records, candidate)
        manifests.append(quarantine_one(row, row_index, candidate, wave, args.out, str(args.rows)))

    aggregate = {
        "schema_id": "ndv-p1-s2-quarantine-aggregate-v2", "wave_id": wave["wave_id"],
        "dataset_revision": wave["source"]["dataset_revision"], "candidate_count": len(manifests),
        "passed_count": sum(item["status"] == "PASS" for item in manifests),
        "treatment_execution": "NOT_EXECUTED", "holdout_access": "NONE", "manifests": manifests,
    }
    write_json(args.out / "quarantine-aggregate.json", aggregate)
    print(json.dumps({"status": "PASS", "aggregate": str(args.out / "quarantine-aggregate.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
