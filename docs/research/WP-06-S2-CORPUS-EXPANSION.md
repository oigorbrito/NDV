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

`experiments/p1/s2-parquet-acquisition-v1.json` and `tools/ndv_acquire_s2_pinned_parquet.py` define the explicit operator-invoked acquisition path. The tool binds source snapshot and acquisition contract by file SHA-256, downloads only the exact dataset/revision/path into a `.part` file, fsyncs it, verifies frozen byte size and SHA-256, and only then atomically finalizes the destination. Existing mismatched files are never overwritten implicitly.

The acquisition receipt is `ndv-p1-s2-parquet-acquisition-receipt-v2`; it records hashes of the snapshot/contract bytes, exact expected/observed Parquet identity, network use, `treatment_execution=NOT_EXECUTED`, and `holdout_access=NONE`.

Acquisition is not performed by CI and has not yet been observed locally for Wave 01.

## Frozen extraction environment

`experiments/p1/s2-extraction-environment-v1.json` freezes the minimum materialization environment to Python 3.13.x and PyArrow 25.0.1. Network access during extraction is forbidden.

The extractor checks the environment contract before reading rows and records the observed Python/PyArrow versions in its result. `tools/ndv_materialize_s2_wave.py` independently verifies the same contract and binds its SHA-256 into the materialization receipt.

## Byte-bound materialization gate

`tools/ndv_materialize_s2_wave.py` is the only recommended post-acquisition entry point. It performs **no network access, Docker execution, model call, treatment, or holdout access**. Before extraction it revalidates:

- acquisition receipt schema/status;
- receipt → exact snapshot/contract file hashes;
- receipt/source `source_id`, dataset, pinned revision, and Parquet path;
- local Parquet size and SHA-256 against the frozen snapshot;
- receipt expected/observed byte identity against the local Parquet;
- frozen extraction-environment schema/hash and exact Python/PyArrow versions.

Only after those checks pass does it invoke the pinned extractor with quarantine. It then requires a complete `ndv-p1-s2-quarantine-aggregate-v2` where every Wave-01 candidate passed quarantine and writes `ndv-p1-s2-wave-materialization-receipt-v2`, binding the Parquet, acquisition receipt, wave file, extraction environment, extracted JSONL, and quarantine aggregate by SHA-256.

This separates network acquisition from corpus materialization while maintaining one cryptographic evidence chain.

## Pinned extraction and row identity

The extractor verifies Parquet SHA-256 and frozen revision, rejects duplicate/invalid `source_row_index`, binds each selected row to `instance_id` and `base_commit`, and writes `ndv-p1-s2-extracted-row-envelope-v1`. Each envelope stores the **original Parquet row index separately from the untouched upstream row**. This prevents compact selected exports (`0..N`) from being confused with original indices `0,2,3,12,15,23`. The raw row is not modified before hashing.

## Quarantine

`tools/ndv_quarantine_swe_rebench_rows.py` accepts a complete ordered raw export or indexed extraction envelopes. Mixed modes, duplicate indices, identity mismatch, and original-index mismatch fail closed.

For each candidate it produces `admission-only.json` (complete upstream row), `executor-visible.json` (strict allowlist projection), and `quarantine-manifest.json` (cryptographic binding). The executor allowlist is `instance_id`, `repo`, `base_commit`, `problem_statement`, and `language`. Known gold/grader fields (`patch`, `test_patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`, `interface`, `meta`, `install_config`, `pr_description`) are never projected; unknown future fields default to admission-only.

## Byte-bound base-audit planning

`tools/ndv_prepare_s2_base_audit_plan.py` is the handoff between corpus materialization and Docker execution. It **does not run Docker**. It consumes a completed materialization receipt v2 and:

1. revalidates the receipt → wave and receipt → quarantine-aggregate hashes;
2. requires the exact six-candidate set from the frozen wave;
3. re-reads every `admission-only.json` and `executor-visible.json`;
4. recomputes full-row, task-statement, and executor-projection hashes;
5. rechecks instance/repository/base-revision/original-row identity;
6. freezes one exact `ndv_run_s2_base_audit.py` argv per candidate;
7. leaves `image_digest=null` until the real base audit resolves the immutable Docker RepoDigest;
8. records `authorized_action=PRE_SOLUTION_BASE_AUDIT_ONLY`, model execution `NONE`, treatment `NOT_EXECUTED`, holdout `NONE`.

A materialized wave with altered admission bytes, altered executor projection, stale aggregate, missing candidate, duplicate candidate, or treatment/holdout contamination cannot produce `AUDIT_PLAN_READY`.

## Pre-solution base audit

`tools/ndv_run_s2_base_audit.py` consumes the quarantined artifact, re-hashes `full_row`, and rebinds candidate, instance, original row index, and raw-row hash. It requires an immutable Docker RepoDigest, `--network none`, and commands derived only from frozen `install_config.test_cmd`.

