#!/usr/bin/env python3
"""Materialize a Codex workspace from the immutable WP-06 audited Docker image.

No task prompt or model is invoked. The tool revalidates the frozen run-spec,
admission record, base-audit evidence and immutable image digest, copies the
exact audited repository checkout from the container image, and proves HEAD +
cleanliness before emitting a workspace manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ndv_compile_wp07_codex_prompt import verify_admission, sha_value


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def run(argv: list[str], cwd: Path | None = None, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout)


def validate_inputs(run_spec_path: Path, artifact_root: Path) -> dict[str, Any]:
    spec = load(run_spec_path)
    if spec.get("schema_id") != "ndv-p1-s2-run-spec-v1" or spec.get("execution_status") != "NOT_EXECUTED":
        raise ValueError("NOT_EXECUTED P1-S2 run-spec required")
    if spec.get("holdout") != "DEVELOPMENT_ONLY":
        raise ValueError("development-only run-spec required")
    task = spec.get("task") or {}
    admission_path = resolve(artifact_root, task.get("admission_record_ref"), "admission_record_ref")
    if sha_file(admission_path) != task.get("admission_record_file_sha256"):
        raise ValueError("admission record file hash mismatch")
    admission = verify_admission(admission_path)
    if admission.get("record_sha256") != task.get("admission_record_sha256"):
        raise ValueError("admission semantic hash mismatch")
    if admission.get("candidate_id") != task.get("task_id") or admission.get("base_revision") != task.get("base_sha"):
        raise ValueError("run-spec/admission identity mismatch")

    audit = admission.get("audit") or {}
    base_run_path = resolve(artifact_root, audit.get("base_run_ref"), "base_run_ref")
    if sha_file(base_run_path) != audit.get("base_run_sha256"):
        raise ValueError("base-run file hash mismatch")
    base = load(base_run_path)
    if base.get("schema_id") != "ndv-p1-s2-base-audit-run-v2" or base.get("harness_integrity") != "PASS":
        raise ValueError("harness-valid base-audit run required")
    for key, expected in (
        ("candidate_id", admission.get("candidate_id")),
        ("repository", admission.get("repository")),
        ("base_revision", admission.get("base_revision")),
    ):
        if base.get(key) != expected:
            raise ValueError(f"base-run {key} mismatch")
    image_digest = base.get("image_digest")
    if not isinstance(image_digest, str) or "@sha256:" not in image_digest:
        raise ValueError("base-run immutable repository image digest required")
    if "sha256:" + image_digest.split("@sha256:", 1)[1] != audit.get("image_digest"):
        raise ValueError("base-run/admission image digest mismatch")
    workdir = base.get("workdir")
    expected_workdir = "/" + admission["repository"].split("/", 1)[1]
    if workdir != expected_workdir:
        raise ValueError("base-run workdir mismatch")
    if base.get("network") != "none" or base.get("gold_patch_applied") is not False or base.get("test_patch_applied") is not False:
        raise ValueError("base-run contamination detected")
    return {"spec":spec,"admission":admission,"admission_path":admission_path,"base":base,"base_run_path":base_run_path,"image_digest":image_digest,"workdir":workdir}


def materialize(run_spec_path: Path, artifact_root: Path, out_dir: Path) -> dict[str, Any]:
    bound = validate_inputs(run_spec_path.resolve(), artifact_root.resolve())
    if out_dir.exists():
        raise ValueError(f"out-dir exists; refusing overwrite: {out_dir}")
    out_dir.mkdir(parents=True)
    workspace = out_dir / "workspace"
    workspace.mkdir()

    inspect = run(["docker","image","inspect",bound["image_digest"],"--format","{{.Id}}"], timeout=30)
    if inspect.returncode != 0 or not inspect.stdout.strip():
        raise ValueError(f"immutable image unavailable locally: {bound['image_digest']}")
    create = run(["docker","create","--network","none","--entrypoint","/bin/true",bound["image_digest"]], timeout=60)
    if create.returncode != 0 or not create.stdout.strip():
        raise ValueError(f"docker create failed: {(create.stderr or create.stdout)[-500:]}")
    container_id = create.stdout.strip().splitlines()[-1]
    try:
        cp = run(["docker","cp",f"{container_id}:{bound['workdir']}/.",str(workspace)], timeout=300)
        if cp.returncode != 0:
            raise ValueError(f"docker cp failed: {(cp.stderr or cp.stdout)[-500:]}")
    finally:
        run(["docker","rm","-f",container_id], timeout=30)

    git_dir = workspace / ".git"
    if not git_dir.exists():
        raise ValueError("materialized workspace is not a git checkout")
    head = run(["git","rev-parse","HEAD"], cwd=workspace, timeout=30)
    status = run(["git","status","--porcelain=v1"], cwd=workspace, timeout=30)
    if head.returncode != 0 or status.returncode != 0:
        raise ValueError("git integrity check failed in materialized workspace")
    observed_head = head.stdout.strip()
    if observed_head != bound["admission"]["base_revision"]:
        raise ValueError(f"materialized HEAD mismatch: {observed_head}")
    if status.stdout.strip():
        raise ValueError("materialized workspace is not clean")

    manifest = {
        "schema_id":"ndv-p1-wp07-codex-workspace-v1",
        "status":"CODEX_WORKSPACE_READY_NOT_EXPOSED",
        "run_id":bound["spec"].get("run_id"),
        "task_id":bound["admission"].get("candidate_id"),
        "repository":bound["admission"].get("repository"),
        "base_revision":bound["admission"].get("base_revision"),
        "workspace_ref":str(workspace.resolve()),
        "observed_head":observed_head,
        "clean":True,
        "source_image_digest":bound["image_digest"],
        "source_base_run_ref":str(bound["base_run_path"]),
        "source_base_run_file_sha256":sha_file(bound["base_run_path"]),
        "admission_record_ref":str(bound["admission_path"]),
        "admission_record_file_sha256":sha_file(bound["admission_path"]),
        "admission_record_sha256":bound["admission"].get("record_sha256"),
        "run_spec_ref":str(run_spec_path.resolve()),
        "run_spec_file_sha256":sha_file(run_spec_path.resolve()),
        "task_prompt_exposed":False,
        "treatment_execution":"NOT_EXECUTED",
        "holdout_access":"NONE",
    }
    manifest_path = out_dir / "workspace-manifest.json"
    manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return manifest


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-spec",required=True,type=Path)
    ap.add_argument("--artifact-root",type=Path,default=Path("."))
    ap.add_argument("--out-dir",required=True,type=Path)
    args=ap.parse_args()
    try:
        r=materialize(args.run_spec,args.artifact_root,args.out_dir.resolve())
    except (OSError,ValueError,json.JSONDecodeError,subprocess.SubprocessError) as exc:
        if args.out_dir.exists():
            shutil.rmtree(args.out_dir,ignore_errors=True)
        print(json.dumps({"status":"FAIL","reason":"CODEX_WORKSPACE_MATERIALIZATION_BLOCKED","detail":str(exc)},indent=2))
        return 2
    print(json.dumps({k:r[k] for k in ("status","run_id","task_id","repository","base_revision","source_image_digest")},indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
