#!/usr/bin/env python3
"""Run one S2 pre-solution base audit inside an immutable Docker image.

This utility is admission tooling, not treatment execution. It never applies a
solution patch. It consumes an admission-only quarantined row, resolves the
container image to a digest, executes the frozen install_config.test_cmd at the
repository base state, and records auditable evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "ndv-p1-s2-base-audit-run-v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def run(argv: list[str], *, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, capture_output=True, check=False, timeout=timeout)


def normalize_commands(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise ValueError("install_config.test_cmd must be a string or array")
    commands = [x for x in value if isinstance(x, str) and x.strip()]
    if not commands:
        raise ValueError("install_config.test_cmd must contain at least one command")
    return commands


def resolve_image_digest(image_ref: str) -> str:
    proc = run(["docker", "image", "inspect", image_ref, "--format", "{{json .RepoDigests}}"], timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(f"docker image inspect failed for {image_ref}: {proc.stderr.strip()}")
    try:
        digests = json.loads(proc.stdout.strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid docker RepoDigests JSON: {exc}") from exc
    if not isinstance(digests, list):
        raise RuntimeError("docker RepoDigests must be a list")
    candidates = sorted(x for x in digests if isinstance(x, str) and "@sha256:" in x)
    if not candidates:
        raise RuntimeError("image has no immutable RepoDigest; pull or build with digest evidence first")
    return candidates[0]


def validate_row(row: dict[str, Any], candidate: dict[str, Any]) -> tuple[list[str], str, str, list[str], str | None]:
    errors: list[str] = []
    if row.get("instance_id") != candidate.get("source_instance_id"):
        errors.append("instance_id mismatch between admission-only row and candidate")
    if row.get("repo") != candidate.get("repository"):
        errors.append("repo mismatch between admission-only row and candidate")
    if row.get("base_commit") != candidate.get("base_revision"):
        errors.append("base_commit mismatch between admission-only row and candidate")

    install = row.get("install_config")
    if not isinstance(install, dict):
        errors.append("admission-only row missing install_config")
        install = {}
    try:
        commands = normalize_commands(install.get("test_cmd"))
    except ValueError as exc:
        errors.append(str(exc))
        commands = []
    parser_name = install.get("log_parser") if isinstance(install.get("log_parser"), str) else None
    if not parser_name:
        errors.append("admission-only row missing install_config.log_parser")

    image_ref = candidate.get("image_ref")
    if not isinstance(image_ref, str) or not image_ref:
        errors.append("candidate image_ref missing")
        image_ref = ""
    repo = candidate.get("repository", "")
    workdir = "/" + repo.split("/", 1)[1] if isinstance(repo, str) and "/" in repo else ""
    if not workdir:
        errors.append("candidate repository must be owner/name")
    return errors, image_ref, workdir, commands, parser_name


def execute_base(image_digest: str, workdir: str, commands: list[str], timeout: float) -> dict[str, Any]:
    script = "\n".join([
        "set +e",
        "git reset --hard HEAD",
        "git status --porcelain=v1",
        *commands,
    ])
    argv = [
        "docker", "run", "--rm",
        "--network", "none",
        "-w", workdir,
        image_digest,
        "/bin/bash", "-lc", script,
    ]
    started = time.monotonic()
    try:
        proc = run(argv, timeout=timeout)
        timed_out = False
        returncode = proc.returncode
        stdout, stderr = proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = 124
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\ntimeout after {timeout} seconds\n"
    return {
        "argv": argv,
        "returncode": returncode,
        "timed_out": timed_out,
        "duration_seconds": time.monotonic() - started,
        "stdout": stdout,
        "stderr": stderr,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wave", type=Path, default=Path("experiments/p1/s2-candidate-wave-01.json"))
    ap.add_argument("--candidate-id", required=True)
    ap.add_argument("--admission-row", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--timeout-seconds", type=float, default=1800)
    args = ap.parse_args()

    wave = json.loads(args.wave.read_text(encoding="utf-8"))
    row = json.loads(args.admission_row.read_text(encoding="utf-8"))
    if not isinstance(row, dict):
        raise SystemExit("admission row must be a JSON object")
    candidates = [c for c in wave.get("candidates", []) if c.get("candidate_id") == args.candidate_id]
    if len(candidates) != 1:
        raise SystemExit("candidate-id must resolve to exactly one wave candidate")
    candidate = candidates[0]

    errors, image_ref, workdir, commands, parser_name = validate_row(row, candidate)
    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, indent=2))
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    try:
        image_digest = resolve_image_digest(image_ref)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        report = {
            "schema_id": SCHEMA,
            "candidate_id": args.candidate_id,
            "status": "ENVIRONMENT_BLOCKED",
            "reason": str(exc),
            "image_ref": image_ref,
            "gold_patch_applied": False,
            "test_patch_applied": False,
            "observed_at": utc_now(),
        }
        write_json(args.out / "base-audit-run.json", report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 3

    result = execute_base(image_digest, workdir, commands, args.timeout_seconds)
    stdout_path = args.out / "base.stdout.log"
    stderr_path = args.out / "base.stderr.log"
    stdout_path.write_text(result.pop("stdout"), encoding="utf-8")
    stderr_path.write_text(result.pop("stderr"), encoding="utf-8")

    admission_sha = sha256_file(args.admission_row)
    report = {
        "schema_id": SCHEMA,
        "candidate_id": args.candidate_id,
        "source_instance_id": candidate["source_instance_id"],
        "repository": candidate["repository"],
        "base_revision": candidate["base_revision"],
        "admission_row_ref": str(args.admission_row),
        "admission_row_file_sha256": admission_sha,
        "image_ref": image_ref,
        "image_digest": image_digest,
        "runtime": "docker",
        "network": "none",
        "workdir": workdir,
        "test_commands": commands,
        "test_commands_sha256": sha256_bytes(json.dumps(commands, sort_keys=True, separators=(",", ":")).encode()),
        "log_parser_name": parser_name,
        "gold_patch_applied": False,
        "test_patch_applied": False,
        "process": result,
        "evidence": {
            "stdout_ref": str(stdout_path),
            "stdout_sha256": sha256_file(stdout_path),
            "stderr_ref": str(stderr_path),
            "stderr_sha256": sha256_file(stderr_path),
        },
        "observed_at": utc_now(),
        "classification": "BASE_RUN_RECORDED",
        "note": "A nonzero test exit is not automatically an infrastructure failure; oracle interpretation is a separate audit step.",
    }
    report_path = args.out / "base-audit-run.json"
    write_json(report_path, report)
    print(json.dumps({"status": "PASS", "report": str(report_path), "report_sha256": sha256_file(report_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
