# Luna-only composition research track

## Status

Prospective research track. No development-task treatment has been executed and no holdout has been accessed.

The active executor/model is fixed to the already-qualified Codex + `gpt-5.6-luna` v4 surface. Other model tiers are outside the active critical path.

This does not erase or reinterpret the earlier P1 multi-model/routing artifacts. Those remain historical prospective work and may be revisited later, but they are not required for the current question.

## Question

Does explicit decomposition/composition improve verified software-engineering outcomes enough to pay for its own total-system overhead when the underlying model is held constant?

This isolates composition from model selection. A positive result cannot be attributed to using a stronger model.

## Initial comparison

- **D0 — LUNA_DIRECT_VERIFY**: one Luna execution, then independent verification.
- **D1 — LUNA_PLAN_EXECUTE_VERIFY**: one non-mutating Luna planning call emits a constrained structured plan; a fresh Luna execution starts from the exact base with task + plan; then verification.
- **D2 — LUNA_PLAN_STEPWISE_VERIFY**: the same plan format is executed step-by-step by fresh Luna invocations on one evolving candidate workspace; then verification.

No retries, repair loop, model escalation, dynamic routing, parallel agents, or learned controller are part of the initial comparison.

## Why these treatments

D0 establishes the cost/quality frontier of the simplest useful system.

D1 tests whether an explicit external decomposition artifact is useful at all.

D2 tests whether the additional control boundary of stepwise execution adds value beyond merely giving Luna a plan.

If D0 dominates, the decomposition layer is rejected. If D1 helps but D2 does not, a thin plan compiler may be justified while a stepwise controller is not. If D2 helps only in some task families, that creates a later hypothesis for adaptive composition; it does not authorize an adaptive controller by itself.

## Structured plan, not chain-of-thought

The planning artifact is an operational specification, not hidden reasoning. It contains objective, constraints, ordered steps, dependencies, expected artifacts, and verification instructions. It explicitly excludes chain-of-thought, hidden reasoning, gold patches, test patches, holdout data, and post-hoc treatment hints.

Schema: `experiments/luna-only/luna-decomposition-plan-schema-v1.json`.

Protocol: `experiments/luna-only/luna-composition-protocol-v1.json`.

## Accounting

The primary metric remains:

`TOTAL_SYSTEM_TOKENS / VERIFIED_SOLVED_TASK`

All planner, executor, failed invocation, and verifier cost remains in the treatment total. Decomposition does not get free compute. Latency and number of invocations are retained separately.

The initial study does not force equal token budgets across treatments because doing so would hide the real cost of decomposition. Instead, each invocation has a frozen resource ceiling and the complete treatment cost is measured.

## Release requirements

Before any development task is exposed:

1. the exact Luna v4 qualification bundle must be preserved and hash-valid;
2. the development corpus must satisfy the existing admission/readiness rules;
3. planner/executor prompt templates must be frozen;
4. invocation and treatment ceilings must be frozen;
5. the verifier must be frozen and independent of the executor;
6. no holdout task may be accessed.

## Architecture consequences

This track can justify only the minimum capability supported by evidence.

- D0 dominates -> `NO_BUILD_DECOMPOSITION`.
- D1 earns the frontier -> investigate a thin context/plan compiler.
- D2 additionally earns the frontier -> investigate sequential composition mechanics.
- unstable/underpowered result -> `INCONCLUSIVE`.

No result from this development track alone justifies a generic orchestrator, multi-agent framework, learned router, persistent memory system, or full NDV runtime.
