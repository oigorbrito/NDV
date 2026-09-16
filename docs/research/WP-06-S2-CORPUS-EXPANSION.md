# WP-06 — P1-S2 Corpus Expansion

## Purpose

Expand the comparative development corpus under the historical verifier-first admissibility contract without exposing candidates to treatment execution during discovery.

## Historical continuity

The authoritative historical admission contract remains in `oigorbrito/dv` at commit `66f3a218fba800daed5d86fdfce386491b8ab0e8`, path `experiments/p1/task-admissibility-contract-v1.json`. Historical admitted tasks `D-F5-01` and `D-F6-01` retain their original provenance and are not rewritten as NDV-native discoveries.

The previous W8 screening found only those two tasks admissible; rejected candidates remain rejected for their recorded reasons unless genuinely new independent evidence changes the admissibility facts. Rejection history is not overwritten.

## Prospective intake

The machine-readable intake contract is `experiments/p1/s2-corpus-intake-v1.json`.

Operational target:

- about 9 admitted development tasks,
- at least 3 task families,
- at least 3 repositories,
- at least 2 languages.

This target is for useful comparative diversity. It is not itself a statistical power claim.

## Source priority

1. SWE-rebench V2 — primary development acquisition source.
2. OmniCode — secondary source for task-type diversity.
3. SWE-Bench Pro Verified — preserve where possible for later confirmation rather than tune on it immediately.
4. Terminal-Bench 2.0 — later heterogeneity/generalization source, not the primary P1-S2 SWE corpus.

A source being high priority does not admit any instance automatically.

## Candidate funnel

Every instance must pass, in order:

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

Treatment/model performance must not influence candidate selection. No admitted or prospective candidate should be run through Luna, a local model, a hosted-free model, or a strong executor until its admission disposition is frozen.

## Full-row quarantine

SWE-rebench V2 contains both executor-appropriate task text and fields that can leak gold-solution or grader information. Dataset preview snippets are discovery aids only and are insufficient for row integrity because they may be truncated.

An operator must export the full selected rows from the exact pinned dataset revision and run:

```bash
python tools/ndv_quarantine_swe_rebench_rows.py \
  --rows path/to/pinned-full-rows.jsonl \
  --out .ndv-corpus/s2-w01
```

The tool creates, per candidate:

- `admission-only.json` — the complete upstream row for verifier/admission work;
- `executor-visible.json` — a strict allowlist projection;
- `quarantine-manifest.json` — hashes binding the two views to the same pinned source row.

It also creates `quarantine-aggregate.json` for the wave.

The executor-visible projection is allowlist-based, not merely a blacklist. Current allowed fields are:

- `instance_id`,
- `repo`,
- `base_commit`,
- `problem_statement`,
- `language`.

Known gold/grader fields remain admission-only, including at least:

- `patch`,
- `test_patch`,
- `FAIL_TO_PASS`,
- `PASS_TO_PASS`,
- `interface`,
- `meta`,
- `install_config`,
- `pr_description`.

Critically, any future upstream field that NDV does not explicitly allow also remains admission-only by default. This prevents schema drift upstream from silently expanding executor context.

The external discovery donor's record hash is retained as provenance but is not assumed to use the same canonicalization as NDV. NDV computes its own canonical full-row SHA-256, task-statement SHA-256, and executor-visible projection SHA-256.

A candidate cannot become `ADMITTED` until the intake validator sees `quarantine_status=PASS` plus references and hashes for the quarantine artifacts.

Admission tooling may inspect full grader/gold metadata only for oracle validity, provenance, environment setup, and leakage control. That material must never be copied into executor-visible artifacts unless a new field is separately preregistered and demonstrated to be non-leaking.

## First prospective wave

`experiments/p1/s2-candidate-wave-01.json` freezes the first NDV-native discovery wave from SWE-rebench V2. It contains six candidates from six repositories and six languages (`ts`, `js`, `java`, `go`, `python`, `rust`).

The wave deliberately starts at `SCREENING`, not `ADMITTED`. Source metadata was discovered from a separately published pinned smoke manifest; that manifest is a discovery donor, not admission authority. NDV must independently acquire the full rows from the pinned dataset revision, resolve source integrity, image digests, verifier independence, and base/preservation behavior.

## Validation

Run the deterministic governance validator with:

```bash
python tools/ndv_validate_corpus_intake.py experiments/p1/s2-candidate-wave-01.json
```

It checks pinned revision format, candidate/base/hash structure, quarantine coverage, disposition validity, diversity-summary consistency, holdout isolation, and stricter requirements for any future `ADMITTED` disposition. It does not execute models or tests.

Quarantine boundary behavior has synthetic unit tests in `tools/test_ndv_quarantine_swe_rebench_rows.py`, including checks that known gold fields and unknown future upstream fields cannot silently enter the executor projection.

## Task profiling

After admission criteria are satisfied, record structural profile features such as spread, novelty, centrality, tool intensity, sequential depth, parallelizability, specification ambiguity, verification strength, and context footprint. These profiles are descriptive inputs for later analysis; they must not be post-hoc labels derived from which executor won.

## Current gate

The current gate for Wave 01 is:

`FULL_PINNED_ROW_ACQUISITION_AND_QUARANTINE`

No candidate in Wave 01 is currently admitted. No treatment execution is authorized on these candidates.

## Stop conditions

Corpus acquisition may pause when the operational diversity target is met or when the marginal cost of finding another admissible task becomes high enough that the next scientific decision can already be made with the current development set. Rejections are first-class outputs.

## Claims

WP-06 can support claims about corpus admissibility, diversity, source integrity, quarantine, leakage controls, and reproducibility. It cannot support executor rankings, routing benefits, architecture superiority, or NDV product claims.
