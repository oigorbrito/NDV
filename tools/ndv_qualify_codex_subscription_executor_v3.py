#!/usr/bin/env python3
"""Prospective Codex subscription qualifier v3 with an explicit workspace writable root.

V3 preserves V1/V2 evidence, keeps workspace-write, adds only the exact synthetic
workspace as --add-dir, and classifies sandbox/policy blocks as environment
failures rather than model mutation failures. No P1 task is exposed.
"""
from __future__ import annotations

import argparse, hashlib, json, os, subprocess, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ndv_qualify_codex_subscription_executor as v1
import ndv_qualify_codex_subscription_executor_v2 as v2
from ndv_wp07_codex_bundle import seal_bundle

AMENDMENT = Path("experiments/p1/wp07-codex-qualification-amendment-v3.json")


def sha_file(path: Path) -> str:
    return v2.sha_file(path)


def load_amendment(path: Path) -> dict[str, Any]:
    x = json.loads(path.resolve().read_text(encoding="utf-8"))
    if x.get("schema_id") != "ndv-p1-wp07-codex-qualification-amendment-v3" or x.get("status") != "PROSPECTIVE_AMENDMENT_FROZEN_NOT_EXECUTED":
        raise ValueError("qualification amendment v3 invalid")
    if x.get("historical_v1_v2_evidence_reinterpretation") != "FORBIDDEN":
        raise ValueError("historical evidence reinterpretation forbidden")
    if x.get("development_task_exposure") is not False or x.get("holdout_access") != "NONE" or x.get("treatment_execution") != "NOT_EXECUTED":
        raise ValueError("qualification amendment v3 contaminated")
    return x


def invocation_v3(codex: Path, model: str, task: str, surface: dict[str, Any], repo: Path) -> list[str]:
    argv = v1.invocation(codex, model, task, surface)
    if not argv or argv[-1] != task:
        raise ValueError("frozen task must be final positional prompt")
    return argv[:-1] + ["--add-dir", str(repo.resolve()), task]


def environment_blocked(raw: str, amendment: dict[str, Any]) -> bool:
    low = raw.lower()
    return any(str(marker).lower() in low for marker in amendment.get("environment_failure_markers", []))


