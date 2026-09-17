#!/usr/bin/env python3
"""Qualify Luna, Terra, then Sol on synthetic repos with one attempt per model.

This batch never executes a P1 task. It stops at the first non-ready synthetic
qualification and records a batch receipt. No model gets retried or substituted.
The Codex executable may be supplied explicitly or resolved from a frozen
subscription-surface probe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import ndv_qualify_codex_subscription_executor as qualifier

ORDER = ("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol")
PROBE_SCHEMA = "ndv-p1-wp07-subscription-surface-probe-v1"


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_codex_exe(*, codex_exe: Path | None, probe: Path | None, program: Path) -> tuple[Path, dict[str, Any] | None]:
    if (codex_exe is None) == (probe is None):
        raise ValueError("provide exactly one of --codex-exe or --probe")
    if codex_exe is not None:
        exe = codex_exe.expanduser().resolve()
        if not exe.is_file():
            raise ValueError(f"Codex executable not found: {exe}")
        return exe, None

    probe_path = probe.expanduser().resolve()
    if not probe_path.is_file():
        raise ValueError(f"surface probe not found: {probe_path}")
    payload = load(probe_path)
    if payload.get("schema_id") != PROBE_SCHEMA or payload.get("status") != "DISCOVERY_COMPLETE":
        raise ValueError("valid WP-07 subscription surface probe required")
    if payload.get("task_exposure") is not False or payload.get("treatment_execution") != "NOT_EXECUTED" or payload.get("holdout_access") != "NONE":
        raise ValueError("surface probe contamination")
    program_path = program.expanduser().resolve()
    if not program_path.is_file():
        raise ValueError(f"qualification program not found: {program_path}")
    if payload.get("program_file_sha256") != sha_file(program_path):
        raise ValueError("surface probe qualification-program hash mismatch")
    codex = ((payload.get("surfaces") or {}).get("codex") or {})
    if codex.get("status") != "DISCOVERED":
        raise ValueError(f"Codex surface is not DISCOVERED in probe: {codex.get('status')!r}")
    if codex.get("noninteractive_exec_discovered") is not True or codex.get("model_flag_discovered") is not True or codex.get("sandbox_flag_discovered") is not True:
        raise ValueError("Codex probe lacks required noninteractive/model/sandbox interface")
    raw = codex.get("executable_path")
    if not isinstance(raw, str) or not raw:
        raise ValueError("Codex executable_path missing from probe")
    exe = Path(raw).expanduser().resolve()
    if not exe.is_file():
        raise ValueError(f"Codex executable recorded by probe is no longer present: {exe}")
    return exe, {"probe_ref": str(probe_path), "probe_file_sha256": sha_file(probe_path)}


def batch(codex_exe: Path, out_root: Path, program: Path, timeout: int, probe_binding: dict[str, Any] | None = None) -> dict:
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
                "probe_binding": probe_binding,
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
        "probe_binding": probe_binding,
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
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument("--codex-exe", type=Path)
    source.add_argument("--probe", type=Path)
    ap.add_argument("--out-root", required=True, type=Path)
    ap.add_argument("--program", type=Path, default=qualifier.PROGRAM)
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()
    try:
        exe, probe_binding = resolve_codex_exe(codex_exe=args.codex_exe, probe=args.probe, program=args.program)
        result = batch(exe, args.out_root, args.program, args.timeout, probe_binding)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status":"FAIL","reason":"CODEX_BATCH_QUALIFICATION_BLOCKED","detail":str(exc)}, indent=2))
        return 2
    print(json.dumps({"status":result["status"],"blocked_on_model":result["blocked_on_model"],"completed_models":[r["model"] for r in result["results"]],"codex_executable":result["codex_executable"]}, indent=2))
    return 0 if result["status"] == "ALL_SYNTHETIC_QUALIFICATIONS_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
