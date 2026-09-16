# WP-06 — P1-S2 Corpus Expansion

## Purpose

Expand the comparative development corpus under the historical verifier-first admissibility contract without exposing candidates to treatment execution during discovery.

## Historical continuity

The authoritative historical admission contract remains in `oigorbrito/dv` at commit `66f3a218fba800daed5d86fdfce386491b8ab0e8`, path `experiments/p1/task-admissibility-contract-v1.json`.

The **normative development corpus at the DV→NDV cutover is `experiments/p1/p1-development-corpus-v6.json`**, not the earlier W8/v3 snapshot. Corpus v6 contains four admitted historical tasks: `D-F2-05`, `D-F2-06`, `D-F5-01`, and `D-F6-01`, spanning three families and three repositories. Its own frozen status is still `comparative_corpus_ready=NO`, with holdout sealed and no treatment execution.

Earlier corpus versions and W8 evidence remain valid historical snapshots of their time; they are not rewritten or deleted. They must not, however, be used as the cutover authority when a later superseding corpus exists in the same frozen DV commit.

## Prospective intake

The machine-readable intake contract is `experiments/p1/s2-corpus-intake-v1.json`.

Operational target:

- about 9 admitted development tasks in total,
- at least 3 task families,
- at least 3 repositories,
- at least 2 languages.

The four historical v6 admissions count toward historical corpus state; new NDV-native admissions must still pass the prospective NDV gate. This target is for useful comparative diversity, not a universal statistical power claim.

## Source priority

1. SWE-rebench V2 — primary development acquisition source.
2. OmniCode — secondary source for task-type diversity.
3. SWE-Bench Pro Verified — preserve where possible for later confirmation rather than tune on it immediately.
4. Terminal-Bench 2.0 — later heterogeneity/generalization source, not the primary P1-S2 SWE corpus.

A source being high priority does not admit any instance automatically.

## Candidate funnel

Every new NDV-native instance must pass, in order:

1. discovery and source metadata freeze,
2. exact pre-solution base identification,
3. full row acquisition from the pinned dataset revision,
4. admission-only / executor-visible quarantine split,
5. task-statement freeze and hash,
6. focal verifier identification,
7. verifier provenance and independence proof,
8. reproducible environment materialization,
9. base verifier execution,
10. preservation/regression baseline execution,
11. environment classification,
12. solution-isolation check,
13. exactly-one-family assignment,
14. explicit admission or rejection.

## Selection firewall

Treatment/model performance must not influence candidate selection. No prospective candidate should be exposed to a treatment executor until its admission disposition is frozen. Historical DV admissions retain their historical provenance; prospective NDV admissions use the NDV gate.

## Full-row quarantine

SWE-rebench V2 contains both executor-appropriate task text and fields that can leak gold-solution or grader information. Dataset preview snippets are discovery aids only and are insufficient for row integrity because they may be truncated.

An operator must acquire the source Parquet from the exact pinned dataset revision and verify it against `experiments/p1/s2-source-snapshot-01.json`. Then run:

```bash
python tools/ndv_extract_pinned_swe_rebench_rows.py \
  --parquet path/to/train-00000-of-00001.parquet \
  --wave experiments/p1/s2-candidate-wave-01.json \
  --snapshot experiments/p1/s2-source-snapshot-01.json \
  --out .ndv-corpus/s2-w01/pinned-rows.jsonl
```

The extractor refuses to proceed if the Parquet SHA-256, candidate instance identity, or base commit does not match the frozen source/wave metadata.

Then run:

```bash
python tools/ndv_quarantine_swe_rebench_rows.py \
  --rows .ndv-corpus/s2-w01/pinned-rows.jsonl \
  --out .ndv-corpus/s2-w01/quarantine
```

The quarantine tool creates, per candidate:

- `admission-only.json` — the complete upstream row for verifier/admission work;
- `executor-visible.json` — a strict allowlist projection;
- `quarantine-manifest.json` — hashes binding the two views to the same pinned source row.

It also creates `quarantine-aggregate.json` for the wave.

