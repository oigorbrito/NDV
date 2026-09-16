# WP-06 — P1-S2 Corpus Expansion

## Purpose

Expand the comparative development corpus under the historical verifier-first admissibility contract without exposing candidates to treatment execution during discovery.

The authoritative historical contract remains `oigorbrito/dv@66f3a218fba800daed5d86fdfce386491b8ab0e8:experiments/p1/task-admissibility-contract-v1.json`. The normative cutover corpus is `p1-development-corpus-v6`: four admitted tasks (`D-F2-05`, `D-F2-06`, `D-F5-01`, `D-F6-01`), three families, three repositories, still `comparative_corpus_ready=NO`.

The prospective machine-readable contract is `experiments/p1/s2-corpus-intake-v1.json`. The operational target remains about nine admitted development tasks total, at least three families, three repositories, and two languages. This is a diversity target, not a universal power claim.

## Selection firewall

Treatment/model performance must not influence discovery or admission. No Wave-01 candidate may be exposed to an executor before `ADMITTED_FROZEN`. Gold solution fields, test-patch content, grader metadata, and holdout material remain admission-side only.

## Wave 01

`experiments/p1/s2-candidate-wave-01.json` contains six prospective SWE-rebench V2 candidates from six repositories and six languages (`ts`, `js`, `java`, `go`, `python`, `rust`). All remain `SCREENING`; admitted count is zero.

Source identity is frozen by `experiments/p1/s2-source-snapshot-01.json`. Admission requires the strong path: exact pinned Parquet revision, local SHA-256 verification, selected-row extraction, quarantine, verifier/environment audit, deterministic decision, then immutable admission freeze.

## Pinned extraction and row identity

Run:

```bash
python tools/ndv_extract_pinned_swe_rebench_rows.py \
  --parquet path/to/train-00000-of-00001.parquet \
  --wave experiments/p1/s2-candidate-wave-01.json \
  --snapshot experiments/p1/s2-source-snapshot-01.json \
  --out .ndv-corpus/s2-w01/pinned-rows.jsonl \
  --quarantine-out .ndv-corpus/s2-w01/quarantine
```

The extractor verifies the Parquet SHA-256 and frozen revision, rejects duplicate/invalid `source_row_index` values, binds each selected row to `instance_id` and `base_commit`, and writes `ndv-p1-s2-extracted-row-envelope-v1` records. Each envelope stores the **original Parquet row index separately from the untouched upstream row**. This prevents compact selected exports (`0..N`) from being confused with original indices such as `0,2,3,12,15,23`.

The raw row is not modified before hashing or admission preservation.

## Quarantine

`tools/ndv_quarantine_swe_rebench_rows.py` accepts either a complete ordered raw export or the indexed extraction envelopes. Mixed modes, duplicate source indices, identity mismatch, and original-index mismatch fail closed.

For each candidate it produces:

- `admission-only.json`: complete upstream `full_row` plus source binding;
- `executor-visible.json`: strict allowlist projection;
- `quarantine-manifest.json`: cryptographic binding and original row index.

The executor allowlist is currently `instance_id`, `repo`, `base_commit`, `problem_statement`, and `language`. Known gold/grader fields (`patch`, `test_patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`, `interface`, `meta`, `install_config`, `pr_description`) are never projected. Unknown future upstream fields default to admission-only.

## Pre-solution base audit

`tools/ndv_run_s2_base_audit.py` now consumes the quarantined artifact schema directly and re-hashes `full_row` before use. It refuses an admission artifact whose candidate, instance, original row index, or raw-row hash no longer matches.

The base run requires an immutable Docker RepoDigest, network disabled, and commands derived only from frozen `install_config.test_cmd`. Before tests, the container proves:

1. `git rev-parse HEAD == candidate.base_revision`;
2. the worktree is clean;
3. every frozen test command emits an independent return-code marker.

A later successful command can no longer mask an earlier failed command. Missing HEAD, cleanliness, or command markers yields `harness_integrity=FAIL`; such a run cannot support admission. `patch` and `test_patch` are never applied.

## Oracle interpretation and verifier evidence

`tools/ndv_interpret_s2_base_oracle.py` requires base-audit schema v2 and `harness_integrity=PASS`, revalidates the quarantined raw-row hash, then uses the frozen upstream parser. It classifies only:

- `EXPECTED_BASE_BEHAVIOR`,
- `ORACLE_MISMATCH`,
- `ENVIRONMENT_INCONCLUSIVE`.

If preregistered tests are missing from pre-solution evidence, the result remains `ORACLE_MISMATCH`; NDV does not repair this using gold/test-patch knowledge.

`tools/ndv_build_s2_verifier_evidence.py` also consumes the quarantined artifact directly and freezes focal tests from `FAIL_TO_PASS`, preservation tests from `PASS_TO_PASS`, exact source-row index, raw-row hash binding, and parser content provenance. Gold patch content is not copied into verifier artifacts.

`tools/ndv_validate_s2_audit.py`, `tools/ndv_decide_s2_admission.py`, and `tools/ndv_freeze_s2_admission.py` remain the downstream deterministic gates. Discovery history is never rewritten to manufacture admission.

## Validation

Static intake validation:

```bash
python tools/ndv_validate_corpus_intake.py experiments/p1/s2-candidate-wave-01.json
```

The validator now additionally requires unique non-negative `source_row_index` and unique `source_instance_id` values.

CI is `.github/workflows/wp06-corpus-intake-validation.yml`. It compiles the S2 admission tooling, validates the frozen Wave-01 metadata, and runs unit tests for extraction, original-index preservation, quarantine, Docker base-audit contract, oracle interpretation, and verifier-evidence construction. It performs no model calls, Parquet download, Docker candidate run, or treatment execution.

## Current gate

The tooling path is now:

`PINNED_PARQUET_SHA_PASS → INDEXED_FULL_ROW_EXTRACTION → QUARANTINE_PASS → HARNESS_VALID_BASE_RUN → EXPECTED_BASE_BEHAVIOR → HASHED_VERIFIER_EVIDENCE → AUDIT_PASS → ADMISSION_DECISION → ADMITTED_FROZEN`.

Current empirical state remains unchanged: the pinned Parquet has **not** been locally materialized/verified by NDV in this wave, no Wave-01 base Docker audit has been executed, no candidate is admitted, holdout access is `NONE`, and treatment execution is `NOT_EXECUTED`.

## Stop conditions and claims

Rejections are first-class results. Acquisition may pause when the diversity target is sufficient for the next scientific decision or marginal admission cost becomes unjustified.

WP-06 may support claims about source integrity, quarantine/leakage controls, verifier provenance, environment reproducibility, base behavior, admission, and corpus diversity. It cannot support executor ranking, routing benefit, economic superiority, architecture superiority, or NDV product claims.
