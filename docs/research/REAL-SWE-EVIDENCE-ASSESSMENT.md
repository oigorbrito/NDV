# Real-SWE evidence assessment

Issue: #1  
Assessment date: 2026-09-18  
Decision: **COMPLEMENTARY**

## Scope

This note evaluates Specific Labs' September 2026 Real-SWE benchmark only as external evidence for NDV hypotheses around task-aware routing, model+harness selection, verifier-gated success, and cost per verified solved task.

It is not a benchmark reproduction and does not import leaderboard ordering as NDV architecture authority.

## Primary-source observations

Specific Labs states that Real-SWE uses licensed private production codebases and evaluates model+harness combinations rather than models in isolation. The public sample analysis covers ten tasks, with eight independent runs per task for each evaluated model+harness combination.

The benchmark page reports:

- resolution rate as pass@1 averaged over eight independent runs per task;
- isolated sandbox execution;
- Harbor task format;
- verifiers injected at grading time;
- verifiers inspired by or reusing existing codebase tests;
- per-model/harness mean rollout cost, output-token, tool-call, and wall-clock summaries;
- strong heterogeneity across tasks and failure categories.

The public page explicitly calls the shown set a small sample and offers sample access by request rather than publishing the private codebases as an ordinary public benchmark corpus.

## Reproducibility boundary

The following are not publicly available in a form sufficient for ordinary independent reproduction:

- the licensed private repositories;
- the complete benchmark corpus;
- all verifier implementations;
- raw per-rollout traces/artifacts for all reported runs;
- a public reproducible pipeline that an independent evaluator can execute against the same private source material.

A web search on 2026-09-18 found secondary analyses but no independent reproduction of the published Real-SWE run.

Therefore:

```text
PUBLISHER_RUN != INDEPENDENT_REPLICATION
PUBLIC_AGGREGATES != RAW_ROLLOUT_DATA
PRIVATE_TASK_ACCESS != PUBLIC_REPRODUCIBILITY
```

## Model-versus-harness attribution

Real-SWE intentionally measures complete model+harness combinations. That is useful for NDV's system-level executor-selection hypothesis, but it means the public results do not isolate scaffold quality from model quality.

Allowed use:

- evidence that end-to-end model+harness composition matters;
- evidence that task-specific heterogeneity is material;
- evidence that verifier-gated success should dominate self-report;
- evidence that cost and token use vary materially between compositions.

Disallowed use:

- claim that a model alone caused a published score;
- claim that a harness alone caused a published score;
- use leaderboard rank as direct executor authority in NDV.

## Cost/accounting fit

Specific Labs publishes mean estimated rollout costs and aggregate output-token/tool-call/wall-clock views by model+harness and task.

This is directionally compatible with NDV metrics such as:

```text
verified_success_rate
total_system_tokens / verified_solved_task
estimated_cost / verified_solved_task
failure_class / task_family
```

However the public material does not expose enough raw accounting detail to establish metric-equivalence with NDV's accounting contract. NDV should therefore treat the benchmark's cost/token values as external comparative signals, not directly merge them into internal accounting.

## Failure-taxonomy fit

The public failure taxonomy includes:

- unverified assumption;
- missed requirement;
- integration error;
- regression;
- wrong file.

These categories are useful as candidate external signals for NDV failure attribution and escalation design. They should be mapped explicitly rather than copied as canonical NDV categories.

## Independent commentary

Recent secondary coverage consistently notes the benchmark's main limitations:

- publisher-designed/run/graded;
- small public sample;
- private tasks/codebases constrain independent replication;
- model+harness confounding is intentional;
- adjacent leaderboard ordering should not be treated as precise authority.

No true independent replication was identified during this assessment.

## Decision

```text
REAL_SWE_EVIDENCE = COMPLEMENTARY
PRIMARY_ARCHITECTURE_AUTHORITY = NO
ROUTING_SIGNAL = YES_WITH_SCOPE
COST_SIGNAL = YES_WITH_SCOPE
FAILURE_TAXONOMY_SIGNAL = YES_WITH_SCOPE
INDEPENDENT_REPLICATION = NOT_FOUND
RAW_PER_ROLLOUT_PUBLIC_DATA = NOT_FOUND
MODEL_ONLY_ATTRIBUTION = NOT_SUPPORTED
HARNESS_ONLY_ATTRIBUTION = NOT_SUPPORTED
```

### Why not ADMISSIBLE as primary evidence

The benchmark is useful and materially relevant, but the current public evidence does not satisfy the stronger standard needed for independent reproducibility or causal attribution.

### Why not INCONCLUSIVE or REJECT

The methodology and published aggregate measurements are sufficiently concrete to inform hypothesis formation, external validity checks, task-aware routing experiments, and cost-aware experiment design.

## NDV usage rule

Real-SWE may inform experiment design and candidate metrics. It must not by itself:

- select a canonical executor;
- justify an architecture change;
- establish causal superiority of a model or harness;
- override NDV's own verifier/evidence gates;
- substitute for internal controlled trials.

NDV should test any derived hypothesis on its own controlled corpus and account all outcomes under its own evidence contract.

## Sources

Primary:
- Specific Labs, Real-SWE benchmark: https://realswe.withspecific.com/
- Specific Labs benchmark mirror/page: https://withspecific.com/benchmarks/real-swe

Secondary review used only for replication/limitations cross-check:
- VarOps: https://varops.com/coding-agents-most-common-failure-is-missed-requirements-not-broken-code-heres-what-to-check-in-a-pilot/
- Creative AI News: https://www.creativeainews.com/articles/real-swe-coding-agents-private-codebases-2026/

## Naming warning

Specific Labs' **Real-SWE** should not be conflated with separately named **RealSWE** research/papers unless provenance is explicitly checked. Similar naming is not evidence identity.
