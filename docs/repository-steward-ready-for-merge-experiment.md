# Repository Steward Experiment: Ready-for-Merge Candidate Detection

## Status

`PARTIALLY_EXECUTED / POSITIVE_RULE_QUALIFIED / NATIVE_BLOCKED_STATES_NOT_PROVEN`

The positive readiness rule is implemented and executed. R4 conflict is proven with a live native observation. The live native states for R5–R7 remain unproven; synthetic matrix coverage is reported separately.

## Claim

A repository steward can report pull requests that are candidates for human merge by reusing GitHub-native readiness fields, without reconstructing branch protection or implementing semantic policy.

## Native fields

The observer reads:

- `state`;
- `isDraft`;
- `mergeStateStatus`;
- `mergeable`;
- `reviewDecision`;
- `statusCheckRollup.state`;
- base branch, head branch, and head SHA.

The observer is triggered by the explicit PR comment `/readiness-observe`. It runs from the default branch so it does not add its own check to the PR being observed. Its permissions are read-only; it reports a candidate and cannot merge.

## Approved positive rule

The classifier emits `READY_FOR_MERGE_CANDIDATE` only when every field is known and these conditions hold:

```text
state == OPEN
AND isDraft == false
AND mergeStateStatus == CLEAN
AND mergeable == MERGEABLE
AND statusCheckRollup.state == SUCCESS
```

`mergeStateStatus` alone is insufficient: a draft PR was observed with `mergeStateStatus=CLEAN`. Unknown draft, merge-state, or mergeability values fail closed. Missing or non-success check rollup cannot produce readiness.

This is a report-only candidate classification. It does not authorize a merge or reconstruct repository policy.

## Implementation and executed classifier evidence

- Read-only observer and shared classifier are in `.github/workflows/repository-steward-readiness-observer.yml` and `.github/scripts/repository-steward-readiness-classifier.sh`.
- Observer implementation PR #47, head `3b985cc40d69fa6feb84428d0874117170ab0d12`, merged as `2a15108586c696e2304ded90bf11222b06fb6030`.
- PR #47 live positive observation: run `37414217414`, job `112109141086`; `OPEN / non-draft / CLEAN / MERGEABLE / SUCCESS -> READY_FOR_MERGE_CANDIDATE`.
- Original classifier matrix: run `37410180416`, job `112096641369`, merge ref `4454f616ed7221b6aad82a933d52d33dc34680a6`; shell syntax and matrix passed with `CLASSIFIER_MATRIX=PASS`.
- Follow-up PR #52 tightened the draft predicate to require exactly `false`; synthetic `draft=UNKNOWN` and `draft=null` return `READINESS_UNKNOWN`. Exact head `4f3cecc22b1d62812eb45fc1ba24f3668108af87`; classifier run `37415038278`, job `112111684060`, `CLASSIFIER_MATRIX=PASS`; all six head checks succeeded. Merged as `71352f6040646f6ad9e5bbf5380c0fe07b688713`.
- The executed synthetic matrix covers `BLOCKED`, `BEHIND`, unknown merge state, unknown mergeability, pending/missing checks, and unknown draft. This proves classifier behavior for those inputs, not that GitHub emitted each state in a live PR.

## Live native observations

### R1 — pending checks

PR #45 was open and non-draft while CodeQL checks were actually pending. GitHub reported `UNSTABLE / MERGEABLE / PENDING`, and the observer returned `NOT_READY_CHECKS`. REST inspection confirmed CodeQL Analyze (actions) and Analyze (python) were pending.

Result: `R1 PENDING_CHECKS = PASS`.

### R1 — checks complete

On the same PR #45 head after checks completed, GitHub reported `CLEAN / MERGEABLE / SUCCESS`; the observer returned `READY_FOR_MERGE_CANDIDATE`.

Run `37409113765`, job `112093307029`.

Result: `R1 CLEAN = PASS`.

### R2 — draft

The same PR #45 was converted to draft without changing the head. GitHub still reported `mergeStateStatus=CLEAN`, with checks successful. The observer returned `NOT_READY_DRAFT`.

Run `37409150158`, job `112093418903`.

Result: `R2 DRAFT = PASS`; `MERGE_STATE_STATUS_ALONE = REJECTED`.

### R4 — conflict

