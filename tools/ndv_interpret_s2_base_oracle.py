#!/usr/bin/env python3
"""Interpret an NDV S2 base-run log against frozen SWE-rebench oracle metadata.

Read-only admission tooling. It consumes the quarantined admission artifact and
a harness-valid base audit; it never executes Docker, applies patches, or calls
models.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

UPSTREAM_REVISION = "c71902a8cf8d2b725f63d51f199f4d3e56f68d2d"
TIMING_PATTERNS = [
    re.compile(r"\s*\[\s*\d+(?:\.\d+)?\s*(?:ms|s)\s*\]\s*$", re.I),
    re.compile(r"\s+in\s+\d+(?:\.\d+)?\s+(?:msec|sec)\b", re.I),
    re.compile(r"\s*\(\s*\d+(?:\.\d+)?\s*(?:ms|s)\s*\)\s*$", re.I),
]
PASS = "PASSED"
FAIL_LIKE = {"FAILED", "ERROR"}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def normalize(name: str) -> str:
    out = name.strip()
    for p in TIMING_PATTERNS:
        out = p.sub("", out)
    return out.strip()


def unwrap_admission(artifact: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if artifact.get("schema_id") != "ndv-p1-s2-admission-only-row-v1":
        raise RuntimeError("unexpected admission-only schema")
    row, source = artifact.get("full_row"), artifact.get("source")
    if not isinstance(row, dict) or not isinstance(source, dict):
        raise RuntimeError("admission artifact requires full_row and source")
    if source.get("ndv_canonical_row_sha256") != sha256_value(row):
        raise RuntimeError("admission full_row hash mismatch")
    return row, source


def verify_upstream(root: Path) -> dict[str, str]:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"upstream root is not a readable git checkout: {proc.stderr.strip()}")
    head = proc.stdout.strip()
    if head != UPSTREAM_REVISION:
        raise RuntimeError(f"upstream revision mismatch: expected {UPSTREAM_REVISION}, got {head}")
    parser_path = root / "lib" / "agent" / "log_parsers.py"
    if not parser_path.is_file():
        raise RuntimeError("missing frozen upstream lib/agent/log_parsers.py")
    return {"revision": head, "log_parsers_sha256": sha256_file(parser_path)}


def import_parser(root: Path, parser_name: str):
    root_s, lib_s = str(root), str(root / "lib")
    if root_s not in sys.path:
        sys.path.insert(0, root_s)
    if lib_s not in sys.path:
        sys.path.insert(0, lib_s)
    mod = importlib.import_module("agent.log_parsers")
    parser = getattr(mod, "NAME_TO_PARSER", {}).get(parser_name) or getattr(mod, parser_name, None)
    if parser is None:
        raise RuntimeError(f"unknown frozen parser: {parser_name}")
    return parser


def interpret(row: dict[str, Any], base_run: dict[str, Any], log_text: str, parser) -> dict[str, Any]:
    if row.get("instance_id") != base_run.get("source_instance_id"):
        raise RuntimeError("instance identity mismatch between admission row and base run")
    if row.get("base_commit") != base_run.get("base_revision"):
        raise RuntimeError("base revision mismatch between admission row and base run")
    if base_run.get("gold_patch_applied") is not False or base_run.get("test_patch_applied") is not False:
        raise RuntimeError("base run is not pre-solution")
    if base_run.get("harness_integrity") != "PASS":
        raise RuntimeError("base run harness integrity is not PASS")

    install = row.get("install_config")
    if not isinstance(install, dict):
        raise RuntimeError("full row missing install_config")
    parser_name = install.get("log_parser")
    if not isinstance(parser_name, str) or not parser_name:
        raise RuntimeError("full row missing install_config.log_parser")

    parsed_raw = parser(log_text)
    if not isinstance(parsed_raw, dict):
        raise RuntimeError("upstream parser returned non-object")
    parsed = {normalize(str(k)): str(v) for k, v in parsed_raw.items()}

    ftp = [normalize(str(x)) for x in row.get("FAIL_TO_PASS", [])]
    ptp = [normalize(str(x)) for x in row.get("PASS_TO_PASS", [])]
    if not ftp:
        return {"classification": "ORACLE_MISMATCH", "reason": "no FAIL_TO_PASS expectations available for a bug-fix base task", "parsed_test_count": len(parsed), "fail_to_pass": [], "pass_to_pass": []}

    ftp_obs = [{"test": t, "observed": parsed.get(t)} for t in ftp]
    ptp_obs = [{"test": t, "observed": parsed.get(t)} for t in ptp]
    missing = [x["test"] for x in ftp_obs + ptp_obs if x["observed"] is None]
    ftp_wrong = [x for x in ftp_obs if x["observed"] not in FAIL_LIKE]
    ptp_wrong = [x for x in ptp_obs if x["observed"] != PASS]

    if not parsed:
        classification, reason = "ENVIRONMENT_INCONCLUSIVE", "parser produced no test results from recorded base log"
    elif missing:
        classification, reason = "ORACLE_MISMATCH", "one or more preregistered tests were absent from parsed base evidence; this may indicate test-patch-dependent verifier material and is not repaired with solution knowledge"
    elif ftp_wrong or ptp_wrong:
        classification, reason = "ORACLE_MISMATCH", "observed base statuses do not match preregistered FAIL_TO_PASS/PASS_TO_PASS expectations"
    else:
        classification, reason = "EXPECTED_BASE_BEHAVIOR", "all preregistered focal failures and preservation passes were reproduced"

    return {"classification": classification, "reason": reason, "parsed_test_count": len(parsed), "fail_to_pass": ftp_obs, "pass_to_pass": ptp_obs, "missing_expected_tests": missing, "unexpected_fail_to_pass_statuses": ftp_wrong, "unexpected_pass_to_pass_statuses": ptp_wrong}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--admission-row", required=True, type=Path)
    ap.add_argument("--base-run", required=True, type=Path)
    ap.add_argument("--upstream-root", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    artifact, run = load(args.admission_row), load(args.base_run)
    if not isinstance(artifact, dict) or not isinstance(run, dict):
        raise SystemExit("admission artifact and base run must be JSON objects")
    if run.get("schema_id") != "ndv-p1-s2-base-audit-run-v2":
        raise SystemExit("base run must use harness-valid v2 schema")
    try:
        row, source = unwrap_admission(artifact)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    upstream = verify_upstream(args.upstream_root)
    install = row.get("install_config") or {}
    parser_name = install.get("log_parser")
    if not isinstance(parser_name, str) or not parser_name:
        raise SystemExit("full row missing install_config.log_parser")
    parser = import_parser(args.upstream_root, parser_name)

    evidence = run.get("evidence")
    if not isinstance(evidence, dict):
        raise SystemExit("base run missing evidence object")
    log_ref, expected_log_hash = evidence.get("stdout_ref"), evidence.get("stdout_sha256")
    if not isinstance(log_ref, str) or not log_ref:
        raise SystemExit("base run missing evidence.stdout_ref")
    log_path = Path(log_ref)
    if not log_path.is_absolute():
        candidate_paths = [args.base_run.parent / log_path, args.base_run.parent / Path(log_ref).name]
        log_path = next((p for p in candidate_paths if p.is_file()), candidate_paths[0])
    if not log_path.is_file():
        raise SystemExit(f"recorded base log not found: {log_path}")
    observed_log_hash = sha256_file(log_path)
    if expected_log_hash != observed_log_hash:
        raise SystemExit("base log SHA-256 mismatch")

    result = interpret(row, run, log_path.read_text(encoding="utf-8", errors="replace"), parser)
    payload = {
        "schema_id": "ndv-p1-s2-base-oracle-interpretation-v2", "candidate_id": run.get("candidate_id"),
        "source_instance_id": row.get("instance_id"), "source_row_index": source.get("source_row_index"),
        "base_revision": row.get("base_commit"), "parser_name": parser_name,
        "parser_provenance": {"repository": "SWE-rebench/SWE-rebench-V2", **upstream, "path": "lib/agent/log_parsers.py"},
        "base_run_ref": str(args.base_run), "base_run_sha256": sha256_file(args.base_run),
        "base_log_ref": str(log_path), "base_log_sha256": observed_log_hash,
        "gold_patch_applied": False, "test_patch_applied": False, "treatment_execution": "NOT_EXECUTED", "holdout_access": "NONE", **result,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.out)
    return 0 if payload["classification"] == "EXPECTED_BASE_BEHAVIOR" else 2


if __name__ == "__main__":
    raise SystemExit(main())
