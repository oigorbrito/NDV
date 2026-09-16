# WP-06 — Verifier Evidence and Admission Gate

## Scope

This block closes the prospective S2 admission path after source acquisition, quarantine, base execution and oracle interpretation. It does not execute any treatment or model.

## Verifier evidence

`tools/ndv_build_s2_verifier_evidence.py` consumes only admission-side metadata and frozen parser provenance. It produces four immutable artifacts:

- `focal-verifier.json` from `FAIL_TO_PASS`,
- `preservation-verifier.json` from `PASS_TO_PASS`,
- `verifier-provenance.json`,
- `bundle.json` binding the artifact hashes.

The builder deliberately does not copy `patch` or `test_patch` into any output. Parser identity must match the task's frozen `install_config.log_parser`.

## Audit gate

`tools/ndv_validate_s2_audit.py` requires an `AUDIT_PASS` record to contain authenticated evidence for:

- immutable image digest,
- base run,
- oracle interpretation,
- focal verifier,
- preservation verifier,
- verifier provenance,
- environment evidence.

The corresponding SHA-256 values for base, oracle, focal, preservation and provenance are mandatory. `oracle_classification` must be `EXPECTED_BASE_BEHAVIOR`, verifier independence must be true, base behavior must match expectation, and preservation baseline must pass.

## Deterministic admission decision

`tools/ndv_decide_s2_admission.py` joins the frozen discovery wave with audit state and emits one of:

- `ADMIT`, or
- `DO_NOT_ADMIT` plus explicit blockers.

A candidate is blocked if quarantine is incomplete, audit is not `AUDIT_PASS`, base oracle is not expected, verifier independence is unresolved, preservation fails, treatment execution contaminated admission, family is unassigned, or solution isolation is not proven.

This tool does not mutate the discovery wave.

## Immutable admission record

`tools/ndv_freeze_s2_admission.py` freezes a candidate only from an unblocked `ADMIT` decision. It creates an `ndv-p1-s2-admission-record-v1` artifact binding task identity, executor-visible task hash, quarantine evidence and all audit evidence.

The original discovery record remains historical. Admission is represented by a new immutable artifact rather than rewriting how the candidate was originally discovered.

## Treatment firewall

Until an admission record exists with `status=ADMITTED_FROZEN`, treatment execution remains forbidden for that candidate. Admission decisions must not consult model/treatment performance.

## Block outcome

At implementation level, the complete S2 intake path is now:

```text
pinned source
→ full-row extraction
→ quarantine
→ base environment run
→ oracle interpretation
→ focal/preservation evidence
→ audit validation
→ deterministic admission decision
→ immutable admission record
```

The six Wave-01 candidates remain unadmitted until the local evidence-producing stages are actually executed. The presence of tooling is not evidence that any candidate passed.
