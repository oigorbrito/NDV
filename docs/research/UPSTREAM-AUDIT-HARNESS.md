# NDV Upstream Audit Harness

**Status:** ACTIVE  
**Version:** 1  
**Scope:** donor-project audit during `REUSE_ONLY`  
**Authority:** operational companion to `docs/research/UPSTREAM-REUSE-PLAN.md`  
**Nature:** evidence and decision harness; not an execution framework or benchmark implementation

## Purpose

Provide a repeatable way to audit upstream donor projects without turning the audit into a repair, porting, or reimplementation effort.

This harness exists to answer one question efficiently:

> Does an upstream donor already satisfy the unresolved NDV capability contract, and at what temporal/runtime granularity?

The harness is intentionally procedural. It does not introduce an NDV runtime, benchmark, router, controller, adapter, or agent loop.

## Empirical and software-engineering basis

The harness follows these principles:

1. **Immutable subject identity.** Record the canonical repository and exact commit/release before interpreting behavior.
2. **Separate claims from evidence.** README/paper claims, source-code observations, import/entry-point qualification, and runtime observations are recorded separately.
3. **Automate repeatable phases.** Setup, execution, verification, and cleanup should be explicit and scriptable when upstream already provides those mechanisms.
4. **Record the environment.** Python/runtime version, dependency state, platform constraints, required assets, and exact commands are evidence.
5. **Fail closed on missing provenance.** A successful later command does not erase an earlier identity, dependency, asset, or harness-integrity failure.
6. **No silent repair.** Missing datasets, stale checkpoints, incompatible pins, eager imports, provider drift, and broken examples are upstream reproducibility observations, not invitations to patch donor code.
7. **Minimal intervention.** Prefer upstream configuration and documented extension points. Do not edit donor implementation merely to make an audit pass.
8. **Explicit uncertainty.** If runtime confirmation is blocked, record `CODE_CONFIRMED_EXECUTION_BLOCKED` or `INCONCLUSIVE`; do not upgrade a source-code inference into an execution claim.
9. **Stop when the question is answered.** Do not reproduce a full paper or benchmark if the unresolved NDV contract has already been answered with sufficient evidence.
10. **Preserve negative evidence.** Operational friction and failed reproduction attempts remain part of the audit record.

These rules are consistent with ACM reproducibility guidance emphasizing explicit setup/run/cleanup phases, automated experiments, recorded runtime parameters and software versions, and artifacts sufficient for independent evaluation.

References:

- ACM SIGMOD Availability & Reproducibility Initiative: https://reproducibility.sigmodconf.hosting.acm.org/
- ACM SIGPLAN Empirical Evaluation Guidelines: https://www.sigplan.org/Resources/EmpiricalEvaluation/
- ACM Artifact Review and Badging: https://www.acm.org/publications/policies/artifact-review-and-badging-current

## Claim classes

Every conclusion must identify its strongest evidence class.

| Class | Meaning | Allowed wording |
| --- | --- | --- |
| `DOC_CLAIM` | README, paper, docs, or comments only | "Upstream claims..." |
| `CODE_CONFIRMED` | behavior located in pinned source code | "Source code implements..." |
| `ENTRYPOINT_QUALIFIED` | documented/imported entry point loads in a supported environment | "Entry point is operationally importable..." |
| `EXECUTION_CONFIRMED` | relevant upstream path executed with observable runtime behavior | "Execution demonstrated..." |
| `CODE_CONFIRMED_EXECUTION_BLOCKED` | source supports the conclusion but runtime qualification is blocked by upstream reproducibility constraints | "Code confirms X; runtime confirmation blocked by Y." |
| `INCONCLUSIVE` | evidence does not resolve the contract | no stronger conclusion permitted |

`DOC_CLAIM` alone is never sufficient to close a capability gate.

## Audit state machine

Each donor moves through the following states:

```text
ACQUIRED
  -> IDENTITY_PINNED
  -> STATIC_MAPPED
  -> ENTRYPOINT_PRECHECK
  -> MINIMAL_UPSTREAM_EXECUTION
  -> CONTRACT_DECISION
  -> STOP
```

A donor may terminate early as:

```text
UPSTREAM_ENVIRONMENT_BLOCKED
UPSTREAM_DEPENDENCY_DRIFT
UPSTREAM_ASSET_MISSING
UPSTREAM_CHECKPOINT_INCOMPATIBLE
UPSTREAM_ENTRYPOINT_BLOCKED
CODE_CONFIRMED_EXECUTION_BLOCKED
INCONCLUSIVE
```

These are audit outcomes, not reasons to build NDV code.

## Phase 1 — acquisition and identity

Record before installation or modification:

```text
canonical_repository
local_path
commit_sha_or_release
license
acquisition_date
working_tree_status
declared_runtime_versions
declared_dependency_files
```

Required checks:

```text
git status --short
git rev-parse HEAD
```

If the local tree is already modified, distinguish pre-existing modifications from audit-generated configuration or caches before using it as evidence.

## Phase 2 — static architecture mapping

Inspect only enough code to answer the unresolved contract.

Record:

```text
entry_points
controller_or_orchestrator
execution_loop
composition_units
state_handoff
selection_inputs
selection_outputs
feedback_path
cost_or_quality_objective
```

For adaptive systems, always classify **when** a decision changes:

```text
offline
training-time
per-dataset
per-query
per-episode
per-rollout
per-subtask
between-delegations
per-step
per-tool-call
during-active-executor
```

And classify **what** can change:

```text
model
reasoning/prompt
tools
memory/state
context
instructions
skills
subagents
topology/workflow
verifier
retry policy
handoff
```

The distinction between "can produce different architectures" and "can recompose during an active trajectory" is mandatory.

