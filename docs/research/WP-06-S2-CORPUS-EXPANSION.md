# WP-06 — P1-S2 Corpus Expansion

## Purpose

Expand the comparative development corpus under the historical verifier-first admissibility contract without exposing candidates to treatment execution during discovery.

The authoritative historical contract remains `oigorbrito/dv@66f3a218fba800daed5d86fdfce386491b8ab0e8:experiments/p1/task-admissibility-contract-v1.json`. The normative cutover corpus is `p1-development-corpus-v6`: four admitted tasks (`D-F2-05`, `D-F2-06`, `D-F5-01`, `D-F6-01`), three families, three repositories, still `comparative_corpus_ready=NO`.

The prospective contract is `experiments/p1/s2-corpus-intake-v1.json`. The operational target remains about nine admitted development tasks total, at least three families, three repositories, and two languages. This is a diversity target, not a power claim.

## Selection firewall

Treatment/model performance must not influence discovery or admission. No Wave-01 candidate may be exposed to an executor before `ADMITTED_FROZEN`. Gold solution fields, test-patch content, grader metadata, and holdout material remain admission-side only.

## Wave 01

`experiments/p1/s2-candidate-wave-01.json` contains six prospective SWE-rebench V2 candidates from six repositories and six languages (`ts`, `js`, `java`, `go`, `python`, `rust`). All remain `SCREENING`; admitted count is zero.

Source identity is frozen by `experiments/p1/s2-source-snapshot-01.json`: `nebius/SWE-rebench-V2`, train split, revision `475dd5e8703bb5fb22dd3c60b5d038b019eba1e0`, one 449,839,104-byte Parquet with frozen SHA-256 `0e0bf9355f892ad74ae98d4e1c404f39fd6654a8e351ee3e6ab162e4a64cd3ad`.

## Pinned acquisition

`experiments/p1/s2-parquet-acquisition-v1.json` and `tools/ndv_acquire_s2_pinned_parquet.py` define the explicit acquisition path. The operator-invoked command downloads only the exact dataset/revision/path into a `.part` file, fsyncs it, verifies frozen byte size and SHA-256, and only then atomically finalizes the destination. Existing mismatched files are never overwritten implicitly. The receipt records network use, source identity, expected/observed integrity, `treatment_execution=NOT_EXECUTED`, and `holdout_access=NONE`.

Acquisition is not performed by CI and has not yet been observed for Wave 01.

## Pinned extraction and row identity

```bash
python tools/ndv_extract_pinned_swe_rebench_rows.py \
  --parquet path/to/train-00000-of-00001.parquet \
  --wave experiments/p1/s2-candidate-wave-01.json \
  --snapshot experiments/p1/s2-source-snapshot-01.json \
  --out .ndv-corpus/s2-w01/pinned-rows.jsonl \
  --quarantine-out .ndv-corpus/s2-w01/quarantine
```

The extractor verifies Parquet SHA-256 and frozen revision, rejects duplicate/invalid `source_row_index`, binds each selected row to `instance_id` and `base_commit`, and writes `ndv-p1-s2-extracted-row-envelope-v1`. Each envelope stores the **original Parquet row index separately from the untouched upstream row**. This prevents compact selected exports (`0..N`) from being confused with original indices `0,2,3,12,15,23`. The raw row is not modified before hashing.

## Quarantine

`tools/ndv_quarantine_swe_rebench_rows.py` accepts a complete ordered raw export or indexed extraction envelopes. Mixed modes, duplicate indices, identity mismatch, and original-index mismatch fail closed.

For each candidate it produces `admission-only.json` (complete upstream row), `executor-visible.json` (strict allowlist projection), and `quarantine-manifest.json` (cryptographic binding). The executor allowlist is `instance_id`, `repo`, `base_commit`, `problem_statement`, and `language`. Known gold/grader fields (`patch`, `test_patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`, `interface`, `meta`, `install_config`, `pr_description`) are never projected; unknown future fields default to admission-only.

## Pre-solution base audit

