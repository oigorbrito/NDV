# Readiness v2 — executed qualification evidence

## Classification

```text
PROTOCOL                  = FROZEN
IMPLEMENTATION            = IMPLEMENTED
SYNTHETIC_MATRIX          = EXECUTED_PASS
LIVE_NATIVE_UNKNOWN       = EXECUTED_PASS (v2)
LIVE_NO_REVIEW_CANDIDATE   = EXECUTED_PASS (v2)
LIVE_REVIEW_VETO           = EXECUTED_PASS (v2)
V2_ACCEPTED               = YES / READ_REPORT_SCOPE
DEFAULT_PROTOCOL          = v2 / EXECUTED_PASS
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
- Initial opt-in implementation selected v1 by default. Following the live gate below, activation routes `/readiness-observe` and `/readiness-observe-v2` to v2; `/readiness-observe-v1` preserves historical reproduction. The v1 classifier file is unchanged.

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

### Authorized native review veto

The earlier controlled review attempt was rejected by automatic approval review because no explicit later user-authored override was present; a reviews GET then returned `[]`. That rejection was preserved without a bypass. On 2026-10-06, the owner explicitly authorized this single fixture review.

Collaborator `gmailum` submitted review `5428690062`, state `CHANGES_REQUESTED`, commit `4621120d2c223896ad2502a1f7ead12d72cca0ff`. Primary account `oigorbrito` posted trigger comment `6016765001`. Run `37467149253`, job `112280943711`, checked out implementation `e6eec2c55433449ec5036acb56c46cc70709e209`; the classifier and opt-in workflow are unchanged from the before-review measurement.

Actual query log:

```text
state=OPEN draft=false mergeStateStatus=CLEAN mergeable=MERGEABLE reviewDecision=CHANGES_REQUESTED checks=SUCCESS base=main head=readiness-fixture/v2-review-veto head_sha=4621120d2c223896ad2502a1f7ead12d72cca0ff decision=NOT_READY_REVIEW protocol=v2
```

The same-head positive baseline and native review veto both passed. This qualifies v2 within the frozen report-only scope. APPROVED and REVIEW_REQUIRED retain synthetic coverage only; this CLEAN observation does not establish native BLOCKED.

## Activation and cleanup

The activation change selects v2 for the standard command and retains explicit v1 reproduction. PR #61 activation head `5a7d5fb59174fb7e6d4b45d16d6cf495cc1c0187` passed all six exact-head checks. Hosted classifier run `37467590705`, job `112282415451`, recorded both classifier matrices PASS. It merged as `e587247197db28501f1ad27cc9946ee28d77bbbe`.

Default-command trigger `/readiness-observe`, comment `6016858543`, run `37467755522`, job `112282980804`, used that implementation and encountered native UNKNOWN; it returned READINESS_UNKNOWN protocol=v2. A settled observation, comment `6016869589`, run `37467828436`, job `112283228723`, used the same implementation and fixture head:

```text
OBSERVATION state=OPEN draft=false mergeStateStatus=CLEAN mergeable=MERGEABLE reviewDecision=CHANGES_REQUESTED checks=SUCCESS base=main head=readiness-fixture/v2-review-veto head_sha=4621120d2c223896ad2502a1f7ead12d72cca0ff decision=NOT_READY_REVIEW protocol=v2
```

This verifies the default command actually runs v2 and preserves the native review veto. Fixture #59 was closed without merge on 2026-10-06T13:03:59Z; its exact head, branch and experimental review were retained. No additional review was submitted. Earlier fixtures #48–#51 remain closed without merge. No branch was deleted and no repository rule changed.

## Acceptance boundary and remaining work

V2 is accepted within the frozen report-only scope on the executed synthetic matrix and native same-head before/after gate. Acceptance does not authorize merging any observed candidate.

R5 native BLOCKED and R6 native BEHIND remain NOT_PROVEN. Ruleset `24581248` is now active and explicitly targets only `refs/heads/readiness-fixture/r6-base`; branch collection reports that fixture base protected. Its readable rules are only `deletion` and `non_fast_forward`, with no required status check or strict up-to-date requirement. This configuration does not establish BEHIND; R6 remains pending a human-controlled required-check policy on that fixture branch. The connector lacks branch-policy write operations and legacy protection reads return HTTP 403. This restriction is separate from the rejected fixture review. R7 now has an actual UNKNOWN observation for the v2 observer; do not retroactively relabel the v1 experiment.

Primary project operations use `oigorbrito`. The single explicitly authorized fixture review used `gmailum`. Steward authority remains READ/REPORT; no merge, approval, review request, rerun, release, rule change or branch deletion authority is delegated to its workflow.
