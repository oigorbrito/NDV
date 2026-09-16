#!/usr/bin/env python3
"""Qualify one already-installed Ollama model for NDV WP-04 binding.

Fail-closed rules:
- never downloads a model;
- never selects a model implicitly;
- requires exact installed model name and digest from a prior local-surface probe;
- performs one synthetic non-P1 qualification request only;
- records raw response, usage/timing when exposed, and candidate text;
- emits a WP-04 binding only when identity and invocation evidence are complete.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

QUALIFICATION_PROMPT = (
    "Return only a unified diff for a hypothetical file named ndv_fixture.py. "
    "Change exactly `VALUE = 1` to `VALUE = 2`. Do not add prose."
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def find_model(probe: dict[str, Any], model_name: str) -> dict[str, Any]:
    if probe.get("schema_id") != "ndv-local-surface-probe-v1":
        raise ValueError("unexpected probe schema")
    if probe.get("downloads_performed") is not False or probe.get("credentials_used") is not False:
        raise ValueError("probe must be credential-free and download-free")
    models = probe.get("ollama", {}).get("models", [])
    matches = [m for m in models if isinstance(m, dict) and m.get("name") == model_name]
    if len(matches) != 1:
        raise ValueError(f"model {model_name!r} must match exactly one installed model")
    model = matches[0]
    digest = model.get("digest")
    if not isinstance(digest, str) or len(digest) < 32:
        raise ValueError("installed model digest missing or invalid")
    return model


def post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[dict[str, Any], bytes, float]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    start = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    elapsed = time.monotonic() - start
    decoded = json.loads(raw.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("Ollama response is not an object")
    return decoded, raw, elapsed


def make_binding(probe: dict[str, Any], model: dict[str, Any], qualification_ref: str, qualification_sha: str) -> dict[str, Any]:
    cli = probe.get("ollama", {}).get("cli", {})
    version = cli.get("stdout") if cli.get("returncode") == 0 else None
    return {
        "schema_id": "ndv-wp04-executor-binding-v1",
        "binding_status": "QUALIFIED",
        "binding_class": "LOCAL_PINNED",
        "provider": "Ollama local runtime",
        "executor_identity": model.get("name"),
        "executor_version_or_model_hash": model.get("digest"),
        "runtime_version": version,
        "invocation_surface": "http://127.0.0.1:11434/api/generate",
        "qualification_evidence_ref": qualification_ref,
        "qualification_evidence_sha256": qualification_sha,
        "telemetry_mode": "OLLAMA_NATIVE_RESPONSE_FIELDS_OR_EXPLICIT_MISSINGNESS",
        "candidate_capture_mode": "RAW_RESPONSE_AND_EXTRACTED_TEXT",
        "network_policy": "LOCAL_LOOPBACK_ONLY",
        "automatic_download": False,
        "dynamic_routing": False,
        "implicit_fallback": False,
        "retry_limit": 0,
        "escalation_limit": 0,
        "task_shaping": "S0_RAW_TASK",
        "holdout_access": "FORBIDDEN",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--probe", required=True, type=Path)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--binding-out", required=True, type=Path)
    ap.add_argument("--timeout", type=float, default=120.0)
    args = ap.parse_args()

    probe = load(args.probe)
    model = find_model(probe, args.model)

    payload = {
        "model": args.model,
        "prompt": QUALIFICATION_PROMPT,
        "stream": False,
        "options": {"temperature": 0},
    }
    try:
        response, raw, elapsed = post_json("http://127.0.0.1:11434/api/generate", payload, args.timeout)
        candidate = response.get("response")
        if not isinstance(candidate, str) or not candidate.strip():
            raise ValueError("empty candidate text")
        observed_model = response.get("model")
        if observed_model not in (None, args.model):
            raise ValueError(f"runtime reported unexpected model identity: {observed_model!r}")
        status = "S0_READY"
        error = None
    except Exception as exc:
        response, raw, elapsed, candidate = {}, b"", 0.0, None
        status = "S0_FAIL"
        error = f"{type(exc).__name__}: {exc}"

    evidence = {
        "schema_id": "ndv-local-ollama-qualification-v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "probe_ref": str(args.probe),
        "model_name": args.model,
        "model_digest": model.get("digest"),
        "quantization_level": model.get("quantization_level"),
        "parameter_size": model.get("parameter_size"),
        "qualification_prompt_sha256": sha256_bytes(QUALIFICATION_PROMPT.encode("utf-8")),
        "request": payload,
        "status": status,
        "error": error,
        "elapsed_seconds": elapsed,
        "raw_response_sha256": sha256_bytes(raw),
        "response": response,
        "candidate_text": candidate,
        "downloads_performed": False,
        "credentials_used": False,
        "p1_task_exposed": False,
        "holdout_access": "NONE",
    }
    encoded = json.dumps(evidence, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(encoded, encoding="utf-8")
    evidence_sha = sha256_bytes(encoded.encode("utf-8"))

    if status == "S0_READY":
        binding = make_binding(probe, model, str(args.out), evidence_sha)
        args.binding_out.parent.mkdir(parents=True, exist_ok=True)
        args.binding_out.write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": status, "binding": str(args.binding_out), "evidence": str(args.out)}, indent=2))
        return 0

    print(json.dumps({"status": status, "binding": None, "evidence": str(args.out), "error": error}, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
