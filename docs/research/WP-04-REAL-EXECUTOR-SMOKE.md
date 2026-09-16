# WP-04 — Real Executor Pipeline Smoke

## Purpose

Validate the real-executor evidence pipeline after WP-03 deterministic harness qualification. WP-04 is **pipeline qualification only**: it does not compare executors, establish routing headroom, demonstrate economic superiority, or justify NDV architecture.

Historical authority remains `oigorbrito/dv@66f3a218fba800daed5d86fdfce386491b8ab0e8`. The cutover development corpus remains four admitted tasks across three families and three repositories with `comparative_corpus_ready=NO`.

## Concrete frozen surface

The direct Ollama model endpoint is not treated as a software executor. Task exposure requires binding-v2: model plus a repository-capable scaffold proven on a synthetic mutation task.

The qualified WP-04 surface used for Stage 1 is:

- binding: `WP04-AIDER-OLLAMA-bcf636703b1a2973`;
- scaffold: Aider `aider 0.86.2`;
- model: `qwen2.5-coder:3b` through local Ollama;
- retries: 0;
- escalations: 0;
- dynamic routing/fallback: forbidden.

`experiments/p1/wp04-executor-binding-v1.template.json` is historical/superseded for task exposure. Current task exposure requires `ndv-p1-wp04-executor-binding-v2`.

## Stage sequence

WP-04 uses two historically admitted metaO tasks only to qualify mechanics while reducing environment variance:

1. `D-F5-01`
2. `D-F6-01`

This is not representative sampling and creates no comparative authority.

### Stage 1 — D-F5-01

The frozen task packet is `experiments/p1/wp04-stage1-d-f5-01-v1.json`, base `9cc5d6d722d509175a669624c9235156dffb4f85`.

Stage 1 was executed once with raw task shaping and the frozen Aider+Qwen binding. The preserved result is `experiments/p1/wp04-stage1-result-r1.json`:

```text
outcome = SMOKE_VALID_FAILED
failure_attribution = PRODUCT_FAILURE (frozen executor surface)
executor_returncode = 0
candidate_diff_bytes = 0
baseline_structural_focal = FAIL as required
candidate_structural_focal = FAIL
baseline_preservation = PASS
candidate_preservation = PASS
retry_count = 0
escalation_count = 0
holdout_access = NONE
reconciled_total_tokens ≈ 27,404
```

Observed behavior: Aider reported that the model requested files be added to chat, exited successfully, and produced no repository diff. This is evidence about the **frozen Aider+Qwen surface**, not the model in isolation.

Raw Stage-1 evidence is preserved under `pilot-runs/wp04-real-executor-smoke/stage1-d-f5-01-r1/`. Its historical `import-manifest.json` is v1 and remains unchanged.

### Evidence-schema upgrade without rewriting history

The current importer emits `ndv-wp04-import-manifest-v2`, with a byte-hashed inventory of `run-report.json` and immutable `evidence/` artifacts. Stage 2 and campaign closure require this evidence-only v2 contract.

Because the already-preserved Stage-1 bundle predates v2, `tools/ndv_upgrade_wp04_import_manifest.py` creates a **non-destructive sidecar** `import-manifest-v2.json`. It independently revalidates the report/candidate evidence, recalculates artifact SHA-256/size and Aider token telemetry, and never modifies the historical v1 manifest or re-executes the treatment.

Stage 2 and closure prefer this v2 sidecar when present.

### Original binding preservation

The preserved Stage-1 report records the local original binding path `.ndv-probes\bindings\wp04-aider-qwen25-coder-3b-v2.json`, but the exact binding bytes are not yet present in the repository. The binding must **not** be reconstructed after the fact from the report.

`tools/ndv_import_wp04_binding.py` is the preservation gate. Given the original local binding-v2 file, it:

1. validates the full current binding-v2 contract;
2. requires exact Stage-1 `binding_id` and executor-identity match;
3. rejects retry/escalation, fallback, dynamic routing, or download drift;
4. copies the exact original bytes into a stable evidence directory;
5. records binding SHA-256/size and Stage-1 report SHA-256 in `binding-import-receipt.json`;
6. explicitly records `binding_reconstructed=false` and `treatment_reexecuted=false`.

GitHub issue #2 tracks this provenance blocker. The importer/tests are CI-green in WP-04 run `35148684510`; the remaining blocker is availability of the original local binding file.

### Stage 2 — D-F6-01

Stage 2 has **not** been executed. Its task contract and runner are frozen. Before any D-F6-01 exposure, `tools/ndv_run_wp04_stage2_df601.py` now requires:

1. a hash-valid Stage-1 import manifest v2;
2. the same original binding used in Stage 1;
3. the exact Aider executable path frozen in that binding;
4. `aider --version` to exactly match the frozen Aider version;
5. discriminating structural focal failure on the untouched historical base;
6. all frozen Rust baseline oracle checks to pass;
7. zero retry/escalation and sealed holdout.

The Stage-1 artifact inventory shape is aligned with the canonical v2 importer format: a list of `{path, size_bytes, sha256}` records. This fixes the prior inconsistency where the Stage-2 runner expected a dict/`bytes` shape that the official importer never emitted.

## Import and campaign closure

`tools/ndv_import_wp04_stage_run.py` imports only immutable evidence, never `workspace/` or verifier environments, and emits manifest v2 with token reconciliation.

`tools/ndv_close_wp04_campaign.py` closes WP-04 only after **both** D-F5-01 and D-F6-01 have hash-valid v2 evidence bundles from the same binding. It re-hashes the preserved artifacts and rejects retry/escalation, holdout access, missing raw evidence provenance, treatment reexecution, or binding mismatch.

Even a successful closure grants only `WP04_PIPELINE_SMOKE_COMPLETE`; comparative P1 release remains `NO`.

## Outcome vocabulary

Valid stage outcomes are:

- `SMOKE_VALID_SOLVED`
- `SMOKE_VALID_FAILED`
- `SMOKE_INCONCLUSIVE`

A valid failure is useful if candidate capture, verifier evidence, accounting, and attribution close correctly. An untraceable success is not sufficient.

## Current status

```text
WP-03 = PASS
WP-04_CONTRACT = FROZEN
WP-04_EXECUTOR_BINDING_V2 = FROZEN / QUALIFIED AT STAGE1 EXECUTION
WP-04_ORIGINAL_BINDING_BYTES_IN_REPO = NO
WP-04_BINDING_IMPORT_TOOLING = PASS (CI 35148684510)
WP-04_STAGE1_D-F5-01 = EXECUTED
WP-04_STAGE1_OUTCOME = SMOKE_VALID_FAILED
WP-04_STAGE1_RAW_EVIDENCE = PRESERVED
WP-04_STAGE1_IMPORT_V1 = HISTORICAL
WP-04_STAGE1_IMPORT_V2_SIDECAR = TOOLING_READY / NOT_YET_PERSISTED
WP-04_STAGE2_D-F6-01 = BLOCKED_ON_ORIGINAL_BINDING_PRESERVATION
WP-04_CAMPAIGN_CLOSURE = NOT_COMPLETE
COMPARATIVE_AUTHORITY = NONE
ARCHITECTURE_AUTHORITY = NONE
```

The next execution gate is: import the **original** binding-v2 bytes, create/revalidate the Stage-1 v2 sidecar, and only then run D-F6-01 once with that exact binding. No Stage-2 exposure is authorized if the binding/sidecar/hash/scaffold gates fail.
