# AGENTS.md

These rules apply to humans and automated coding/research agents working in this repository.

## Operating posture

1. NDV is research-first. Do not implement a runtime, router, orchestrator, memory system, workflow engine, model gateway, generic agent framework, or adaptive controller unless an approved experiment and architecture gate explicitly require it.
2. Existing ecosystem capabilities must be evaluated for reuse before custom implementation.
3. Experimental contracts are immutable after freeze. If semantics change, create a new version; do not silently edit frozen evidence.
4. Historical artifacts in `oigorbrito/dv` must not be rewritten or rebranded as if they were originally NDV artifacts.
5. Executor-reported success is not verified success. Independent verification governs acceptance.
6. Account for complete system cost, including failures, routing, shaping, context, planning, execution, handoff, verification, retries, latency, local hardware/energy where reliable, and coordination overhead.
7. `NO_BUILD`, `REUSE_ONLY`, `REFUTED_IN_SCOPE`, and `INCONCLUSIVE` are valid outcomes.
8. Never tune task selection, stopping criteria, repetitions, or analysis because a favored treatment is leading or losing.
9. Do not expose secrets in files, logs, issues, commits, prompts, or result artifacts.
10. Prefer the smallest change that preserves scientific traceability and reproducibility.

## Decision order

For every proposed capability:

`claim -> controlled experiment -> evidence level -> decision -> reuse/adapt/build choice`

Never use:

`idea -> implementation`.

## Architecture default

Use this order unless evidence justifies otherwise:

`REUSE -> ADAPT -> WRAP -> FORK -> BUILD CUSTOM`

A custom capability is blocked when existing prior art satisfies the required contract at lower expected integration and maintenance cost.

## Verification rule

`EXECUTOR_DONE != VERIFIED_SOLVED`

Verification must be attributable, versioned, reproducible, and independent of the treatment output when the experiment requires an independent oracle.

## Provenance

New NDV work belongs in this repository. Historical DV evidence remains authoritative at its original source repository/commit. Reference legacy artifacts by repository, path, commit and hash when needed.