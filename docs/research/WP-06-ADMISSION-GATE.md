# WP-06 — Verifier Evidence and Admission Gate

## Scope

This gate closes the prospective S2 admission path after pinned source acquisition, quarantine, pre-solution base audit, and oracle interpretation. It performs no treatment/model execution.

The active audit contract is `experiments/p1/s2-verifier-environment-audit-v2.json`. Version 1 remains historical and is superseded before any Wave-01 empirical audit result was produced.

## Source and verifier binding

Admission-side artifacts remain bound to the original pinned source row, not merely to instance text. The chain carries:

- dataset revision,
- original `source_row_index`,
- source instance ID,
- canonical full-row SHA-256,
- task-statement SHA-256,
- executor-visible projection SHA-256.

`tools/ndv_build_s2_verifier_evidence.py` consumes the quarantined `admission-only.json`, revalidates the full-row hash, and emits v2 focal, preservation, provenance, and bundle artifacts. `patch` and `test_patch` content are not copied to verifier evidence.

## Base-audit integrity

An `AUDIT_PASS` cannot rely on a test exit code alone. The v2 base audit must independently prove:

- exact repository `HEAD == base_revision`,
- clean worktree before tests,
- immutable image RepoDigest,
- network disabled,
- no gold patch or test patch applied,
- return-code evidence for every frozen test command.

The resulting audit record must carry `harness_integrity=PASS`. A later successful command cannot hide an earlier failure.

## Oracle and preservation gate

`tools/ndv_interpret_s2_base_oracle.py` only interprets a v2, harness-valid base run. `AUDIT_PASS` requires:

- `oracle_classification=EXPECTED_BASE_BEHAVIOR`,
- `base_behavior_matches_expected=true`,
- `preservation_baseline_pass=true`,
- `verifier_independent=true`,
- all evidence refs and SHA-256 values,
- immutable image digest,
- `treatment_execution=NOT_EXECUTED`,
- both patch-application flags false.

Missing expected pre-solution tests remain `ORACLE_MISMATCH`; they are not repaired from `test_patch` or gold-solution knowledge.

## Direct-call fail-closed rule

Safety does not depend on running tools in the expected order.

`tools/ndv_validate_s2_audit.py`, `tools/ndv_decide_s2_admission.py`, and `tools/ndv_freeze_s2_admission.py` each independently recheck the critical gates. A forged `AUDIT_PASS` label, missing hash, harness failure, patch contamination, treatment contamination, invalid image digest, unresolved family, or missing source binding blocks admission even if an earlier validator was skipped.

The admission decision schema is `ndv-p1-s2-admission-decisions-v2` and emits `ADMIT` only when no blocker remains.

## Immutable admission record

`tools/ndv_freeze_s2_admission.py` creates `ndv-p1-s2-admission-record-v2` only from an unblocked decision and revalidates the same gates itself.

The frozen record binds the original row index and raw-row SHA to task identity, quarantine artifacts, executor-visible projection, image digest, harness integrity, oracle evidence, focal/preservation evidence, verifier provenance, and environment evidence. Discovery history is not rewritten.

Until such a record exists with `status=ADMITTED_FROZEN`, treatment execution remains forbidden for that candidate.

## Current state

The complete path is:

```text
pinned parquet identity
→ indexed full-row extraction
→ quarantine
→ harness-valid pre-solution base run
→ frozen oracle interpretation
→ focal/preservation/provenance evidence
→ audit validation
→ deterministic admission decision
→ source-bound ADMITTED_FROZEN record
```

All six Wave-01 candidates remain `SCREENING` / `WAITING_QUARANTINE`. No local pinned-Parquet verification, candidate Docker base audit, admission, holdout access, or treatment execution has been recorded for them. Tooling readiness is not empirical admission evidence.
