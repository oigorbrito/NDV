# WP-04 — Real Executor Pipeline Smoke

## Purpose

Validate the first real executor pipeline after the deterministic harness gate passed.

WP-04 is **pipeline qualification only**. It does not compare executors, estimate routing headroom, establish economic superiority, or justify NDV architecture.

## Authority and prerequisites

Historical authority remains `oigorbrito/dv` at cutover commit `66f3a218fba800daed5d86fdfce386491b8ab0e8`.

The normative historical development corpus at that cutover is `experiments/p1/p1-development-corpus-v6.json`, containing four admitted tasks across three families and three repositories. The historical artifact still states `comparative_corpus_ready = NO`.

WP-03 passed in GitHub Actions run `35100959680`. The uploaded deterministic smoke artifact has digest:

`sha256:e1081b2befbaad04454996bec2a0a40e655f0137eff54ae2b18b9758bf9d9e90`.

Therefore the harness-mechanics blocker is closed.

The frozen WP-04 campaign contract and its validator were independently exercised by GitHub Actions run `35106775556`; the `validate` job completed successfully, including both static contract validation and `tools/test_ndv_validate_wp04_smoke.py`.

## Provider-neutral design, concrete execution

The campaign definition is provider-neutral. An execution is not.

Before an admitted task can be exposed to an executor, exactly one concrete executor binding must be frozen using `experiments/p1/wp04-executor-binding-v1.template.json`.

Allowed classes are:

- `LOCAL_PINNED`
- `HOSTED_FREE_PINNED`
- `SUBSCRIPTION_EXECUTOR_PINNED`

A binding must record exact executor identity, version/model hash, invocation surface, qualification evidence, telemetry mode, candidate capture mode, timeout and network policy.

The following are forbidden:

- random/free routers whose underlying model can change;
- implicit fallback;
- automatic model download during the run;
- retries;
- escalation to another executor;
- dynamic routing.

This preserves the causal unit of the smoke.

## Staged task sequence

WP-04 deliberately uses two historically admitted metaO tasks first:

1. `D-F5-01`
2. `D-F6-01`

This choice minimizes environment variation during pipeline qualification because both share the same repository and already have mature offline verifier evidence. It must not be interpreted as representative sampling.

Stage 2 is gated on stage 1 producing a traceable result. A traceable result may be solved, failed, or inconclusive; the key requirement is that the pipeline can attribute what happened.

For D-F5-01 the frozen historical oracle requires:

```text
focal:
python -m unittest tests.unit.test_operator_ux_doctor

preservation:
python -m unittest discover -s tests/unit
```

The historical base revision is `9cc5d6d722d509175a669624c9235156dffb4f85`.

## Outcome vocabulary

Only these WP-04 outcomes are valid:

- `SMOKE_VALID_SOLVED`
- `SMOKE_VALID_FAILED`
- `SMOKE_INCONCLUSIVE`

A valid failure is useful evidence if candidate capture, verifier evidence, accounting and failure attribution all close correctly.

An untraceable success is not sufficient.

## Accounting and failure attribution

The inherited accounting contract remains authoritative:

`oigorbrito/dv@66f3a218...:experiments/p1/run-accounting-contract-v1.json`

All consumed resources remain accounted on failure or inconclusive runs. `FREE != ZERO COST`. Local and free surfaces still retain hardware/runtime identity, wall-clock cost, setup information and missing telemetry explicitly.

The inherited failure-attribution contract remains authoritative:

`oigorbrito/dv@66f3a218...:experiments/p1/failure-attribution-v1.json`

Only valid `PRODUCT_FAILURE` supports a treatment-level `NO`. Harness failure, oracle defect, environment drift, provider failure, resource limit and mandatory telemetry gaps must not be relabeled as product failure.

## Governance validation

Validate the static campaign contract:

```bash
python tools/ndv_validate_wp04_smoke.py
```

Validate a concrete executor binding before execution:

```bash
python tools/ndv_validate_wp04_smoke.py \
  --binding path/to/frozen-executor-binding.json
```

The binding validator rejects unqualified surfaces, dynamic routing, fallbacks, downloads, retries and escalation.

## Release gate

WP-04 is not complete merely because an executor produced code.

Completion requires:

1. one concrete qualified binding frozen before task exposure;
2. D-F5-01 executed with raw task shaping and no retry/escalation;
3. candidate artifact captured;
4. exact executor identity and raw execution evidence retained;
5. independent focal/preservation verification;
6. accounting reconciled, including explicit missingness;
7. failure attribution recorded;
8. D-F6-01 executed only after stage 1 is traceable;
9. holdout remains sealed.

Even after WP-04 passes, `P1_COMPARATIVE_READY` remains a separate gate requiring a sufficient corpus and multiple frozen treatment surfaces.

## Current status

```text
WP-03 = PASS
WP-04_CONTRACT = FROZEN
WP-04_CONTRACT_VALIDATION = PASS (GitHub Actions run 35106775556)
WP-04_EXECUTOR_BINDING = NOT_YET_FROZEN
WP-04_EXECUTION = NOT_YET_EXECUTED
NEXT_BLOCKER = QUALIFY_AND_FREEZE_ONE_CONCRETE_EXECUTOR_SURFACE
COMPARATIVE_AUTHORITY = NONE
```
