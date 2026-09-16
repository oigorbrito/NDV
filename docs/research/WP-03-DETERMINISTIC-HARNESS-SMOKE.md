# WP-03 — Deterministic Harness Smoke

## Purpose

Validate the inherited DV pilot harness before any NDV LLM treatment execution.

This work package is **not** a model evaluation and carries no authority for claims about executor quality, routing, economics, or NDV architecture.

## Reused historical component

The smoke reuses the historical harness without semantic rewrite:

- repository: `oigorbrito/dv`
- cutover commit: `66f3a218fba800daed5d86fdfce386491b8ab0e8`
- path: `tools/dv_pilot_harness.py`
- blob SHA: `0f7f936e46dbaccf243b6b77dd6014eedeb076cf`

The runner is native to NDV and is intentionally thin: `tools/ndv_deterministic_harness_smoke.py`.

## Cases

| Case | Deterministic executor behavior | Expected verifier result |
| --- | --- | --- |
| `H0_NOOP` | makes no candidate change | `NO` / `PRODUCT_FAILURE` |
| `H1_KNOWN_VALID` | writes exact valid marker | `YES` |
| `H2_KNOWN_INVALID` | writes deterministic invalid marker | `NO` / `PRODUCT_FAILURE` |

Each fixture emits explicit zero-token and zero-monetary-cost telemetry. This is intentional: the smoke verifies that the harness distinguishes **measured zero** from **missing/unresolved telemetry**.

## Pass gate

WP-03 passes only when all three cases:

1. produce a run directory;
2. reconcile with harness status `PASS`;
3. produce the expected conclusive verifier outcome;
4. contain non-empty `evidence_refs`;
5. reconcile explicit telemetry to zero;
6. do not require credentials, provider calls, holdout tasks, or manual intervention.

Any failure blocks the real-executor smoke.

## Execution modes

Local persisted execution:

```bash
python tools/ndv_deterministic_harness_smoke.py --legacy-dv-root ../dv --out .ndv-smoke
```

CI execution is frozen in:

```text
.github/workflows/wp03-deterministic-harness-smoke.yml
```

The CI workflow checks out the exact historical DV cutover commit, verifies the historical harness blob SHA before execution, runs H0/H1/H2, publishes the summary and uploads the evidence artifact.

## Recorded execution — 2026-09-16

GitHub Actions run:

- workflow: `WP-03 Deterministic Harness Smoke`
- run id: `35100959680`
- triggering NDV commit: `458c2aa0874b2671f3fccd1ea07a945062a4257e`
- job: `deterministic-smoke`
- conclusion: `success`
- frozen-DV identity check: `success`
- deterministic smoke execution step: `success`
- evidence upload: `success`
- artifact: `wp03-deterministic-harness-smoke`
- artifact id: `10448500428`
- artifact digest: `sha256:e1081b2befbaad04454996bec2a0a40e655f0137eff54ae2b18b9758bf9d9e90`

The NDV smoke runner exits zero only when every H0/H1/H2 case satisfies the pass assertions. Therefore this execution closes the WP-03 harness-mechanics gate.

## Outcome

```text
WP-03_IMPLEMENTATION = COMPLETE
WP-03_EXECUTION = COMPLETE
WP-03_RESULT = PASS
WP-04_REAL_EXECUTOR_SMOKE = UNBLOCKED_BY_WP03
```

This `PASS` authorizes only the next pipeline step. It does not establish executor quality, economic superiority, routing headroom, architecture value, or any model-performance claim.
