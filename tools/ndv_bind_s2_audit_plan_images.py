#!/usr/bin/env python3
"""Bind a byte-bound S2 base-audit plan to acquired immutable image digests.

No Docker container, model, treatment, or holdout operation is executed here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load(path: Path) -> Any: return json.loads(path.read_text(encoding="utf-8"))
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()
def require_file(path: Path, label: str) -> Path:
    p = path.resolve()
    if not p.is_file(): raise ValueError(f"{label} not found: {p}")
    return p

def bind(plan_path: Path, image_receipt_path: Path) -> dict[str, Any]:
    plan_path, image_receipt_path = require_file(plan_path, "audit plan"), require_file(image_receipt_path, "image acquisition receipt")
    plan, receipt = load(plan_path), load(image_receipt_path)
    if plan.get("schema_id") != "ndv-p1-s2-base-audit-plan-v2" or plan.get("status") != "AUDIT_PLAN_READY": raise ValueError("audit plan v2 required")
    if receipt.get("schema_id") != "ndv-p1-s2-image-acquisition-receipt-v1" or receipt.get("status") != "IMAGES_ACQUIRED_AND_PINNED": raise ValueError("verified image acquisition receipt required")
    if receipt.get("container_execution") is not False or receipt.get("model_execution") != "NONE" or receipt.get("treatment_execution") != "NOT_EXECUTED" or receipt.get("holdout_access") != "NONE": raise ValueError("image receipt contamination detected")
    wave = require_file(Path(plan["wave_ref"]), "wave")
    if receipt.get("wave_id") != plan.get("wave_id") or receipt.get("wave_file_sha256") != plan.get("wave_file_sha256") or sha256_file(wave) != plan.get("wave_file_sha256"): raise ValueError("image receipt/audit plan wave binding mismatch")
    images = receipt.get("images")
    if not isinstance(images, list) or len(images) != receipt.get("image_count"): raise ValueError("image receipt inventory invalid")
    by_ref = {x.get("image_ref"): x.get("repo_digest") for x in images if isinstance(x, dict)}
    entries = plan.get("entries")
    if not isinstance(entries, list) or len(entries) != plan.get("candidate_count"): raise ValueError("audit plan entries invalid")
    if set(by_ref) != {e.get("image_ref") for e in entries}: raise ValueError("image receipt does not exactly cover audit plan image refs")
    bound = []
    for entry in entries:
        digest = by_ref[entry["image_ref"]]
        if not isinstance(digest, str) or "@sha256:" not in digest: raise ValueError(f"{entry['candidate_id']}: invalid immutable image digest")
        argv = list(entry.get("argv", []))
        if "--image-digest" in argv: raise ValueError(f"{entry['candidate_id']}: image digest already present in unbound plan")
        out_idx = argv.index("--out") if "--out" in argv else len(argv)
        argv[out_idx:out_idx] = ["--image-digest", digest]
        updated = dict(entry); updated["image_digest"] = digest; updated["image_digest_state"] = "PINNED_FROM_ACQUISITION_RECEIPT"; updated["argv"] = argv; bound.append(updated)
    return {
        "schema_id": "ndv-p1-s2-base-audit-execution-plan-v1", "status": "AUDIT_EXECUTION_PLAN_READY",
        "wave_id": plan.get("wave_id"), "wave_ref": plan.get("wave_ref"), "wave_file_sha256": plan.get("wave_file_sha256"),
        "base_audit_plan_ref": str(plan_path), "base_audit_plan_file_sha256": sha256_file(plan_path),
        "image_acquisition_receipt_ref": str(image_receipt_path), "image_acquisition_receipt_file_sha256": sha256_file(image_receipt_path),
        "runner_ref": plan.get("runner_ref"), "runner_file_sha256": plan.get("runner_file_sha256"),
        "candidate_count": len(bound), "entries": bound,
        "docker_execution": False, "model_execution": "NONE", "treatment_execution": "NOT_EXECUTED", "holdout_access": "NONE",
        "prepared_at": datetime.now(timezone.utc).isoformat(),
    }
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument("--plan", required=True, type=Path); ap.add_argument("--image-receipt", required=True, type=Path); ap.add_argument("--out", type=Path, default=Path(".ndv-corpus/s2-w01/base-audit-execution-plan.json")); args = ap.parse_args()
    try: result = bind(args.plan, args.image_receipt)
    except (OSError, ValueError, json.JSONDecodeError) as exc: print(json.dumps({"status":"FAIL","reason":"IMAGE_BINDING_BLOCKED","detail":str(exc)}, indent=2)); return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists(): raise SystemExit(f"refusing overwrite: {args.out}")
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n", encoding="utf-8"); print(json.dumps({"status":result["status"],"out":str(args.out),"candidate_count":result["candidate_count"]}, indent=2)); return 0
if __name__ == "__main__": raise SystemExit(main())
