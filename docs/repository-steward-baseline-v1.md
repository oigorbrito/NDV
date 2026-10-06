# Repository Steward Baseline v1

## Status

QUALIFIED_BY_EXECUTION

This baseline records only components that were reproduced from upstream examples and executed successfully in `oigorbrito/NDV`.

## Qualified components

| Component | Upstream version | Local deviation | Evidence |
|---|---|---|---|
| OpenSSF Scorecard | ossf/scorecard-action v2.4.4 | none in workflow behavior; upstream SHAs preserved | run 37403830939: analysis, artifact upload and code-scanning upload succeeded |
| actions/stale | v11.0.0 | `days-before-close: -1`; `delete-branch: false`; SHA pinning | run 37404213965: 18 items processed; job succeeded; no automatic close |
| actions/labeler | v7.0.0 | tag replaced by exact SHA | run 37404557948: PR touching `docs/**` received `documentation` label |
| github/issue-labeler | v3.5 | config path changed to `.github/issue-labeler.yml`; tag replaced by exact SHA | run 37404927563 / issue #24: `critical` label applied from upstream regex example |

## Authority boundary

Allowed automatically in the qualified baseline:

- read repository state;
- run security posture analysis;
- upload Scorecard SARIF/code-scanning results;
- mark stale candidates after upstream threshold;
- apply deterministic path-based PR labels;
- apply deterministic regex-based issue labels.

Explicitly not qualified:

- automatic issue closure;
- automatic PR closure;
- branch deletion;
- automatic merge;
- automatic release publication;
- semantic completion inference;
- supersession inference;
- CI infrastructure-vs-code diagnosis;
- automatic reconciliation of linked issues and PRs.

## Reproducibility constraints

- Actions are pinned to exact commit SHAs.
- Upstream examples are preserved unless a local deviation is explicitly documented.
- A component is not promoted to PASS from configuration presence alone.
- PASS requires an executed workflow/job/step and observable expected behavior.
- Test-only issues/PRs are not treated as project work evidence.

## Qualified baseline

```text
OpenSSF Scorecard     = EXECUTED_PASS
actions/stale         = EXECUTED_PASS
actions/labeler       = EXECUTED_PASS
github/issue-labeler  = EXECUTED_PASS
semantic reconciler   = NOT_IMPLEMENTED
```

## Next engineering gate

The next component must address a semantic gap not covered by the upstream automation above.

The first candidate is a deterministic reconciler rule with no LLM dependency:

```text
IF a merged PR contains an explicit GitHub closing keyword for an issue
AND the referenced issue remains open
THEN emit CLOSURE_CANDIDATE
ELSE do not infer completion
```

Initial authority: OBSERVE/REPORT ONLY.

No automatic closure is authorized by this baseline.
