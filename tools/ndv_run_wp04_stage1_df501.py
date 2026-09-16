#!/usr/bin/env python3
"""Run WP-04 Stage 1 (D-F5-01) with one frozen binding-v2.

This runner is intentionally narrow. It materializes the exact base revision,
invokes the frozen Aider+Ollama surface once, captures the candidate diff, runs
independent focal/preservation verification, and emits one evidence bundle.
No retry, fallback, escalation, or holdout access is implemented.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TASK_PATH = Path("experiments/p1/wp04-stage1-d-f5-01-v1.json")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run(argv: list[str], cwd: Path | None = None, timeout: int = 600, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, check=False, timeout=timeout)


def require_clean_exact_base(workspace: Path, base_sha: str) -> None:
    head = run(["git", "rev-parse", "HEAD"], workspace, 30)
    if head.returncode != 0 or head.stdout.strip() != base_sha:
        raise RuntimeError(f"workspace HEAD mismatch: expected {base_sha}, observed {head.stdout.strip()!r}")
    status = run(["git", "status", "--porcelain"], workspace, 30)
    if status.returncode != 0 or status.stdout.strip():
        raise RuntimeError("workspace must be clean before executor exposure")


def classify(focal_rc: int | None, preservation_rc: int | None, executor_rc: int | None, timed_out: bool) -> tuple[str, str]:
    if timed_out:
        return "SMOKE_INCONCLUSIVE", "RESOURCE_LIMIT"
    if executor_rc not in (0, None):
        return "SMOKE_INCONCLUSIVE", "PROVIDER_FAILURE"
    if focal_rc == 0 and preservation_rc == 0:
        return "SMOKE_VALID_SOLVED", "NONE"
    if focal_rc is not None and preservation_rc is not None:
        return "SMOKE_VALID_FAILED", "PRODUCT_FAILURE"
    return "SMOKE_INCONCLUSIVE", "HARNESS_FAILURE"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--binding", required=True, type=Path)
    ap.add_argument("--source-repo", required=True, type=Path, help="Local clone of oigorbrito/metaO used only as clone source")
    ap.add_argument("--out-dir", type=Path, default=Path(".ndv-runs/wp04-stage1-d-f5-01"))
    ap.add_argument("--aider-exe", type=Path)
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args()

    task = load(TASK_PATH)
    binding = load(args.binding)
    if binding.get("schema_id") != "ndv-p1-wp04-executor-binding-v2" or binding.get("status") != "QUALIFIED":
        raise SystemExit("binding-v2 with status=QUALIFIED required")
    if binding.get("retry_limit") != 0 or binding.get("escalation_limit") != 0:
        raise SystemExit("WP-04 Stage 1 forbids retry/escalation")
    if not args.source_repo.exists():
        raise SystemExit(f"source repo does not exist: {args.source_repo}")

    aider = str(args.aider_exe) if args.aider_exe else shutil.which("aider")
    if not aider or not Path(aider).exists():
        raise SystemExit("aider executable not found; pass --aider-exe explicitly")

    out = args.out_dir.resolve()
    workspace = out / "workspace"
    evidence_dir = out / "evidence"
    if out.exists():
        raise SystemExit(f"out-dir already exists; refusing overwrite: {out}")
    evidence_dir.mkdir(parents=True)

    clone = run(["git", "clone", "--no-local", str(args.source_repo.resolve()), str(workspace)], timeout=300)
    if clone.returncode != 0:
        raise SystemExit(f"clone failed: {clone.stderr or clone.stdout}")
    checkout = run(["git", "checkout", "--detach", task["base_sha"]], workspace, 120)
    if checkout.returncode != 0:
        raise SystemExit(f"checkout failed: {checkout.stderr or checkout.stdout}")
    require_clean_exact_base(workspace, task["base_sha"])

    started = datetime.now(timezone.utc).isoformat()
    env = os.environ.copy()
    env["OLLAMA_API_BASE"] = "http://127.0.0.1:11434"
    model_name = binding["model"]["identity"]
    message = task["task_statement"]
    argv = [
        aider,
        "--model", f"ollama_chat/{model_name}",
        "--message", message,
        "--yes",
        "--no-auto-commits",
        "--no-dirty-commits",
        "--no-gitignore",
        "--no-check-update",
        "--no-stream",
        "--disable-playwright",
    ]
    t0 = time.monotonic()
    try:
        executor = run(argv, workspace, args.timeout, env)
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        executor = subprocess.CompletedProcess(exc.cmd, 124, stdout=exc.stdout or "", stderr=exc.stderr or "")
        timed_out = True
    executor_seconds = time.monotonic() - t0

    diff_proc = run(["git", "diff", "--binary"], workspace, 60)
    diff_text = diff_proc.stdout
    (evidence_dir / "candidate.diff").write_text(diff_text, encoding="utf-8")
    (evidence_dir / "executor.stdout.log").write_text(executor.stdout or "", encoding="utf-8")
    (evidence_dir / "executor.stderr.log").write_text(executor.stderr or "", encoding="utf-8")

    focal_argv = task["verifier"]["focal"]
    preservation_argv = task["verifier"]["preservation"]
    focal = run(focal_argv, workspace, 900)
    preservation = run(preservation_argv, workspace, 1800)
    (evidence_dir / "focal.stdout.log").write_text(focal.stdout or "", encoding="utf-8")
    (evidence_dir / "focal.stderr.log").write_text(focal.stderr or "", encoding="utf-8")
    (evidence_dir / "preservation.stdout.log").write_text(preservation.stdout or "", encoding="utf-8")
    (evidence_dir / "preservation.stderr.log").write_text(preservation.stderr or "", encoding="utf-8")

    outcome, attribution = classify(focal.returncode, preservation.returncode, executor.returncode, timed_out)
    report = {
        "schema_id": "ndv-wp04-stage1-run-v1",
        "task_id": task["task_id"],
        "base_sha": task["base_sha"],
        "task_statement_sha256": sha256_text(message),
        "binding_ref": str(args.binding),
        "binding_id": binding.get("binding_id"),
        "executor_identity": binding.get("exact_executor_identity"),
        "started_at": started,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "retry_count": 0,
        "escalation_count": 0,
        "holdout_access": "NONE",
        "executor": {
            "argv_redacted_task": [aider, "--model", f"ollama_chat/{model_name}", "--message", "<FROZEN_RAW_TASK>", "..."],
            "returncode": executor.returncode,
            "timed_out": timed_out,
            "wall_seconds": executor_seconds,
            "stdout_ref": "evidence/executor.stdout.log",
            "stderr_ref": "evidence/executor.stderr.log"
        },
        "candidate": {
            "diff_ref": "evidence/candidate.diff",
            "diff_sha256": sha256_text(diff_text),
            "diff_bytes": len(diff_text.encode("utf-8")),
        },
        "verification": {
            "focal": {"argv": focal_argv, "returncode": focal.returncode, "stdout_ref": "evidence/focal.stdout.log", "stderr_ref": "evidence/focal.stderr.log"},
            "preservation": {"argv": preservation_argv, "returncode": preservation.returncode, "stdout_ref": "evidence/preservation.stdout.log", "stderr_ref": "evidence/preservation.stderr.log"}
        },
        "accounting": {
            "executor_wall_seconds": executor_seconds,
            "token_usage": "EXPLICIT_MISSINGNESS_UNLESS_PRESENT_IN_EXECUTOR_LOGS",
            "monetary_cost": "LOCAL_COST_NOT_CONVERTED_TO_TOKENS",
            "failure_resources_retained": true
        },
        "outcome": outcome,
        "failure_attribution": attribution,
        "stage2_release": "YES" if outcome in {"SMOKE_VALID_SOLVED", "SMOKE_VALID_FAILED", "SMOKE_INCONCLUSIVE"} else "NO"
    }
    # Python boolean fix before serialization
    report["accounting"]["failure_resources_retained"] = True
    (out / "run-report.json").write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"outcome": outcome, "failure_attribution": attribution, "report": str(out / "run-report.json")}, indent=2))
    return 0 if outcome == "SMOKE_VALID_SOLVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