Post-merge integrated observer on fixture PR #48, head `2bb327f294c27f12fa4fe4200f0d713f9cbcc361):

```text
state=OPEN
draft=false
mergeStateStatus=DIRTY
mergeable=CONFLICTING
checks=SUCCESS
decision=NOT_READY_CONFLICT
```

Run `37414352582`, job `112109554882`.

Result: `R4 LIVE_NATIVE_OBSERVATION = PASS`.

### R5 — blocked by policy or review

Fixture PR #49 did not produce a block. Both the settled pre-merge run `37410839432`, job `112098698480`, and post-merge integrated run `37414415806`, job `112109746306`, observed `CLEAN / MERGEABLE / reviewDecision=NONE / SUCCESS`.

The ruleset read returned an empty list. The branch-protection read returned 403; this does not establish absence of protection. No reviewer was requested and no rule was changed.

Result: `R5 BLOCKED = NOT_PROVEN`.

### R6 — behind base

The divergent fixture PR #50 returned `CLEAN / MERGEABLE / SUCCESS`, not `BEHIND`, after checks settled (run `37410794935`, job `112098559804`). The post-merge smoke encountered `UNSTABLE / MERGEABLE / PENDING -> NOT_READY_CHECKS` (run `37414469141`, job `112109908382`), which did not exercise the behind state.

No branch policy was changed.

Result: `R6 BEHIND = NOT_PROVEN`.

### R7 — native unknown state

Fixture PR #51 first returned `UNSTABLE / PENDING` (run `37410910916`, job `112098914813`). The post-merge observation later returned `CLEAN / MERGEABLE / SUCCESS` (run `37414515006`, job `112110051188`). Neither observation returned a native unknown state.

The classifier's synthetic unknown-state cases passed, but that does not count as a live native observation.

Result: `R7 NATIVE_UNKNOWN = NOT_PROVEN`; `R7 SYNTHETIC_CLASSIFICATION = PASS`.

## Human-gate follow-up

On 2026-10-06, the repository owner authorized attempts to obtain controlled R5 and R6 observations.

- R5 remains `NOT_PROVEN`: no `CODEOWNERS` file or reviewer recipient was identified. No review was sent to a guessed person. The repository-protection endpoint remains unreadable to the active GitHub connection (403); no policy change was made.
- R6 remains `NOT_PROVEN`: the active GitHub connection has no branch-protection/ruleset write capability. No existing rule was changed, and the fixture observation remains `CLEAN` or pending checks rather than `BEHIND`.
- R7 remains `NOT_PROVEN` as a native state; no policy mutation can establish a transient GitHub `UNKNOWN` observation without an actual occurrence.

Authorization to attempt these tests is distinct from successful execution. These cases remain pending; no review request or repository rule change is claimed.

## Decision and authority

```text
REUSE_GITHUB_NATIVE_FIELDS = YES
MERGE_STATE_STATUS_ALONE = REJECTED
MINIMAL_READ_ONLY_WRAPPER = REQUIRED
CUSTOM_SEMANTIC_ENGINE = REJECTED

READ = ALLOWED
REPORT = ALLOWED
AUTO_MERGE = FORBIDDEN
AUTO_RELEASE = FORBIDDEN
BRANCH_DELETE = FORBIDDEN
APPROVE_PR = FORBIDDEN
REQUEST_REVIEW = FORBIDDEN
RERUN_CHECKS = FORBIDDEN
CHANGE_REPOSITORY_RULES = FORBIDDEN
```

Fixture PRs #48–#51 were closed without merge; branches were retained for traceability. No repository policy was changed.

## Current classification

```text
R1 pending checks          = PASS
R1 CLEAN                   = PASS
R2 draft                   = PASS
R4 conflict (live)         = PASS
R5 blocked (live)          = NOT_PROVEN
R6 behind (live)           = NOT_PROVEN
R7 unknown (live)          = NOT_PROVEN
R7 unknown (synthetic)     = PASS

POSITIVE_RULE_IMPLEMENTED  = YES
POSITIVE_RULE_EXECUTED     = PASS
LIVE_NATIVE_EXPERIMENT     = PARTIALLY_EXECUTED
```

R5 and R6 need repository-policy/review conditions that were not authorized for mutation. R7's native unknown state was not observed; no synthetic result is promoted to a live-state PASS.
