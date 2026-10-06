# Repository Steward Experiment: Native Closure Candidate Detection

## Status

PROTOCOL_DEFINED / NOT_EXECUTED

## Claim

A repository steward can detect closure candidates without custom semantic parsing by reusing GitHub's native issue-closing relationship.

## Prior art / reuse decision

GitHub natively:

- interprets supported closing keywords in pull request descriptions and commit messages;
- links a pull request to issues that it may close;
- exposes those relationships through GraphQL `PullRequest.closingIssuesReferences`;
- automatically closes linked issues when the pull request is merged into the repository default branch.

Therefore the first implementation candidate is REUSE, not BUILD CUSTOM.

## Scope

Observe only.

Given a merged pull request targeting the repository default branch:

1. read GitHub-native `closingIssuesReferences`;
2. read the referenced issue state;
3. if a referenced issue is still open, emit:

```text
CLOSURE_CANDIDATE
```

4. do not close, edit, label, or otherwise mutate the issue.

## Non-goals

- no regex parser for PR bodies;
- no LLM interpretation;
- no automatic issue closure;
- no inference from ordinary `#123` references;
- no inference from PR title alone;
- no inference for PRs merged into non-default branches;
- no cross-repository mutation;
- no replacement of GitHub's native closing-keyword semantics.

## Controlled cases

### C1 — positive native link

PR targets default branch and contains a supported closing keyword referencing an open issue.

Expected before merge:
- GitHub exposes the issue in `closingIssuesReferences`.

Expected after merge:
- normally GitHub closes the issue automatically.
- if the issue remains open for any reason, steward output is `CLOSURE_CANDIDATE`.

### C2 — ordinary reference only

PR body contains `#N` without a closing keyword.

Expected:
- not present as an auto-detected closing reference;
- no candidate emitted.

### C3 — non-default base

PR contains `Fixes #N` but targets a non-default branch.

Expected:
- GitHub closing-keyword semantics are not activated;
- no candidate emitted.

### C4 — already closed issue

GitHub-native closing reference exists but issue is already closed.

Expected:
- no candidate emitted.

### C5 — manually linked issue

Issue is manually linked to the PR.

Expected:
- record separately from auto-detected closing keyword evidence;
- do not treat it as keyword-derived evidence unless the query excludes user-linked references.

## Acceptance

The experiment passes only if the steward can distinguish:

- GitHub-native auto-detected closing references;
- manually linked references;
- ordinary textual references;
- non-default-branch references;

without parsing PR text itself.

## Authority

```text
READ = ALLOWED
REPORT = ALLOWED
CLOSE_ISSUE = FORBIDDEN
EDIT_ISSUE = FORBIDDEN
MERGE_PR = FORBIDDEN
```

## Decision rule

If native GitHub relationship data satisfies the experiment:

```text
DECISION = REUSE_GITHUB_NATIVE_SIGNAL
CUSTOM_PARSER = REJECTED
```

If it does not:

```text
DECISION = INCONCLUSIVE
NEXT = evaluate minimal wrapper before custom parser
```