## Phase 3 — entry-point precheck

Use the upstream-supported runtime version.

Attempt the least expensive documented entry point first, normally:

```text
--help
import
dry-run
published minimal example
```

Record each failure by cause rather than repeatedly calling it a product defect.

Examples:

```text
DEPENDENCY_MISSING
DEPENDENCY_VERSION_DRIFT
RUNTIME_VERSION_UNSUPPORTED
CONFIG_REQUIRED_AT_IMPORT
EAGER_OPTIONAL_PROVIDER_IMPORT
ASSET_MISSING
CHECKPOINT_MISMATCH
```

A package-manager consistency check such as `pip check` proves only that installed packages are mutually satisfiable. It does not prove that all upstream requirements are installed or that the upstream environment is reproducible.

## Phase 4 — minimal upstream execution

Execution should be attempted only when all of the following hold:

1. the upstream path is relevant to the unresolved NDV contract;
2. required assets/checkpoints are available or documented;
3. the run can be bounded without editing donor implementation;
4. cost and external API usage are understood;
5. the run does not require rebuilding a benchmark or inventing an NDV harness.

Use, in order:

```text
upstream test
upstream example
upstream smoke/dry-run
upstream benchmark with upstream-exposed subset
existing external benchmark
```

Do not modify a donor solely to expose a smaller subset or to make an obsolete checkpoint load.

## Operational stop rule

Stop attempting runtime reproduction when the next step would primarily test or repair upstream packaging rather than the NDV capability contract.

Typical stop triggers:

- the relevant runtime semantics are already located in code and additional installation work concerns unrelated eager imports;
- the documented benchmark requires external assets not shipped with the repository;
- the current loader expects checkpoints not present in the pinned revision;
- the framework has an internal subset mechanism but does not expose it through the upstream entry point;
- bounded execution would require editing donor code, dataset, loader, benchmark, or checkpoint;
- full reproduction would be materially more expensive than the information gain for the current gate.

When stopping, preserve the strongest supported conclusion and explicitly record the runtime blocker.

## No-repair boundary

During `REUSE_ONLY`, do not perform any of the following merely to complete an audit:

```text
patch donor source
rename or convert checkpoints
rewrite dependency declarations
vendor missing algorithms
create a custom benchmark
create a custom execution loop
inject a hidden subset selector
change evaluation semantics
manufacture missing assets
```

Configuration-only changes are allowed when they use an existing upstream interface. They must be recorded and reverted or kept outside the donor working tree where practical.

## Evidence record

For each donor, record at minimum:

```text
donor
repository
commit
license
environment
working_tree_before
working_tree_after
question_under_test
documentation_claims
code_evidence
entrypoint_evidence
execution_evidence
runtime_blockers
temporal_granularity
mutable_dimensions
unresolved_gap
decision
next_gate
```

`working_tree_after` must separate:

```text
versioned_source_changes
configuration_changes
generated_caches
virtual_environment
logs
downloaded_assets
```

Never describe generated caches or a local virtual environment as donor source changes.

## Decision vocabulary

A donor audit closes with exactly one primary disposition:

```text
REUSE_AS_IS
REUSE_WITH_CONFIGURATION
REUSE_WITH_MINIMAL_ADAPTER
NO_BUILD
CODE_CONFIRMED_EXECUTION_BLOCKED
INCONCLUSIVE
GAP_PERSISTS_NEXT_DONOR
```

`REUSE_WITH_MINIMAL_ADAPTER` is unavailable unless the conditions in `UPSTREAM-REUSE-PLAN.md` Phase B are met.

`BUILD_CUSTOM_REQUIRED` is not an audit-harness outcome during the active `REUSE_ONLY` phase.

## Gate decision rule

For the current donor queue:

```text
if donor closes unresolved contract:
    record reuse decision
    STOP donor queue for that contract
elif donor contributes a distinct reusable capability but gap remains:
    record capability
    proceed to next donor
elif runtime is blocked but code resolves the temporal/capability question:
    record CODE_CONFIRMED_EXECUTION_BLOCKED
    proceed only if the next donor may close the remaining gap
else:
    record INCONCLUSIVE
```

Never convert "upstream is difficult to reproduce" into "NDV must implement it."

## Application to completed audits

### AOrchestra

Strongest evidence:

```text
EXECUTION_CONFIRMED
```

Observed adaptation boundary:

```text
between delegations / new SubAgent
```

Residual question:

```text
generic recomposition during an already-active executor
```

### MaAS

Strongest architectural evidence:

```text
CODE_CONFIRMED
```

Observed adaptation boundary:

```text
per query, before operator execution
```

Operational observations include:

```text
Python version constraint (<3.12)
dependency/version drift sensitivity
eager imports of unrelated tools/providers
configuration validation during import
HumanEval dataset absent from clone
current test loader checkpoint absent
versioned .pth artifacts not matching current loader naming
internal subset support not exposed by the CLI path
```

Therefore the correct audit posture is:

```text
MaAS contributes query-conditioned architecture selection.
The residual active-executor recomposition gap remains.
Do not repair MaAS merely to run a full HumanEval reproduction.
Proceed to AgentSquare after recording the operational blocker state.
```

## Cleanup and handoff

At donor close:

1. capture final `git status --short`;
2. do not commit secrets;
3. restore versioned configuration containing credentials;
4. remove only audit-generated caches/logs/venvs when safe and useful;
5. preserve commands, versions, blockers, and conclusions in the handoff;
6. start the next donor from its pinned identity, not from assumptions inherited from the previous implementation.

The audit is complete when another engineer can determine **what was proven, what was only inferred, what was blocked, and why work stopped** without repeating the investigation.
