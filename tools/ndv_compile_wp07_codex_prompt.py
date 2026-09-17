#!/usr/bin/env python3
"""Compile a deterministic Codex prompt from ADMITTED_FROZEN executor-visible bytes only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ALLOWED_TASK_FIELDS = {"instance_id", "repo", "base_commit", "problem_statement", "language"}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha_value(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve(root: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} missing")
    p = Path(value)
    if not p.is_absolute():
        p = root / p
    p = p.resolve()
    if not p.is_file():
        raise ValueError(f"{label} not found: {p}")
    return p


def verify_admission(path: Path) -> dict[str, Any]:
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("schema_id") != "ndv-p1-s2-admission-record-v2" or record.get("status") != "ADMITTED_FROZEN":
        raise ValueError("ADMITTED_FROZEN v2 required")
    expected = record.get("record_sha256")
    body = {k:v for k,v in record.items() if k != "record_sha256"}
    if not isinstance(expected, str) or sha_value(body) != expected:
        raise ValueError("admission record_sha256 mismatch")
    sel = record.get("selection") or {}
    if sel.get("treatment_execution_before_admission") is not False or sel.get("holdout_access") != "NONE":
        raise ValueError("admission record contaminated")
    return record


def normalize_s0(statement: str) -> str:
    return statement.rstrip("\r\n") + "\n"


def compile_prompt(run_spec_path: Path, artifact_root: Path) -> dict[str, Any]:
    spec = json.loads(run_spec_path.read_text(encoding="utf-8"))
    if spec.get("schema_id") != "ndv-p1-s2-run-spec-v1" or spec.get("execution_status") != "NOT_EXECUTED":
        raise ValueError("NOT_EXECUTED P1-S2 run-spec required")
    if spec.get("holdout") != "DEVELOPMENT_ONLY":
        raise ValueError("development-only run-spec required")
    task_spec = spec.get("task") or {}
    admission_path = resolve(artifact_root, task_spec.get("admission_record_ref"), "admission_record_ref")
    if sha_file(admission_path) != task_spec.get("admission_record_file_sha256"):
        raise ValueError("admission record file SHA-256 mismatch")
    admission = verify_admission(admission_path)
    if admission.get("record_sha256") != task_spec.get("admission_record_sha256"):
        raise ValueError("run-spec/admission semantic hash mismatch")
    if admission.get("candidate_id") != task_spec.get("task_id") or admission.get("base_revision") != task_spec.get("base_sha"):
        raise ValueError("run-spec/admission identity mismatch")

    source = admission.get("source_binding") or {}
    integrity = admission.get("artifact_integrity") or {}
    executor_path = resolve(artifact_root, source.get("executor_visible_ref"), "executor_visible_ref")
    expected_file_sha = integrity.get("executor_visible_file_sha256")
    if not isinstance(expected_file_sha, str) or sha_file(executor_path) != expected_file_sha:
        raise ValueError("executor-visible file SHA-256 mismatch")
    executor = json.loads(executor_path.read_text(encoding="utf-8"))
    if executor.get("schema_id") != "ndv-p1-s2-executor-visible-row-v1" or executor.get("candidate_id") != admission.get("candidate_id"):
        raise ValueError("executor-visible schema/identity mismatch")
    projection = executor.get("task")
    if not isinstance(projection, dict) or set(projection) - ALLOWED_TASK_FIELDS:
        raise ValueError("executor-visible projection contains unapproved fields")
    if sha_value(projection) != source.get("executor_visible_sha256") or executor.get("executor_visible_sha256") != source.get("executor_visible_sha256"):
        raise ValueError("executor-visible canonical hash mismatch")
    statement = projection.get("problem_statement")
    if not isinstance(statement, str) or not statement.strip():
        raise ValueError("non-empty problem_statement required")
    statement_sha = hashlib.sha256(statement.encode("utf-8")).hexdigest()
    if statement_sha != source.get("task_statement_sha256") or statement_sha != task_spec.get("task_statement_sha256"):
        raise ValueError("task statement SHA-256 mismatch")

    shaping = ((spec.get("treatment") or {}).get("shaping"))
    if shaping == "S0_RAW_TASK":
        prompt = normalize_s0(statement)
    elif shaping == "S1_DETERMINISTIC_TASK_SHAPING":
        language = projection.get("language") or admission.get("language")
        prompt = (
            "Objective:\n" + normalize_s0(statement) +
            "\nFrozen task context:\n"
            f"- repository: {admission.get('repository')}\n"
            f"- base revision: {admission.get('base_revision')}\n"
            f"- language: {language}\n"
            "\nConstraints:\n"
            "- Work only from the task statement and repository state provided in this workspace.\n"
            "- Do not assume access to a gold patch, hidden tests, admission-only metadata, or holdout data.\n"
            "- Produce the smallest repository change that satisfies the task while preserving existing behavior.\n"
            "- Leave the repository in a verifiable state; do not report success as a substitute for code changes.\n"
        )
    else:
        raise ValueError(f"unsupported shaping: {shaping!r}")

    prompt_bytes = prompt.encode("utf-8")
    return {
        "schema_id": "ndv-p1-wp07-codex-prompt-v1",
        "status": "PROMPT_COMPILED_NOT_EXPOSED",
        "run_id": spec.get("run_id"),
        "task_id": admission.get("candidate_id"),
        "shaping": shaping,
        "executor_visible_ref": str(executor_path),
        "executor_visible_file_sha256": sha_file(executor_path),
        "executor_visible_sha256": source.get("executor_visible_sha256"),
        "task_statement_sha256": statement_sha,
        "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
        "prompt_bytes": len(prompt_bytes),
        "prompt": prompt,
        "forbidden_source_accessed": False,
        "task_prompt_exposed": False,
        "treatment_execution": "NOT_EXECUTED",
        "holdout_access": "NONE",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-spec", required=True, type=Path)
    ap.add_argument("--artifact-root", type=Path, default=Path("."))
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    try:
        result = compile_prompt(args.run_spec.resolve(), args.artifact_root.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status":"FAIL","reason":"CODEX_PROMPT_COMPILATION_BLOCKED","detail":str(exc)}, indent=2))
        return 2
    if args.out.exists():
        raise SystemExit(f"refusing overwrite: {args.out}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("status","run_id","task_id","shaping","prompt_sha256","prompt_bytes")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
