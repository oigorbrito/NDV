# Repository Steward Experiment: Native Closure Candidate Detection

## Status

EXECUTED_PASS

## Claim

A repository steward can detect closure candidates without custom semantic parsing by reusing GitHub's native issue-closing relationship.

## Reuse decision

GitHub natively:

- interprets supported closing keywords in pull request descriptions and commit messages;
- links a pull request to issues that it may close;
- exposes those relationships through GraphQL `PullRequest.closingIssuesReferences`;
- distinguishes automatically detected closing references from manually linked references;
- automatically closes supported references when a qualifying pull request is merged into the repository default branch.

Decision:

```text
DECISION = REUSE_GITHUB_NATIVE_SIGNAL
CUSTOM_PARSER = REJECTED
LLM_PARSER = REJECTED
WRAPPER_READ_ONLY = QUALIFIED
```

## Qualified wrapper

Workflow:

`.github/workflows/repository-steward-native-closure-observer.yml`

Authority:

```text
READ = ALLOWED
REPORT = ALLOWED
CLOSE_ISSUE = FORBIDDEN
EDIT_ISSUE = FORBIDDEN
MERGE_PR = FORBIDDEN
```

The workflow uses only read permissions for contents, issues and pull requests.

## Executed controlled cases

### C1 — positive native closing reference

Fixture:
- issue #28 open;
- PR #29 targeted `main`;
- PR body contained `Fixes #28`.

Observed:
- `auto_count=1`;
- `manual_count=0`;
- `open_auto_count=1`;
- PR was not merged during the fixture.

Result: PASS.

### C2 — ordinary textual reference

Fixture:
- issue #30 open;
- PR #31 targeted `main`;
- PR body contained a normal reference without a closing keyword.

Observed:
- `auto_count=0`;
- `manual_count=0`;
- `open_auto_count=0`.

Result: PASS.

### C3 — closing keyword on non-default base

Fixture:
- issue #32 open;
- PR #33 contained `Fixes #32`;
- base was `test/native-closure-c3-base`, not the repository default branch.

Observed:
- `auto_count=0`;
- `manual_count=0`;
- `open_auto_count=0`.

Result: PASS.

### C4 — already closed issue

Fixture:
- issue #34 was closed before PR creation;
- PR #35 targeted `main`;
- PR body contained `Fixes #34`.

Observed:
- `auto_count=1`;
- `manual_count=0`;
- `open_auto_count=0`.

Result: PASS.

### C5 — manually linked issue

Fixture:
- issue #37 remained open;
- PR #38 targeted `main`;
- PR body contained no closing keyword;
- issue #37 was linked manually through GitHub Development metadata.

Timeline evidence:
- issue #37 recorded `event=connected`;
- subject was PR #38.

Observer evidence:
- run `37407762669`;
- job `112089036493`;
- explicit log:

```text
OBSERVATION auto_count=0 manual_count=1 open_auto_count=0 merged=false base=main default=main
```

Result: PASS.

## Acceptance result

The experiment demonstrated that the native GitHub relationship data distinguishes:

- auto-detected closing references;
- manually linked references;
- ordinary textual references;
- non-default-branch references;
- already-closed issues;

without parsing pull request text.

```text
C1 = PASS
C2 = PASS
C3 = PASS
C4 = PASS
C5 = PASS

EXPERIMENT = EXECUTED_PASS
```

## Operational rule

The observer emits `CLOSURE_CANDIDATE` only when all of these are true:

```text
PR merged = true
PR base = repository default branch
auto-detected closing reference exists
referenced issue state = OPEN
```

Otherwise it emits `NO_CLOSURE_CANDIDATE`.

This is an observation/reporting decision only. No automatic issue closure is authorized.

## Rejected alternatives

Not justified by evidence:

- custom regex parsing of PR bodies;
- LLM-based semantic parsing;
- mutation of issues based only on inferred completion;
- treating manual links as closing-keyword evidence.

The qualified architecture remains REUSE first: GitHub-native relationship signal plus a minimal read-only wrapper.
