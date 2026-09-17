#!/usr/bin/env python3
"""Qualify Luna, Terra, then Sol on synthetic repos with one attempt per model.

This batch never executes a P1 task. It stops at the first non-ready synthetic
qualification and records a batch receipt. No model gets retried or substituted.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import ndv_qualify_codex_subscription_executor as qualifier

ORDER = ("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol")


def batch(codex_exe: Path, out_root: Path, program: Path, timeout: int) -> dict:
    codex_exe = codex_exe.resolve()
    out_root = out_root.resolve()
    if out_root.exists():
        raise ValueError(f"out-root exists; refusing overwrite: {out_root}")
    version_raw, _ = qualifier.require_interface(codex_exe)
    out_root.mkdir(parents=True)
    results = []
    for model in ORDER:
        model_dir = out_root / model
        result = qualifier.qualify(codex_exe, model, model_dir, program.resolve(), timeout)
        q = result["qualification"]
        results.append({
            "model": model,
            "status": q["status"],
            "candidate_id": q["candidate_id"],
            "qualification_ref": str((model_dir / "qualification.json").resolve()),
            "binding_ref": str((model_dir / "executor-binding.json").resolve()) if result["binding"] else None,
            "evidence_manifest_ref": str((model_dir / "evidence-manifest.json").resolve()) if result["manifest"] else None,
            "codex_version_raw": q["codex_version_raw"],
        })
        if q["codex_version_raw"] != version_raw:
            raise ValueError(f"Codex version drift during batch: expected {version_raw!r}, observed {q['codex_version_raw']!r}")
        if q["status"] != "S0_READY":
            receipt = {
                "schema_id": "ndv-p1-wp07-codex-batch-qualification-v1",
                "status": "QUALIFICATION_BLOCKED",
                "order": list(ORDER),
                "codex_executable": str(codex_exe),
                "codex_version_raw": version_raw,
                "results": results,
                "blocked_on_model": model,
                "retry_count_per_model": 0,
                "development_task_exposure": False,
                "treatment_execution": "NOT_EXECUTED",
                "holdout_access": "NONE",
            }
            (out_root / "batch-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return receipt
    receipt = {
        "schema_id": "ndv-p1-wp07-codex-batch-qualification-v1",
        "status": "ALL_SYNTHETIC_QUALIFICATIONS_READY",
        "order": list(ORDER),
        "codex_executable": str(codex_exe),
        "codex_version_raw": version_raw,
        "results": results,
        "blocked_on_model": None,
        "retry_count_per_model": 0,
        "development_task_exposure": False,
        "treatment_execution": "NOT_EXECUTED",
        "holdout_access": "NONE",
    }
    (out_root / "batch-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--codex-exe", required=True, type=Path)
    ap.add_argument("--out-root", required=True, type=Path)
    ap.add_argument("--program", type=Path, default=qualifier.PROGRAM)
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()
    try:
        result = batch(args.codex_exe, args.out_root, args.program, args.timeout)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status":"FAIL","reason":"CODEX_BATCH_QUALIFICATION_BLOCKED","detail":str(exc)}, indent=2))
        return 2
    print(json.dumps({"status":result["status"],"blocked_on_model":result["blocked_on_model"],"completed_models":[r["model"] for r in result["results"]]}, indent=2))
    return 0 if result["status"] == "ALL_SYNTHETIC_QUALIFICATIONS_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
