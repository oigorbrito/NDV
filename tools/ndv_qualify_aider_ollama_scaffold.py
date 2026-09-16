#!/usr/bin/env python3
"""Qualify Aider + an already-installed Ollama model as a WP-04 executor scaffold.

The qualification uses only a synthetic temporary git repository. It never
exposes a P1 task and never downloads a model. A binding-v2 is emitted only if
Aider actually edits the fixture repository and the resulting git diff matches
the frozen oracle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def find_model(probe: dict[str, Any], model_name: str) -> dict[str, Any]:
    models = probe.get("ollama", {}).get("models", [])
    matches = [m for m in models if isinstance(m, dict) and m.get("name") == model_name]
    if len(matches) != 1:
        raise ValueError(f"model {model_name!r} must match exactly one installed Ollama model")
    digest = matches[0].get("digest")
    if not isinstance(digest, str) or not BASE_SHA_RE.fullmatch(digest):
        raise ValueError("installed Ollama model digest must be exact 64-hex")
    return matches[0]


def resolve_aider(explicit: Path | None) -> str:
    if explicit is not None:
        candidate = explicit.expanduser()
        if not candidate.is_file():
            raise ValueError(f"explicit aider executable does not exist: {candidate}")
        return str(candidate.resolve())

    from_path = shutil.which("aider")
    if from_path:
        return from_path

    home = Path.home()
    candidates = [
        home / ".local" / "bin" / "aider.exe",
        home / ".local" / "bin" / "aider",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())

    raise ValueError(
        "aider executable not found; pass --aider-exe explicitly or install it before qualification"
    )


def run(argv: list[str], cwd: Path, timeout: int, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def parse_aider_version(text: str) -> str:
    line = next((x.strip() for x in text.splitlines() if x.strip()), "")
    if not line:
        raise ValueError("aider version output is empty")
    return line


def diff_is_valid(diff: str) -> bool:
    normalized = diff.replace("\r\n", "\n")
    return "-VALUE = 1" in normalized and "+VALUE = 2" in normalized and "fixture.py" in normalized


def make_binding(
    *,
    aider_version: str,
    aider_executable: str,
    model_name: str,
    model_digest: str,
    evidence_ref: str,
    evidence_sha: str,
    frozen_at: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    seed = f"aider|{aider_version}|{aider_executable}|{model_name}|{model_digest}|{evidence_sha}".encode("utf-8")
    return {
        "schema_id": "ndv-p1-wp04-executor-binding-v2",
        "binding_id": "WP04-AIDER-OLLAMA-" + sha256_bytes(seed)[:16],
        "campaign_ref": "experiments/p1/wp04-real-executor-smoke-v1.json",
        "surface_class": "LOCAL_PINNED",
        "executor_kind": "MODEL_PLUS_FROZEN_SCAFFOLD",
        "provider_or_runtime": "Ollama local runtime + Aider",
        "exact_executor_identity": f"aider({aider_version})+{model_name}",
        "version_or_model_hash": f"aider:{aider_version}|ollama:{model_digest}",
        "scaffold": {
            "name": "aider",
            "source_repository": "Aider-AI/aider",
            "version_or_commit": aider_version,
            "executable_path": aider_executable,
            "invocation_mode": "noninteractive --message repository edit",
            "repository_tool_access": True,
            "implicit_model_fallback": False,
            "dynamic_routing": False,
        },
        "model": {
            "identity": model_name,
            "digest_or_exact_version": model_digest,
            "endpoint": "http://127.0.0.1:11434",
        },
        "invocation_command_or_surface": f"{aider_executable} --model ollama_chat/{model_name} --message <RAW_TASK>",
        "qualification_evidence_ref": evidence_ref,
        "qualification_evidence_sha256": evidence_sha,
        "telemetry_mode": {
            "identity": "AIDER_VERSION_PLUS_OLLAMA_MODEL_DIGEST",
            "usage": "AIDER_OR_OLLAMA_NATIVE_USAGE_OR_EXPLICIT_MISSINGNESS",
            "timestamps": "NDV_WALL_CLOCK",
            "raw_response_or_local_trace": "AIDER_STDOUT_STDERR_PLUS_GIT_DIFF_HASHED",
        },
        "candidate_capture_mode": "ISOLATED_WORKTREE_GIT_DIFF",
        "timeout_seconds": timeout_seconds,
        "network_policy": "LOCAL_OLLAMA_REQUIRED; EXTERNAL_NETWORK_NOT_REQUIRED_BY_QUALIFICATION",
        "retry_limit": 0,
        "escalation_limit": 0,
        "automatic_download": False,
        "implicit_fallback": False,
        "dynamic_routing": False,
        "task_context_mode": "RAW_TASK_PLUS_REPOSITORY_TOOL_ACCESS",
        "pricing_or_local_cost_ref": "LOCAL_COST_EVIDENCE_REQUIRED_AT_WP04_RUN_ACCOUNTING",
        "frozen_at": frozen_at,
        "status": "QUALIFIED",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--probe", required=True, type=Path)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--binding-out", required=True, type=Path)
    ap.add_argument("--aider-exe", type=Path, help="Explicit Aider executable path; useful when uv's bin dir is not active in PATH")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()

    probe = load(args.probe)
    model = find_model(probe, args.model)
    try:
        aider = resolve_aider(args.aider_exe)
    except ValueError as exc:
        raise SystemExit(str(exc))

    now = datetime.now(timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(prefix="ndv-aider-qual-") as tmp:
        root = Path(tmp)
        (root / "fixture.py").write_text("VALUE = 1\n", encoding="utf-8")
        for argv in (["git", "init", "-q"], ["git", "config", "user.email", "ndv@example.invalid"], ["git", "config", "user.name", "NDV Fixture"], ["git", "add", "fixture.py"], ["git", "commit", "-qm", "fixture base"]):
            proc = run(list(argv), root, 30)
            if proc.returncode != 0:
                raise SystemExit(f"fixture git setup failed: {proc.stderr or proc.stdout}")

        ver = run([aider, "--version"], root, 30)
        if ver.returncode != 0:
            raise SystemExit(f"aider --version failed: {ver.stderr or ver.stdout}")
        aider_version = parse_aider_version(ver.stdout or ver.stderr)

        message = "Edit fixture.py so that its only assignment becomes exactly `VALUE = 2`. Make no other repository changes."
        env = os.environ.copy()
        env["OLLAMA_API_BASE"] = "http://127.0.0.1:11434"
        start = time.monotonic()
        try:
            proc = run([
                aider,
                "--model", f"ollama_chat/{args.model}",
                "--message", message,
                "--yes",
                "--no-auto-commits",
                "--no-dirty-commits",
                "--no-gitignore",
                "--no-check-update",
                "--no-stream",
                "--disable-playwright",
                "fixture.py",
            ], root, args.timeout, env)
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            proc = subprocess.CompletedProcess(exc.cmd, 124, stdout=exc.stdout or "", stderr=exc.stderr or "")
            timed_out = True
        elapsed = time.monotonic() - start

        diff_proc = run(["git", "diff", "--", "fixture.py"], root, 30)
        diff = diff_proc.stdout
        valid = proc.returncode == 0 and not timed_out and diff_is_valid(diff)

        evidence = {
            "schema_id": "ndv-wp05-aider-ollama-scaffold-qualification-v1",
            "timestamp_utc": now,
            "aider_version": aider_version,
            "aider_executable": aider,
            "model_name": args.model,
            "model_digest": model.get("digest"),
            "model_quantization": model.get("quantization_level"),
            "synthetic_task": message,
            "p1_task_exposed": False,
            "holdout_access": "NONE",
            "automatic_model_download": False,
            "retry_limit": 0,
            "escalation_limit": 0,
            "elapsed_seconds": elapsed,
            "timed_out": timed_out,
            "aider_exit_code": proc.returncode,
            "aider_stdout": proc.stdout,
            "aider_stderr": proc.stderr,
            "git_diff": diff,
            "git_diff_sha256": sha256_bytes(diff.encode("utf-8")),
            "oracle": "PASS" if valid else "FAIL",
            "status": "S0_READY" if valid else "S0_FAIL",
        }
        encoded = json.dumps(evidence, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded, encoding="utf-8")
        evidence_sha = sha256_bytes(encoded.encode("utf-8"))

        if not valid:
            print(json.dumps({"status": "S0_FAIL", "evidence": str(args.out), "binding": None}, indent=2))
            return 2

        binding = make_binding(
            aider_version=aider_version,
            aider_executable=aider,
            model_name=args.model,
            model_digest=str(model.get("digest")),
            evidence_ref=str(args.out),
            evidence_sha=evidence_sha,
            frozen_at=now,
            timeout_seconds=args.timeout,
        )
        args.binding_out.parent.mkdir(parents=True, exist_ok=True)
        args.binding_out.write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": "S0_READY", "evidence": str(args.out), "binding": str(args.binding_out)}, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
