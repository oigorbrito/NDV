# Repository Steward Experiment: Ready-for-Merge Candidate Detection

## Status

PARTIALLY_EXECUTED / NATIVE_FIELD_ENSEMBLE_REQUIRED

## Claim

A repository steward can identify pull requests that are candidates for human merge by reusing GitHub-native readiness fields, without reconstructing branch protection or implementing semantic policy.

## Native fields

The observer reads:

- `mergeStateStatus`;
- `mergeable`;
- `reviewDecision`;
- `statusCheckRollup.state`;
- `isDraft`;
- base branch and head SHA.

The experiment no longer treats `mergeStateStatus` alone as authoritative. Executed evidence showed that a draft PR can still report `mergeStateStatus=CLEAN`.

## Observer harness correction

The original `pull_request_target` trigger caused self-interference because the observer itself became part of the PR check rollup while measuring readiness.

The harness was changed to explicit PR comment trigger:

```text
/readiness-observe
```

This runs the read-only observer from `main` without making the observer itself a pending check on the PR head.

## Executed evidence

### R1a — checks pending

Fixture: PR #45, open, non-draft.

Observed while CodeQL was still running:

```text
state=OPEN
draft=false
mergeStateStatus=UNSTABLE
mergeable=MERGEABLE
reviewDecision=NONE
checks=PENDING
decision=NOT_READY_CHECKS
```

REST check-run inspection showed the pending work was real: CodeQL `Analyze (actions)` and `Analyze (python)` had not yet completed.

Result: PASS for fail-closed pending-check behavior.

### R1b — clean open PR

Same PR #45, same head SHA, after all checks completed successfully.

Observed:

```text
state=OPEN
draft=false
mergeStateStatus=CLEAN
mergeable=MERGEABLE
reviewDecision=NONE
checks=SUCCESS
decision=READY_FOR_MERGE_CANDIDATE
```

Run: `37409113765`
Job: `112093307029`

Result: PASS.

### R2 — draft PR

The same PR #45 was converted to draft without changing the head SHA.

Observed:

```text
state=OPEN
draft=true
mergeStateStatus=CLEAN
mergeable=MERGEABLE
reviewDecision=NONE
checks=SUCCESS
decision=NOT_READY_DRAFT
```

Run: `37409150158`
Job: `112093418903`

Result: PASS for the wrapper, but disproves the stronger hypothesis that `mergeStateStatus` alone is sufficient.

## Interim decision

```text
REUSE_GITHUB_NATIVE_FIELDS = YES
MERGE_STATE_STATUS_ALONE = REJECTED
MINIMAL_READ_ONLY_WRAPPER = REQUIRED
CUSTOM_SEMANTIC_ENGINE = REJECTED
```

The current safe positive rule is:

```text
state == OPEN
AND isDraft == false
AND mergeStateStatus == CLEAN
AND mergeable == MERGEABLE
AND statusCheckRollup.state == SUCCESS
=> READY_FOR_MERGE_CANDIDATE
```

This remains a report-only candidate classification. It does not authorize merge.

## Remaining controlled cases

Still not executed:

- R4 — merge conflict;
- R5 — policy/review block;
- R6 — behind base;
- R7 — unknown state.

These cases remain NOT_PROVEN and must not be inferred from R1/R2.

## Authority

```text
READ = ALLOWED
REPORT = ALLOWED
MERGE_PR = FORBIDDEN
APPROVE_PR = FORBIDDEN
REQUEST_REVIEW = FORBIDDEN
RERUN_CHECKS = FORBIDDEN
CHANGE_REPOSITORY_RULES = FORBIDDEN
```

## Current classification

```text
R1 pending checks = PASS
R1 clean          = PASS
R2 draft          = PASS
R4 conflict       = NOT_PROVEN
R5 blocked        = NOT_PROVEN
R6 behind         = NOT_PROVEN
R7 unknown        = NOT_PROVEN

EXPERIMENT = PARTIALLY_EXECUTED
```
