# NDV

**Research program for minimum-sufficient composition of software-engineering capabilities.**

NDV investigates whether adaptive selection of the **smallest sufficient combination of capabilities** can improve the verified-success / total-cost / latency frontier relative to fixed execution strategies.

NDV is **not an approved software architecture**.

It is research-first, falsification-driven, and explicitly allows:

```text
NO_BUILD
REUSE_ONLY
INCONCLUSIVE
```

as valid outcomes.

---

## Research question

The core question is not:

> How do we build another orchestrator?

It is:

> **Which capabilities are actually necessary for a given class of software-engineering task, and when does their benefit exceed their total system cost?**

The unit of analysis is **capability**, not repository identity.

Models, agents, runtimes, verifiers, orchestrators, memory systems, routers, and future tools are treated as replaceable candidate mechanisms.

---

## Relationship to the other projects

NDV is intentionally separated from the operational/product repositories.

### CodePro

CodePro is an executable software-engineering chassis with operational contracts, qualification tooling, telemetry, verification, and real-task evidence boundaries.

NDV is broader and more research-oriented:

```text
NDV
  asks which capability composition should exist

CodePro
  implements and measures a bounded software-engineering chassis
```

NDV results may justify reuse, removal, or later experimentation in another system. They do not automatically promote a CodePro mechanism.

### MetaO

MetaO asks how to govern heterogeneous runtimes/orchestrators under an external control plane.

NDV asks whether a composition/control layer is economically justified in the first place.

A valid NDV result could therefore be:

```text
NO_ADDITIONAL_CONTROL_LAYER_REQUIRED
```

### SMAG / SMAG-ReX

Those projects have operational/governance responsibilities.

NDV may study mechanisms related to execution, routing, handoff, decomposition, or composition, but research evidence remains separate from product promotion.

---

## Core principle

Use the ecosystem to NDV's advantage rather than rebuilding it.

Default engineering order:

```text
REUSE
  ↓
ADAPT
  ↓
WRAP
  ↓
FORK
  ↓
BUILD CUSTOM
```

A new layer must pay for its own overhead.

Default execution concept:

```text
minimum sufficient composition
        ↓
external execution
        ↓
independent evidence
        ↓
continue / verify / retry / handoff / escalate / stop
```

---

## Primary economic objective

Minimize complete system cost subject to a required probability of verified success.

Primary metric:

```text
TOTAL_SYSTEM_TOKENS
────────────────────
VERIFIED_SOLVED_TASK
```

Token count alone is not the full cost model.

Accounting retains:

- monetary cost;
- latency;
- retries;
- calls;
- context;
- verification;
- routing;
- handoff;
- coordination;
- compute;
- failure cost;
- operational complexity.

```text
FREE != ZERO_COST
```

---

## Scientific posture

NDV starts from the assumption that its hypotheses may be wrong.

```text
research
  ↓
hypothesis
  ↓
controlled test
  ↓
evidence
  ↓
decision
  ↓
implementation only if justified
```

Important rules:

```text
EXECUTOR_DONE != VERIFIED_SOLVED
SYNTHETIC_PASS != PRODUCT_PROMOTION
UPSTREAM_FEATURE_EXISTS != LOCAL_NEED
MECHANISM_AVAILABLE != MECHANISM_NECESSARY
```

Mandatory architecture capabilities normally require holdout-confirmed evidence before becoming core.

---

## Current engineering mode

The current upstream-reuse phase is explicitly:

```text
REUSE_ONLY
```

Before custom implementation is justified, NDV audits whether the required behavior already exists in upstream projects and can be reused through configuration, existing extension points, adapters, or bounded wrappers.

The phase exits only when evidence supports one of two outcomes:

1. upstream capability is sufficient -> `REUSE_ONLY` / `NO_BUILD`;
2. a concrete gap remains and cannot be closed without new implementation.

See:

- [Upstream Reuse Plan](docs/research/UPSTREAM-REUSE-PLAN.md)
- [Upstream Audit Harness](docs/research/UPSTREAM-AUDIT-HARNESS.md)

---

## Experimental program

The research program is staged:

- **P1** — executor and routing economics
- **P2** — continuity and handoff
- **P3** — composition selection
- **P4** — sequential adaptive control
- **P5** — integrated-system validation

Later phases do not start merely because an earlier phase exists.

Negative evidence may eliminate later work entirely.

---

## Current implementation boundary

Research tooling and contracts may exist to make experiments reproducible.

That does **not** mean an NDV runtime has been approved.

Current status:

```text
NDV_RUNTIME            = NOT_APPROVED
ROUTER                 = NOT_APPROVED
ORCHESTRATOR           = NOT_APPROVED
MEMORY_SYSTEM          = NOT_APPROVED
GENERIC_AGENT_FRAMEWORK= NOT_APPROVED
MODEL_GATEWAY          = NOT_APPROVED
CONTROLLER             = NOT_APPROVED
```

This distinction is intentional.

Research infrastructure may be implemented while the architecture being studied remains unselected.

---

## Historical provenance

The program was previously maintained in `oigorbrito/dv`.

Historical DV artifacts remain authoritative at their original repository and immutable commits.

Prospective NDV work is canonical in this repository from the cutover recorded in:

```text
provenance/dv-legacy-manifest.json
```

Historical evidence is not silently relabeled as new NDV evidence.

---

## Start here

Before changing the research program:

- read [AGENTS.md](AGENTS.md);
- read the governance and research documents under [docs/](docs/);
- preserve exact source/revision/environment identity for decision-bearing experiments.

The desired outcome is not “more architecture”.

The desired outcome is **the smallest composition that survives evidence**.