def qualify(codex: Path, model: str, out_dir: Path, program_path: Path, timeout: int,
            surface_path: Path = v1.SURFACE, amendment_path: Path = AMENDMENT) -> dict[str, Any]:
    if model not in v1.ALLOWED:
        raise ValueError(f"model not preregistered: {model}")
    out_dir = out_dir.resolve()
    if out_dir.exists():
        raise ValueError(f"out-dir exists; refusing overwrite: {out_dir}")
    program_path, surface_path, amendment_path = program_path.resolve(), surface_path.resolve(), amendment_path.resolve()
    v1.load_program(program_path)
    surface = v1.load_surface(surface_path)
    amendment = load_amendment(amendment_path)
    version_raw, _ = v1.require_interface(codex.resolve(), surface)
    candidate_id, roles = v1.ALLOWED[model]

    out_dir.mkdir(parents=True)
    evidence = out_dir / "evidence"; evidence.mkdir()
    repo = out_dir / "synthetic-workspace"; repo.mkdir()
    v1.init_repo(repo)

    env = os.environ.copy()
    for key in surface["environment_variables_removed"]:
        env.pop(key, None)
    argv = invocation_v3(codex.resolve(), model, v1.TASK, surface, repo)
    identity = v2.identity_assurance(version_raw, argv, model, {
        "identity_policy": {"required_cli_version_exact": amendment["identity_policy"]["required_cli_version_exact"]},
        "upstream_provenance": amendment["upstream_provenance"],
    })

    started = datetime.now(timezone.utc).isoformat(); t0 = time.monotonic()
    try:
        proc = v1.run(argv, repo, env, timeout); timed_out = False
    except subprocess.TimeoutExpired as exc:
        proc = subprocess.CompletedProcess(exc.cmd, 124, stdout=exc.stdout or "", stderr=exc.stderr or ""); timed_out = True
    wall = time.monotonic() - t0
    raw = v1.text(proc)
    (evidence / "executor.log").write_text(raw, encoding="utf-8")
    exact, status, diff = v1.validate_diff(repo)
    (evidence / "candidate.diff").write_bytes(diff)
    (evidence / "git-status.txt").write_text(status + "\n", encoding="utf-8")
    env_block = environment_blocked(raw, amendment)

    if timed_out: state = "S0_RESOURCE_LIMIT"
    elif proc.returncode != 0: state = "S0_EXECUTOR_BLOCKED"
    elif identity["status"] != "CLI_PINNED_SOURCE_VERIFIED": state = "S0_IDENTITY_UNRESOLVED"
    elif not exact and env_block: state = "S0_ENVIRONMENT_BLOCKED"
    elif not exact: state = "S0_MUTATION_FAILED"
    else: state = "S0_READY"

    q = {
        "schema_id":"ndv-p1-wp07-codex-subscription-qualification-v3","status":state,"qualification_cohort":"V3",
        "candidate_id":candidate_id,"requested_model":model,"identity_assurance":identity,"candidate_roles":roles,
        "surface_class":"SUBSCRIPTION_EXECUTOR_PINNED","codex_executable":str(codex.resolve()),"codex_version_raw":version_raw,
        "auth_path":"CHATGPT_SUBSCRIPTION_FORCED_BY_REMOVING_API_KEY_ENV","api_key_env_removed":True,
        "execution_surface_ref":str(surface_path),"execution_surface_file_sha256":sha_file(surface_path),
        "amendment_ref":str(amendment_path),"amendment_file_sha256":sha_file(amendment_path),
        "synthetic_workspace_ref":str(repo),"explicit_writable_root":str(repo),"writable_root_delivery":"--add-dir",
        "task":"SYNTHETIC_MUTATION_ONLY","task_exposure":False,"development_task_exposure":False,"holdout_access":"NONE",
        "retry_count":0,"escalation_count":0,"executor":{"returncode":proc.returncode,"timed_out":timed_out,"wall_seconds":wall},
        "environment_block_marker_observed":env_block,
        "mutation":{"exact":exact,"candidate_diff_sha256":hashlib.sha256(diff).hexdigest(),"candidate_diff_bytes":len(diff)},
        "program_ref":str(program_path),"program_file_sha256":sha_file(program_path),"started_at":started,
        "completed_at":datetime.now(timezone.utc).isoformat(),"treatment_execution":"NOT_EXECUTED"
    }
    qpath = out_dir / "qualification.json"
    qpath.write_text(json.dumps(q, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    binding = manifest = None
    if state == "S0_READY":
        seed = json.dumps({"candidate":candidate_id,"model":model,"codex":version_raw,"qualification":sha_file(qpath),"amendment":sha_file(amendment_path),"execution_surface":sha_file(surface_path)}, sort_keys=True).encode()
        binding = {
            "schema_id":"ndv-p1-wp07-executor-binding-v3","status":"QUALIFIED","binding_id":"WP07-CODEX-V3-"+hashlib.sha256(seed).hexdigest()[:16],
            "candidate_id":candidate_id,"provider":"OpenAI","surface_class":"SUBSCRIPTION_EXECUTOR_PINNED",
            "exact_executor_identity":f"codex({version_raw})+{model}","identity_assurance":"CLI_PINNED_SOURCE_VERIFIED",
            "runtime_model_echo":"UNAVAILABLE_BY_VERSION_MATCHED_UPSTREAM_SCHEMA",
            "scaffold":{"name":"codex","version":version_raw,"executable_path":str(codex.resolve()),"invocation_mode":"exec noninteractive workspace-write explicit-root v3"},
            "model":{"identity":model,"selection":"EXPLICIT_PINNED"},"auth_path":"CHATGPT_SUBSCRIPTION",
            "api_key_routing_forbidden":True,"dynamic_routing":False,"implicit_fallback":False,"retry_limit":0,"escalation_limit":0,
            "qualification_ref":"qualification.json","qualification_file_sha256":sha_file(qpath),"program_ref":str(program_path),"program_file_sha256":sha_file(program_path),
            "execution_surface_ref":str(surface_path),"execution_surface_file_sha256":sha_file(surface_path),"amendment_ref":str(amendment_path),"amendment_file_sha256":sha_file(amendment_path),
            "writable_root_policy":"EXACT_WORKSPACE_VIA_ADD_DIR","candidate_roles":roles,"treatment_execution":"NOT_EXECUTED","holdout_access":"NONE"
        }
        (out_dir/"executor-binding.json").write_text(json.dumps(binding, indent=2, sort_keys=True)+"\n", encoding="utf-8")
        manifest = seal_bundle(out_dir)
    return {"qualification":q,"binding":binding,"manifest":manifest}


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--codex-exe",required=True,type=Path); ap.add_argument("--model",required=True,choices=sorted(v1.ALLOWED)); ap.add_argument("--out-dir",required=True,type=Path)
    ap.add_argument("--program",type=Path,default=v1.PROGRAM); ap.add_argument("--execution-surface",type=Path,default=v1.SURFACE); ap.add_argument("--amendment",type=Path,default=AMENDMENT); ap.add_argument("--timeout",type=int,default=600)
    args=ap.parse_args()
    try: r=qualify(args.codex_exe,args.model,args.out_dir,args.program,args.timeout,args.execution_surface,args.amendment)
    except (OSError,ValueError,json.JSONDecodeError) as exc:
        print(json.dumps({"status":"FAIL","reason":"CODEX_SUBSCRIPTION_QUALIFICATION_V3_BLOCKED","detail":str(exc)},indent=2)); return 2
    q=r["qualification"]
    print(json.dumps({"status":q["status"],"candidate_id":q["candidate_id"],"model":q["requested_model"],"identity_assurance":q["identity_assurance"]["status"],"environment_block_marker_observed":q["environment_block_marker_observed"],"binding":str(args.out_dir/"executor-binding.json") if r["binding"] else None},indent=2))
    return 0 if q["status"]=="S0_READY" else 2

if __name__=="__main__": raise SystemExit(main())
