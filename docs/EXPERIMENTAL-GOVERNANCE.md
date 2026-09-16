# NDV Experimental Governance

## Purpose

Experiments exist to falsify or constrain claims, not to justify a predetermined architecture.

## Core rules

- Freeze task, treatment, executor binding, shaping, budgets, verifier, repetition policy, and analysis plan before comparative execution.
- Smoke tests validate instrumentation; they do not authorize scientific performance claims.
- Holdout tasks must remain sealed until the protocol authorizes their use.
- No treatment result may influence whether a task is admitted.
- Failures and inconclusive runs retain all consumed resource cost.
- Do not stop early because a favored treatment leads or loses.
- Do not silently discard harness failures, provider failures, environment drift, or oracle defects; attribute them explicitly.
- `UNMEASURED != ZERO`.

## Pipeline qualification vs comparative evidence

NDV distinguishes:

- `PIPELINE_SMOKE_READY`: enough to validate materialization, invocation, candidate capture, verification, accounting, and result serialization.
- `COMPARATIVE_READY`: enough qualified treatments and admitted tasks to support the intended scientific comparison.

A pipeline smoke may pass even when no task is solved, provided the pipeline is reproducible and evidence-complete.

## Stop rules

- If `best fixed ~= oracle`, routing headroom is not established.
- If coordination/control overhead is greater than or equal to savings, reject the added layer.
- If existing prior art provides equivalent required capability at lower expected cost, prefer reuse.
- If results are unstable under the frozen repetition policy, return `INCONCLUSIVE`.
- Never tune until a preferred treatment wins.

## Phase gates

- P1 studies executor/routing economics.
- P2 opens only when continuity/recovery cost is materially relevant.
- P3 opens only when composition heterogeneity has measurable headroom.
- P4 opens only when sequential decisions matter and simpler policies leave measurable regret.
- P5 integrates only capabilities that survived earlier gates.

## Documentation discipline

Create documentation when it controls a decision, experiment, provenance requirement, result, or gate. Avoid speculative documentation with no operational consequence.