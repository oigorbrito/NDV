# WP-05 — Free/Local Executor Screening

## Purpose

Identify executor surfaces that can enter later NDV experiments without requiring paid frontier access. This work package does **not** compare model quality and does **not** authorize P1 treatment claims.

## Current strategy

1. Probe the local machine first, without downloads and without credentials.
2. If a local Ollama runtime and installed model exist, qualify that exact model/digest.
3. Only if useful, consider downloading a pinned local model after machine fit is known.
4. Hosted-free candidates are screened separately and require exact model identity; dynamic routers such as `openrouter/free` are exploration-only.

## Local probe

Run:

```powershell
python tools/ndv_local_surface_probe.py --out .ndv-probes/local-surface.json
```

The probe is read-only. It records OS/CPU/RAM, NVIDIA GPU facts when available, Ollama version/API reachability, and installed model names/digests/quantization metadata where exposed. It does not download a model and does not use credentials.

Possible first classifications:

- `S0_ENVIRONMENT_BLOCKED` — no usable local runtime yet.
- `S0_DOWNLOAD_REQUIRED` — Ollama exists, but no installed model is available.
- `S0_LOCAL_SURFACE_DISCOVERED` — installed models were found; each still needs executor-level qualification.

## Hosted-free candidate universe

As of 2026-09-16, the prospective pinned candidates are recorded in `experiments/p1/free-local-executor-screening-v1.json`. Discovery is not qualification.

## Admission requirements

A model becomes an executor candidate only after the historical P1 executor screening requirements are satisfied, including reproducible invocation, exact identity, candidate artifact capture, timeout/cancel behavior, usage telemetry or explicit missingness, terms/licensing, and known cost provenance.

For local execution, also retain hardware identity, runtime/model digest, quantization, warm/cold state, load/wall time, and token telemetry where available. `FREE != ZERO COST` remains mandatory.

## Prohibited shortcuts

- Do not call a random/free router a pinned treatment.
- Do not treat a web chat subscription as an experimental executor.
- Do not silently download a large model during screening.
- Do not treat missing telemetry as zero.
- Do not select models based on performance on admitted P1 tasks before the candidate universe is frozen.

## Gate

WP-05 is complete when at least one additional free/local executor surface is either:

- qualified (`S0_READY` or explicitly telemetry-limited), or
- rejected/blocked with auditable evidence.

A blocked outcome is valid; this work package exists to establish what is actually available, not to force a free/local treatment into P1.
