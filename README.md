# NDV

NDV is a research program investigating whether adaptive selection of the minimum sufficient combination of software-engineering capabilities can improve the verified-success / total-cost / latency frontier relative to fixed execution strategies.

NDV is not an approved software architecture. It is research-first, falsification-driven, and explicitly allows `NO_BUILD`, `REUSE_ONLY`, and `INCONCLUSIVE` outcomes.

## Core principle

Use the ecosystem to NDV's advantage: models, coding agents, runtimes, verifiers, orchestrators, tools, and future systems are replaceable capabilities. NDV should benefit when they improve rather than compete with them.

The unit of composition is capability, not repository identity.

A candidate layer must pay for its own overhead. The default engineering order is:

`REUSE -> ADAPT -> WRAP -> FORK -> BUILD CUSTOM`

The default execution principle is:

`minimum sufficient composition -> external execution -> independent evidence -> continue / verify / retry / handoff / escalate / stop`

## Primary economic objective

Minimize complete system cost subject to a required probability of verified success.

Primary research metric:

`TOTAL_SYSTEM_TOKENS / VERIFIED_SOLVED_TASK`

Accounting must also retain monetary cost, latency, retries, handoff, verification, context, routing, coordination, and failure cost. `FREE != ZERO COST`.

## Scientific posture

Do not assume NDV is correct. Research -> hypothesis -> controlled test -> evidence -> decision -> implementation.

Executor self-report is not task success. `EXECUTOR_DONE != VERIFIED_SOLVED`.

Mandatory architecture capabilities normally require holdout-confirmed evidence before becoming core.

## Experimental program

- P1: executor and routing economics
- P2: continuity and handoff
- P3: composition selection
- P4: sequential adaptive control
- P5: integrated-system validation

Later phases do not start automatically. Negative results may eliminate them.

## Historical provenance

The research program was previously maintained in `oigorbrito/dv`. Historical DV artifacts remain authoritative at their original repository and commits and must not be silently rewritten as NDV artifacts.

Prospective NDV work is canonical in this repository from the cutover defined in `provenance/dv-legacy-manifest.json`.

## Current status

Research only. No NDV runtime, router, orchestrator, memory system, generic agent framework, model gateway, or controller is approved for implementation.

See `AGENTS.md` and the governance documents under `docs/` before making changes.