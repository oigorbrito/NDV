# NDV Upstream Reuse Plan

**Status:** ACTIVE  
**Current engineering mode:** `REUSE_ONLY`  
**Applies to:** current NDV phase until an explicit exit decision is recorded  
**Authority:** complements `AGENTS.md`, `docs/ARCHITECTURE-GOVERNANCE.md`, and `docs/PROJECT-OBJECTIVE.md`

## Purpose

The current NDV phase exists to determine how much of the target capability is already implemented by upstream projects and can be reused directly.

The default assumption for this phase is:

> Do not create NDV implementation code. Run, inspect, measure, and compose existing donor projects first.

This is intentionally stricter than the repository-wide architecture order. The goal is to prevent the research program from drifting into a large custom harness, runtime, router, orchestrator, controller, or benchmark before the existing ecosystem has been exhausted.

## Current phase rule

### Phase A — upstream-first, zero custom implementation

While this document is ACTIVE:

- do not implement an NDV runtime;
- do not implement an NDV orchestrator;
- do not implement an NDV router or adaptive controller;
- do not implement a generic NDV agent framework;
- do not implement new memory/state infrastructure;
- do not implement a new benchmark or harness when an existing one can exercise the same contract;
- do not reproduce upstream algorithms locally merely to obtain tighter control over them;
- do not port or rewrite donor code unless reuse in place has first been shown impossible;
- do not add convenience abstractions that duplicate a donor project's existing interface.

Allowed work is limited to:

- discovering candidate donor projects;
- cloning or acquiring upstream repositories;
- pinning repository URL, license, commit SHA, release/tag, and dependency state;
- running each donor unmodified;
- reading and mapping its architecture and runtime behavior;
- recording which NDV capability contracts it already satisfies;
- recording gaps with direct code-level evidence;
- using upstream-provided tests, examples, benchmarks, and harnesses;
- adding documentation, provenance, evidence, configuration, and reproducibility metadata needed to evaluate reuse.

The desired outcome of Phase A is `REUSE_ONLY` whenever the existing ecosystem already satisfies the required contract.

### Phase B — minimal adapter exception

Minimal NDV-specific adapter code is not part of the default Phase A work.

An adapter may be introduced only after all of the following are recorded:

1. the donor implementation has been run successfully in its upstream form;
2. the required NDV contract cannot be exercised through an existing upstream interface;
3. the missing piece is integration glue rather than a reimplementation of donor behavior;
4. the adapter is smaller and lower-maintenance than a fork or rewrite;
5. the change has an explicit experiment or integration decision that needs it.

If approved, the adapter must:

- contain only translation, binding, protocol conversion, or configuration glue;
- delegate substantive behavior to the donor project;
- avoid copying donor algorithms into NDV;
- preserve donor provenance and license requirements;
- be removable if the upstream project later exposes the required interface.

## Donor-first evaluation order

The immediate candidate set identified for audit includes:

1. **AOrchestra** — primary candidate for runtime composition/orchestration reuse.
2. **MaAS** — candidate for automated agent-architecture search/adaptation and cost-aware selection.
3. **AgentSquare** — candidate for modular composition of agent capabilities.
4. **SkillOrchestra** — candidate for reusable skill/capability orchestration.
5. **ClawArena / ClawArena-Team** — candidate benchmark/harness for dynamic coordination and multi-agent orchestration.
6. **TwinRouterBench / Agent-as-a-Router** — candidate routing and cost/capability evaluation infrastructure.
7. **OpenHands / SWE-bench / TerminalBench** — candidate software-engineering execution and verification harnesses.

This list is a research queue, not an integration mandate. A donor should be added to NDV only if it satisfies a required contract more economically than alternatives.

Before a donor is treated as an NDV dependency, record its canonical repository, license, pinned commit or release, execution instructions, and the exact capability being reused.

## Audit protocol for each donor

For each candidate, answer from source code and execution evidence rather than README claims alone:

1. What decisions are made dynamically at runtime?
2. What can be composed, replaced, enabled, disabled, or delegated?
3. At what granularity does adaptation occur: task, subtask, step, tool call, agent, or model call?
4. Which of the following are selectable or mutable: model, tools, context, instructions, memory/state, verifier, retries, handoff, subagents?
5. Is there an explicit cost, quality, latency, or success objective?
6. Does the project preserve state across changes or handoffs?
7. Does it already expose composition/decomposition semantics under another name?
8. Which NDV contracts are already fully satisfied?
9. Which gaps remain after using the donor as intended?
10. Can each remaining gap be solved by configuration or an existing extension point before any adapter is considered?

## Reuse decision record

For every relevant capability, record one of:

- `REUSE_AS_IS`
- `REUSE_WITH_CONFIGURATION`
- `REUSE_WITH_MINIMAL_ADAPTER`
- `FORK_REQUIRED`
- `BUILD_CUSTOM_REQUIRED`
- `NO_BUILD`
- `INCONCLUSIVE`

`FORK_REQUIRED` and `BUILD_CUSTOM_REQUIRED` are not valid conclusions without code-level evidence showing why lower-cost reuse modes fail the required contract.

## Benchmark and test rule

Tests are not the product of this phase.

Prefer, in order:

1. donor project's own tests and examples;
2. donor project's published benchmark or evaluation harness;
3. an existing external benchmark already accepted by the relevant research community;
4. a thin NDV integration check;
5. a new NDV benchmark only when the required property cannot be measured by the previous four options.

A new test must answer a specific unresolved NDV question. Do not create test matrices merely because they are possible.

## Provenance requirement

For every donor used in evidence, record at minimum:

- canonical repository;
- commit SHA or immutable release/tag;
- license;
- acquisition date;
- local modifications, if any;
- exact command used to execute;
- environment/dependency information required for reproduction.

Never present donor code or donor evidence as if it originated in NDV.

## Exit criteria for REUSE_ONLY mode

This document remains ACTIVE until at least one of the following is recorded:

1. the required NDV behavior is fully available upstream, producing a `REUSE_ONLY` or `NO_BUILD` outcome; or
2. a concrete capability gap remains after the relevant donor projects have been run and inspected, and the gap cannot be closed through configuration or existing extension points.

Only case 2 can justify moving from Phase A to the minimal-adapter exception.

A move beyond minimal adapters requires a separate architecture decision supported by experimental evidence.

## Immediate next action

Start with AOrchestra.

Do not write NDV runtime code before the audit.

The first deliverable is a code-level map of what AOrchestra already provides, what can be reused unchanged, and what — if anything — remains missing after upstream execution.
