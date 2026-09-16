# WP-05 — Free/Local Executor Screening

## Purpose

Identify executor surfaces that can enter later NDV experiments without requiring paid frontier access. This work package does **not** compare model quality and does **not** authorize P1 treatment claims.

## Current strategy

1. Probe the local machine without credentials or implicit downloads.
2. Qualify an exact installed Ollama model/digest as an inference endpoint on a synthetic non-P1 task.
3. Separately qualify a repository-capable coding-agent scaffold using the same frozen model.
4. Only a binding-v2 containing both model identity and frozen scaffold identity can authorize WP-04 task exposure.

`MODEL_ENDPOINT_READY != SOFTWARE_EXECUTOR_READY`.

## Observed local surface — 2026-09-16

The operator-provided machine probe observed:

- Windows 11 / AMD64;
- 8 logical CPUs;
- approximately 12.7 GB RAM;
- NVIDIA GeForce GTX 1650, 4096 MiB;
- Ollama 0.34.1 reachable on loopback;
- installed model `qwen2.5-coder:3b`;
- model digest `f72c60cabf6237b07f6e632b2c48d533cef25eda2efbd34bed21c5e9c01e6225`;
- quantization `Q4_K_M`;
- parameter size `3.1B`.

The synthetic model-endpoint qualification returned `S0_READY` under the original v1 bridge and the original WP-04 binding validator returned `PASS`. No P1 task had been exposed at that point.

A methodological review immediately after that result found that the raw Ollama `/api/generate` endpoint has no repository inspection/modification capability by itself. Therefore the original v1 binding is retained as endpoint evidence but is superseded for task-exposure authority by `experiments/p1/wp04-executor-binding-v2.template.json`.

## Local model endpoint qualification

`tools/ndv_qualify_local_ollama_executor.py` now classifies a passing Ollama surface as:

```text
S0_MODEL_ENDPOINT_READY
MODEL_ENDPOINT_QUALIFIED_NOT_EXECUTOR
```

It persists exact model identity/digest and synthetic coding evidence but explicitly sets `wp04_task_exposure_authorized=false`.

## Repository-capable scaffold qualification

The scaffold screen is frozen in `experiments/p1/wp05-agent-scaffold-screening-v1.json`.

For the first native-Windows smoke, Aider is selected for qualification because it documents Windows installation and direct Ollama integration. mini-SWE-agent remains relevant prior art/candidate but is deferred for this first Windows smoke because its local environment describes bash-oriented command execution, creating avoidable shell uncertainty.

Qualify Aider + the already installed Ollama model with:

```powershell
python tools/ndv_qualify_aider_ollama_scaffold.py `
  --probe .ndv-probes/local-surface.json `
  --model qwen2.5-coder:3b `
  --out .ndv-probes/qualification/aider-qwen25-coder-3b.json `
  --binding-out .ndv-probes/bindings/wp04-aider-qwen25-coder-3b-v2.json
```

The qualifier creates a temporary synthetic git repository containing only `fixture.py` with `VALUE = 1`, invokes Aider non-interactively through the local Ollama model, and requires the resulting `git diff` to contain exactly the intended transition to `VALUE = 2`. It does not expose D-F5-01 or holdout material.

A generated binding must then pass:

```powershell
python tools/ndv_validate_wp04_smoke.py `
  --binding .ndv-probes/bindings/wp04-aider-qwen25-coder-3b-v2.json
```

Only that binding-v2 PASS authorizes WP-04 Stage 1 task exposure.

## Hosted-free candidate universe

Prospective hosted-free candidates remain recorded in `experiments/p1/free-local-executor-screening-v1.json`. Discovery is not qualification, and dynamic routers remain unsuitable for frozen treatment identity.

## Accounting

`FREE != ZERO COST`. Local execution must retain hardware identity, runtime/model digest, quantization, wall time, warm/cold state where relevant, token telemetry where exposed, and explicit missingness otherwise. No hardware-to-token conversion is permitted.

## Prohibited shortcuts

- Do not call a raw model API a standalone executor.
- Do not expose P1 tasks before scaffold qualification and binding-v2 validation.
- Do not silently download a model during qualification/run.
- Do not enable dynamic routing, fallback, retry, or escalation.
- Do not coerce missing telemetry to zero.
- Do not select scaffolds based on performance on admitted P1 tasks.

## Current status

```text
LOCAL_MACHINE_PROBE = OBSERVED
OLLAMA_RUNTIME = AVAILABLE
LOCAL_MODEL = qwen2.5-coder:3b
LOCAL_MODEL_DIGEST = f72c60cabf6237b07f6e632b2c48d533cef25eda2efbd34bed21c5e9c01e6225
MODEL_ENDPOINT_QUALIFICATION = PASS
MODEL_ENDPOINT_CLASS = MODEL_ENDPOINT_QUALIFIED_NOT_EXECUTOR
WP04_BINDING_V1 = SUPERSEDED_BEFORE_TASK_EXPOSURE
AIDER_SCAFFOLD_QUALIFIER = IMPLEMENTED
WP04_BINDING_V2 = PENDING_LOCAL_SCAFFOLD_QUALIFICATION
P1_TASK_EXPOSURE = NONE
```
