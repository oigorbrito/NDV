# Readiness v2 — executed interim evidence

## Classification

```text
PROTOCOL                  = FROZEN
IMPLEMENTATION            = IMPLEMENTED / OPT_IN
SYNTHETIC_MATRIX          = EXECUTED_PASS
LIVE_NATIVE_UNKNOWN       = EXECUTED_PASS (v2)
LIVE_NO_REVIEW_CANDIDATE   = EXECUTED_PASS (v2)
LIVE_REVIEW_VETO           = NOT_EXECUTED / BLOCKED_OPERATOR_AUTHORITY
V2_ACCEPTED               = NO
DEFAULT_PROTOCOL          = v1
R5_NATIVE_BLOCKED          = NOT_PROVEN
R6_NATIVE_BEHIND           = NOT_PROVEN
```

This report records v2 observations only. It does not rewrite v1 historical results. Implementation presence, merge and workflow success do not establish v2 acceptance.

## Identity and synthetic evidence

- Frozen six-field protocol: PR #57, freeze commit `e5df7d51e1c22d7f548097df9930ab5625c0c7a0`; merged as `4cc90c4626806a1209042ad8cee006decf4559e8`.
- Opt-in implementation: PR #58, exact head `c8f93127476560bcb81c3597b13bcb0ee813eb24`; merged as `45d227d81119e619a3e7e71b860614b00420bb48`.
- Hosted classifier run `37462410368`, job `112264992901`: actual logs contain `CLASSIFIER_MATRIX=PASS` and `CLASSIFIER_V2_MATRIX=PASS`.
- All six implementation-head checks succeeded: classifier, labeler, closure observe, Analyze (actions), Analyze (python) and CodeQL.
- Local shell syntax, YAML parsing and workflow query/assertion execution with controlled JSON responses passed. These are synthetic verification, not live GitHub observations.
- Default `/readiness-observe` still selects v1. Only `/readiness-observe-v2` selects v2. The v1 classifier file is unchanged.

## Live fixture

Fixture PR #59, unchanged head `4621120d2c223896ad2502a1f7ead12d72cca0ff`, base `main`. The fixture contains one documentation file and must never be merged. The implementation used for both native observations was `45d227d81119e619a3e7e71b860614b00420bb48`.

### Initial native UNKNOWN

Trigger comment `6016113578`; run `37462675955`, job `112265879255`. Actual query log:

```text
state=OPEN draft=false mergeStateStatus=UNKNOWN mergeable=UNKNOWN reviewDecision=NONE checks=SUCCESS base=main head=readiness-fixture/v2-review-veto head_sha=4621120d2c223896ad2502a1f7ead12d72cca0ff decision=READINESS_UNKNOWN protocol=v2
```

The workflow executed checkout, native query and report-only assertion. This native transient was encountered during the planned before-review measurement, without artificial input mutation. It establishes v2 fail-closed behavior for this native UNKNOWN occurrence. The first measurement did not establish the required positive before-review baseline.

### Settled no-review candidate

After native mergeability settled on the same head, trigger comment `6016130339`; run `37462793754`, job `112266273302`. Actual query log:

```text
state=OPEN draft=false mergeStateStatus=CLEAN mergeable=MERGEABLE reviewDecision=NONE checks=SUCCESS base=main head=readiness-fixture/v2-review-veto head_sha=4621120d2c223896ad2502a1f7ead12d72cca0ff decision=READY_FOR_MERGE_CANDIDATE protocol=v2
```

This satisfies the positive before-review part of the prospective live gate. It does not prove APPROVED handling natively; that enum has synthetic coverage only.

### Review-veto gate blocked

The controlled `REQUEST_CHANGES` action on fixture #59 was rejected by automatic approval review. Its stated reason was that the original review restriction has no explicit later user-authored override for the requested action. A subsequent GitHub reviews GET returned `[]`: no review was submitted.

No indirect method or alternative account was used to bypass the rejection. The after-review observation is NOT_EXECUTED. Synthetic CHANGES_REQUESTED/REVIEW_REQUIRED cases passed but cannot replace that missing live gate.

Fixture #59 remains open, head unchanged, pending explicit operator authorization for that single controlled review; close it without merge after the eventual observation. Earlier fixtures #48–#51 remain closed without merge. No branch was deleted and no repository rule changed.

## Acceptance boundary and remaining work

The prospective v2 claim remains unaccepted until a fresh changes-requested review on this fixture produces a verified native `NOT_READY_REVIEW` observation on the same head. Preserve the default v1 command until that gate passes and its evidence is independently inspected.

R5 native BLOCKED and R6 native BEHIND remain NOT_PROVEN. The connector still lacks branch-policy write operations and protection reads return HTTP 403. This restriction is separate from the rejected fixture review. R7 now has an actual UNKNOWN observation for the v2 observer; do not retroactively relabel the v1 experiment.

Primary project operations use `oigorbrito`. Only the explicitly selected, authorized fixture review would use `gmailum`. Steward authority remains READ/REPORT; no merge, approval, review request, rerun, release, rule change or branch deletion authority is delegated to its workflow.