The executor-visible projection is allowlist-based, not merely a blacklist. Current allowed fields are `instance_id`, `repo`, `base_commit`, `problem_statement`, and `language`.

Known gold/grader fields remain admission-only, including at least `patch`, `test_patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`, `interface`, `meta`, `install_config`, and `pr_description`. Any future upstream field that NDV does not explicitly allow also remains admission-only by default.

A candidate cannot become admitted until the intake validator sees `quarantine_status=PASS` plus references and hashes for the quarantine artifacts.

## Verifier/environment audit

After quarantine, each candidate enters `experiments/p1/s2-audit-state-01.json` under `experiments/p1/s2-verifier-environment-audit-v1.json`.

The upstream SWE-rebench V2 `scripts/eval.py` is useful verifier prior art, but its normal evaluation path is not a base verifier because it applies the solution `patch` and `test_patch` before executing test commands. NDV therefore establishes pre-solution base behavior independently.

`tools/ndv_run_s2_base_audit.py` performs the pre-solution environment run. It requires an immutable Docker digest, derives commands only from frozen `install_config.test_cmd`, runs with Docker network disabled, never applies `patch` or `test_patch`, and records hashed stdout/stderr plus execution metadata.

`tools/ndv_interpret_s2_base_oracle.py` interprets that evidence with the frozen upstream parser and classifies only `EXPECTED_BASE_BEHAVIOR`, `ORACLE_MISMATCH`, or `ENVIRONMENT_INCONCLUSIVE`.

`tools/ndv_build_s2_verifier_evidence.py` then freezes focal evidence from `FAIL_TO_PASS`, preservation evidence from `PASS_TO_PASS`, and parser provenance without copying gold solution content.

`tools/ndv_validate_s2_audit.py` requires authenticated hashes for base run, oracle interpretation, focal verifier, preservation verifier, and verifier provenance before `AUDIT_PASS` is possible.

## Admission

`tools/ndv_decide_s2_admission.py` emits deterministic `ADMIT` or `DO_NOT_ADMIT` decisions from the frozen wave plus audit state. `tools/ndv_freeze_s2_admission.py` creates a new immutable `ADMITTED_FROZEN` record only from an unblocked `ADMIT` decision. Discovery history is never rewritten to manufacture an admission.

See `docs/research/WP-06-ADMISSION-GATE.md` for the detailed admission contract.

## First prospective wave

`experiments/p1/s2-candidate-wave-01.json` freezes the first NDV-native discovery wave from SWE-rebench V2. It contains six candidates from six repositories and six languages (`ts`, `js`, `java`, `go`, `python`, `rust`).

All six remain prospective `SCREENING` candidates. Historical DV v6 admissions are separate historical corpus members and must not be relabeled as Wave-01 discoveries.

## Validation

Run the deterministic governance validators with:

```bash
python tools/ndv_validate_corpus_intake.py experiments/p1/s2-candidate-wave-01.json
python tools/ndv_validate_s2_audit.py experiments/p1/s2-audit-state-01.json
```

They check governance and evidence completeness only. They do not execute models.

## Current gate

For each Wave-01 candidate the gates are sequential:

1. `LOCAL_PARQUET_SHA_PASS`,
2. `FULL_PINNED_ROW_EXTRACTION`,
3. `QUARANTINE_PASS`,
4. `BASE_ENVIRONMENT_RUN_RECORDED`,
5. `EXPECTED_BASE_BEHAVIOR`,
6. hashed focal/preservation/provenance evidence,
7. `VERIFIER_ENVIRONMENT_AUDIT_PASS`,
8. deterministic admission decision,
9. `ADMITTED_FROZEN` record.

No Wave-01 candidate is currently admitted. No treatment execution is authorized on those candidates.

## Stop conditions

Corpus acquisition may pause when the operational diversity target is met or when the marginal cost of another admissible task is high enough that the next scientific decision can already be made. Rejections are first-class outputs.

## Claims

WP-06 can support claims about corpus admissibility, diversity, source integrity, quarantine, leakage controls, verifier provenance, environment reproducibility, and base/preservation behavior. It cannot support executor rankings, routing benefits, architecture superiority, or NDV product claims.
