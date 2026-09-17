#!/usr/bin/env python3
"""Execute one frozen WP-07 single-hop Codex development run exactly once.

Only B0/B1/B3 are supported. B2/B4 require an explicit cascade controller. The
runner is inert unless the exact execution token is supplied. It re-runs all
pre-exposure integrity gates, compiles the task prompt from executor-visible
bytes only, invokes the frozen Codex surface once, preserves raw evidence and
usage, and stops before focal/preservation verification. It never declares a
verified task outcome by itself.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ndv_compile_wp07_codex_prompt import compile_prompt
from ndv_parse_codex_jsonl_usage import parse_lines
from ndv_preflight_wp07_codex_run_spec import preflight

EXECUTE_TOKEN = "P1S2_EXECUTE_FROZEN_DEVELOPMENT_RUN"
SINGLE_HOP = {"B0", "B1", "B3"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run(argv: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, check=False, timeout=timeout)


def git(root: Path, args: list[str], timeout: float = 60) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], cwd=root, timeout=timeout)


def verify_workspace_manifest(manifest_path: Path, run_spec_path: Path) -> dict[str, Any]:
    manifest = load(manifest_path.resolve())
    if manifest.get("schema_id") != "ndv-p1-wp07-codex-workspace-v1" or manifest.get("status") != "CODEX_WORKSPACE_READY_NOT_EXPOSED":
        raise ValueError("CODEX_WORKSPACE_READY_NOT_EXPOSED manifest required")
    if manifest.get("task_prompt_exposed") is not False or manifest.get("treatment_execution") != "NOT_EXECUTED" or manifest.get("holdout_access") != "NONE":
        raise ValueError("workspace manifest contaminated")
    if manifest.get("run_spec_ref") != str(run_spec_path.resolve()) or manifest.get("run_spec_file_sha256") != sha_file(run_spec_path.resolve()):
        raise ValueError("workspace/run-spec binding mismatch")
    spec = load(run_spec_path.resolve())
    if manifest.get("run_id") != spec.get("run_id") or manifest.get("task_id") != ((spec.get("task") or {}).get("task_id")):
        raise ValueError("workspace/run identity mismatch")
    if manifest.get("base_revision") != ((spec.get("task") or {}).get("base_sha")):
        raise ValueError("workspace base revision mismatch")
    workspace = Path(manifest.get("workspace_ref") or "").resolve()
    if not workspace.is_dir() or not (workspace / ".git").exists():
        raise ValueError(f"workspace git checkout missing: {workspace}")
    head = git(workspace, ["rev-parse", "HEAD"])
    status = git(workspace, ["status", "--porcelain=v1"])
    if head.returncode != 0 or status.returncode != 0:
        raise ValueError("workspace git integrity check failed")
    if head.stdout.strip() != manifest.get("base_revision"):
        raise ValueError("workspace HEAD drift before task exposure")
    if status.stdout.strip():
        raise ValueError("workspace is not clean before task exposure")
    return {"manifest": manifest, "workspace": workspace, "spec": spec}


def capture_candidate_diff(workspace: Path, base_sha: str) -> tuple[str, bytes]:
    status = git(workspace, ["status", "--porcelain=v1"])
    if status.returncode != 0:
        raise ValueError("git status failed after executor")
    # Intent-to-add exposes untracked files to git diff without staging contents.
    add_n = git(workspace, ["add", "-N", "--", "."])
    if add_n.returncode != 0:
        raise ValueError("git add -N failed while capturing candidate")
    try:
        diff = git(workspace, ["diff", "--binary", base_sha, "--"], timeout=120)
        if diff.returncode != 0:
            raise ValueError("git diff failed while capturing candidate")
        data = diff.stdout.encode("utf-8")
    finally:
        # Restore the index to the frozen base while leaving working-tree bytes intact.
        git(workspace, ["reset", "--mixed", base_sha, "--"], timeout=120)
    return status.stdout, data


def stage_classification(*, timed_out: bool, returncode: int, usage: dict[str, Any] | None, accounting_error: str | None, candidate_bytes: int) -> dict[str, Any]:
    if timed_out:
        return {"stage_status":"EXECUTOR_INCONCLUSIVE","verified_solved_task":"INCONCLUSIVE","failure_attribution":"RESOURCE_LIMIT","pending_verification":False,"escalation_trigger":"DETERMINISTIC_RESOURCE_CEILING"}
    if accounting_error is not None:
        return {"stage_status":"EXECUTOR_INCONCLUSIVE","verified_solved_task":"INCONCLUSIVE","failure_attribution":"INCONCLUSIVE_OTHER","pending_verification":False,"escalation_trigger":"STRUCTURALLY_INVALID_ARTIFACT","accounting_integrity_error":accounting_error}
    assert usage is not None
    if returncode != 0 or usage.get("turn_failed_count",0) > 0 or usage.get("error_event_count",0) > 0:
        return {"stage_status":"EXECUTOR_INCONCLUSIVE","verified_solved_task":"INCONCLUSIVE","failure_attribution":"PROVIDER_FAILURE","pending_verification":False,"escalation_trigger":"EXPLICIT_EXECUTOR_BLOCKER"}
    if usage.get("status") != "AUTHORITATIVE":
        return {"stage_status":"EXECUTOR_INCONCLUSIVE","verified_solved_task":"INCONCLUSIVE","failure_attribution":"INCONCLUSIVE_OTHER","pending_verification":False,"escalation_trigger":"STRUCTURALLY_INVALID_ARTIFACT","accounting_integrity_error":"mandatory Codex turn.completed usage missing"}
    if candidate_bytes > 0:
        return {"stage_status":"EXECUTOR_CANDIDATE_PRODUCED_PENDING_VERIFICATION","verified_solved_task":"PENDING_VERIFICATION","failure_attribution":None,"pending_verification":True,"escalation_trigger":None}
    return {"stage_status":"EXECUTOR_NO_CANDIDATE_PENDING_VERIFICATION","verified_solved_task":"PENDING_VERIFICATION","failure_attribution":None,"pending_verification":True,"escalation_trigger":"MISSING_CANDIDATE_BEFORE_TIMEOUT"}


def execute(run_spec_path: Path, workspace_manifest_path: Path, artifact_root: Path, out_dir: Path, execute_token: str) -> dict[str, Any]:
    if execute_token != EXECUTE_TOKEN:
        raise ValueError("explicit frozen development execution token required")
    if out_dir.exists():
        raise ValueError(f"out-dir exists; refusing overwrite: {out_dir}")

    # All checks below occur before the task prompt is sent to Codex.
    pre = preflight(run_spec_path.resolve(), artifact_root.resolve())
    if pre.get("treatment_id") not in SINGLE_HOP:
        raise ValueError("single-hop runner supports only B0/B1/B3")
    ws = verify_workspace_manifest(workspace_manifest_path.resolve(), run_spec_path.resolve())
    compiled = compile_prompt(run_spec_path.resolve(), artifact_root.resolve())
    if compiled.get("run_id") != pre.get("run_id") or compiled.get("run_id") != ws["manifest"].get("run_id"):
        raise ValueError("preflight/prompt/workspace run_id mismatch")

    out_dir.mkdir(parents=True)
    evidence = out_dir / "evidence"
    evidence.mkdir()
    prompt_path = evidence / "prompt.txt"
    prompt_path.write_text(compiled["prompt"], encoding="utf-8")
    if sha_file(prompt_path) != compiled["prompt_sha256"]:
        raise ValueError("compiled prompt persistence hash mismatch")

    argv_template = list(pre["argv_template"])
    if not argv_template or argv_template[-1] != "<FROZEN_TASK_PROMPT>":
        raise ValueError("preflight argv template is not safely redacted")
    argv = [*argv_template[:-1], compiled["prompt"]]
    env = os.environ.copy()
    removed: list[str] = []
    for key in pre.get("environment_variables_to_remove") or []:
        if key in env:
            removed.append(key)
            env.pop(key, None)

    started_at = utc_now()
    t0 = time.monotonic()
    timeout_seconds = pre["executor_timeout_ms"] / 1000.0
    try:
        proc = run(argv, cwd=ws["workspace"], env=env, timeout=timeout_seconds)
        timed_out = False
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        returncode = proc.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes): stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes): stderr = stderr.decode("utf-8", errors="replace")
        stderr += f"\nNDV timeout after {timeout_seconds} seconds\n"
        returncode = 124
    wall_seconds = time.monotonic() - t0
    completed_at = utc_now()

    stdout_path = evidence / "codex.stdout.jsonl"
    stderr_path = evidence / "codex.stderr.log"
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")

    usage: dict[str, Any] | None = None
    accounting_error: str | None = None
    try:
        usage = parse_lines(stdout)
    except ValueError as exc:
        accounting_error = str(exc)
    usage_path = evidence / "usage.json"
    usage_path.write_text(json.dumps(usage if usage is not None else {"schema_id":"ndv-p1-wp07-codex-usage-v1","status":"INVALID","error":accounting_error,"missing_telemetry_is_zero":False}, indent=2, sort_keys=True)+"\n", encoding="utf-8")

    candidate_status = ""
    candidate_diff = b""
    candidate_error: str | None = None
    try:
        candidate_status, candidate_diff = capture_candidate_diff(ws["workspace"], ws["manifest"]["base_revision"])
    except ValueError as exc:
        candidate_error = str(exc)
        if accounting_error is None:
            accounting_error = "candidate artifact integrity failure: " + candidate_error
    status_path = evidence / "git-status.txt"
    diff_path = evidence / "candidate.diff"
    status_path.write_text(candidate_status, encoding="utf-8")
    diff_path.write_bytes(candidate_diff)

    classification = stage_classification(timed_out=timed_out, returncode=returncode, usage=usage, accounting_error=accounting_error, candidate_bytes=len(candidate_diff))
    redacted_argv = [*argv_template[:-1], "<FROZEN_TASK_PROMPT>"]
    report = {
        "schema_id":"ndv-p1-wp07-codex-single-hop-run-v1",
        "run_id":pre["run_id"],
        "treatment_id":pre["treatment_id"],
        "task_id":compiled["task_id"],
        "binding_id":pre["binding_id"],
        "model":pre["model"],
        "execution":{
            "started_at":started_at,
            "completed_at":completed_at,
            "wall_seconds":wall_seconds,
            "returncode":returncode,
            "timed_out":timed_out,
            "executor_timeout_ms":pre["executor_timeout_ms"],
            "run_timeout_ms":pre["run_timeout_ms"],
            "retry_count":0,
            "escalation_count":0,
            "argv_redacted":redacted_argv,
            "environment_variables_removed":sorted(set(pre.get("environment_variables_to_remove") or [])),
            "environment_variables_present_and_removed":sorted(removed),
        },
        "prompt":{
            "ref":str(prompt_path),
            "sha256":sha_file(prompt_path),
            "bytes":prompt_path.stat().st_size,
            "shaping":compiled["shaping"],
            "source_executor_visible_sha256":compiled["executor_visible_sha256"],
            "task_statement_sha256":compiled["task_statement_sha256"],
            "exposed_to_executor":True,
        },
        "candidate":{
            "diff_ref":str(diff_path),
            "diff_sha256":sha_file(diff_path),
            "diff_bytes":len(candidate_diff),
            "git_status_ref":str(status_path),
            "git_status_sha256":sha_file(status_path),
            "capture_error":candidate_error,
        },
        "usage":usage,
        "usage_ref":str(usage_path),
        "usage_file_sha256":sha_file(usage_path),
        "raw_evidence":{
            "stdout_ref":str(stdout_path),"stdout_sha256":sha_file(stdout_path),
            "stderr_ref":str(stderr_path),"stderr_sha256":sha_file(stderr_path),
        },
        "classification":classification,
        "verification":{
            "focal":"NOT_EXECUTED",
            "preservation":"NOT_EXECUTED",
            "final_treatment_outcome":"PENDING_VERIFICATION" if classification.get("pending_verification") else "INCONCLUSIVE_AT_EXECUTOR_STAGE",
        },
        "accounting":{
            "failure_cost_retained":True,
            "inconclusive_cost_retained":True,
            "missing_telemetry_is_zero":False,
            "total_system_tokens_component":usage.get("total_system_tokens_component") if isinstance(usage,dict) else None,
        },
        "source_chain":{
            "run_spec_ref":str(run_spec_path.resolve()),"run_spec_file_sha256":sha_file(run_spec_path.resolve()),
            "workspace_manifest_ref":str(workspace_manifest_path.resolve()),"workspace_manifest_file_sha256":sha_file(workspace_manifest_path.resolve()),
            "execution_surface_ref":pre["execution_surface_ref"],"execution_surface_file_sha256":pre["execution_surface_file_sha256"],
            "budget_contract_ref":pre["budget_contract_ref"],"budget_contract_file_sha256":pre["budget_contract_file_sha256"],
        },
        "treatment_execution":"EXECUTOR_STAGE_EXECUTED_ONCE",
        "holdout_access":"NONE",
    }
    report_path = out_dir / "executor-stage-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    return report


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-spec",required=True,type=Path)
    ap.add_argument("--workspace-manifest",required=True,type=Path)
    ap.add_argument("--artifact-root",type=Path,default=Path("."))
    ap.add_argument("--out-dir",required=True,type=Path)
    ap.add_argument("--execute-token",required=True)
    args=ap.parse_args()
    try:
        r=execute(args.run_spec,args.workspace_manifest,args.artifact_root,args.out_dir.resolve(),args.execute_token)
    except (OSError,ValueError,json.JSONDecodeError,subprocess.SubprocessError) as exc:
        print(json.dumps({"status":"FAIL","reason":"CODEX_SINGLE_HOP_EXECUTION_BLOCKED_BEFORE_OR_DURING_STAGE","detail":str(exc)},indent=2))
        return 2
    print(json.dumps({"status":r["classification"]["stage_status"],"run_id":r["run_id"],"treatment_id":r["treatment_id"],"candidate_diff_bytes":r["candidate"]["diff_bytes"],"verified_solved_task":r["classification"]["verified_solved_task"],"final_treatment_outcome":r["verification"]["final_treatment_outcome"]},indent=2))
    return 0 if r["classification"].get("pending_verification") else 3


if __name__=="__main__":
    raise SystemExit(main())
