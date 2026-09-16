# WP-06 — Base Oracle Interpreter

## Purpose

Convert an already-recorded, harness-valid pre-solution base-run log into explicit oracle evidence without executing a model, applying a solution/test patch, or changing the candidate workspace.

Implementation: `tools/ndv_interpret_s2_base_oracle.py`.

## Inputs and binding

The interpreter requires:

1. quarantine `admission-only.json` with `full_row` and source binding;
2. a `ndv-p1-s2-base-audit-run-v2` report;
3. a local checkout of `SWE-rebench/SWE-rebench-V2` at exactly `c71902a8cf8d2b725f63d51f199f4d3e56f68d2d`;
4. the recorded stdout log matching `evidence.stdout_sha256`.

It re-hashes the admission `full_row`, checks source identity/base revision against the base run, requires `harness_integrity=PASS`, and rejects any run reporting gold or test patch application.

The frozen parser is `lib/agent/log_parsers.py` at that exact upstream revision; parser selection comes from the quarantined full row's `install_config.log_parser`.

## Classification

The v2 interpretation emits one of:

- `EXPECTED_BASE_BEHAVIOR`: every preregistered `FAIL_TO_PASS` test is observed failed/error and every `PASS_TO_PASS` test is observed passed;
- `ORACLE_MISMATCH`: expected tests are missing, statuses conflict, or no usable focal failures exist;
- `ENVIRONMENT_INCONCLUSIVE`: the frozen parser produces no test observations.

Missing expected tests are not filled from `test_patch`. A likely test-patch-dependent verifier is still an oracle blocker until independent pre-solution evidence exists.

These classifications concern admission evidence only, not treatment performance.

## Command

```bash
python tools/ndv_interpret_s2_base_oracle.py \
  --admission-row .ndv-corpus/s2-w01/quarantine/<candidate>/admission-only.json \
  --base-run .ndv-corpus/s2-w01/audit/<candidate>/base-audit-run.json \
  --upstream-root ../SWE-rebench-V2 \
  --out .ndv-corpus/s2-w01/audit/<candidate>/base-oracle.json
```

## Audit integration

Under `experiments/p1/s2-verifier-environment-audit-v2.json`, `AUDIT_PASS` requires the oracle interpretation hash and `oracle_classification=EXPECTED_BASE_BEHAVIOR` in addition to harness integrity, preservation, verifier independence, immutable environment identity, and no treatment/patch contamination.

`ORACLE_MISMATCH` and `ENVIRONMENT_INCONCLUSIVE` remain blockers/rejection evidence. They cannot be manually promoted using treatment output or gold knowledge.

## Non-goals

This interpreter does not repair an oracle, choose a treatment, execute an LLM, apply `patch`/`test_patch`, or decide final admission by itself.
