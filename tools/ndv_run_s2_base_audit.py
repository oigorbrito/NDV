#!/usr/bin/env python3
"""Run one S2 pre-solution base audit inside an immutable Docker image.

Admission tooling only: no model call, gold patch, test patch, or holdout access.
The runner cryptographically rebinds the quarantined raw row, verifies exact
repository HEAD/cleanliness inside the container, executes every frozen test
command with explicit per-command return-code markers, and persists evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "ndv-p1-s2-base-audit-run-v2"
CMD_RC_RE = re.compile(r"^__NDV_CMD_(\d+)_RC__=(\d+)$", re.MULTILINE)
HEAD_RE = re.compile(r"^__NDV_HEAD__=([0-9a-f]{40})$", re.MULTILINE)
CLEAN_RE = re.compile(r"^__NDV_CLEAN__=(YES|NO)$", re.MULTILINE)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def normalize_image_repository(image_ref: str) -> str:
    ref = image_ref.strip()
    if "@" in ref:
        ref = ref.split("@", 1)[0]
    slash = ref.rfind("/")
    colon = ref.rfind(":")
    if colon > slash:
        ref = ref[:colon]
    if ref.startswith("docker.io/"):
        ref = ref[len("docker.io/"):]
    return ref


def repo_digest_matches_image_ref(repo_digest: str, image_ref: str) -> bool:
    if "@sha256:" not in repo_digest:
        return False
    digest_repo = repo_digest.split("@", 1)[0]
    return normalize_image_repository(digest_repo) == normalize_image_repository(image_ref)


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
    candidates = sorted(
        x for x in digests
        if isinstance(x, str) and repo_digest_matches_image_ref(x, image_ref)
    )
    if not candidates:
        raise RuntimeError(f"image has no immutable RepoDigest matching frozen repository {normalize_image_repository(image_ref)!r}")
    if len(candidates) != 1:
        raise RuntimeError(f"image has multiple RepoDigests matching frozen repository: {candidates!r}")
    return candidates[0]


def unwrap_admission_artifact(artifact: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    if artifact.get("schema_id") != "ndv-p1-s2-admission-only-row-v1":
        raise ValueError("unexpected admission-only schema")
    if artifact.get("candidate_id") != candidate.get("candidate_id"):
        raise ValueError("candidate_id mismatch between admission artifact and wave")
    row = artifact.get("full_row")
    source = artifact.get("source")
    if not isinstance(row, dict) or not isinstance(source, dict):
        raise ValueError("admission artifact requires full_row and source")
    expected_raw_sha = source.get("ndv_canonical_row_sha256")
    actual_raw_sha = sha256_bytes(canonical_bytes(row))
    if expected_raw_sha != actual_raw_sha:
        raise ValueError("admission full_row hash mismatch")
    if source.get("source_instance_id") != candidate.get("source_instance_id"):
        raise ValueError("source_instance_id mismatch in admission binding")
    if source.get("source_row_index") != candidate.get("source_row_index"):
        raise ValueError("source_row_index mismatch in admission binding")
    return row


def validate_row(row: dict[str, Any], candidate: dict[str, Any]) -> tuple[list[str], str, str, list[str], str | None]:
    errors: list[str] = []
    if row.get("instance_id") != candidate.get("source_instance_id"):
        errors.append("instance_id mismatch")
    if row.get("repo") != candidate.get("repository"):
        errors.append("repo mismatch")
    if row.get("base_commit") != candidate.get("base_revision"):
        errors.append("base_commit mismatch")

    install = row.get("install_config")
    if not isinstance(install, dict):
        errors.append("full row missing install_config")
        install = {}
    try:
        commands = normalize_commands(install.get("test_cmd"))
    except ValueError as exc:
        errors.append(str(exc))
        commands = []
    parser_name = install.get("log_parser") if isinstance(install.get("log_parser"), str) else None
    if not parser_name:
        errors.append("full row missing install_config.log_parser")

    image_ref = candidate.get("image_ref")
    if not isinstance(image_ref, str) or not image_ref:
        errors.append("candidate image_ref missing")
        image_ref = ""
    repo = candidate.get("repository", "")
    workdir = "/" + repo.split("/", 1)[1] if isinstance(repo, str) and "/" in repo else ""
    if not workdir:
        errors.append("candidate repository must be owner/name")
    return errors, image_ref, workdir, commands, parser_name


def build_script(base_revision: str, commands: list[str]) -> str:
    lines = [
        "set +e",
        "observed_head=$(git rev-parse HEAD 2>/dev/null)",
        'printf "__NDV_HEAD__=%s\\n" "$observed_head"',
        f"if [ \"$observed_head\" != {shlex.quote(base_revision)} ]; then exit 90; fi",
        "if [ -z \"$(git status --porcelain=v1)\" ]; then echo __NDV_CLEAN__=YES; else echo __NDV_CLEAN__=NO; exit 91; fi",
        "overall=0",
    ]
    for idx, command in enumerate(commands, 1):
        lines.extend([
            f"eval {shlex.quote(command)}",
            "rc=$?",
            f'printf "__NDV_CMD_{idx}_RC__=%s\\n" "$rc"',
            'if [ "$rc" -ne 0 ]; then overall=1; fi',
        ])
    lines.append('exit "$overall"')
    return "\n".join(lines)


def parse_execution_markers(stdout: str, expected_command_count: int) -> dict[str, Any]:
    head = HEAD_RE.search(stdout)
    clean = CLEAN_RE.search(stdout)
    observed = {int(i): int(rc) for i, rc in CMD_RC_RE.findall(stdout)}
    return {
        "observed_head": head.group(1) if head else None,
        "clean_before_tests": clean.group(1) == "YES" if clean else None,
        "command_returncodes": [observed.get(i) for i in range(1, expected_command_count + 1)],
        "all_command_markers_present": set(observed) == set(range(1, expected_command_count + 1)),
    }


def execute_base(image_digest: str, workdir: str, base_revision: str, commands: list[str], timeout: float) -> dict[str, Any]:
    script = build_script(base_revision, commands)
    argv = ["docker", "run", "--rm", "--network", "none", "-w", workdir, image_digest, "/bin/bash", "-lc", script]
    started = time.monotonic()
    try:
        proc = run(argv, timeout=timeout)
        timed_out, returncode, stdout, stderr = False, proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out, returncode = True, 124
        stdout, stderr = exc.stdout or "", (exc.stderr or "") + f"\ntimeout after {timeout} seconds\n"
    markers = parse_execution_markers(stdout, len(commands))
    return {"argv": argv, "script_sha256": sha256_bytes(script.encode()), "returncode": returncode, "timed_out": timed_out, "duration_seconds": time.monotonic() - started, "markers": markers, "stdout": stdout, "stderr": stderr}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wave", type=Path, default=Path("experiments/p1/s2-candidate-wave-01.json"))
    ap.add_argument("--candidate-id", required=True)
    ap.add_argument("--admission-row", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--timeout-seconds", type=float, default=1800)
    args = ap.parse_args()

    wave = json.loads(args.wave.read_text(encoding="utf-8"))
    artifact = json.loads(args.admission_row.read_text(encoding="utf-8"))
    candidates = [c for c in wave.get("candidates", []) if c.get("candidate_id") == args.candidate_id]
    if len(candidates) != 1:
        raise SystemExit("candidate-id must resolve to exactly one wave candidate")
    candidate = candidates[0]
    try:
        row = unwrap_admission_artifact(artifact, candidate)
    except ValueError as exc:
        print(json.dumps({"status": "FAIL", "errors": [str(exc)]}, indent=2))
        return 2

    errors, image_ref, workdir, commands, parser_name = validate_row(row, candidate)
    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, indent=2))
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    try:
        image_digest = resolve_image_digest(image_ref)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        report = {"schema_id": SCHEMA, "candidate_id": args.candidate_id, "status": "ENVIRONMENT_BLOCKED", "reason": str(exc), "image_ref": image_ref, "gold_patch_applied": False, "test_patch_applied": False, "observed_at": utc_now()}
        write_json(args.out / "base-audit-run.json", report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 3

    result = execute_base(image_digest, workdir, candidate["base_revision"], commands, args.timeout_seconds)
    stdout_path, stderr_path = args.out / "base.stdout.log", args.out / "base.stderr.log"
    stdout_path.write_text(result.pop("stdout"), encoding="utf-8")
    stderr_path.write_text(result.pop("stderr"), encoding="utf-8")

    markers = result["markers"]
    harness_integrity = (
        markers["observed_head"] == candidate["base_revision"]
        and markers["clean_before_tests"] is True
        and markers["all_command_markers_present"]
    )
    report = {
        "schema_id": SCHEMA, "candidate_id": args.candidate_id, "source_instance_id": candidate["source_instance_id"],
        "repository": candidate["repository"], "base_revision": candidate["base_revision"],
        "admission_row_ref": str(args.admission_row), "admission_row_file_sha256": sha256_file(args.admission_row),
        "admission_full_row_sha256": sha256_bytes(canonical_bytes(row)), "image_ref": image_ref, "image_digest": image_digest,
        "runtime": "docker", "network": "none", "workdir": workdir, "test_commands": commands,
        "test_commands_sha256": sha256_bytes(canonical_bytes(commands)), "log_parser_name": parser_name,
        "gold_patch_applied": False, "test_patch_applied": False, "process": result,
        "harness_integrity": "PASS" if harness_integrity else "FAIL",
        "evidence": {"stdout_ref": str(stdout_path), "stdout_sha256": sha256_file(stdout_path), "stderr_ref": str(stderr_path), "stderr_sha256": sha256_file(stderr_path)},
        "observed_at": utc_now(), "classification": "BASE_RUN_RECORDED" if harness_integrity else "HARNESS_INVALID",
        "note": "Test failures are interpreted separately; missing HEAD/clean/command markers invalidate the harness run.",
        "treatment_execution": "NOT_EXECUTED", "holdout_access": "NONE",
    }
    report_path = args.out / "base-audit-run.json"
    write_json(report_path, report)
    print(json.dumps({"status": "PASS" if harness_integrity else "FAIL", "report": str(report_path), "report_sha256": sha256_file(report_path)}, indent=2))
    return 0 if harness_integrity else 2


if __name__ == "__main__":
    raise SystemExit(main())
