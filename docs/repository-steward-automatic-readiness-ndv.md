# NDV automatic readiness observation — prospective portability gate

## Scope and reuse decision

Reuse the GitHub-native `workflow_run` observer and commit-to-PR association wrapper from RJ commit `5ae90995d235714d622cbc0f7b81005efc62bb92`. Keep the NDV v1 and v2 classifier files unchanged. This changes invocation only, not the frozen decision protocol.

NDV has several CI names and dynamic CodeQL runs instead of RJ's single `ci` workflow. Listen for completed workflows using the native name glob, excluding this observer to prevent recursion. Accept only source events `pull_request` or `dynamic`; native association must identify exactly one OPEN PR whose current head equals the source head. Reject pagination, ambiguity, errors and obsolete heads. Recheck the head in the subsequent native readiness query.

The existing lightweight classifier workflow now tests every PR on its exact head, providing an automatic observation source for documentation-only PRs too. The observer checks out the default branch and consumes no PR artifacts or code. Permissions remain READ/REPORT. Manual commands remain available but are not required. Operator merge authorization does not grant merge authority to the steward.

## Frozen gate before activation

1. Inspect the diff: classifier blobs unchanged, read permissions, default-branch checkout, native association, head recheck and self-trigger exclusion.
2. On the exact implementation head, execute shell syntax, the existing v1/v2 matrix and the reused association matrix. Inspect logs and all head checks before operator merge.
3. After activation, open a minimal documentation fixture without posting an observer comment. Record fixture head, implementation commit, source run, observer run/job and actual ASSOCIATION / OBSERVATION lines.
4. Accept automatic invocation only if the native head association and v2 observation execute without adding the observer to the fixture head's check rollup. Accept a positive candidate only if the recorded native fields satisfy v2. Native transient states retain their actual classifications; do not fabricate them.
5. Close the fixture without merge, retain its branch and record evidence. Until gate 3–4 execution, automatic invocation is IMPLEMENTED / NOT_PROVEN, never PASS.

This gate does not reopen existing NDV v2 qualification or optional policy cases, and does not qualify unrelated NDV research PRs.

## Executed evidence — 2026-10-06

```text
DOCUMENTED = prospective gate above
IMPLEMENTED = PR #67 / merge c2c9d335c0e2d34af208f4f077c03f3ae9a636b4
EXACT_HEAD_SYNTHETIC = EXECUTED_PASS
AUTOMATIC_NATIVE_INVOCATION = EXECUTED_PASS
AUTOMATIC_PENDING_EXCLUSION = EXECUTED_PASS
AUTOMATIC_FAILURE_EXCLUSION = EXECUTED_PASS
SELF_INTERFERENCE_EXCLUSION = EXECUTED_PASS
ACCEPTED = automatic READ_REPORT invocation / recorded snapshots only
POSITIVE_READINESS_FIXTURE_68 = NOT_PROVEN
```

Implementation PR #67 head `2648a33a46fd71a5d484517e11570103500e10c9`, hosted run `37521362201`, job `112467297751`: actual TESTED_HEAD equals that head; CLASSIFIER_MATRIX=PASS, CLASSIFIER_V2_MATRIX=PASS and RUN_ASSOCIATION_MATRIX=PASS. All six exact-head checks succeeded before the authorized operator merge. Neither classifier blob changed.

Minimal fixture #68 head `0ef2dd58a9da98493510557cf7c801a6ec6e2841`, implementation `c2c9d335c0e2d34af208f4f077c03f3ae9a636b4`. Its comment list was empty. The fixture was closed without merge at `2026-10-06T19:50:01Z`; branch retained.

### Automatic classifier-completion snapshot

Source run `37521556066` (pull_request); observer run `37521576317`, job `112468060505`. Checkout, association, query and report-only assertion all actually executed.

```text
ASSOCIATION source_run=37521556066 source_head=0ef2dd58a9da98493510557cf7c801a6ec6e2841 pr=68
OBSERVATION state=OPEN draft=false mergeStateStatus=UNSTABLE mergeable=MERGEABLE reviewDecision=NONE checks=PENDING base=main head=readiness-fixture/ndv-automatic-invocation head_sha=0ef2dd58a9da98493510557cf7c801a6ec6e2841 decision=NOT_READY_CHECKS protocol=v2
```

### Automatic dynamic CodeQL-completion snapshot

Source run `37521551552` (dynamic); observer run `37521649583`, job `112468324808`. The native event was delivered after CI completed and triggered the query without a comment.

```text
ASSOCIATION source_run=37521551552 source_head=0ef2dd58a9da98493510557cf7c801a6ec6e2841 pr=68
OBSERVATION state=OPEN draft=false mergeStateStatus=UNSTABLE mergeable=MERGEABLE reviewDecision=NONE checks=FAILURE base=main head=readiness-fixture/ndv-automatic-invocation head_sha=0ef2dd58a9da98493510557cf7c801a6ec6e2841 decision=NOT_READY_CHECKS protocol=v2
```

The six fixture-head checks were inspected by job identity: classifier `112467987717`, CodeQL `112468161368`, Analyze(actions) `112467976524`, Analyze(python) `112467976481` and closure observe `112467990574` succeeded; labeler `112467989946` failed with its actual log `##[error]HttpError`. The closure observer's head check is distinct from readiness jobs `112468060505` and `112468324808`, which are absent from the fixture's head check rollup.

This is fail-closed evidence for the actual FAILURE rollup, not a clean candidate PASS. The labeler failure is preserved; no rerun was requested and no check was bypassed. No source code defect or root cause for that external HttpError is claimed.

### Native association rejects a default-branch source

Source main-push dynamic run `37521510263`; observer run `37521660495`, job `112468363490`:

```text
ASSOCIATION source_run=37521510263 source_head=c2c9d335c0e2d34af208f4f077c03f3ae9a636b4 decision=READINESS_UNKNOWN
```

No PR readiness query ran for this unmatched source. Native pagination, ambiguity and obsolete-head rejection also retain their separately executed synthetic association coverage.

### Acceptance boundary

The prospective automatic invocation gate passed within READ/REPORT scope. The rule and prior v2 qualification remain unchanged. Observations are snapshots; a positive candidate is never an authorization to merge, and an older head observation is not current-head acceptance. A later head change requires its own source event and current-head association.

This fixture proves automatic pending and failure exclusion, not automatic positive readiness. Existing historical NDV positive observations remain attributed to their original runs. The fixture's failed labeler does not block recording the correctly executed observer evidence or unrelated work. No branch deletion, issue closure, review, check rerun, release or repository-rule change occurred.
