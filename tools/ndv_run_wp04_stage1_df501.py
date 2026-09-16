#!/usr/bin/env python3
"""Run WP-04 Stage 1 (D-F5-01) with one frozen binding-v2.

Flow: exact base -> frozen offline environment setup -> baseline preservation PASS
and structural focal FAIL -> one Aider+Ollama execution -> candidate capture ->
structural focal + preservation verification -> accounting and attribution.
No retry, fallback, escalation, or holdout access is implemented.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TASK_PATH = Path("experiments/p1/wp04-stage1-d-f5-01-v1.json")
STRUCTURAL_VERIFIER = Path(__file__).with_name("ndv_verify_df501_structural.py").resolve()


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
        raise RuntimeError(f"workspace must be clean before executor exposure: {status.stdout!r}")


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def write_log(path: Path, proc: subprocess.CompletedProcess[str]) -> None:
    path.write_text((proc.stdout or "") + ("\n[stderr]\n" + proc.stderr if proc.stderr else ""), encoding="utf-8")


def classify(focal_rc: int, preservation_rc: int, executor_rc: int, timed_out: bool) -> tuple[str, str]:
    if timed_out:
        return "SMOKE_INCONCLUSIVE", "RESOURCE_LIMIT"
    if executor_rc != 0:
        return "SMOKE_INCONCLUSIVE", "PROVIDER_FAILURE"
    if focal_rc == 0 and preservation_rc == 0:
        return "SMOKE_VALID_SOLVED", "NONE"
    return "SMOKE_VALID_FAILED", "PRODUCT_FAILURE"


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
    venv = out / "verifier-venv"
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

    # Reproduce the historically admitted offline verifier environment.
    create_venv = run([sys.executable, "-m", "venv", "--system-site-packages", str(venv)], timeout=180)
    write_log(evidence_dir / "environment-venv.log", create_venv)
    if create_venv.returncode != 0:
        raise SystemExit("verifier venv creation failed before task exposure")
    py = str(venv_python(venv))
    install = run([py, "-m", "pip", "install", "--no-index", "--no-deps", "--no-build-isolation", "--editable", str(workspace)], workspace, 300)
    write_log(evidence_dir / "environment-install.log", install)
    if install.returncode != 0:
        raise SystemExit("frozen offline editable install failed before task exposure")
    require_clean_exact_base(workspace, task["base_sha"])

    # Oracle discriminability gate: base must fail focal but pass preservation.
    base_focal = run([sys.executable, str(STRUCTURAL_VERIFIER), "--workspace", str(workspace)], timeout=60)
    write_log(evidence_dir / "baseline-focal.log", base_focal)
    if base_focal.returncode == 0:
        raise SystemExit("ORACLE_DEFECT: structural focal unexpectedly passes on untouched base")
    preservation_argv = [py, "-B", "-m", "unittest", "discover", "-s", "tests/unit"]
    base_preservation = run(preservation_argv, workspace, 1800)
    write_log(evidence_dir / "baseline-preservation.log", base_preservation)
    if base_preservation.returncode != 0:
        raise SystemExit("ENVIRONMENT_DRIFT: baseline preservation failed before task exposure")
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
    write_log(evidence_dir / "executor.log", executor)

    diff_proc = run(["git", "diff", "--binary"], workspace, 60)
    diff_text = diff_proc.stdout
    (evidence_dir / "candidate.diff").write_text(diff_text, encoding="utf-8")

    focal = run([sys.executable, str(STRUCTURAL_VERIFIER), "--workspace", str(workspace)], timeout=60)
    write_log(evidence_dir / "candidate-focal.log", focal)
    preservation = run(preservation_argv, workspace, 1800)
    write_log(evidence_dir / "candidate-preservation.log", preservation)

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
        "baseline_gate": {
            "structural_focal_expected_fail_returncode": base_focal.returncode,
            "preservation_returncode": base_preservation.returncode,
            "environment_setup": "venv --system-site-packages + offline editable install"
        },
        "executor": {
            "argv_redacted_task": [aider, "--model", f"ollama_chat/{model_name}", "--message", "<FROZEN_RAW_TASK>", "..."],
            "returncode": executor.returncode,
            "timed_out": timed_out,
            "wall_seconds": executor_seconds,
            "log_ref": "evidence/executor.log"
        },
        "candidate": {
            "diff_ref": "evidence/candidate.diff",
            "diff_sha256": sha256_text(diff_text),
            "diff_bytes": len(diff_text.encode("utf-8"))
        },
        "verification": {
            "focal": {"kind": "EXTERNAL_REQUIREMENT_STRUCTURAL", "returncode": focal.returncode, "log_ref": "evidence/candidate-focal.log"},
            "preservation": {"argv": preservation_argv, "returncode": preservation.returncode, "log_ref": "evidence/candidate-preservation.log"}
        },
        "accounting": {
            "executor_wall_seconds": executor_seconds,
            "token_usage": "EXPLICIT_MISSINGNESS_UNLESS_PRESENT_IN_EXECUTOR_LOG",
            "monetary_cost": "LOCAL_COST_NOT_CONVERTED_TO_TOKENS",
            "failure_resources_retained": True
        },
        "outcome": outcome,
        "failure_attribution": attribution,
        "stage2_release": "YES"
    }
    (out / "run-report.json").write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"outcome": outcome, "failure_attribution": attribution, "report": str(out / "run-report.json")}, indent=2))
    return 0 if outcome == "SMOKE_VALID_SOLVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
