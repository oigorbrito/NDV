# Repository Steward Experiment: Ready-for-Merge Candidate Detection

## Status

PROTOCOL_DEFINED / NOT_EXECUTED

## Claim

A repository steward can identify pull requests that are candidates for human merge by reusing GitHub-native merge state, without reconstructing branch protection or implementing custom semantic policy.

## Prior art / reuse decision

GitHub GraphQL exposes:

- `PullRequest.mergeStateStatus`;
- `PullRequest.mergeable`;
- `PullRequest.reviewDecision`;
- `PullRequest.statusCheckRollup`;
- `PullRequest.isDraft`.

GitHub documents `mergeStateStatus` values including:

- `CLEAN`: mergeable and passing commit status;
- `BLOCKED`: merge is blocked;
- `BEHIND`: head is out of date;
- `DIRTY`: merge commit cannot be created cleanly;
- `DRAFT`: blocked because the PR is draft;
- `UNSTABLE`: mergeable with non-passing commit status;
- `UNKNOWN`: state cannot currently be determined.

Repository rulesets currently returned by the REST API are empty. Branch-protection details are not readable through the installed integration, so the steward must not rebuild policy from incomplete repository settings.

Therefore the experiment treats GitHub's own aggregate merge state as the authoritative readiness signal.

## Scope

Observe/report only.

For an open pull request:

1. read `mergeStateStatus`;
2. read `mergeable`, `reviewDecision`, `statusCheckRollup.state`, `isDraft`, base branch and head SHA;
3. emit `READY_FOR_MERGE_CANDIDATE` only when the GitHub-native merge state is `CLEAN`;
4. otherwise emit a non-ready classification derived directly from the native state;
5. do not merge, approve, request review, dismiss review, rerun checks or modify branch protection.

## Controlled cases

### R1 — clean open PR

Expected:
- PR open;
- not draft;
- `mergeStateStatus=CLEAN`.

Decision:
`READY_FOR_MERGE_CANDIDATE`.

### R2 — draft PR

Expected:
- `mergeStateStatus=DRAFT` or explicit `isDraft=true`.

Decision:
`NOT_READY_DRAFT`.

### R3 — non-passing checks

Expected:
- `mergeStateStatus=UNSTABLE` or `statusCheckRollup.state` non-success.

Decision:
`NOT_READY_CHECKS`.

### R4 — merge conflict

Expected:
- `mergeStateStatus=DIRTY` and/or `mergeable=CONFLICTING`.

Decision:
`NOT_READY_CONFLICT`.

### R5 — policy/review block

Expected:
- `mergeStateStatus=BLOCKED`;
- supporting evidence may include `reviewDecision=REVIEW_REQUIRED` or `CHANGES_REQUESTED`.

Decision:
`NOT_READY_BLOCKED`.

### R6 — behind base

Expected:
- `mergeStateStatus=BEHIND`.

Decision:
`NOT_READY_BEHIND`.

### R7 — unknown

Expected:
- `mergeStateStatus=UNKNOWN`.

Decision:
`READINESS_UNKNOWN`.

## Acceptance

The experiment passes only if:

- readiness classification comes from GitHub-native fields;
- `CLEAN` is not inferred from the absence of visible failures;
- missing branch-protection visibility does not get converted into PASS;
- a green workflow alone is not sufficient for `READY_FOR_MERGE_CANDIDATE`;
- no mutation is required to classify a PR.

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

## Decision rule

If GitHub-native merge state is sufficient:

```text
DECISION = REUSE_GITHUB_MERGE_STATE
CUSTOM_READINESS_ENGINE = REJECTED
```

If it is not sufficient:

```text
DECISION = INCONCLUSIVE
NEXT = evaluate minimal read-only wrapper around native fields
```
