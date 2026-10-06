# Readiness reuse — Searchleads target register

## Decision and evidence boundary

Searchleads completed the target acceptance gate after the original two-profile contract was frozen. This is an additive evidence register, not a replacement manifest or a claim that every repository is qualified.

```text
DOCUMENTED = frozen target protocols and adaptation decisions
IMPLEMENTED = installed observer and two recorded target adaptations
EXECUTED = target synthetic matrices and native automatic observations
ACCEPTED = automatic READ/REPORT readiness in the recorded target scope
NEW_TARGET_BY_COPY = NOT_PROVEN until that target executes its acceptance gate
```

The source contract remains manifest v1 at NDV commit `3cd4c6bfa0a660e160d11ca9e16496d12692a878`; the chosen source profile is NDV `ed1698905f04f87c6792baf570544fe714bc059e`. Historical two-profile verification and original third-target NOT_PROVEN statements retain their original temporal scope.

## Pinned target and adaptations

Target repository: [oigorbrito/searchleads](https://github.com/oigorbrito/searchleads).
Accepted implementation activated at `b425caba891bc11b21f3736f2ee221f08a183cb7`; evidence merged at `450243c4de7223db5d2e0b10de737de403520d3d`.

Five of seven installed files remain identical to the chosen profile. The two adapted files are:

| Path | Target Git blob | Recorded adaptation |
| --- | --- | --- |
| `.github/scripts/repository-steward-readiness-classifier-v2.sh` | b1139508a580b17f0cda18fbbb64291357aaa8de | rename three discarded local bindings; field order and decisions unchanged |
| `.github/workflows/repository-steward-readiness-observer.yml` | 531a731750e6a2902a9ca85eab6f08c24b0943b8 | bounded native reread while automatic v2 reports pending checks |

The native positive ensemble remains OPEN, non-draft, CLEAN, MERGEABLE, SUCCESS, with native APPROVED or explicit null normalized to NONE. Missing, malformed or uncertain data stays fail-closed. No local branch-policy reconstruction, semantic LLM inference or write authority was added.

Original Searchleads Project4 automation failed for a missing token. The owner chose retirement instead of credential setup. Its removal is RETIRED / NOT_EXECUTED after retirement, never PASS. It is an unrelated target integration decision, not part of the reusable readiness bundle.

## Executed target gates

| Gate | Exact PR head | Run / job | Scope |
| --- | --- | --- | --- |
| Installation matrices | c4f246415865a634eff14f7f65d72c09d5b945f2 | 37526618538 / 112485127900 | literal head; existing v1, v2 and association matrices PASS |
| Transport matrices | 38e054854cc33b8ed842572b1664e7b86fa1764c | 37527196090 / 112487077001 | literal head; same three matrices PASS |
| Native classifier-source observer | 8091a0a19c6f0d51708c662e04b83723335a1e44 | 37527481317 / 112488054628 | source 37527458397; attempts 0–2 pending, attempt 3 candidate |
| Native application-source observer | 8091a0a19c6f0d51708c662e04b83723335a1e44 | 37527505845 / 112488141811 | source 37527458484; attempts 0–1 pending, attempt 2 candidate |

Both actual final observations on the same fixture head recorded:

```text
state=OPEN draft=false mergeStateStatus=CLEAN mergeable=MERGEABLE
reviewDecision=NONE checks=SUCCESS base=main
head_sha=8091a0a19c6f0d51708c662e04b83723335a1e44
decision=READY_FOR_MERGE_CANDIDATE protocol=v2
```

The observers executed from activated default-branch implementation b425caba; no PR code/artifacts or manual readiness command supplied these observations. Both observer jobs were absent from the fixture head check rollup. All five applicable fixture checks succeeded.

Application CI executed on native PR merge refs, separately from literal-head classifier execution. Python 3.11/3.12/3.13 each recorded 944 passed, 24 skipped, 1 xpassed. Skips and xpass are not new PASS evidence. Exact application jobs and Codacy checks are in the pinned target ledger.

Fixture [#156](https://github.com/oigorbrito/searchleads/pull/156) was closed without merge at 2026-10-06T20:35:55Z; its branch was retained. Installation [#155](https://github.com/oigorbrito/searchleads/pull/155), transport [#157](https://github.com/oigorbrito/searchleads/pull/157) and evidence [#158](https://github.com/oigorbrito/searchleads/pull/158) were operator-merged after applicable checks succeeded. Operator merge authorization grants no merge authority to the steward.

## Timing boundary and next installations

The initial single-query target observer only recorded pending checks; later external Codacy completion did not yield another workflow_run event. That initial head's automatic positive observation remains NOT_PROVEN.

The target adaptation permits an initial query plus at most six additional native queries, separated by ten-second waits, only for automatic v2 NOT_READY_CHECKS/PENDING. Every response is checked against the fixed source head. Other decisions stop; unknown/stale data does not gain more budget. The executed two observers used seven readiness queries, two association queries and fifty seconds aggregate configured sleep, plus API/job time.

Checks completing after the fixed budget are not guaranteed a settled automatic observation. This is a bounded report, not continuous monitoring. No budget enlargement, extra refresh or rerun was used to obtain acceptance.

Native budget exhaustion, head changes during reread, API errors, draft, conflict and optional policy/review states were not induced on Searchleads; no new native PASS is assigned. Existing synthetic/source coverage stays separately attributable. These are evidence limits, not a requirement to configure extra review rules for ordinary use.

For another target, choose the frozen source profile or explicitly record reuse of the pinned Searchleads adaptation. Preserve its limitations, inspect that target's CI, execute its matrices and minimal automatic fixture, record exact heads/runs/jobs and clean up the fixture without merge. Neither this register nor successful copying accepts another target.

No automatic merge, close, release, review, check rerun, rule mutation or branch deletion is enabled. Closure, labels, stale and Scorecard remain separate capability contracts.

## Authoritative target evidence

- [Pinned executed ledger](https://github.com/oigorbrito/searchleads/blob/450243c4de7223db5d2e0b10de737de403520d3d/docs/engineering/repository-steward-readiness-portability-evidence.md).
- [Pinned portability protocol](https://github.com/oigorbrito/searchleads/blob/450243c4de7223db5d2e0b10de737de403520d3d/docs/engineering/repository-steward-readiness-portability-protocol.md).
- [Pinned bounded-reread protocol](https://github.com/oigorbrito/searchleads/blob/450243c4de7223db5d2e0b10de737de403520d3d/docs/engineering/repository-steward-bounded-native-reread-protocol.md).
