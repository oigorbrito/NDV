#!/usr/bin/env python3
"""Qualify one already-installed Ollama model as an inference endpoint.

This tool intentionally does NOT qualify the endpoint as a standalone software
executor. A WP-04 executable binding additionally requires a frozen agent
scaffold with repository inspection/modification capability.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

QUALIFICATION_PROMPT = (
    "Return only a unified diff for a hypothetical file named ndv_fixture.py. "
    "Change exactly `VALUE = 1` to `VALUE = 2`. Do not add prose."
)
EXPECTED_DIFF_RE = re.compile(
    r"---\s+.*ndv_fixture\.py.*\n\+\+\+\s+.*ndv_fixture\.py.*\n.*-VALUE = 1.*\n.*\+VALUE = 2",
    re.DOTALL,
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


def candidate_is_valid(text: str) -> bool:
    return bool(EXPECTED_DIFF_RE.search(text.replace("\r\n", "\n")))


def make_endpoint_record(
    probe: dict[str, Any],
    model: dict[str, Any],
    qualification_ref: str,
    qualification_sha: str,
    frozen_at: str,
) -> dict[str, Any]:
    cli = probe.get("ollama", {}).get("cli", {})
    version = cli.get("stdout") if cli.get("returncode") == 0 else "UNMEASURED"
    return {
        "schema_id": "ndv-wp05-local-model-endpoint-v1",
        "classification": "MODEL_ENDPOINT_QUALIFIED_NOT_EXECUTOR",
        "provider_or_runtime": f"Ollama local runtime ({version})",
        "model_identity": model.get("name"),
        "model_digest": model.get("digest"),
        "quantization_level": model.get("quantization_level"),
        "parameter_size": model.get("parameter_size"),
        "endpoint": "http://127.0.0.1:11434/api/generate",
        "qualification_evidence_ref": qualification_ref,
        "qualification_evidence_sha256": qualification_sha,
        "repository_tool_access": False,
        "wp04_task_exposure_authorized": False,
        "required_next_gate": "MODEL_PLUS_FROZEN_SCAFFOLD_OR_STANDALONE_AGENT_BINDING_V2",
        "frozen_at": frozen_at,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--probe", required=True, type=Path)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument(
        "--binding-out",
        required=True,
        type=Path,
        help="Compatibility name: writes an endpoint record, not a WP-04 executable binding.",
    )
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args()

    probe = load(args.probe)
    model = find_model(probe, args.model)
    payload = {
        "model": args.model,
        "prompt": QUALIFICATION_PROMPT,
        "stream": False,
        "options": {"temperature": 0},
    }
    frozen_at = datetime.now(timezone.utc).isoformat()
    try:
        response, raw, elapsed = post_json("http://127.0.0.1:11434/api/generate", payload, float(args.timeout))
        candidate = response.get("response")
        if not isinstance(candidate, str) or not candidate.strip():
            raise ValueError("empty candidate text")
        observed_model = response.get("model")
        if observed_model not in (None, args.model):
            raise ValueError(f"runtime reported unexpected model identity: {observed_model!r}")
        if not candidate_is_valid(candidate):
            raise ValueError("synthetic coding qualification output did not satisfy the frozen diff oracle")
        status = "S0_MODEL_ENDPOINT_READY"
        error = None
    except Exception as exc:
        response, raw, elapsed, candidate = {}, b"", 0.0, None
        status = "S0_FAIL"
        error = f"{type(exc).__name__}: {exc}"

    evidence = {
        "schema_id": "ndv-local-ollama-qualification-v2",
        "timestamp_utc": frozen_at,
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
        "candidate_oracle": "PASS" if isinstance(candidate, str) and candidate_is_valid(candidate) else "FAIL",
        "downloads_performed": False,
        "credentials_used": False,
        "p1_task_exposed": False,
        "holdout_access": "NONE",
        "standalone_executor_qualification": "NOT_CLAIMED",
    }
    encoded = json.dumps(evidence, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(encoded, encoding="utf-8")
    evidence_sha = sha256_bytes(encoded.encode("utf-8"))

    if status == "S0_MODEL_ENDPOINT_READY":
        endpoint_record = make_endpoint_record(probe, model, str(args.out), evidence_sha, frozen_at)
        args.binding_out.parent.mkdir(parents=True, exist_ok=True)
        args.binding_out.write_text(json.dumps(endpoint_record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({
            "status": status,
            "endpoint_record": str(args.binding_out),
            "evidence": str(args.out),
            "wp04_task_exposure_authorized": False,
        }, indent=2))
        return 0

    print(json.dumps({"status": status, "endpoint_record": None, "evidence": str(args.out), "error": error}, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
