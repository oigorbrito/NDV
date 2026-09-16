#!/usr/bin/env python3
"""Run WP-04 Stage 2 (D-F6-01) after Stage 1 evidence import.

The runner materializes the exact historical base, proves the structural focal
fails on base while the historical Rust oracle passes, invokes the same frozen
Aider+Ollama binding exactly once, captures the candidate, and verifies it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TASK_PATH = Path("experiments/p1/wp04-stage2-d-f6-01-v1.json")
STRUCTURAL = Path(__file__).with_name("ndv_verify_df601_structural.py").resolve()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run(argv: list[str], cwd: Path | None = None, timeout: int = 1800, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, check=False, timeout=timeout)


def write_log(path: Path, proc: subprocess.CompletedProcess[str]) -> None:
    path.write_text((proc.stdout or "") + ("\n[stderr]\n" + proc.stderr if proc.stderr else ""), encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def require_clean_exact_base(workspace: Path, base_sha: str) -> None:
    head = run(["git", "rev-parse", "HEAD"], workspace, 30)
    status = run(["git", "status", "--porcelain"], workspace, 30)
    if head.returncode != 0 or head.stdout.strip() != base_sha:
        raise RuntimeError("workspace HEAD mismatch")
    if status.returncode != 0 or status.stdout.strip():
        raise RuntimeError("workspace dirty before executor exposure")


def source_origin(source_repo: Path) -> str:
    proc = run(["git", "remote", "get-url", "origin"], source_repo, 30)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError("source repo origin unavailable")
    return proc.stdout.strip()


def materialize(source_repo: Path, workspace: Path, base_sha: str, evidence: Path) -> str:
    origin = source_origin(source_repo)
    clone = run(["git", "clone", "--no-checkout", origin, str(workspace)], timeout=600)
    write_log(evidence / "materialization-clone.log", clone)
    if clone.returncode != 0:
        raise RuntimeError("clone failed")
    fetch = run(["git", "fetch", "--no-tags", "origin", base_sha], workspace, 600)
    write_log(evidence / "materialization-fetch.log", fetch)
    if fetch.returncode != 0:
        raise RuntimeError("exact base fetch failed")
    object_check = run(["git", "cat-file", "-e", f"{base_sha}^{{tree}}"], workspace, 30)
    write_log(evidence / "materialization-object-check.log", object_check)
    if object_check.returncode != 0:
        raise RuntimeError("exact base tree unavailable")
    checkout = run(["git", "checkout", "--detach", base_sha], workspace, 120)
    write_log(evidence / "materialization-checkout.log", checkout)
    if checkout.returncode != 0:
        raise RuntimeError("exact base checkout failed")
    require_clean_exact_base(workspace, base_sha)
    return origin


def stage1_manifest_path(path: Path) -> Path:
    sidecar = path / "import-manifest-v2.json"
    return sidecar if sidecar.is_file() else path / "import-manifest.json"


def artifact_index(records: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(records, list):
        raise ValueError("Stage 1 preserved_artifacts must use canonical v2 list form")
    out: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("invalid Stage 1 artifact inventory record")
        rel = record.get("path")
        if not isinstance(rel, str) or not rel or rel in out:
            raise ValueError("invalid or duplicate Stage 1 artifact path")
        out[rel] = record
    return out


def validate_stage1_import(path: Path, binding_id: str) -> dict[str, Any]:
    manifest_path = stage1_manifest_path(path)
    report_path = path / "run-report.json"
    if not manifest_path.is_file() or not report_path.is_file():
        raise ValueError("Stage 1 import manifest and run-report are required")
    manifest = load(manifest_path)
    report = load(report_path)
    if manifest.get("schema_id") != "ndv-wp04-import-manifest-v2":
        raise ValueError("Stage 1 must use evidence-only import manifest v2")
    if manifest.get("raw_evidence_preserved") is not True or manifest.get("treatment_reexecuted") is not False:
        raise ValueError("Stage 1 import provenance invalid")
    if manifest.get("task_id") != "D-F5-01" or report.get("task_id") != "D-F5-01":
        raise ValueError("Stage 1 task mismatch")
    if manifest.get("outcome") != "SMOKE_VALID_FAILED" or report.get("outcome") != "SMOKE_VALID_FAILED":
        raise ValueError("expected the frozen valid-failed Stage 1 result")
    if manifest.get("binding_id") != binding_id or report.get("binding_id") != binding_id:
        raise ValueError("Stage 1 and Stage 2 binding mismatch")
    index = artifact_index(manifest.get("preserved_artifacts"))
    for rel in ("run-report.json", "evidence/candidate.diff", "evidence/executor.log"):
        record = index.get(rel)
        artifact = path / Path(rel)
        if not isinstance(record, dict) or not artifact.is_file():
            raise ValueError(f"missing hashed Stage 1 artifact: {rel}")
        data = artifact.read_bytes()
        if sha256_bytes(data) != record.get("sha256") or len(data) != record.get("size_bytes"):
            raise ValueError(f"Stage 1 artifact hash/size mismatch: {rel}")
    return manifest


def resolve_frozen_aider(binding: dict[str, Any], explicit: Path | None) -> str:
    frozen = binding.get("scaffold", {}).get("executable_path")
    if not isinstance(frozen, str) or not frozen:
        raise ValueError("binding missing frozen scaffold executable_path")
    frozen_path = Path(frozen).expanduser().resolve()
    if explicit is not None and explicit.expanduser().resolve() != frozen_path:
        raise ValueError("--aider-exe differs from frozen binding executable_path")
    if not frozen_path.is_file():
        raise ValueError(f"frozen Aider executable not found: {frozen_path}")
    return str(frozen_path)


def validate_aider_version(aider: str, binding: dict[str, Any]) -> str:
    expected = binding.get("scaffold", {}).get("version_or_commit")
    if not isinstance(expected, str) or not expected:
        raise ValueError("binding missing frozen Aider version")
    proc = run([aider, "--version"], timeout=30)
    observed = next((x.strip() for x in (proc.stdout or proc.stderr or "").splitlines() if x.strip()), "")
    if proc.returncode != 0 or observed != expected:
        raise ValueError(f"Aider version mismatch: expected {expected!r}, observed {observed!r}")
    return observed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--binding", required=True, type=Path)
    ap.add_argument("--source-repo", required=True, type=Path)
    ap.add_argument("--stage1-import", required=True, type=Path)
    ap.add_argument("--aider-exe", type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args()

    task = load(TASK_PATH)
    binding = load(args.binding)
    if binding.get("schema_id") != "ndv-p1-wp04-executor-binding-v2" or binding.get("status") != "QUALIFIED":
        raise SystemExit("qualified binding-v2 required")
    if binding.get("retry_limit") != 0 or binding.get("escalation_limit") != 0:
        raise SystemExit("WP-04 Stage 2 forbids retry/escalation")
    try:
        stage1_manifest = validate_stage1_import(args.stage1_import.resolve(), str(binding.get("binding_id")))
        aider = resolve_frozen_aider(binding, args.aider_exe)
        aider_version = validate_aider_version(aider, binding)
    except Exception as exc:
        raise SystemExit(f"STAGE2_BLOCKED: {exc}") from exc

    out = args.out_dir.resolve()
    if out.exists():
        raise SystemExit(f"out-dir exists; refusing overwrite: {out}")
    evidence = out / "evidence"
    workspace = out / "workspace"
    evidence.mkdir(parents=True)

    try:
        origin = materialize(args.source_repo.resolve(), workspace, task["base_sha"], evidence)
    except Exception as exc:
        raise SystemExit(f"MATERIALIZATION_BLOCKED_PRE_EXPOSURE: {exc}") from exc

    rust_cwd = workspace / task["working_directory"]
    env = os.environ.copy()
    env["CARGO_NET_OFFLINE"] = "true"
    cargo_ver = run(["cargo", "--version"], rust_cwd, 30, env)
    write_log(evidence / "environment-cargo.log", cargo_ver)
    if cargo_ver.returncode != 0:
        raise SystemExit("ENVIRONMENT_BLOCKED_PRE_EXPOSURE: cargo unavailable")

    base_focal = run([sys.executable, str(STRUCTURAL), "--workspace", str(workspace)], timeout=60)
    write_log(evidence / "baseline-focal.log", base_focal)
    if base_focal.returncode == 0:
        raise SystemExit("ORACLE_DEFECT_PRE_EXPOSURE: structural focal passes on base")

    checks = task["historical_oracle"]["mandatory_checks"]
    for idx, argv in enumerate(checks, 1):
        proc = run(argv, rust_cwd, 1800, env)
        write_log(evidence / f"baseline-oracle-{idx}.log", proc)
        if proc.returncode != 0:
            raise SystemExit(f"ENVIRONMENT_DRIFT_PRE_EXPOSURE: baseline oracle check {idx} failed")
    require_clean_exact_base(workspace, task["base_sha"])

    started = datetime.now(timezone.utc).isoformat()
    exec_env = os.environ.copy()
    exec_env["OLLAMA_API_BASE"] = "http://127.0.0.1:11434"
    model_name = binding["model"]["identity"]
    message = task["task_statement"]
    argv = [aider, "--model", f"ollama_chat/{model_name}", "--message", message, "--yes", "--no-auto-commits", "--no-dirty-commits", "--no-gitignore", "--no-check-update", "--no-stream", "--disable-playwright"]
    t0 = time.monotonic()
    try:
        executor = run(argv, workspace, args.timeout, exec_env)
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        executor = subprocess.CompletedProcess(exc.cmd, 124, stdout=exc.stdout or "", stderr=exc.stderr or "")
        timed_out = True
    wall = time.monotonic() - t0
    write_log(evidence / "executor.log", executor)

    diff = run(["git", "diff", "--binary"], workspace, 60).stdout
    (evidence / "candidate.diff").write_text(diff, encoding="utf-8")
    focal = run([sys.executable, str(STRUCTURAL), "--workspace", str(workspace)], timeout=60)
    write_log(evidence / "candidate-focal.log", focal)

    candidate_checks = []
    for idx, check_argv in enumerate(checks, 1):
        proc = run(check_argv, rust_cwd, 1800, env)
        write_log(evidence / f"candidate-oracle-{idx}.log", proc)
        candidate_checks.append(proc.returncode)

    if timed_out:
        outcome, attribution = "SMOKE_INCONCLUSIVE", "RESOURCE_LIMIT"
    elif executor.returncode != 0:
        outcome, attribution = "SMOKE_INCONCLUSIVE", "PROVIDER_FAILURE"
    elif focal.returncode == 0 and all(code == 0 for code in candidate_checks):
        outcome, attribution = "SMOKE_VALID_SOLVED", "NONE"
    else:
        outcome, attribution = "SMOKE_VALID_FAILED", "PRODUCT_FAILURE"

    report = {
        "schema_id": "ndv-wp04-stage2-run-v1",
        "task_id": task["task_id"],
        "base_sha": task["base_sha"],
        "binding_id": binding.get("binding_id"),
        "executor_identity": binding.get("exact_executor_identity"),
        "aider_version_revalidated": aider_version,
        "stage1_import_manifest_schema": stage1_manifest.get("schema_id"),
        "stage1_candidate_diff_sha256": stage1_manifest.get("candidate_diff_sha256"),
        "materialization_origin": origin,
        "started_at": started,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "retry_count": 0,
        "escalation_count": 0,
        "holdout_access": "NONE",
        "executor": {"returncode": executor.returncode, "timed_out": timed_out, "wall_seconds": wall},
        "candidate": {"diff_bytes": len(diff.encode("utf-8")), "diff_sha256": sha256_text(diff)},
        "verification": {"structural_focal_returncode": focal.returncode, "oracle_returncodes": candidate_checks},
        "outcome": outcome,
        "failure_attribution": attribution,
        "comparative_authority": "NONE"
    }
    (out / "run-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"outcome": outcome, "failure_attribution": attribution, "report": str(out / "run-report.json")}, indent=2))
    return 0 if outcome == "SMOKE_VALID_SOLVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
