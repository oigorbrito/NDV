#!/usr/bin/env python3
"""Discover subscription-backed coding-agent CLIs without task exposure.

This probe is intentionally introspection-only. It does not authenticate, launch an
interactive TUI, mutate repositories, download models, or execute a treatment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROGRAM = Path("experiments/p1/wp07-executor-role-qualification-v1.json")


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(argv: list[str], timeout: int = 20) -> dict[str, Any]:
    try:
        p = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=timeout)
        return {"returncode": p.returncode, "stdout": p.stdout or "", "stderr": p.stderr or "", "timed_out": False}
    except subprocess.TimeoutExpired as exc:
        return {"returncode": 124, "stdout": exc.stdout or "", "stderr": exc.stderr or "", "timed_out": True}
    except OSError as exc:
        return {"returncode": 127, "stdout": "", "stderr": str(exc), "timed_out": False}


def first_line(result: dict[str, Any]) -> str:
    text = (result.get("stdout") or "") + "\n" + (result.get("stderr") or "")
    return next((line.strip() for line in text.splitlines() if line.strip()), "")


def discover(name: str, explicit: str | None = None) -> dict[str, Any]:
    executable = explicit or shutil.which(name)
    if not executable:
        return {"cli": name, "status": "MISSING", "task_exposure": False}
    path = str(Path(executable).expanduser().resolve())
    version = run([path, "--version"])
    help_result = run([path, "--help"])
    help_text = ((help_result.get("stdout") or "") + "\n" + (help_result.get("stderr") or "")).lower()
    record: dict[str, Any] = {
        "cli": name,
        "status": "DISCOVERED" if version["returncode"] == 0 and help_result["returncode"] == 0 else "INTERFACE_UNRESOLVED",
        "executable_path": path,
        "version_observed": first_line(version),
        "version_returncode": version["returncode"],
        "help_returncode": help_result["returncode"],
        "task_exposure": False,
    }
    if name == "codex":
        exec_help = run([path, "exec", "--help"])
        exec_text = ((exec_help.get("stdout") or "") + "\n" + (exec_help.get("stderr") or "")).lower()
        record["noninteractive_exec_discovered"] = exec_help["returncode"] == 0
        record["model_flag_discovered"] = "--model" in exec_text
        record["sandbox_flag_discovered"] = "--sandbox" in exec_text
        record["json_flag_discovered"] = "--json" in exec_text or "experimental-json" in exec_text
        record["ephemeral_flag_discovered"] = "--ephemeral" in exec_text
        if not record["noninteractive_exec_discovered"] or not record["model_flag_discovered"] or not record["sandbox_flag_discovered"]:
            record["status"] = "INTERFACE_UNRESOLVED"
    elif name == "agy":
        record["noninteractive_interface_discovered"] = any(token in help_text for token in ("non-interactive", "noninteractive", "--prompt", " exec ", " run "))
        record["model_pinning_interface_discovered"] = "--model" in help_text
        if not record["noninteractive_interface_discovered"] or not record["model_pinning_interface_discovered"]:
            record["status"] = "INTERFACE_UNRESOLVED"
    return record


def build(codex: str | None, agy: str | None, program: Path) -> dict[str, Any]:
    program = program.resolve()
    if not program.is_file():
        raise ValueError(f"qualification program not found: {program}")
    payload = json.loads(program.read_text(encoding="utf-8"))
    if payload.get("schema_id") != "ndv-p1-wp07-executor-role-qualification-v1":
        raise ValueError("unexpected qualification program schema")
    if payload.get("status") != "PROSPECTIVE_FROZEN_NOT_EXECUTED" or payload.get("treatment_execution") != "NOT_EXECUTED" or payload.get("holdout_access") != "NONE":
        raise ValueError("qualification program contamination")
    return {
        "schema_id": "ndv-p1-wp07-subscription-surface-probe-v1",
        "status": "DISCOVERY_COMPLETE",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "host": {"os_name": os.name},
        "program_ref": str(program),
        "program_file_sha256": sha_file(program),
        "surfaces": {
            "codex": discover("codex", codex),
            "antigravity": discover("agy", agy),
        },
        "authority": "DISCOVERY_ONLY",
        "binding_created": False,
        "qualification_completed": False,
        "task_exposure": False,
        "treatment_execution": "NOT_EXECUTED",
        "holdout_access": "NONE",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--codex-exe")
    ap.add_argument("--agy-exe")
    ap.add_argument("--program", type=Path, default=PROGRAM)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    try:
        result = build(args.codex_exe, args.agy_exe, args.program)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "reason": "SUBSCRIPTION_SURFACE_PROBE_BLOCKED", "detail": str(exc)}, indent=2))
        return 2
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        if args.out.exists():
            raise SystemExit(f"refusing overwrite: {args.out}")
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
