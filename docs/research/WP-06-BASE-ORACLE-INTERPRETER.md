# WP-06 — Base Oracle Interpreter

## Purpose

Convert an already-recorded pre-solution base-run log into explicit oracle evidence without executing a model, applying a solution patch, or changing the candidate workspace.

The implementation is `tools/ndv_interpret_s2_base_oracle.py`.

## Inputs

The interpreter requires:

1. the candidate `admission-only.json` produced by quarantine;
2. the corresponding `base-run.json` produced by `tools/ndv_run_s2_base_audit.py`;
3. a local checkout of `SWE-rebench/SWE-rebench-V2` at exactly `c71902a8cf8d2b725f63d51f199f4d3e56f68d2d`;
4. the recorded base-run log whose SHA-256 matches the base-run evidence.

The frozen parser implementation is loaded from `lib/agent/log_parsers.py` at that exact upstream revision. The parser name comes from admission-only `install_config.log_parser`.

## Preconditions

Interpretation refuses to proceed when:

- candidate instance identity differs between row and base run;
- base commit differs between row and base run;
- the base run reports either gold `patch` or `test_patch` as applied;
- the upstream checkout is not at the frozen revision;
- the recorded log hash does not match its evidence;
- the declared log parser is unavailable in the frozen parser registry.

## Classification

The result is one of:

- `EXPECTED_BASE_BEHAVIOR` — every preregistered `FAIL_TO_PASS` test is observed failing/erroring and every `PASS_TO_PASS` test is observed passing;
- `ORACLE_MISMATCH` — expected tests are missing, statuses conflict with the frozen expectations, or a bug-fix candidate contains no usable `FAIL_TO_PASS` expectation;
- `ENVIRONMENT_INCONCLUSIVE` — the frozen parser produces no test observations from the recorded base log.

These classifications describe admission evidence, not treatment performance.

## Command

```bash
python tools/ndv_interpret_s2_base_oracle.py \
  --admission-row .ndv-corpus/s2-w01/quarantine/<candidate>/admission-only.json \
  --base-run .ndv-corpus/s2-w01/audit/<candidate>/base-run.json \
  --upstream-root ../SWE-rebench-V2 \
  --out .ndv-corpus/s2-w01/audit/<candidate>/base-oracle.json
```

## Audit integration

`tools/ndv_validate_s2_audit.py` requires any future `AUDIT_PASS` record to include:

- `oracle_interpretation_ref`;
- `oracle_interpretation_sha256`;
- `oracle_classification = EXPECTED_BASE_BEHAVIOR`.

`ORACLE_MISMATCH` and `ENVIRONMENT_INCONCLUSIVE` must not be converted into pass by manual interpretation or by treatment output. They require explicit blocker/rejection handling under the audit contract.

## Non-goals

This interpreter does not:

- repair an oracle;
- select a treatment;
- execute an LLM;
- apply `patch` or `test_patch`;
- decide final candidate admission by itself.
