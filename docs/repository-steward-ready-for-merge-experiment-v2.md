# Repository Steward Readiness Experiment v2 — Native Review Veto

## Status

`AUTHORIZED_FOR_CONTROLLED_QUALIFICATION / FROZEN / NOT_IMPLEMENTED / NOT_EXECUTED / NOT_ACCEPTED`

This is a separate prospective protocol version. It does not amend frozen v1 semantics, supersede historical PASS evidence, authorize a merge, or expand the steward's report-only authority. The owner instructed continuation on 2026-10-06 after the review-veto change was explained. This authorizes controlled v2 qualification, not acceptance or automatic merge. The default v1 command remains active until v2 acceptance.

## Triggering evidence

Fixture PR #49, head `699f24d099de1378b8df995c945216b6eaf80314`, received the owner's authorized controlled `CHANGES_REQUESTED` review `5428005185` from collaborator `gmailum`. V1 implementation `9f7bbcbc910a778bc3e31a900269f5c94e4d2187`, run `37460492814`, job `112258556785`, actually reported:

```text
OPEN / false / CLEAN / MERGEABLE / CHANGES_REQUESTED / SUCCESS
=> READY_FOR_MERGE_CANDIDATE
```

That is faithful execution of the approved five-field rule, but it does not qualify review-veto handling. Native R5 BLOCKED remains NOT_PROVEN. V2 must not relabel this v1 observation as a v2 result.

## Frozen claim and minimal adaptation

Continue reusing GitHub-native fields and add one native review-decision conjunct. Do not reconstruct protection rules, count approvals, implement semantic policy, or add merge automation.

```text
state == OPEN
AND isDraft == false
AND mergeStateStatus == CLEAN
AND mergeable == MERGEABLE
AND statusCheckRollup.state == SUCCESS
AND reviewDecision IN {APPROVED, NONE}
```

`NONE` is only an explicit GraphQL null on a present `reviewDecision` field in a successful response with no GraphQL errors. A missing field, malformed response, query failure, or unrecognized enum is unknown and cannot become NONE. NONE does not establish that branch protection is absent; the candidate still needs human assessment.

- `CHANGES_REQUESTED` or `REVIEW_REQUIRED` veto readiness with `NOT_READY_REVIEW` when other prerequisite fields are valid.
- Unknown review values fail closed with `READINESS_UNKNOWN`.
- Existing draft, conflict, BLOCKED, BEHIND, pending/missing-check and unknown-state exclusions remain mandatory. The positive result is impossible unless every required input is valid.
- Decision precedence: invalid response/extraction -> READINESS_UNKNOWN; otherwise apply v1 state, draft, conflict, BLOCKED, BEHIND, checks and mergeability exclusions in their existing order. Only a v1 candidate reaches the review predicate: CHANGES_REQUESTED/REVIEW_REQUIRED -> NOT_READY_REVIEW; APPROVED/NONE -> candidate; all other review values -> READINESS_UNKNOWN. Combined excluded inputs never produce a candidate.
- A single successful JSON response is required. All requested fields must be present with the expected native types. Nonempty or malformed GraphQL errors invalidate extraction. Explicit null check rollup maps to NONE and is not ready; missing/invalid rollup fields fail closed.
- Frozen synthetic matrix: APPROVED and explicit-null/NONE candidates; CHANGES_REQUESTED and REVIEW_REQUIRED vetoes on a CLEAN fixture; unrecognized review enum, missing review field, malformed review type, errored/partial/malformed/multiple JSON responses; every v1 exclusion; draft plus review veto; conflict plus review veto; pending checks plus review veto; missing check rollup and unknown mergeability. Required exact outputs follow the precedence above.

## Prospective qualification gates

1. Owner authorization and protocol freeze are recorded in this document before v2 implementation/testing. Freeze commit identifies the contract; later outcomes belong in a separate results document.
2. Versioned classifier and extraction adapter; active v1 behavior unchanged until the approved v2 replacement is independently verified.
3. Synthetic matrix on the exact v2 PR head: candidate with APPROVED and explicit null/NONE; CLEAN plus CHANGES_REQUESTED and REVIEW_REQUIRED; unknown, missing, malformed and errored review input; all existing v1 exclusions and combined invalid inputs. Shell syntax and meaningful matrix assertions must pass. Synthetic outcomes are not live-state evidence.
4. Live controlled fixture with successful checks and unchanged head: verify candidate before review; inject an authorized changes-requested review; independently inspect the native query and require `NOT_READY_REVIEW` despite a possible CLEAN state. Record exact fixture head, implementation SHA, review ID, run, job, and actual log. Close fixture without merge after observation.
5. Independently inspect checks and acceptance evidence before activating v2. A successful workflow without the required native inputs does not qualify the live gate.

Do not reuse a live review result from v1 as v2 evidence. Do not extend repetitions or tune classification to promote R5 BLOCKED, R6 BEHIND or R7 UNKNOWN to PASS.

## Remaining native-state gates

R5 BLOCKED still requires a real native policy block. R6 BEHIND requires usable administration of a controlled fixture-base branch with strict required-check policy; do not weaken or edit main policy. The GitHub connector currently has no branch-policy write operation and protection reads return HTTP 403. Leave R6 pending until that capability is available. R7 UNKNOWN remains NOT_PROVEN until the state actually occurs; no synthetic assertion can close it.

## Authority

The controlled human/operator fixture actions are separate from steward authority. The steward retains READ and REPORT only. It cannot merge, approve, request review, rerun checks, delete branches, release, or change repository rules. The secondary account is only the explicitly selected fixture reviewer; primary project operations use `oigorbrito`.
