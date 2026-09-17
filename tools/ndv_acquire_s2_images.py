#!/usr/bin/env python3
"""Acquire Wave-01 Docker images and freeze immutable RepoDigests.

Host network may be used only for docker pull. No container is executed, no model
or treatment is run, and holdout access is forbidden. The receipt binds the exact
wave bytes to one immutable RepoDigest per frozen image_ref.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(argv: list[str], timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, capture_output=True, check=False, timeout=timeout)


def repository_of(image_ref: str) -> str:
    return image_ref.rsplit(":", 1)[0] if ":" in image_ref.rsplit("/", 1)[-1] else image_ref


def resolve_digest(image_ref: str) -> str:
    proc = run(["docker", "image", "inspect", image_ref, "--format", "{{json .RepoDigests}}"], 60)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "docker image inspect failed")
    digests = json.loads(proc.stdout.strip())
    repo = repository_of(image_ref)
    matches = sorted(x for x in digests if isinstance(x, str) and x.startswith(repo + "@sha256:"))
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one RepoDigest for {repo}, observed {matches}")
    return matches[0]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wave", type=Path, default=Path("experiments/p1/s2-candidate-wave-01.json"))
    ap.add_argument("--out", type=Path, default=Path(".ndv-corpus/s2-w01/image-acquisition-receipt.json"))
    args = ap.parse_args()
    wave_path = args.wave.resolve()
    wave = load(wave_path)
    if wave.get("schema_id") != "ndv-p1-s2-candidate-wave-v1":
        raise SystemExit("IMAGE_ACQUISITION_BLOCKED: unexpected wave schema")
    if wave.get("wave_summary", {}).get("treatment_execution") != "NOT_EXECUTED" or wave.get("wave_summary", {}).get("holdout_access") != "NONE":
        raise SystemExit("IMAGE_ACQUISITION_BLOCKED: contaminated wave")
    candidates = wave.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise SystemExit("IMAGE_ACQUISITION_BLOCKED: no candidates")

    refs: list[str] = []
    for c in candidates:
        ref = c.get("image_ref") if isinstance(c, dict) else None
        if not isinstance(ref, str) or not ref:
            raise SystemExit("IMAGE_ACQUISITION_BLOCKED: candidate missing image_ref")
        refs.append(ref)
    if len(refs) != len(set(refs)):
        raise SystemExit("IMAGE_ACQUISITION_BLOCKED: duplicate image_ref")

    images = []
    for ref in refs:
        pull = run(["docker", "pull", ref])
        if pull.returncode != 0:
            raise SystemExit(f"IMAGE_ACQUISITION_BLOCKED: docker pull failed for {ref}: {pull.stderr.strip()}")
        try:
            digest = resolve_digest(ref)
        except Exception as exc:
            raise SystemExit(f"IMAGE_ACQUISITION_BLOCKED: {ref}: {exc}") from exc
        images.append({"image_ref": ref, "repo_digest": digest})

    receipt = {
        "schema_id": "ndv-p1-s2-image-acquisition-receipt-v1",
        "status": "IMAGES_ACQUIRED_AND_PINNED",
        "wave_id": wave.get("wave_id"),
        "wave_ref": str(wave_path),
        "wave_file_sha256": sha256_file(wave_path),
        "images": images,
        "image_count": len(images),
        "host_network_used_for_pull": True,
        "container_execution": False,
        "model_execution": "NONE",
        "treatment_execution": "NOT_EXECUTED",
        "holdout_access": "NONE",
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists():
        raise SystemExit(f"refusing overwrite: {args.out}")
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "out": str(args.out), "image_count": len(images)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
