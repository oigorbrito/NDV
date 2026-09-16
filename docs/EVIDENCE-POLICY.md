# NDV Evidence Policy

## Evidence levels

- `E0 — EXPLORATORY`: isolated observation, pilot, literature signal, or engineering note. Does not authorize architecture.
- `E1 — REPRODUCED`: repeated result in the same setup. Useful for stability, not strong causal claims.
- `E2 — CONTROLLED`: frozen treatment/baseline, reproducible environment, complete accounting, and explicit failure attribution.
- `E3 — HOLDOUT_CONFIRMED`: controlled result survives a prospectively sealed holdout or equivalent external confirmation.
- `E4 — INDEPENDENTLY_REPLICATED`: result reproduced independently outside the original experimental path.

Mandatory core capabilities normally require `E3` unless an explicit exception is documented with scope and rationale.

## Claim states

- `UNTESTED`
- `EXPLORATORY_SIGNAL`
- `SUPPORTED_IN_SCOPE`
- `REFUTED_IN_SCOPE`
- `INCONCLUSIVE`
- `STALE`
- `SUPERSEDED`

Support is always scoped. A claim supported for a specific model family, task distribution, benchmark, cost regime, or date must not be silently generalized beyond that scope.

## Evidence classes

NDV keeps these distinct:

- `LITERATURE_EVIDENCE`
- `NDV_EXPERIMENTAL_EVIDENCE`
- `ENGINEERING_OBSERVATION`

External literature may motivate or challenge a claim, but it does not count as NDV experimental confirmation.

## Retest triggers

Claims may become `STALE` when materially affected by:

- `NEW_FRONTIER_EXECUTOR`
- `MAJOR_MODEL_VERSION_CHANGE`
- `PRICE_SHIFT`
- `MAJOR_HARNESS_CHANGE`
- `VERIFIER_CHANGE`
- `BENCHMARK_INVALIDATION`
- `TASK_DISTRIBUTION_SHIFT`
- `NEW_PRIOR_ART`
- `REPLICATION_CONTRADICTION`

Staleness does not erase historical evidence; it limits current applicability.

## Promotion rule

The normative flow is:

`claim -> experiment -> evidence -> decision -> architecture`

Not:

`idea -> implementation`.

## Negative and null results

Negative, null, and inconclusive findings are first-class outcomes. Do not suppress failed treatments, unstable runs, or evidence that reduces NDV scope.

## Stop discipline

Do not alter task selection, repetitions, stopping rules, analysis method, or holdout policy because a favored treatment is leading or losing.