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

## Execution

From a checkout containing both repositories as siblings:

```bash
python tools/ndv_deterministic_harness_smoke.py --legacy-dv-root ../dv --out .ndv-smoke
```

The persisted report is:

```text
.ndv-smoke/ndv-deterministic-harness-smoke-report.json
```

Temporary execution is also supported by omitting `--out`, but persisted evidence is required before WP-03 is marked complete.

## Outcome vocabulary

- `PASS` — all deterministic cases behave exactly as expected.
- `FAIL` — at least one harness, verification, evidence, or telemetry assertion fails.

A `PASS` authorizes only the next pipeline step: real-executor smoke under the previously frozen restrictions.
