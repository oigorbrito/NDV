# Repository Steward — live observer evidence

## 2026-10-07 live GitHub observations

The v2 observer was invoked through the production `issue_comment` trigger on two existing NDV pull requests. No PR mutation, approval, merge, rerun, or repository-rule change was performed by the observer.

### Open, clean candidate

PR #73, head:

`4bca3a2ec8b5ce45310c9bd4bc84df6a69398d0f`

Observer run:

`37699121824`

Job:

`113058049076`

Observed:

```
state=OPEN
draft=false
mergeStateStatus=CLEAN
mergeable=MERGEABLE
reviewDecision=NONE
checks=SUCCESS
decision=READY_FOR_MERGE_CANDIDATE
protocol=v2
```

The observer job concluded SUCCESS and only asserted that the decision belonged to the report-only decision set.

### Draft, clean candidate

PR #3, head:

`b02bb63bd4e5425f154d7a87426180897df1b678`

Observer run:

`37699178080`

Job:

`113058224423`

Observed:

```
state=OPEN
draft=true
mergeStateStatus=CLEAN
mergeable=MERGEABLE
reviewDecision=NONE
checks=SUCCESS
decision=NOT_READY_DRAFT
protocol=v2
```

This is additional live evidence that `mergeStateStatus=CLEAN` does not override `isDraft=true`.

## Acceptance

These observations are **EXECUTED / PASS** for the observer's live READ/REPORT behavior in the two measured states.

They do not authorize merge and do not qualify unobserved states. Conflict, blocked, behind, review-veto, API failure during observation, and check-wait exhaustion remain governed by their previously recorded evidence status.
