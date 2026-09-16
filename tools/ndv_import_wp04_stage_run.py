#!/usr/bin/env python3
"""Import one user-executed WP-04 run bundle into the repository.

The importer never re-executes a treatment. It validates the persisted bundle,
re-hashes candidate evidence, reconciles token telemetry from Aider logs when
available, and copies the immutable evidence tree under pilot-runs/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"Tokens:\s*([0-9]+(?:\.[0-9]+)?)([kKmM]?)\s+sent,\s*([0-9]+(?:\.[0-9]+)?)([kKmM]?)\s+received")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_scaled(number: str, suffix: str) -> tuple[int, bool]:
    value = float(number)
    scale = {"": 1, "k": 1_000, "m": 1_000_000}[suffix.lower()]
    return int(round(value * scale)), bool(suffix)


def parse_aider_tokens(text: str) -> dict[str, Any]:
    sent = received = 0
    approximate = False
    samples: list[str] = []
    for match in TOKEN_RE.finditer(text):
        s, s_approx = parse_scaled(match.group(1), match.group(2))
        r, r_approx = parse_scaled(match.group(3), match.group(4))
        sent += s
        received += r
        approximate = approximate or s_approx or r_approx
        samples.append(match.group(0))
    return {
        "source": "AIDER_EXECUTOR_LOG",
        "input_tokens": sent if samples else None,
        "output_tokens": received if samples else None,
        "total_tokens": sent + received if samples else None,
        "approximate": approximate if samples else None,
        "samples": samples,
    }


def validate_bundle(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    report_path = run_dir / "run-report.json"
    evidence = run_dir / "evidence"
    if not report_path.is_file() or not evidence.is_dir():
        raise ValueError("run-report.json and evidence/ are required")
    report = load(report_path)
    if report.get("schema_id") != "ndv-wp04-stage1-run-v1":
        raise ValueError("unexpected run-report schema")
    if report.get("retry_count") != 0 or report.get("escalation_count") != 0:
        raise ValueError("WP-04 import refuses retry/escalation")
    if report.get("holdout_access") != "NONE":
        raise ValueError("WP-04 import refuses holdout access")
    candidate = evidence / "candidate.diff"
    executor_log = evidence / "executor.log"
    if not candidate.is_file() or not executor_log.is_file():
        raise ValueError("candidate.diff and executor.log are required")
    candidate_bytes = candidate.read_bytes()
    expected_sha = report.get("candidate", {}).get("diff_sha256")
    if sha256_bytes(candidate_bytes) != expected_sha:
        raise ValueError("candidate.diff hash does not match run-report")
    if len(candidate_bytes) != report.get("candidate", {}).get("diff_bytes"):
        raise ValueError("candidate.diff size does not match run-report")
    tokens = parse_aider_tokens(executor_log.read_text(encoding="utf-8", errors="replace"))
    return report, tokens


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", required=True, type=Path)
    ap.add_argument("--dest", required=True, type=Path)
    args = ap.parse_args()

    run_dir = args.run_dir.resolve()
    dest = args.dest.resolve()
    if dest.exists():
        raise SystemExit(f"destination exists; refusing overwrite: {dest}")
    try:
        report, tokens = validate_bundle(run_dir)
    except Exception as exc:
        raise SystemExit(f"IMPORT_REJECTED: {exc}") from exc

    shutil.copytree(run_dir, dest)
    manifest = {
        "schema_id": "ndv-wp04-import-manifest-v1",
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
        "executor_wall_seconds": report.get("accounting", {}).get("executor_wall_seconds"),
        "token_reconciliation": tokens,
        "raw_bundle_preserved": True,
        "treatment_reexecuted": False,
    }
    (dest / "import-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "IMPORTED", "dest": str(dest), "manifest": manifest}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