The container workdir derivation is no longer implicit. `experiments/p1/s2-verifier-environment-audit-v2.json` freezes the upstream provenance to `SWE-rebench/SWE-rebench-V2@c71902a8…:combine.Dockerfile.j2`, blob `b87c412b…`; that template defines `project_dir = "/<repo-name>"`, clones the repository there, and sets `WORKDIR project_dir`. The NDV runner derives exactly the same `/<repo-name>` path. Changes require a new audited contract revision.

RepoDigest resolution is also repository-bound. The runner no longer selects the first digest from Docker's `RepoDigests`: it normalizes the frozen `image_ref`, keeps only digests for that exact repository, rejects zero matches, and rejects multiple matching immutable digests as ambiguous.

Before tests, the container proves exact `HEAD == base_revision` and a clean worktree. Every test command emits its own return-code marker, so a later success cannot mask an earlier failure. Missing HEAD/cleanliness/command markers yields `harness_integrity=FAIL`. Gold `patch` and `test_patch` are never applied.

The upstream evaluator at the same frozen revision uses the same workdir and `install_config.test_cmd`, but applies both solution `patch` and `test_patch` before tests. NDV intentionally omits both in base mode to observe pre-solution behavior. Upstream evaluation uses host networking; NDV intentionally uses `--network none` for the admission-side base audit, so unavoidable network dependencies become environment-inconclusive rather than silently contaminating reproducibility.

## Oracle interpretation and verifier evidence

`tools/ndv_interpret_s2_base_oracle.py` requires base-audit schema v2 and `harness_integrity=PASS`, revalidates the quarantined row, then uses the frozen upstream parser. Allowed interpretations are `EXPECTED_BASE_BEHAVIOR`, `ORACLE_MISMATCH`, and `ENVIRONMENT_INCONCLUSIVE`. Missing preregistered tests remain `ORACLE_MISMATCH`; NDV does not repair them using gold/test-patch knowledge.

`tools/ndv_build_s2_verifier_evidence.py` freezes focal tests from `FAIL_TO_PASS`, preservation tests from `PASS_TO_PASS`, source-row index, raw-row hash binding, and parser content provenance. Gold patch content is not copied into verifier artifacts.

## Audit, decision, and immutable admission

`tools/ndv_validate_s2_audit.py` requires `AUDIT_PASS` evidence to include immutable image identity, harness integrity, expected base behavior, preservation PASS, verifier independence, no treatment/gold/test-patch contamination, and hashes for base run, oracle interpretation, focal verifier, preservation verifier, verifier provenance, and environment evidence.

`tools/ndv_decide_s2_admission.py` deterministically snapshots all evidence refs and hashes into `ndv-p1-s2-admission-decisions-v2`.

`tools/ndv_freeze_s2_admission.py` is independently fail-closed. It rejects wrong global schemas, treatment/holdout contamination, wave mismatch, stale decision refs/hashes, or missing byte evidence. Before emitting `ADMITTED_FROZEN`, it re-reads quarantine/admission/executor artifacts, re-hashes base/oracle/environment files, re-computes canonical JSON hashes for focal/preservation/provenance, and rechecks source identity. Well-formed declared hashes alone are insufficient.

## Validation

```bash
python tools/ndv_validate_corpus_intake.py experiments/p1/s2-candidate-wave-01.json
```

The validator requires unique non-negative `source_row_index` and unique `source_instance_id` values.

CI is `.github/workflows/wp06-corpus-intake-validation.yml`. It compiles and tests acquisition, frozen extraction environment, byte-bound materialization, original-index preservation, quarantine, byte-bound base-audit planning, upstream image-layout provenance, repository-bound RepoDigest resolution, base audit, oracle interpretation, verifier construction, audit validation, deterministic decision, and admission freeze. It performs no model calls, Parquet download, Docker candidate run, or treatment execution.

Latest validated tooling/contract state: GitHub Actions run `35175549450` completed successfully.

## Current gate

`PINNED_PARQUET_ACQUISITION_PASS → BYTE_BOUND_WAVE_MATERIALIZATION → QUARANTINE_PASS → AUDIT_PLAN_READY → HARNESS_VALID_BASE_RUN → EXPECTED_BASE_BEHAVIOR → HASHED_VERIFIER_EVIDENCE → AUDIT_PASS → SNAPSHOTTED_ADMISSION_DECISION → BYTE_VERIFIED_ADMITTED_FROZEN`.

Current empirical state: the pinned Parquet has **not** been locally materialized/verified by NDV in this wave; therefore no real base-audit plan has yet been emitted from actual Wave-01 bytes, no Wave-01 Docker base audit has been executed, no candidate is admitted, holdout access is `NONE`, and treatment execution is `NOT_EXECUTED`.

## Stop conditions and claims

Rejections are first-class results. Acquisition may pause when the diversity target is sufficient for the next scientific decision or marginal admission cost becomes unjustified.

WP-06 may support claims about source integrity, quarantine/leakage controls, verifier provenance, environment reproducibility, base behavior, admission, and corpus diversity. It cannot support executor ranking, routing benefit, economic superiority, architecture superiority, or NDV product claims.
