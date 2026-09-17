#!/usr/bin/env python3
"""Assess whether WP-06 has reached its preregistered intake target.

This is a corpus-acquisition gate only. It validates frozen S2 admission records,
combines their count with the historical cutover counts, and reports whether the
WP-06 operational intake target has been reached. It never authorizes P1
comparative execution; comparative_corpus_ready and WP07 release remain NO.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_record(path: Path) -> dict[str, Any]:
    record = load(path)
    if not isinstance(record, dict) or record.get("schema_id") != "ndv-p1-s2-admission-record-v2":
        raise ValueError(f"{path}: admission record v2 required")
    if record.get("status") != "ADMITTED_FROZEN":
        raise ValueError(f"{path}: only ADMITTED_FROZEN records count")
    expected = record.get("record_sha256")
    body = {k: v for k, v in record.items() if k != "record_sha256"}
    if not isinstance(expected, str) or sha(body) != expected:
        raise ValueError(f"{path}: record_sha256 mismatch")
    selection = record.get("selection")
    if not isinstance(selection, dict) or selection.get("treatment_performance_consulted") is not False or selection.get("treatment_execution_before_admission") is not False or selection.get("holdout_access") != "NONE":
        raise ValueError(f"{path}: admission selection provenance invalid")
    if record.get("family") not in {"F1", "F2", "F3", "F4", "F5", "F6"}:
        raise ValueError(f"{path}: frozen family missing/invalid")
    for field in ("candidate_id", "repository", "language", "source_instance_id", "base_revision"):
        if not isinstance(record.get(field), str) or not record.get(field):
            raise ValueError(f"{path}: missing {field}")
    return record


def assess(intake_path: Path, legacy_path: Path, record_paths: list[Path]) -> dict[str, Any]:
    intake, legacy = load(intake_path), load(legacy_path)
    if intake.get("schema_id") != "ndv-p1-s2-corpus-intake-v1":
        raise ValueError("unexpected S2 intake contract")
    if legacy.get("schema_id") != "ndv-dv-legacy-manifest-v1":
        raise ValueError("unexpected legacy manifest")
    hist = legacy.get("normative_historical_p1_corpus")
    target = intake.get("target")
    if not isinstance(hist, dict) or not isinstance(target, dict):
        raise ValueError("historical counts/target missing")
    if hist.get("corpus_id") != intake.get("historical_normative_corpus", {}).get("corpus_id"):
        raise ValueError("historical corpus identity mismatch")
    counts = hist.get("counts")
    if not isinstance(counts, dict):
        raise ValueError("historical counts missing")

    records = [validate_record(p.resolve()) for p in record_paths]
    ids = [r["candidate_id"] for r in records]
    instances = [r["source_instance_id"] for r in records]
    if len(ids) != len(set(ids)) or len(instances) != len(set(instances)):
        raise ValueError("duplicate S2 candidate/source instance admission")

    s2_languages = sorted({r["language"] for r in records})
    s2_families = sorted({r["family"] for r in records})
    s2_repositories = sorted({r["repository"] for r in records})
    historical_tasks = int(counts.get("tasks", 0))
    combined_tasks = historical_tasks + len(records)

    # Historical cutover already demonstrates the family/repository minima. Language
    # was not frozen in the legacy manifest, so readiness proves language diversity
    # conservatively from S2 admissions alone instead of inferring it after the fact.
    checks = {
        "task_target": combined_tasks >= int(target.get("initial_admitted_tasks", 0)),
        "family_minimum_historically_demonstrated": int(counts.get("families", 0)) >= int(target.get("minimum_families", 0)),
        "repository_minimum_historically_demonstrated": int(counts.get("repositories", 0)) >= int(target.get("minimum_repositories", 0)),
        "language_minimum_demonstrated_by_s2": len(s2_languages) >= int(target.get("minimum_languages", 0)),
    }
    reached = all(checks.values())
    return {
        "schema_id": "ndv-p1-s2-corpus-readiness-assessment-v1",
        "status": "WP06_INTAKE_TARGET_REACHED" if reached else "WP06_INTAKE_TARGET_NOT_REACHED",
        "historical": {
            "corpus_id": hist.get("corpus_id"),
            "tasks": historical_tasks,
            "families": counts.get("families"),
            "repositories": counts.get("repositories"),
        },
        "s2": {
            "admitted_count": len(records),
            "candidate_ids": sorted(ids),
            "languages": s2_languages,
            "families": s2_families,
            "repositories": s2_repositories,
            "records": [{"ref": str(p.resolve()), "file_sha256": sha_file(p.resolve()), "record_sha256": r["record_sha256"]} for p, r in zip(record_paths, records)],
        },
        "combined_task_count": combined_tasks,
        "target": target,
        "checks": checks,
        "comparative_corpus_ready": "NO",
        "wp07_release": "NO",
        "treatment_execution": "NOT_EXECUTED",
        "holdout_access": "NONE",
        "note": "Meeting WP-06 intake targets is necessary corpus acquisition evidence, not authorization for comparative P1 execution.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--intake", type=Path, default=Path("experiments/p1/s2-corpus-intake-v1.json"))
    ap.add_argument("--legacy-manifest", type=Path, default=Path("provenance/dv-legacy-manifest.json"))
    ap.add_argument("--admission-record", action="append", default=[], type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    try:
        result = assess(args.intake.resolve(), args.legacy_manifest.resolve(), args.admission_record)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "reason": "CORPUS_READINESS_BLOCKED", "detail": str(exc)}, indent=2))
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists():
        raise SystemExit(f"refusing overwrite: {args.out}")
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "combined_task_count": result["combined_task_count"], "s2_admitted_count": result["s2"]["admitted_count"], "comparative_corpus_ready": "NO"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
