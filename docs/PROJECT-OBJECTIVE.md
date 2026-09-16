# NDV Project Objective

## Research question

Can an adaptive meta-control layer choose the minimum sufficient combination of heterogeneous software-engineering capabilities so that verified task success is achieved with lower complete system cost and acceptable latency than fixed execution strategies?

## Scope

NDV studies decision-making above an ecosystem of models, coding agents, executors, tools, verifiers, runtimes, and orchestrators. It does not assume that any of those capabilities should be reimplemented.

The working interaction is:

`User -> NDV decision process -> selected external capability/composition -> evidence -> next decision`

Candidate actions include continue, verify, retry, switch, handoff, escalate, and stop.

## Optimization objective

Minimize complete system cost subject to a required level of verified success.

Complete cost includes execution, routing, task shaping, planning, context, coordination, verification, retry/replanning, handoff/escalation, latency, and applicable local/remote infrastructure costs.

Primary metric:

`TOTAL_SYSTEM_TOKENS / VERIFIED_SOLVED_TASK`

No single composite score should hide solve rate, monetary cost, latency, or failure distribution.

## Core principles

- Task first.
- Minimum sufficient composition.
- Each added layer must pay for itself.
- Verified evidence beats executor self-report.
- Continuity belongs to the task, not the executor.
- Transfer state only when it improves economics or reliability.
- Existing capabilities are preferred over custom implementations when they satisfy the required contract.
- If frontier agents solve the target distribution more cheaply without NDV, NDV should shrink or disappear.

## Non-goals

NDV is not, by default, a new orchestrator, multi-agent framework, memory platform, workflow engine, model gateway, sandbox, vector database, or provider SDK.

## Scientific decision outcomes

Valid outcomes include:

- `NO_BUILD`
- `REUSE_ONLY`
- `THIN_NDV`
- `FULL_NDV_JUSTIFIED`
- `INCONCLUSIVE`

The project is successful if it discovers that some or all proposed NDV capabilities are unnecessary.

## Historical relationship

This repository is the prospective successor to the research historically maintained in `oigorbrito/dv`. Historical experimental artifacts retain their original identity and provenance.