`tools/ndv_run_s2_base_audit.py` consumes the quarantined artifact, re-hashes `full_row`, and rebinds candidate, instance, original row index, and raw-row hash. It requires an immutable Docker RepoDigest, `--network none`, and commands derived only from frozen `install_config.test_cmd`.

Before tests, the container proves exact `HEAD == base_revision` and a clean worktree. Every test command emits its own return-code marker, so a later success cannot mask an earlier failure. Missing HEAD/cleanliness/command markers yields `harness_integrity=FAIL`. Gold `patch` and `test_patch` are never applied.

## Oracle interpretation and verifier evidence

`tools/ndv_interpret_s2_base_oracle.py` requires base-audit schema v2 and `harness_integrity=PASS`, revalidates the quarantined row, then uses the frozen upstream parser. Allowed interpretations are `EXPECTED_BASE_BEHAVIOR`, `ORACLE_MISMATCH`, and `ENVIRONMENT_INCONCLUSIVE`. Missing preregistered tests remain `ORACLE_MISMATCH`; NDV does not repair them using gold/test-patch knowledge.

`tools/ndv_build_s2_verifier_evidence.py` freezes focal tests from `FAIL_TO_PASS`, preservation tests from `PASS_TO_PASS`, source-row index, raw-row hash binding, and parser content provenance. Gold patch content is not copied into verifier artifacts.

## Audit, decision, and immutable admission

`tools/ndv_validate_s2_audit.py` requires `AUDIT_PASS` evidence to include immutable image identity, harness integrity, expected base behavior, preservation PASS, verifier independence, no treatment/gold/test-patch contamination, and hashes for base run, oracle interpretation, focal verifier, preservation verifier, verifier provenance, **and environment evidence**.

`tools/ndv_decide_s2_admission.py` deterministically snapshots all evidence refs and hashes into `ndv-p1-s2-admission-decisions-v2`.

`tools/ndv_freeze_s2_admission.py` is independently fail-closed. It rejects wrong global schemas, treatment/holdout contamination, wave mismatch, stale decision refs/hashes, or missing byte evidence. Before emitting `ADMITTED_FROZEN`, it re-reads quarantine/admission/executor artifacts, re-hashes base/oracle/environment files, re-computes canonical JSON hashes for focal/preservation/provenance, and rechecks source identity. Well-formed declared hashes alone are insufficient.

## Validation

```bash
python tools/ndv_validate_corpus_intake.py experiments/p1/s2-candidate-wave-01.json
```

The validator requires unique non-negative `source_row_index` and unique `source_instance_id` values.

CI is `.github/workflows/wp06-corpus-intake-validation.yml`. It compiles and tests acquisition, extraction, original-index preservation, quarantine, base audit, oracle interpretation, verifier construction, audit validation, deterministic decision, and admission freeze. It performs no model calls, Parquet download, Docker candidate run, or treatment execution.

Latest validated state: WP-06 CI run `35146225089` completed successfully after the byte-verified/stale-decision admission gates were added.

## Current gate

`PINNED_PARQUET_ACQUISITION_PASS → INDEXED_FULL_ROW_EXTRACTION → QUARANTINE_PASS → HARNESS_VALID_BASE_RUN → EXPECTED_BASE_BEHAVIOR → HASHED_VERIFIER_EVIDENCE → AUDIT_PASS → SNAPSHOTTED_ADMISSION_DECISION → BYTE_VERIFIED_ADMITTED_FROZEN`.

Current empirical state: the pinned Parquet has **not** been locally materialized/verified by NDV in this wave; no Wave-01 base Docker audit has been executed; no candidate is admitted; holdout access is `NONE`; treatment execution is `NOT_EXECUTED`.

## Stop conditions and claims

Rejections are first-class results. Acquisition may pause when the diversity target is sufficient for the next scientific decision or marginal admission cost becomes unjustified.

WP-06 may support claims about source integrity, quarantine/leakage controls, verifier provenance, environment reproducibility, base behavior, admission, and corpus diversity. It cannot support executor ranking, routing benefit, economic superiority, architecture superiority, or NDV product claims.
